"""test_providers.py -- provider and fallback tests (all mocked, no network)."""
from __future__ import annotations

import pytest

from skillvm.providers import (
    AuthError, FakeProvider, ModelNotFoundError, ProviderError,
    ProviderExhaustedError, ProviderManager, RateLimitError,
)


def _mgr(*providers):
    return ProviderManager(providers=list(providers), settings=None)


def test_fake_provider_success():
    p = FakeProvider(responses=["hello"])
    assert p.generate("sys", "user") == "hello"
    assert len(p.calls) == 1


def test_primary_success_others_not_called():
    p1 = FakeProvider(responses=["ok"])
    p2 = FakeProvider(responses=["other"])
    mgr = _mgr(p1, p2)
    result = mgr.generate("sys", "q")
    assert result.text == "ok"
    assert len(p2.calls) == 0


def test_primary_timeout_falls_to_second():
    p1 = FakeProvider(failures=[ProviderError("timeout")])
    p2 = FakeProvider(responses=["fallback ok"])
    mgr = _mgr(p1, p2)
    result = mgr.generate("sys", "q")
    assert result.text == "fallback ok"
    assert result.provider == "fake"


def test_both_remote_fail_use_local():
    p1 = FakeProvider(failures=[ProviderError("remote1 down")])
    p2 = FakeProvider(failures=[ProviderError("remote2 down")])
    p3 = FakeProvider(responses=["local answer"])
    mgr = _mgr(p1, p2, p3)
    result = mgr.generate("sys", "q")
    assert result.text == "local answer"


def test_all_fail_raises_provider_exhausted():
    """Regression: all providers fail -> ProviderExhaustedError with attempt records."""
    p1 = FakeProvider(failures=[ProviderError("fail")])
    p2 = FakeProvider(failures=[ProviderError("fail")])
    mgr = _mgr(p1, p2)
    with pytest.raises(ProviderExhaustedError) as exc_info:
        mgr.generate("sys", "q")
    # Must carry attempt records, not just a message string.
    err = exc_info.value
    assert hasattr(err, "attempts")
    assert len(err.attempts) == 2
    assert all(a.outcome == "error" for a in err.attempts)


def test_all_fail_raises_is_subclass_of_provider_error():
    """ProviderExhaustedError is a ProviderError so existing callers still catch it."""
    p1 = FakeProvider(failures=[ProviderError("fail")])
    mgr = _mgr(p1)
    with pytest.raises(ProviderError):
        mgr.generate("sys", "q")


def test_auth_error_recorded_no_retry():
    p1 = FakeProvider(failures=[AuthError("bad key")])
    p2 = FakeProvider(responses=["ok"])
    mgr = _mgr(p1, p2)
    result = mgr.generate("sys", "q")
    assert result.text == "ok"
    assert len(p1.calls) == 1
    assert len(p2.calls) == 1


def test_rate_limit_falls_back():
    p1 = FakeProvider(failures=[RateLimitError("429")])
    p2 = FakeProvider(responses=["ok"])
    mgr = _mgr(p1, p2)
    result = mgr.generate("sys", "q")
    assert result.text == "ok"


def test_model_not_found_no_retry_on_provider():
    p1 = FakeProvider(failures=[ModelNotFoundError("no model")])
    p2 = FakeProvider(responses=["ok"])
    mgr = _mgr(p1, p2)
    result = mgr.generate("sys", "q")
    assert result.text == "ok"
    assert len(p1.calls) == 1


def test_local_unreachable_no_loop():
    """All providers fail — must terminate, not loop."""
    providers = [FakeProvider(failures=[ProviderError("down")]) for _ in range(5)]
    mgr = ProviderManager(providers=providers[:2], settings=None)
    with pytest.raises(ProviderError):
        mgr.generate("sys", "q")
    for p in providers[:2]:
        assert len(p.calls) == 1


def test_probe_returns_caps():
    p = FakeProvider()
    caps = p.probe()
    assert "json_schema" in caps
    assert "system_instruction" in caps
    assert "token_usage" in caps


# ---------------------------------------------------------------------------
# Error classification regression tests
# ---------------------------------------------------------------------------

def test_generate_containing_word_not_rate_limit():
    """Regression: exception message containing 'rate' substring (e.g. 'generate')
    must NOT be classified as RateLimitError.
    The word 'generate' contains 'rate' — old substring check was wrong.
    """
    # Simulate an error whose message contains 'generate' but is NOT a rate limit.
    class FakeWithGenerateMsg(FakeProvider):
        def generate(self, system, user, response_schema=None, settings=None):
            raise ProviderError("Unable to generate response from model")

    p = FakeWithGenerateMsg()
    mgr = _mgr(p)
    with pytest.raises(ProviderExhaustedError) as exc_info:
        mgr.generate("sys", "q")
    # The attempt must be classified as "error", NOT "rate_limit".
    assert exc_info.value.attempts[0].outcome == "error"


def test_actual_rate_limit_error_maps_correctly():
    """Actual RateLimitError -> attempt.outcome == 'rate_limit'."""
    p = FakeProvider(failures=[RateLimitError("429 quota exceeded")])
    p2 = FakeProvider(responses=["ok"])
    mgr = _mgr(p, p2)
    result = mgr.generate("sys", "q")
    assert result.text == "ok"
    assert result.attempts[0].outcome == "rate_limit"


def test_auth_error_outcome():
    """AuthError -> attempt.outcome == 'auth_error'."""
    p1 = FakeProvider(failures=[AuthError("invalid api key")])
    p2 = FakeProvider(responses=["ok"])
    mgr = _mgr(p1, p2)
    result = mgr.generate("sys", "q")
    assert result.attempts[0].outcome == "auth_error"


def test_model_not_found_outcome():
    """ModelNotFoundError -> attempt.outcome == 'model_not_found'."""
    p1 = FakeProvider(failures=[ModelNotFoundError("no such model")])
    p2 = FakeProvider(responses=["ok"])
    mgr = _mgr(p1, p2)
    result = mgr.generate("sys", "q")
    assert result.attempts[0].outcome == "model_not_found"


def test_unknown_error_stays_unknown():
    """An unexpected exception type stays 'error', not mislabeled."""
    class WeirdError(Exception):
        pass

    class WeirdProvider(FakeProvider):
        def generate(self, system, user, response_schema=None, settings=None):
            raise WeirdError("something completely different")

    p = WeirdProvider()
    mgr = _mgr(p)
    with pytest.raises(ProviderExhaustedError) as exc_info:
        mgr.generate("sys", "q")
    assert exc_info.value.attempts[0].outcome == "error"


def test_lmstudio_model_and_key_are_separate():
    """Regression: LM Studio model ID must not be used as the API key."""
    from skillvm.config import Settings
    from pathlib import Path
    settings = Settings(
        provider_order=["lmstudio"],
        fallback_enabled=True,
        local_only=True,
        gemini_api_key="",
        gemini_model="",
        openrouter_api_key="",
        openrouter_base_url="",
        openrouter_model="",
        lmstudio_base_url="http://localhost:1234/v1",
        lmstudio_model="my-local-model",
        lmstudio_api_key="lm-studio",  # separate field
        request_timeout=10,
        max_retries=1,
        max_fallback=3,
        overall_deadline=30,
        temperature=0,
        data_dir=Path("."),
        workspace_root=Path("."),
        bind="127.0.0.1",
        port=8477,
    )
    assert settings.lmstudio_model == "my-local-model"
    assert settings.lmstudio_api_key == "lm-studio"
    # They must be distinct values.
    assert settings.lmstudio_model != settings.lmstudio_api_key


def test_attempt_records_contain_provider_and_outcome():
    """ProviderExhaustedError.attempts contain provider name and outcome."""
    p1 = FakeProvider(failures=[AuthError("bad")])
    p2 = FakeProvider(failures=[RateLimitError("429")])
    mgr = _mgr(p1, p2)
    with pytest.raises(ProviderExhaustedError) as exc_info:
        mgr.generate("sys", "q")
    attempts = exc_info.value.attempts
    assert len(attempts) == 2
    outcomes = {a.outcome for a in attempts}
    assert "auth_error" in outcomes
    assert "rate_limit" in outcomes
