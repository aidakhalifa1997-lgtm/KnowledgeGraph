"""Couche d'accès au LLM, indépendante du fournisseur.

Trois implémentations :
- `OfflineLLM` : aucun appel réseau ; lève `LLMUnavailable`. Les nœuds appelants basculent
  alors sur leur implémentation de repli (extraction par règles, générateur extractif).
- `OpenAICompatibleLLM` : toute API exposant `POST {base_url}/chat/completions`
  (format « OpenAI Chat Completions »). Utilisée seulement si le fournisseur l'implémente
  réellement : ce point doit être vérifié dans sa documentation avant configuration.
- `AnthropicLLM` : API Messages d'Anthropic via le SDK officiel `anthropic`.

Une implémentation `ScriptedLLM` sert aux tests (réponses simulées, aucune clé requise).

Sécurité : la clé n'est jamais journalisée (type SecretStr, filtre de journalisation), et les
erreurs remontées ne contiennent pas les en-têtes de requête.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from core.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Erreur d'appel au LLM (réseau, quota, réponse invalide)."""


class LLMUnavailable(LLMError):
    """Aucun LLM configuré (mode hors-ligne)."""


class LLMRefusal(LLMError):
    """Le modèle a refusé de répondre (politique de sécurité du fournisseur)."""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_stop_reason: str | None = None


class LLMClient(Protocol):
    provider: str
    model: str

    def complete(self, system: str, user: str, *, max_tokens: int | None = None) -> LLMResult: ...


class OfflineLLM:
    provider = "offline"
    model = "none"

    def complete(self, system: str, user: str, *, max_tokens: int | None = None) -> LLMResult:
        raise LLMUnavailable("Aucun fournisseur LLM configuré (LLM_PROVIDER=offline ou clé absente).")


class OpenAICompatibleLLM:
    """Client HTTP minimal pour les API compatibles « Chat Completions »."""

    provider = "openai_compatible"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        if not settings.llm_base_url or not settings.llm_model:
            raise LLMError("LLM_BASE_URL et LLM_MODEL sont obligatoires pour openai_compatible.")
        self.model = settings.llm_model
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.llm_base_url.rstrip("/"),
            timeout=settings.llm_timeout_seconds,
            transport=transport,
            headers={"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"},
        )

    def complete(self, system: str, user: str, *, max_tokens: int | None = None) -> LLMResult:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens or self._settings.llm_max_tokens,
            "temperature": self._settings.llm_temperature,
        }
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self._client.post("/chat/completions", json=body)
            except httpx.HTTPError as exc:  # réseau, délai dépassé
                last_error = exc
            else:
                if response.status_code == 200:
                    data = response.json()
                    try:
                        text = data["choices"][0]["message"]["content"] or ""
                    except (KeyError, IndexError, TypeError) as exc:
                        raise LLMError("Réponse du fournisseur dans un format inattendu.") from exc
                    usage = data.get("usage") or {}
                    return LLMResult(
                        text=text, provider=self.provider, model=self.model,
                        latency_ms=(time.perf_counter() - started) * 1000,
                        input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
                        raw_stop_reason=data["choices"][0].get("finish_reason"),
                    )
                if response.status_code not in (408, 409, 429) and response.status_code < 500:
                    raise LLMError(f"Erreur du fournisseur LLM (HTTP {response.status_code}).")
                last_error = LLMError(f"HTTP {response.status_code}")
                retry_after = response.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(float(retry_after), 30.0))
                    continue
            time.sleep(min(2 ** attempt, 16))
        raise LLMError(f"Échec de l'appel LLM après plusieurs tentatives : {type(last_error).__name__}")


class AnthropicLLM:
    """API Messages d'Anthropic via le SDK officiel.

    - Les nouveaux modèles refusent `temperature` : le paramètre n'est pas envoyé.
    - La profondeur de raisonnement se règle avec `output_config.effort`.
    - Le SDK réessaie automatiquement les erreurs 408/409/429/5xx.
    - Le repli côté serveur (`fallbacks: "default"`) est activé par défaut : en cas de refus
      par les classifieurs de sécurité, l'API relance la requête sur un modèle de repli.
    """

    provider = "anthropic"

    def __init__(self, settings: Settings, client=None) -> None:
        import anthropic

        self._anthropic = anthropic
        self._settings = settings
        if not settings.llm_model:
            # Le modèle est choisi explicitement avec la clé : aucun identifiant n'est codé en dur.
            raise LLMError("LLM_MODEL est obligatoire pour anthropic.")
        self.model = settings.llm_model
        kwargs = {"api_key": settings.llm_api_key.get_secret_value(), "timeout": settings.llm_timeout_seconds,
                  "max_retries": 3}
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        self._client = client or anthropic.Anthropic(**kwargs)

    def complete(self, system: str, user: str, *, max_tokens: int | None = None) -> LLMResult:
        anthropic = self._anthropic
        params = {
            "model": self.model,
            "max_tokens": max_tokens or self._settings.llm_max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": self._settings.llm_effort},
        }
        started = time.perf_counter()
        try:
            if self._settings.llm_anthropic_fallbacks:
                response = self._client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
                )
            else:
                response = self._client.messages.create(**params)
        except anthropic.RateLimitError as exc:
            raise LLMError("Quota du fournisseur LLM atteint (HTTP 429).") from exc
        except anthropic.AuthenticationError as exc:
            raise LLMError("Clé d'API refusée par le fournisseur (HTTP 401).") from exc
        except anthropic.BadRequestError as exc:
            raise LLMError(f"Requête refusée par le fournisseur (HTTP 400) : {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Erreur du fournisseur LLM (HTTP {exc.status_code}).") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Fournisseur LLM injoignable (réseau).") from exc

        if response.stop_reason == "refusal":
            raise LLMRefusal("Le modèle a refusé de traiter la demande.")
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResult(
            text=text, provider=self.provider, model=getattr(response, "model", self.model),
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens,
            raw_stop_reason=response.stop_reason,
        )


@dataclass
class ScriptedLLM:
    """LLM simulé pour les tests : une fonction calcule la réponse à partir du prompt."""

    responder: Callable[[str, str], str]
    provider: str = "scripted"
    model: str = "scripted-test-model"
    calls: list[tuple[str, str]] = field(default_factory=list)

    def complete(self, system: str, user: str, *, max_tokens: int | None = None) -> LLMResult:
        self.calls.append((system, user))
        return LLMResult(text=self.responder(system, user), provider=self.provider, model=self.model, latency_ms=0.0)


def build_llm(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    if not settings.llm_enabled:
        return OfflineLLM()
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLM(settings)
    if settings.llm_provider == "anthropic":
        return AnthropicLLM(settings)
    return OfflineLLM()
