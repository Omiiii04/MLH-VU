"""eval.py -- evaluation harness.

Measures false-success rate: SkillVM arm vs baseline.
- Arm 1: SkillVM (compiled WorkflowIR + sandbox snapshot + deterministic postcondition verifier)
- Arm 2: Real LLM baseline (genuine raw-skill multi-turn tool-use loop with bounded tools)
- Arm 3: Deterministic step baseline (offline reference parser)
Ground truth checkers are INDEPENDENT of runtime verifiers.
"""
from __future__ import annotations

import json
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillvm.compiler import compile_skill
from skillvm.config import Settings, load_settings
from skillvm.ir import WorkflowIR
from skillvm.providers import BaseProvider, ProviderManager, build_manager
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
    arm: str  # "skillvm", "baseline", "llm_baseline"
    run_index: int
    task_success: bool      # ground truth says done
    false_success: bool     # claimed done but ground truth says no
    verified_success: bool  # runtime said VERIFIED_SUCCESS
    ground_truth_available: bool = True  # False when no checker exists
    error: str | None = None
    duration: float = 0.0
    provider: str | None = None
    model: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    claimed_success: bool = False


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


def _ground_truth(skill_dir: Path, workspace: Path) -> bool | None:
    """Run independent ground-truth checker. Returns None if no checker exists.

    IMPORTANT: A missing checker is NOT evidence of success.
    Callers must treat None as 'unknown', not True.
    """
    gt_file = skill_dir / "ground_truth.py"
    if not gt_file.exists():
        return None  # unknown — never treat as success
    import importlib.util
    spec = importlib.util.spec_from_file_location("gt", gt_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return bool(mod.check(workspace))


def run_skillvm_arm(
    skill_dir: Path,
    n: int,
    manager: ProviderManager | None = None,
    settings: Settings | None = None,
) -> list[SkillResult]:
    """SkillVM arm: compiles SKILL.md to IR, executes with snapshot & verifiers in isolated workspaces."""
    results = []
    skill_md = (skill_dir / "skill.md").read_text(encoding="utf-8")
    fixture = _load_fixture(skill_dir)

    provider_name = None
    model_name = None
    compile_result = None

    if manager and getattr(manager, "providers", None):
        try:
            from skillvm.llm_compile import compile_with_llm
            compile_result = compile_with_llm(skill_md, manager)
            if compile_result.ir:
                provider_name = compile_result.ir.provider
                model_name = compile_result.ir.model
        except Exception:
            compile_result = None

    if compile_result is None:
        compile_result = compile_skill(skill_md)

    skill_id = compile_result.ir.skill_id if compile_result.ir else skill_dir.name

    if compile_result.ir is None:
        for i in range(n):
            results.append(SkillResult(
                skill_id=skill_id, arm="skillvm", run_index=i,
                task_success=False, false_success=False, verified_success=False,
                error="compile failed", provider=provider_name, model=model_name,
            ))
        return results

    for i in range(n):
        with tempfile.TemporaryDirectory(prefix=f"skillvm_eval_svm_{skill_id}_{i}_") as tmpdir:
            try:
                ws = _setup_workspace(Path(tmpdir), fixture)
                t0 = time.monotonic()
                approvals = {node.id: f"approved:{node.id}" for node in compile_result.ir.nodes if node.type == "approval"}
                run_rec = execute_ir(
                    compile_result.ir,
                    fixture.get("inputs", {}),
                    workspace=ws,
                    pending_approvals=approvals,
                    run_id=f"eval_svm_{skill_id}_{i}",
                )
                dt = time.monotonic() - t0
                verified = run_rec.state == RunState.VERIFIED_SUCCESS
                gt = _ground_truth(skill_dir, ws)
                gt_available = gt is not None
                gt_bool = bool(gt) if gt is not None else False  # unknown = not-success
                false_success = verified and not gt_bool
                results.append(SkillResult(
                    skill_id=skill_id, arm="skillvm", run_index=i,
                    task_success=gt_bool, false_success=false_success,
                    verified_success=verified, ground_truth_available=gt_available,
                    duration=dt, provider=provider_name, model=model_name,
                    claimed_success=verified,
                ))
            except Exception as e:
                results.append(SkillResult(
                    skill_id=skill_id, arm="skillvm", run_index=i,
                    task_success=False, false_success=False, verified_success=False,
                    error=str(e), provider=provider_name, model=model_name,
                ))
    return results


def run_baseline_arm(skill_dir: Path, n: int) -> list[SkillResult]:
    """Deterministic baseline: offline step parser that executes inferred tools without IR or verifiers."""
    results = []
    fixture = _load_fixture(skill_dir)
    skill_md = (skill_dir / "skill.md").read_text(encoding="utf-8")
    skill_id = skill_dir.name

    from skillvm.parse import parse_skill
    from skillvm.compiler import _infer_tool, _path_from_step
    from skillvm.tools import execute_tool

    parsed = parse_skill(skill_md)
    perms = list((parsed.meta or {}).get("permissions", []))

    for i in range(n):
        with tempfile.TemporaryDirectory(prefix=f"skillvm_eval_det_{skill_id}_{i}_") as tmpdir:
            try:
                ws = _setup_workspace(Path(tmpdir), fixture)
                t0 = time.monotonic()
                sandbox = Sandbox(workspace=ws, authorized_root=ws, run_id=f"eval_det_{skill_id}_{i}")
                claimed_success = True
                tool_calls: list[dict] = []
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
                    tool_calls.append({"tool": tool, "args": args})
                    try:
                        execute_tool(tool, args, perms, sandbox)
                    except Exception:
                        claimed_success = False

                dt = time.monotonic() - t0
                gt = _ground_truth(skill_dir, ws)
                gt_available = gt is not None
                gt_bool = bool(gt) if gt is not None else False
                false_success = claimed_success and not gt_bool
                results.append(SkillResult(
                    skill_id=skill_id, arm="baseline", run_index=i,
                    task_success=gt_bool, false_success=false_success,
                    verified_success=False, ground_truth_available=gt_available,
                    duration=dt, tool_calls=tool_calls, claimed_success=claimed_success,
                ))
            except Exception as e:
                results.append(SkillResult(
                    skill_id=skill_id, arm="baseline", run_index=i,
                    task_success=False, false_success=False, verified_success=False,
                    error=str(e),
                ))
    return results


def run_llm_baseline_arm(
    skill_dir: Path,
    n: int,
    manager: ProviderManager,
    settings: Settings | None = None,
    max_turns: int = 10,
) -> list[SkillResult]:
    """Genuine raw-skill LLM tool-use loop (no IR, no verify, pure model + tools)."""
    results = []
    fixture = _load_fixture(skill_dir)
    skill_md = (skill_dir / "skill.md").read_text(encoding="utf-8")
    skill_id = skill_dir.name

    from skillvm.parse import parse_skill
    from skillvm.tools import execute_tool

    parsed = parse_skill(skill_md)
    perms = list((parsed.meta or {}).get("permissions", []))

    system_prompt = (
        "You are an AI assistant executing a skill directly in an isolated workspace using available tools.\n"
        "Bounded tool catalog:\n"
        "- fs.read: {\"path\": str}\n"
        "- fs.list: {\"path\": str}\n"
        "- fs.write: {\"path\": str, \"content\": any}\n"
        "- json.parse: {\"text\": str}\n"
        "- data.transform: {\"op\": str, \"value\": any, \"fields\": any}\n\n"
        "Respond with a single JSON object. Either invoke a tool or claim completion:\n"
        "Tool call:       {\"action\": \"tool\", \"tool\": \"<tool_name>\", \"args\": {<tool_arguments>}}\n"
        "Completion claim: {\"action\": \"complete\", \"message\": \"<summary of completion>\"}\n"
        "Do not output commentary outside the JSON."
    )

    for i in range(n):
        with tempfile.TemporaryDirectory(prefix=f"skillvm_eval_llm_{skill_id}_{i}_") as tmpdir:
            ws = _setup_workspace(Path(tmpdir), fixture)
            t0 = time.monotonic()
            sandbox = Sandbox(workspace=ws, authorized_root=ws, run_id=f"eval_llm_{skill_id}_{i}")
            tool_calls: list[dict] = []
            claimed_success = False
            last_provider = None
            last_model = None

            user_msg = (
                f"Skill definition (SKILL.md):\n```markdown\n{skill_md}\n```\n\n"
                f"Task inputs:\n```json\n{json.dumps(fixture.get('inputs', {}), indent=2)}\n```\n\n"
                "Execute the skill steps using the available tools."
            )

            try:
                for turn in range(max_turns):
                    gen_res = manager.generate(system=system_prompt, user=user_msg)
                    last_provider = gen_res.provider
                    last_model = gen_res.model

                    raw_text = gen_res.text.strip()
                    action_data = None
                    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
                    if m:
                        try:
                            action_data = json.loads(m.group(1))
                        except Exception:
                            pass
                    if not action_data:
                        m2 = re.search(r"(\{.*\})", raw_text, re.DOTALL)
                        if m2:
                            try:
                                action_data = json.loads(m2.group(1))
                            except Exception:
                                pass
                    if not action_data:
                        try:
                            action_data = json.loads(raw_text)
                        except Exception:
                            action_data = {"action": "error", "message": "Failed to parse action JSON"}

                    action = action_data.get("action")
                    if action == "complete":
                        claimed_success = True
                        break

                    if action == "tool":
                        t_name = str(action_data.get("tool", ""))
                        t_args = action_data.get("args", {})
                        tool_calls.append({"tool": t_name, "args": t_args})
                        try:
                            res = execute_tool(t_name, t_args, perms, sandbox)
                            obs = f"Tool '{t_name}' succeeded: {json.dumps(res)}"
                        except Exception as te:
                            obs = f"Tool '{t_name}' failed: {te}"
                        user_msg += f"\n\nObservation:\n{obs}\nNext step or complete:"
                    else:
                        user_msg += "\n\nInvalid action format. Provide a JSON tool call or completion claim."

                dt = time.monotonic() - t0
                gt = _ground_truth(skill_dir, ws)
                gt_available = gt is not None
                gt_bool = bool(gt) if gt is not None else False
                false_success = claimed_success and not gt_bool

                results.append(SkillResult(
                    skill_id=skill_id, arm="llm_baseline", run_index=i,
                    task_success=gt_bool, false_success=false_success,
                    verified_success=False, ground_truth_available=gt_available,
                    duration=dt, provider=last_provider, model=last_model,
                    tool_calls=tool_calls, claimed_success=claimed_success,
                ))
            except Exception as e:
                dt = time.monotonic() - t0
                results.append(SkillResult(
                    skill_id=skill_id, arm="llm_baseline", run_index=i,
                    task_success=False, false_success=False, verified_success=False,
                    error=str(e), duration=dt, provider=last_provider, model=last_model,
                    tool_calls=tool_calls, claimed_success=False,
                ))
    return results


def _aggregate(results: list[SkillResult]) -> dict:
    if not results:
        return {}
    n = len(results)
    with_gt = [r for r in results if r.ground_truth_available]
    unknown = [r for r in results if not r.ground_truth_available]
    errors = [r for r in results if r.error]
    claimed = [r for r in results if r.claimed_success]

    providers = sorted({r.provider for r in results if r.provider})
    models = sorted({r.model for r in results if r.model})

    per_skill: dict[str, dict] = {}
    for r in results:
        ps = per_skill.setdefault(
            r.skill_id,
            {"n": 0, "task_success": 0, "false_success": 0, "verified_success": 0, "claimed_success": 0},
        )
        ps["n"] += 1
        if r.task_success: ps["task_success"] += 1
        if r.false_success: ps["false_success"] += 1
        if r.verified_success: ps["verified_success"] += 1
        if r.claimed_success: ps["claimed_success"] += 1

    return {
        "n": n,
        "n_with_ground_truth": len(with_gt),
        "n_unknown": len(unknown),
        "n_errors": len(errors),
        "task_success_rate": sum(r.task_success for r in with_gt) / len(with_gt) if with_gt else None,
        "false_success_rate": sum(r.false_success for r in with_gt) / len(with_gt) if with_gt else None,
        "verified_success_rate": sum(r.verified_success for r in results) / n,
        "claimed_success_rate": len(claimed) / n,
        "error_rate": len(errors) / n,
        "mean_duration": sum(r.duration for r in results) / n,
        "providers": providers,
        "models": models,
        "per_skill": per_skill,
    }


def run_eval(
    corpus_dir: Path,
    n_per_skill: int = 1,
    run_baseline: bool = True,
    run_llm: bool = False,
    manager: ProviderManager | None = None,
    settings: Settings | None = None,
) -> dict:
    """Run evaluation harness across the corpus."""
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        return {"error": f"Corpus dir not found: {corpus_dir}", "arms": {}}

    skill_dirs = [d for d in corpus_dir.iterdir() if d.is_dir() and (d / "skill.md").exists()]
    if not skill_dirs:
        return {"error": "No skills found in corpus", "arms": {}}

    settings = settings or load_settings()
    llm_manager = manager
    llm_baseline_executed = False
    llm_baseline_reason = None

    if run_llm:
        if llm_manager is None:
            llm_manager = build_manager(settings)
        if not llm_manager.providers:
            llm_baseline_executed = False
            llm_baseline_reason = "No usable provider credentials configured."
        else:
            # Usable providers exist; execute live arms
            llm_baseline_executed = True

    all_skillvm: list[SkillResult] = []
    all_baseline: list[SkillResult] = []
    all_llm_baseline: list[SkillResult] = []

    for skill_dir in sorted(skill_dirs):
        sv = run_skillvm_arm(skill_dir, n_per_skill, manager=llm_manager if llm_baseline_executed else None, settings=settings)
        all_skillvm.extend(sv)
        if run_baseline:
            bl = run_baseline_arm(skill_dir, n_per_skill)
            all_baseline.extend(bl)
        if llm_baseline_executed and llm_manager is not None:
            lbl = run_llm_baseline_arm(skill_dir, n_per_skill, manager=llm_manager, settings=settings)
            all_llm_baseline.extend(lbl)

    arms: dict = {"skillvm": _aggregate(all_skillvm)}
    if run_baseline:
        arms["baseline"] = _aggregate(all_baseline)
    if llm_baseline_executed:
        arms["llm_baseline"] = _aggregate(all_llm_baseline)

    out: dict[str, Any] = {
        "corpus": str(corpus_dir),
        "n_per_skill": n_per_skill,
        "n_skills": len(skill_dirs),
        "arms": arms,
        "baseline_type": "deterministic_parser" if not llm_baseline_executed else "deterministic_parser_and_llm_baseline",
        "baseline_disclaimer": (
            "The offline baseline is a deterministic step parser reusing SkillVM helpers without IR/verification. "
            "The LLM baseline (when executed) is a genuine multi-turn raw-skill prompt loop using the configured provider."
        ),
        "llm_baseline_executed": llm_baseline_executed,
    }
    if llm_baseline_reason:
        out["llm_baseline_skipped_reason"] = llm_baseline_reason

    return out
