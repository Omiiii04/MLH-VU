from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _b(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _i(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v else default


def _f(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v else default


@dataclass
class Settings:
    provider_order: list[str]
    fallback_enabled: bool
    local_only: bool
    gemini_api_key: str
    gemini_model: str
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    lmstudio_base_url: str
    lmstudio_model: str
    request_timeout: float
    max_retries: int
    max_fallback: int
    overall_deadline: float
    temperature: float
    data_dir: Path
    bind: str
    port: int


def load_settings() -> Settings:
    order = os.environ.get("LLM_PROVIDER_ORDER", "google,openrouter,lmstudio")
    data = os.environ.get("SKILLVM_DATA_DIR", ".skillvm")
    return Settings(
        provider_order=[p.strip() for p in order.split(",") if p.strip()],
        fallback_enabled=_b("LLM_FALLBACK_ENABLED", True),
        local_only=_b("LLM_LOCAL_ONLY", False),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        gemini_model=os.environ.get("GEMINI_MODEL", "").strip(),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
        openrouter_base_url=os.environ.get(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).strip(),
        openrouter_model=os.environ.get("OPENROUTER_MODEL", "").strip(),
        lmstudio_base_url=os.environ.get(
            "LMSTUDIO_BASE_URL", "http://localhost:1234/v1"
        ).strip(),
        lmstudio_model=os.environ.get("LMSTUDIO_MODEL", "").strip(),
        request_timeout=_f("LLM_REQUEST_TIMEOUT_SECONDS", 60),
        max_retries=_i("LLM_MAX_RETRIES_PER_PROVIDER", 1),
        max_fallback=_i("LLM_MAX_FALLBACK_ATTEMPTS", 3),
        overall_deadline=_f("LLM_OVERALL_DEADLINE_SECONDS", 120),
        temperature=_f("LLM_TEMPERATURE", 0),
        data_dir=Path(data),
        bind=os.environ.get("SKILLVM_BIND", "127.0.0.1"),
        port=_i("SKILLVM_PORT", 8477),
    )
