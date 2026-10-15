import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from backend.security import RateLimiter, TokenService, User, UserStore, hash_password, verify_password
from core.llm import AnthropicLLM, LLMError, LLMRefusal, OpenAICompatibleLLM, build_llm
from core.logging_config import JsonFormatter, redact
from core.settings import CODE_DIR, Settings

FAKE_KEY = "sk-test-0000000000000000000000000000"


# ------------------------------------------------------------------ mots de passe, jetons, débit
def test_password_hashing():
    stored = hash_password("Correct-Horse-1")
    assert stored.startswith("pbkdf2_sha256$600000$")
    assert verify_password("Correct-Horse-1", stored)
    assert not verify_password("mauvais", stored)
    assert not verify_password("x", "format-invalide")
    assert hash_password("même") != hash_password("même"), "le sel doit être aléatoire"


def test_demo_user_store():
    store = UserStore(CODE_DIR / "config" / "users.example.yaml")
    user = store.authenticate("collaborateur", "Demo-Orizia-2026")
    assert user is not None and user.groups == frozenset({"ALL"})
    assert store.authenticate("collaborateur", "faux") is None
    assert store.authenticate("inconnu", "Demo-Orizia-2026") is None


def test_roles_hierarchy():
    admin = User("a", "A", frozenset({"admin"}), frozenset())
    viewer = User("v", "V", frozenset({"viewer"}), frozenset())
    assert admin.has_role("manager") and admin.has_role("viewer")
    assert not viewer.has_role("manager")


def test_tokens_roundtrip_and_tampering():
    service = TokenService("s" * 40, ttl_minutes=5)
    user = User("ingenieur.dsi", "Ingénieur", frozenset({"viewer"}), frozenset({"ALL", "DSI"}))
    token = service.issue(user)
    decoded = service.decode(token)
    assert decoded.username == "ingenieur.dsi" and decoded.groups == frozenset({"ALL", "DSI"})
    header, payload, signature = token.split(".")
    assert service.decode(f"{header}.{payload}.{signature[::-1]}") is None
    assert TokenService("t" * 40, 5).decode(token) is None, "un jeton signé avec une autre clé est refusé"
    assert TokenService("s" * 40, ttl_minutes=-1).decode(TokenService("s" * 40, ttl_minutes=-1).issue(user)) is None
    with pytest.raises(ValueError):
        TokenService("trop-court", 5)


def test_rate_limiter():
    limiter = RateLimiter(2, window_seconds=60)
    assert limiter.allow("u") and limiter.allow("u") and not limiter.allow("u")
    assert limiter.allow("autre")


# ------------------------------------------------------------------ secrets dans les journaux
def test_redaction_masks_secrets():
    text = redact(f"clé {FAKE_KEY} ; api_key={FAKE_KEY} ; Authorization: Bearer abc.def.ghi ; password: hunter2")
    assert FAKE_KEY not in text and "abc.def.ghi" not in text and "hunter2" not in text


def test_json_formatter_redacts_extra_fields():
    record = logging.LogRecord("t", logging.INFO, "", 0, "appel avec %s", (FAKE_KEY,), None)
    record.detail = f"token={FAKE_KEY}"
    line = JsonFormatter().format(record)
    assert FAKE_KEY not in line and json.loads(line)["level"] == "INFO"


def test_settings_never_expose_secret():
    settings = Settings(llm_api_key=FAKE_KEY, app_secret_key="x" * 40)
    assert FAKE_KEY not in repr(settings) and FAKE_KEY not in str(settings.model_dump())


# ------------------------------------------------------------------ clients LLM (simulés, sans réseau)
def _settings(**kw) -> Settings:
    base = {"llm_provider": "openai_compatible", "llm_api_key": FAKE_KEY, "llm_base_url": "https://llm.example/v1",
            "llm_model": "modele-test", "app_secret_key": "x" * 40}
    base.update(kw)
    return Settings(**base)


def test_build_llm_is_offline_without_key():
    assert build_llm(_settings(llm_api_key="")).provider == "offline"
    assert build_llm(Settings(llm_provider="offline", app_secret_key="x" * 40)).provider == "offline"


def test_openai_compatible_success_and_request_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Réponse [C1]"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 3}})

    llm = OpenAICompatibleLLM(_settings(), transport=httpx.MockTransport(handler))
    result = llm.complete("système", "question")
    assert result.text == "Réponse [C1]" and result.input_tokens == 10
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "système"}
    assert seen["auth"] == f"Bearer {FAKE_KEY}"


def test_openai_compatible_retries_then_fails_cleanly():
    calls = []

    def flaky(request):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "0"}) if len(calls) == 1 else httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]})

    assert OpenAICompatibleLLM(_settings(), transport=httpx.MockTransport(flaky)).complete("s", "u").text == "ok"
    with pytest.raises(LLMError) as err:
        OpenAICompatibleLLM(_settings(), transport=httpx.MockTransport(lambda r: httpx.Response(401))).complete("s", "u")
    assert "401" in str(err.value) and FAKE_KEY not in str(err.value)
    with pytest.raises(LLMError, match="format inattendu"):
        OpenAICompatibleLLM(_settings(), transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"oups": True}))).complete("s", "u")


class _FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _fake_anthropic(stop_reason="end_turn", text="Réponse [C1]"):
    response = SimpleNamespace(stop_reason=stop_reason, model="modele-anthropic",
                               content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=12, output_tokens=4))
    return SimpleNamespace(messages=_FakeMessages(response), beta=SimpleNamespace(messages=_FakeMessages(response)))


def test_anthropic_adapter_uses_fallbacks_and_no_temperature():
    client = _fake_anthropic()
    llm = AnthropicLLM(_settings(llm_provider="anthropic", llm_base_url=""), client=client)
    result = llm.complete("système", "question")
    sent = client.beta.messages.kwargs
    assert result.text == "Réponse [C1]" and result.output_tokens == 4
    assert sent["fallbacks"] == "default" and sent["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in sent and sent["output_config"] == {"effort": "medium"}
    assert sent["system"] == "système" and sent["messages"] == [{"role": "user", "content": "question"}]


def test_anthropic_adapter_without_fallbacks_and_refusal():
    client = _fake_anthropic()
    AnthropicLLM(_settings(llm_provider="anthropic", llm_anthropic_fallbacks=False), client=client).complete("s", "u")
    assert client.messages.kwargs is not None and client.beta.messages.kwargs is None
    with pytest.raises(LLMRefusal):
        AnthropicLLM(_settings(llm_provider="anthropic"), client=_fake_anthropic("refusal", "")).complete("s", "u")


def test_anthropic_adapter_requires_explicit_model():
    with pytest.raises(LLMError):
        AnthropicLLM(_settings(llm_provider="anthropic", llm_model=""), client=_fake_anthropic())
