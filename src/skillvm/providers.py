"""providers.py -- LLM provider layer.

GeminiProvider: google-genai SDK.
OpenAICompatProvider: openai SDK with configurable base_url (OpenRouter + LM Studio).
FakeProvider: deterministic, scriptable failures for tests.
Manager: tries providers in order, falls back on transient errors.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from skillvm.config import Settings
from skillvm.redact import prompt_hash, excerpt, redact_obj


# ---------------------------------------------------------------------------
# Provider base
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    pass


class AuthError(ProviderError):
    pass


class ModelNotFoundError(ProviderError):
    pass


class RateLimitError(ProviderError):
    pass


class SchemaInvalidError(ProviderError):
    pass


@dataclass
class ProviderAttempt:
    provider: str
    model: str
    started_at: float
    finished_at: float | None = None
    outcome: str = "unknown"  # success, timeout, auth_error, rate_limit, model_not_found, schema_invalid, error
    failover_reason: str | None = None
    token_usage: dict | None = None
    prompt_hash: str | None = None
    prompt_excerpt: str | None = None


@dataclass
class ProviderResult:
    text: str
    provider: str
    model: str
    constrained_mode: str = "schema_prompt"
    token_usage: dict | None = None
    attempts: list[ProviderAttempt] = field(default_factory=list)


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, system: str, user: str, response_schema: dict | None = None, settings: Settings | None = None) -> str:
        """Return raw text. Raises ProviderError subclasses on failure."""

    def list_models(self, settings: Settings | None = None) -> list[str]:
        return []

    def probe(self, settings: Settings | None = None) -> dict[str, Any]:
        """Returns capability dict: system_instruction, json_schema, token_usage."""
        return {"system_instruction": False, "json_schema": False, "token_usage": False}


# ---------------------------------------------------------------------------
# FakeProvider — deterministic, for tests
# ---------------------------------------------------------------------------

class FakeProvider(BaseProvider):
    """Scriptable fake. responses is a list consumed in order. failures is a list of exceptions."""

    name = "fake"

    def __init__(self, responses: list[str] | None = None, failures: list[Exception] | None = None):
        self._responses = list(responses or [])
        self._failures = list(failures or [])
        self.calls: list[dict] = []

    def generate(self, system: str, user: str, response_schema: dict | None = None, settings: Settings | None = None) -> str:
        call = {"system": system[:50], "user": user[:50]}
        self.calls.append(call)
        if self._failures:
            raise self._failures.pop(0)
        if self._responses:
            return self._responses.pop(0)
        return json.dumps({"nodes": [], "inputs": [], "outputs": []})

    def list_models(self, settings: Settings | None = None) -> list[str]:
        return ["fake-model"]

    def probe(self, settings: Settings | None = None) -> dict[str, Any]:
        return {"system_instruction": True, "json_schema": True, "token_usage": True}


# ---------------------------------------------------------------------------
# GeminiProvider
# ---------------------------------------------------------------------------

class GeminiProvider(BaseProvider):
    name = "google"

    def generate(self, system: str, user: str, response_schema: dict | None = None, settings: Settings | None = None) -> str:
        try:
            from google import genai
            from google.genai import types as gtypes
        except ImportError:
            raise ProviderError("google-genai not installed")

        api_key = settings.gemini_api_key if settings else os.environ.get("GEMINI_API_KEY", "")
        model = settings.gemini_model if settings else os.environ.get("GEMINI_MODEL", "")
        if not api_key:
            raise AuthError("GEMINI_API_KEY not set")
        if not model:
            raise ModelNotFoundError("GEMINI_MODEL not set — run: skillvm probe")

        client = genai.Client(api_key=api_key)
        config_kwargs: dict[str, Any] = {}
        # Probe: Gemma 4 on Gemini API may not support system instructions or JSON mode.
        # We prepend system to user if needed (detected by probe result).
        combined_user = f"[SYSTEM]\n{system}\n\n[USER]\n{user}" if system else user
        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"

        timeout = settings.request_timeout if settings else 60
        try:
            response = client.models.generate_content(
                model=model,
                contents=combined_user,
                config=gtypes.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
            )
            return response.text or ""
        except Exception as e:
            _classify_genai_error(e)

    def list_models(self, settings: Settings | None = None) -> list[str]:
        try:
            from google import genai
        except ImportError:
            return []
        api_key = settings.gemini_api_key if settings else os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return []
        try:
            client = genai.Client(api_key=api_key)
            return [m.name for m in client.models.list()]
        except Exception:
            return []

    def probe(self, settings: Settings | None = None) -> dict[str, Any]:
        """Best-effort probe. Returns dict or raises ProviderError."""
        try:
            from google import genai
            from google.genai import types as gtypes
        except ImportError:
            raise ProviderError("google-genai not installed")
        api_key = settings.gemini_api_key if settings else os.environ.get("GEMINI_API_KEY", "")
        model = settings.gemini_model if settings else os.environ.get("GEMINI_MODEL", "")
        if not api_key or not model:
            raise AuthError("GEMINI_API_KEY or GEMINI_MODEL not set")
        client = genai.Client(api_key=api_key)
        caps = {"system_instruction": False, "json_schema": False, "token_usage": False}
        # Test JSON mode
        try:
            r = client.models.generate_content(
                model=model,
                contents="Reply with JSON: {\"ok\": true}",
                config=gtypes.GenerateContentConfig(response_mime_type="application/json"),
            )
            txt = r.text or ""
            json.loads(txt)
            caps["json_schema"] = True
        except Exception:
            pass
        # Token usage
        try:
            r2 = client.models.generate_content(model=model, contents="hi")
            if getattr(r2, "usage_metadata", None):
                caps["token_usage"] = True
        except Exception:
            pass
        return caps


def _classify_genai_error(e: Exception) -> None:
    msg = str(e).lower()
    if "auth" in msg or "api_key" in msg or "permission" in msg:
        raise AuthError(str(e)) from e
    if "not found" in msg or "404" in msg:
        raise ModelNotFoundError(str(e)) from e
    if "429" in msg or "quota" in msg or "rate" in msg:
        raise RateLimitError(str(e)) from e
    raise ProviderError(str(e)) from e


# ---------------------------------------------------------------------------
# OpenAICompatProvider (OpenRouter + LM Studio)
# ---------------------------------------------------------------------------

class OpenAICompatProvider(BaseProvider):
    """One class, two configs (OpenRouter and LM Studio)."""

    def __init__(self, name: str = "openrouter"):
        self.name = name

    def _client_and_model(self, settings: Settings | None):
        try:
            from openai import OpenAI, AuthenticationError, NotFoundError
        except ImportError:
            raise ProviderError("openai package not installed")
        if self.name == "openrouter":
            base_url = settings.openrouter_base_url if settings else os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            api_key = settings.openrouter_api_key if settings else os.environ.get("OPENROUTER_API_KEY", "")
            model = settings.openrouter_model if settings else os.environ.get("OPENROUTER_MODEL", "")
        else:  # lmstudio
            base_url = settings.lmstudio_base_url if settings else os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
            api_key = settings.lmstudio_model if settings else os.environ.get("LMSTUDIO_API_KEY", "lm-studio")  # LM Studio ignores key
            model = settings.lmstudio_model if settings else os.environ.get("LMSTUDIO_MODEL", "")
            if not api_key:
                api_key = "lm-studio"
        if not api_key:
            raise AuthError(f"{self.name}: API key not set")
        if not model:
            raise ModelNotFoundError(f"{self.name}: model not set — run: skillvm probe")
        client = OpenAI(base_url=base_url, api_key=api_key)
        return client, model

    def generate(self, system: str, user: str, response_schema: dict | None = None, settings: Settings | None = None) -> str:
        from openai import AuthenticationError, NotFoundError
        client, model = self._client_and_model(settings)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        timeout = settings.request_timeout if settings else 60
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "timeout": timeout}
        if response_schema:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except AuthenticationError as e:
            raise AuthError(str(e)) from e
        except NotFoundError as e:
            raise ModelNotFoundError(str(e)) from e
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate" in msg:
                raise RateLimitError(str(e)) from e
            raise ProviderError(str(e)) from e

    def list_models(self, settings: Settings | None = None) -> list[str]:
        try:
            client, _ = self._client_and_model(settings)
            return [m.id for m in client.models.list().data]
        except Exception:
            return []

    def probe(self, settings: Settings | None = None) -> dict[str, Any]:
        client, model = self._client_and_model(settings)
        caps = {"system_instruction": False, "json_schema": False, "token_usage": False}
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": "You are a test."}, {"role": "user", "content": 'Reply with JSON: {"ok": true}'}],
                response_format={"type": "json_object"},
                timeout=15,
            )
            txt = resp.choices[0].message.content or ""
            json.loads(txt)
            caps["json_schema"] = True
            caps["system_instruction"] = True
            if resp.usage:
                caps["token_usage"] = True
        except Exception:
            pass
        return caps


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class ProviderManager:
    """Tries providers in order; falls back on transient errors."""

    def __init__(self, providers: list[BaseProvider], settings: Settings | None = None):
        self.providers = providers
        self.settings = settings

    def generate(self, system: str, user: str, response_schema: dict | None = None) -> ProviderResult:
        settings = self.settings
        max_fallback = settings.max_fallback if settings else 3
        deadline = time.monotonic() + (settings.overall_deadline if settings else 120)
        attempts: list[ProviderAttempt] = []
        phash = prompt_hash(user)
        pexcerpt = excerpt(user)

        for provider in self.providers[:max_fallback]:
            if time.monotonic() > deadline:
                break
            attempt = ProviderAttempt(
                provider=provider.name,
                model="",
                started_at=time.monotonic(),
                prompt_hash=phash,
                prompt_excerpt=pexcerpt,
            )
            try:
                text = provider.generate(system=system, user=user, response_schema=response_schema, settings=settings)
                attempt.finished_at = time.monotonic()
                attempt.outcome = "success"
                attempts.append(attempt)
                return ProviderResult(
                    text=text,
                    provider=provider.name,
                    model=getattr(provider, "_last_model", ""),
                    attempts=attempts,
                )
            except AuthError as e:
                attempt.outcome = "auth_error"; attempt.failover_reason = str(e)
                attempt.finished_at = time.monotonic(); attempts.append(attempt)
                continue  # no retry on auth
            except ModelNotFoundError as e:
                attempt.outcome = "model_not_found"; attempt.failover_reason = str(e)
                attempt.finished_at = time.monotonic(); attempts.append(attempt)
                continue
            except RateLimitError as e:
                attempt.outcome = "rate_limit"; attempt.failover_reason = str(e)
                attempt.finished_at = time.monotonic(); attempts.append(attempt)
                continue  # fall back, don`t wait on Retry-After
            except ProviderError as e:
                attempt.outcome = "error"; attempt.failover_reason = str(e)
                attempt.finished_at = time.monotonic(); attempts.append(attempt)
                continue
            except Exception as e:
                attempt.outcome = "error"; attempt.failover_reason = str(e)
                attempt.finished_at = time.monotonic(); attempts.append(attempt)
                continue

        raise ProviderError(f"All providers failed. Attempts: {[a.outcome for a in attempts]}")


def build_manager(settings: Settings) -> ProviderManager:
    """Build a ProviderManager from settings."""
    providers: list[BaseProvider] = []
    for name in settings.provider_order:
        if settings.local_only and name != "lmstudio":
            continue
        if name == "google" and settings.gemini_api_key:
            providers.append(GeminiProvider())
        elif name == "openrouter" and settings.openrouter_api_key:
            providers.append(OpenAICompatProvider("openrouter"))
        elif name == "lmstudio":
            providers.append(OpenAICompatProvider("lmstudio"))
    return ProviderManager(providers=providers, settings=settings)
