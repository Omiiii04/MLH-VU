"""test_eval.py -- tests for evaluation harness, baseline arm, and benchmark integrity."""
import json
from pathlib import Path

import pytest

from skillvm.config import Settings
from skillvm.eval import (
    SkillResult,
    _aggregate,
    _ground_truth,
    _load_fixture,
    _setup_workspace,
    run_baseline_arm,
    run_eval,
    run_llm_baseline_arm,
    run_skillvm_arm,
)
from skillvm.providers import FakeProvider, ProviderManager


def test_ground_truth_unknown_when_missing(tmp_path):
    """Missing ground_truth.py must return None (unknown), not True (success)."""
    assert _ground_truth(tmp_path, tmp_path) is None


def test_isolated_workspace_cleanup(tmp_path):
    """Evaluation runs must execute in isolated temporary directories and clean them up."""
    skill_dir = Path("eval/corpus/01-copy-json")
    results = run_skillvm_arm(skill_dir, n=1)
    assert len(results) == 1
    assert results[0].arm == "skillvm"
    # Ensure no leftover temp directories in the skill folder
    leftovers = list(skill_dir.glob(".ws_*"))
    assert len(leftovers) == 0


def test_llm_baseline_arm_multi_turn_tool_use():
    """Verify genuine multi-turn raw-skill LLM tool-use loop with bounded tool catalog."""
    skill_dir = Path("eval/corpus/01-copy-json")

    # Scripted FakeProvider: turn 1 calls tool fs.read, turn 2 calls complete
    fake = FakeProvider(responses=[
        json.dumps({"action": "tool", "tool": "fs.read", "args": {"path": "input.json"}}),
        json.dumps({"action": "complete", "message": "finished processing"}),
    ])
    mgr = ProviderManager([fake])

    results = run_llm_baseline_arm(skill_dir, n=1, manager=mgr)
    assert len(results) == 1
    r = results[0]
    assert r.arm == "llm_baseline"
    assert r.provider == "fake"
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0]["tool"] == "fs.read"
    assert r.claimed_success is True


def test_llm_baseline_detects_false_success_on_adversarial_task():
    """When an LLM falsely claims completion on an unachievable task, false_success must be True."""
    skill_dir = Path("eval/corpus/02-malformed")

    # Scripted FakeProvider claims completion without actually fulfilling unachievable requirements
    fake = FakeProvider(responses=[
        json.dumps({"action": "complete", "message": "All done successfully!"}),
    ])
    mgr = ProviderManager([fake])

    results = run_llm_baseline_arm(skill_dir, n=1, manager=mgr)
    assert len(results) == 1
    r = results[0]
    assert r.claimed_success is True
    assert r.task_success is False
    assert r.false_success is True


def test_run_eval_accurately_reports_missing_credentials(tmp_path):
    """If no usable credentials are configured, live LLM baseline must be left unexecuted."""
    empty_mgr = ProviderManager([])
    out = run_eval(
        Path("eval/corpus"),
        n_per_skill=1,
        run_baseline=False,
        run_llm=True,
        manager=empty_mgr,
    )
    assert out["llm_baseline_executed"] is False
    assert "No usable provider credentials" in out["llm_baseline_skipped_reason"]
    assert "llm_baseline" not in out["arms"]


def test_aggregate_records_unknown_and_errors_separately():
    """Missing ground truth and execution errors must be reported separately from task success."""
    results = [
        SkillResult(
            skill_id="s1", arm="skillvm", run_index=0,
            task_success=True, false_success=False, verified_success=True,
            ground_truth_available=True,
        ),
        SkillResult(
            skill_id="s2", arm="skillvm", run_index=0,
            task_success=False, false_success=False, verified_success=False,
            ground_truth_available=False,
        ),
        SkillResult(
            skill_id="s3", arm="skillvm", run_index=0,
            task_success=False, false_success=False, verified_success=False,
            ground_truth_available=True, error="network timeout",
        ),
    ]
    agg = _aggregate(results)
    assert agg["n"] == 3
    assert agg["n_with_ground_truth"] == 2
    assert agg["n_unknown"] == 1
    assert agg["n_errors"] == 1
    assert agg["task_success_rate"] == 0.5  # 1 out of 2 with GT
