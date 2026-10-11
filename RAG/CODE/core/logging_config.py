"""Journalisation structurée (JSON) sans secrets.

Chaque ligne de log est un objet JSON : horodatage, niveau, module, message et champs
additionnels (`extra`). Un filtre masque systématiquement tout ce qui ressemble à une clé
d'API ou à un mot de passe avant écriture.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime

_SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{8,})"),
    re.compile(r"(?i)(api[_-]?key|password|secret|token)(\"?\s*[:=]\s*\"?)([^\s\",}]+)"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9\-_.=]+)"),
]

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def redact(text: str) -> str:
    """Masque les secrets présents dans une chaîne."""
    text = _SECRET_PATTERNS[0].sub("sk-***", text)
    text = _SECRET_PATTERNS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    text = _SECRET_PATTERNS[2].sub(lambda m: f"{m.group(1)}***", text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return redact(json.dumps(payload, ensure_ascii=False, default=str))


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(level)
    # Bibliothèques trop bavardes ou susceptibles de journaliser des en-têtes HTTP.
    for noisy in ("neo4j", "httpx", "httpcore", "anthropic", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
