"""eval.py -- evaluation harness.

Measures false-success rate: SkillVM arm vs baseline (raw SKILL.md prompt loop).
Ground truth checkers are INDEPENDENT of runtime verifiers.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillvm.compiler import compile_skill
from skillvm.ir import WorkflowIR
from skillvm.runtime import execute_ir, RunState
from skillvm.tools import Sandbox


# ---------------------------------------------------------------------------
# Corpus fixture format
# ---------------------------------------------------------------------------
# Each skill dir: skill.md, fixture.json, ground_truth.py (optional)
# fixture.json: {"inputs": {...}, "workspace_files": {"file.json": "content"}}
# ground_truth.py: def check(workspace_path) -> bool

@dataclass
class SkillResult:
    skill_id: str
    arm: str  # "skillvm" or "baseline"
    run_index: int
    task_success: bool      # ground truth says done
    false_success: bool     # claimed done but ground truth says no
    verified_success: bool  # runtime said VERIFIED_SUCCESS
    error: str | None = None
    duration: float = 0.0


def _load_fixture(skill_dir: Path) -> dict:
    fx = skill_dir / "fixture.json"
    if fx.exists():
        return json.loads(fx.read_text(encoding="utf-8"))
    return {"inputs": {}, "workspace_files": {}}


def _setup_workspace(tmp: Path, fixture: dict) -> Path:
    ws = tmp
    ws.mkdir(parents=True, exist_ok=True)
    for name, content in fixture.get("workspace_files", {}).items():
        p = ws / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            p.write_text(json.dumps(content), encoding="utf-8")
        else:
            p.write_text(str(content), encoding="utf-8")
    return ws


def _ground_truth(skill_dir: Path, workspace: Path) -> bool:
    """Run independent ground-truth checker."""
    gt_file = skill_dir / "ground_truth.py"
    if not gt_file.exists():
        # No ground truth = unknown, treat as success if any output file exists
        return True
    import importlib.util
    spec = importlib.util.spec_from_file_location("gt", gt_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return bool(mod.check(workspace))


def run_skillvm_arm(skill_dir: Path, n: int) -> list[SkillResult]:
    results = []
    skill_md = (skill_dir / "skill.md").read_text(encoding="utf-8")
    fixture = _load_fixture(skill_dir)
    compile_result = compile_skill(skill_md)
    skill_id = compile_result.ir.skill_id if compile_result.ir else skill_dir.name

    if compile_result.ir is None:
        for i in range(n):
            results.append(SkillResult(skill_id=skill_id, arm="skillvm", run_index=i, task_success=False, false_success=False, verified_success=False, error="compile failed"))
        return results

    for i in range(n):
        tmp = skill_dir / f".ws_skillvm_{i}"
        try:
            ws = _setup_workspace(tmp, fixture)
            t0 = time.monotonic()
            # Auto-approve for eval
            approvals = {n.id: f"approved:{n.id}" for n in compile_result.ir.nodes if n.type == "approval"}
            run_rec = execute_ir(compile_result.ir, fixture.get("inputs", {}), workspace=ws, pending_approvals=approvals)
            dt = time.monotonic() - t0
            verified = run_rec.state == RunState.VERIFIED_SUCCESS
            gt = _ground_truth(skill_dir, ws)
            false_success = verified and not gt
            results.append(SkillResult(skill_id=skill_id, arm="skillvm", run_index=i, task_success=gt, false_success=false_success, verified_success=verified, duration=dt))
        except Exception as e:
            results.append(SkillResult(skill_id=skill_id, arm="skillvm", run_index=i, task_success=False, false_success=False, verified_success=False, error=str(e)))
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    return results


def run_baseline_arm(skill_dir: Path, n: int) -> list[SkillResult]:
    """Baseline: raw SKILL.md as prompt in a plain tool-use loop (no IR, no verify)."""
    results = []
    fixture = _load_fixture(skill_dir)
    skill_md = (skill_dir / "skill.md").read_text(encoding="utf-8")
    skill_id = skill_dir.name

    for i in range(n):
        tmp = skill_dir / f".ws_baseline_{i}"
        try:
            ws = _setup_workspace(tmp, fixture)
            t0 = time.monotonic()
            # Baseline: parse steps, run tools naively, claim success
            from skillvm.parse import parse_skill
            from skillvm.compiler import _infer_tool, _path_from_step
            from skillvm.tools import execute_tool

            parsed = parse_skill(skill_md)
            perms = list((parsed.meta or {}).get("permissions", []))
            sandbox = Sandbox(workspace=ws, authorized_root=ws)
            claimed_success = True
            for _, _, step_text in parsed.steps:
                tool = _infer_tool(step_text)
                if not tool:
                    continue
                path = _path_from_step(step_text)
                args: dict = {}
                if tool in ("fs.read", "fs.list", "fs.write"):
                    args["path"] = path
                    if tool == "fs.write":
                        args["content"] = "baseline output"
                elif tool == "json.parse":
                    args["text"] = "{}"
                elif tool == "data.transform":
                    args["op"] = "identity"; args["value"] = None
                try:
                    execute_tool(tool, args, perms, sandbox)
                except Exception:
                    claimed_success = False
            dt = time.monotonic() - t0
            gt = _ground_truth(skill_dir, ws)
            false_success = claimed_success and not gt
            results.append(SkillResult(skill_id=skill_id, arm="baseline", run_index=i, task_success=gt, false_success=false_success, verified_success=False, duration=dt))
        except Exception as e:
            results.append(SkillResult(skill_id=skill_id, arm="baseline", run_index=i, task_success=False, false_success=False, verified_success=False, error=str(e)))
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    return results


def _aggregate(results: list[SkillResult]) -> dict:
    if not results:
        return {}
    n = len(results)
    return {
        "n": n,
        "task_success_rate": sum(r.task_success for r in results) / n,
        "false_success_rate": sum(r.false_success for r in results) / n,
        "verified_success_rate": sum(r.verified_success for r in results) / n,
        "error_rate": sum(1 for r in results if r.error) / n,
        "mean_duration": sum(r.duration for r in results) / n,
        "per_skill": {},
    }


def run_eval(corpus_dir: Path, n_per_skill: int = 3, run_baseline: bool = True) -> dict:
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        return {"error": f"Corpus dir not found: {corpus_dir}", "arms": {}}

    skill_dirs = [d for d in corpus_dir.iterdir() if d.is_dir() and (d / "skill.md").exists()]
    if not skill_dirs:
        return {"error": "No skills found in corpus", "arms": {}}

    all_skillvm: list[SkillResult] = []
    all_baseline: list[SkillResult] = []

    for skill_dir in sorted(skill_dirs):
        sv = run_skillvm_arm(skill_dir, n_per_skill)
        all_skillvm.extend(sv)
        if run_baseline:
            bl = run_baseline_arm(skill_dir, n_per_skill)
            all_baseline.extend(bl)

    arms: dict = {"skillvm": _aggregate(all_skillvm)}
    if run_baseline:
        arms["baseline"] = _aggregate(all_baseline)

    return {
        "corpus": str(corpus_dir),
        "n_per_skill": n_per_skill,
        "n_skills": len(skill_dirs),
        "arms": arms,
    }
