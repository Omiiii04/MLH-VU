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


class ProviderExhaustedError(ProviderError):
    """All providers failed. Carries sanitized attempt records."""
    def __init__(self, msg: str, attempts: list["ProviderAttempt"]):
        super().__init__(msg)
        self.attempts = attempts


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

        self._current_model = model  # record for ProviderManager
        client = genai.Client(api_key=api_key)
        config_kwargs: dict[str, Any] = {}
        # Use system_instruction if the SDK supports it; fall back to prepended user text.
        # Detect support by checking for the attribute on GenerateContentConfig.
        use_system_instruction = hasattr(gtypes.GenerateContentConfig, "system_instruction")
        if use_system_instruction and system:
            config_kwargs["system_instruction"] = system
            combined_user = user
        else:
            combined_user = f"[SYSTEM]\n{system}\n\n[USER]\n{user}" if system else user

        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"

        timeout = settings.request_timeout if settings else 60
        # Apply timeout via httpx_options when supported, or accept best-effort.
        timeout_kwargs: dict[str, Any] = {}
        if hasattr(gtypes.GenerateContentConfig, "timeout"):
            timeout_kwargs["timeout"] = timeout

        try:
            response = client.models.generate_content(
                model=model,
                contents=combined_user,
                config=gtypes.GenerateContentConfig(**config_kwargs, **timeout_kwargs) if (config_kwargs or timeout_kwargs) else None,
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
    """Raise a typed ProviderError from a google-genai exception.

    Primary: inspect the exception type and HTTP status code.
    Narrow fallback: inspect metadata fields on the exception object.
    Never classify by free-form message substrings that could match unrelated text.
    """
    # Try to get HTTP status code from the exception (varies by SDK version).
    status_code: int | None = None
    for attr in ("status_code", "code", "http_status"):
        val = getattr(e, attr, None)
        if isinstance(val, int):
            status_code = val
            break

    # Check typed exception classes first (SDK may expose these).
    exc_name = type(e).__name__
    if exc_name in ("ClientError",) and status_code == 401:
        raise AuthError(str(e)) from e
    if exc_name in ("ClientError",) and status_code == 404:
        raise ModelNotFoundError(str(e)) from e
    if exc_name in ("ClientError",) and status_code == 429:
        raise RateLimitError(str(e)) from e

    # Status-code classification (when type alone is insufficient).
    if status_code == 401 or status_code == 403:
        raise AuthError(str(e)) from e
    if status_code == 404:
        raise ModelNotFoundError(str(e)) from e
    if status_code == 429:
        raise RateLimitError(str(e)) from e

    # Narrow metadata fallback: only inspect structured error fields, not free-form message.
    details = getattr(e, "details", None) or getattr(e, "error", None)
    if isinstance(details, dict):
        code_str = str(details.get("code", "") or details.get("status", "")).upper()
        if code_str in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
            raise AuthError(str(e)) from e
        if code_str == "NOT_FOUND":
            raise ModelNotFoundError(str(e)) from e
        if code_str == "RESOURCE_EXHAUSTED":
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
            # Use lmstudio_api_key (separate from model). For local servers that
            # don't require auth, the default "lm-studio" placeholder is used.
            if settings:
                api_key = settings.lmstudio_api_key or "lm-studio"
                model = settings.lmstudio_model
            else:
                api_key = os.environ.get("LMSTUDIO_API_KEY", "lm-studio") or "lm-studio"
                model = os.environ.get("LMSTUDIO_MODEL", "")
        if not api_key:
            raise AuthError(f"{self.name}: API key not set")
        if not model:
            raise ModelNotFoundError(f"{self.name}: model not set — run: skillvm probe")
        self._current_model = model  # record for ProviderManager
        client = OpenAI(base_url=base_url, api_key=api_key)
        return client, model

    def generate(self, system: str, user: str, response_schema: dict | None = None, settings: Settings | None = None) -> str:
        from openai import AuthenticationError, NotFoundError, RateLimitError as OAIRateLimit
        try:
            from openai import APITimeoutError, APIConnectionError
        except ImportError:
            APITimeoutError = APIConnectionError = None  # older SDK
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
        except OAIRateLimit as e:
            raise RateLimitError(str(e)) from e
        except Exception as e:
            # Use HTTP status code if available; never match free-form substrings.
            status = getattr(e, "status_code", None)
            if status == 429:
                raise RateLimitError(str(e)) from e
            if status in (401, 403):
                raise AuthError(str(e)) from e
            if status == 404:
                raise ModelNotFoundError(str(e)) from e
            if APITimeoutError and isinstance(e, APITimeoutError):
                raise ProviderError(f"timeout: {e}") from e
            if APIConnectionError and isinstance(e, APIConnectionError):
                raise ProviderError(f"connection: {e}") from e
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
            model = getattr(provider, "_current_model", "") or ""
            attempt = ProviderAttempt(
                provider=provider.name,
                model=model,
                started_at=time.monotonic(),
                prompt_hash=phash,
                prompt_excerpt=pexcerpt,
            )
            try:
                text = provider.generate(system=system, user=user, response_schema=response_schema, settings=settings)
                attempt.finished_at = time.monotonic()
                attempt.outcome = "success"
                # Record the model that was actually used (set by provider during generate).
                attempt.model = getattr(provider, "_current_model", model) or model
                attempts.append(attempt)
                return ProviderResult(
                    text=text,
                    provider=provider.name,
                    model=attempt.model,
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

        raise ProviderExhaustedError(
            f"All providers failed. Attempts: {[a.outcome for a in attempts]}",
            attempts=attempts,
        )


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
