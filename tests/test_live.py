"""test_live.py -- live provider smoke tests.
Skipped automatically when credentials are absent.
Labeled: pytest.mark.live
"""
from __future__ import annotations
import os
import json
import pytest

pytestmark = pytest.mark.live

SIMPLE_SKILL = """\
---
id: live-smoke
inputs:
  - name: p
    type: string
permissions: [fs.read, verify.run]
postconditions:
  - kind: file_exists
    path: "{p}"
---
# Live smoke
## Steps
1. Read `p` with fs.read
"""


@pytest.fixture()
def settings():
    from skillvm.config import load_settings
    return load_settings()


def _has_gemini(s):
    return bool(s.gemini_api_key and s.gemini_model)

def _has_openrouter(s):
    return bool(s.openrouter_api_key and s.openrouter_model)

def _has_lmstudio(s):
    # Check if LM Studio is reachable
    import httpx
    try:
        r = httpx.get(f"{s.lmstudio_base_url}/models", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
def test_live_gemini_compile(settings):
    from skillvm.llm_compile import compile_with_llm
    from skillvm.providers import GeminiProvider, ProviderManager
    if not _has_gemini(settings):
        pytest.skip("Gemini not configured")
    mgr = ProviderManager(providers=[GeminiProvider()], settings=settings)
    result = compile_with_llm(SIMPLE_SKILL, mgr)
    assert result.status.value in ("COMPILED", "NEEDS_REVIEW")
    assert result.ir is not None or result.status.value == "NEEDS_REVIEW"
    if result.ir:
        assert result.ir.provider == "google"
        print(f"\nGemini IR nodes: {[n.type for n in result.ir.nodes]}")
        print(f"Constrained mode: {result.ir.constrained_mode}")


@pytest.mark.skipif(not os.environ.get("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set")
def test_live_openrouter_compile(settings):
    from skillvm.llm_compile import compile_with_llm
    from skillvm.providers import OpenAICompatProvider, ProviderManager
    if not _has_openrouter(settings):
        pytest.skip("OpenRouter not configured")
    mgr = ProviderManager(providers=[OpenAICompatProvider("openrouter")], settings=settings)
    result = compile_with_llm(SIMPLE_SKILL, mgr)
    assert result.status.value in ("COMPILED", "NEEDS_REVIEW")
    if result.ir:
        assert result.ir.provider == "openrouter"
        print(f"\nOpenRouter IR nodes: {[n.type for n in result.ir.nodes]}")


def test_live_lmstudio_compile(settings):
    from skillvm.llm_compile import compile_with_llm
    from skillvm.providers import OpenAICompatProvider, ProviderManager
    if not _has_lmstudio(settings):
        pytest.skip("LM Studio not reachable at " + settings.lmstudio_base_url)
    mgr = ProviderManager(providers=[OpenAICompatProvider("lmstudio")], settings=settings)
    result = compile_with_llm(SIMPLE_SKILL, mgr)
    # LM Studio may produce schema_prompt_repaired or fallback to deterministic
    assert result.status.value in ("COMPILED", "NEEDS_REVIEW")
    print(f"\nLM Studio result: status={result.status.value}")
    if result.ir:
        print(f"  mode={result.ir.constrained_mode} nodes={[n.type for n in result.ir.nodes]}")


@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
def test_live_fallback_chain(settings):
    """Primary (fake timeout) -> Google as fallback -> compiles."""
    from skillvm.llm_compile import compile_with_llm
    from skillvm.providers import FakeProvider, GeminiProvider, ProviderManager, ProviderError
    if not _has_gemini(settings):
        pytest.skip("Gemini not configured")
    mgr = ProviderManager(
        providers=[FakeProvider(failures=[ProviderError("simulated timeout")]), GeminiProvider()],
        settings=settings,
    )
    result = compile_with_llm(SIMPLE_SKILL, mgr)
    assert result.status.value in ("COMPILED", "NEEDS_REVIEW")
    print(f"\nFallback chain result: {result.status.value}, provider: {result.ir.provider if result.ir else 'N/A'}")
