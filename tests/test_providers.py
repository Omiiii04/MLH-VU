"""test_providers.py -- provider and fallback tests (all mocked, no network)."""
from __future__ import annotations

import pytest

from skillvm.providers import (
    AuthError, FakeProvider, ModelNotFoundError, ProviderError,
    ProviderManager, RateLimitError,
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


def test_all_fail_raises():
    p1 = FakeProvider(failures=[ProviderError("fail")])
    p2 = FakeProvider(failures=[ProviderError("fail")])
    mgr = _mgr(p1, p2)
    with pytest.raises(ProviderError):
        mgr.generate("sys", "q")


def test_auth_error_recorded_no_retry():
    p1 = FakeProvider(failures=[AuthError("bad key")])
    p2 = FakeProvider(responses=["ok"])
    mgr = _mgr(p1, p2)
    result = mgr.generate("sys", "q")
    assert result.text == "ok"
    # p1 was tried once, p2 got the call
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
    # All providers fail — must terminate, not loop
    providers = [FakeProvider(failures=[ProviderError("down")]) for _ in range(5)]
    mgr = ProviderManager(providers=providers[:2], settings=None)
    with pytest.raises(ProviderError):
        mgr.generate("sys", "q")
    # Each was called exactly once
    for p in providers[:2]:
        assert len(p.calls) == 1


def test_probe_returns_caps():
    p = FakeProvider()
    caps = p.probe()
    assert "json_schema" in caps
    assert "system_instruction" in caps
    assert "token_usage" in caps
