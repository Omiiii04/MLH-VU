from __future__ import annotations

import hashlib
import re
from typing import Any

_SECRET = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*([^\s,;]+)"
)
_KEYISH = re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{10,})\b")


def redact_text(text: str) -> str:
    text = _SECRET.sub(lambda m: f"{m.group(1)}=***", text)
    return _KEYISH.sub("***", text)


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in {"api_key", "authorization", "token", "secret", "password"}:
                out[k] = "***"
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    return obj


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def excerpt(text: str, n: int = 240) -> str:
    return redact_text(text[:n])
