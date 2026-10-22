# Graph Report - MLH-VU  (2026-10-22)

## Corpus Check
- 75 files · ~29,959 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .example 1)

## Summary
- 570 nodes · 1430 edges · 35 communities (12 shown, 23 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 227 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `28313ae2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- FakeProvider
- compiler.py
- execute_ir
- eval.py
- SkillVM
- json
- ProviderManager
- pytest
- skillvm
- test_server.py
- compile_with_llm
- redact.py
- cli.py
- 05-field-pick/skill.md
- 06-schema-validate/skill.md
- 07-schema-validate-fail/skill.md
- 08-file-list/skill.md
- 09-field-merge/skill.md
- 10-missing-source/skill.md
- 11-checksum/skill.md
- 12-bad-json/skill.md
- 02-malformed/ground_truth.py
- 14-multi-step-chain/skill.md
- 15-schema-unchanged/skill.md
- 03-permission-violation/ground_truth.py
- 07-schema-validate-fail/ground_truth.py
- 10-missing-source/ground_truth.py
- 12-bad-json/ground_truth.py
- 13-path-traversal/ground_truth.py
- Copy JSON
- Malformed
- Permission Violation
- Verify Catch
- 13-path-traversal/skill.md

## God Nodes (most connected - your core abstractions)
1. `execute_ir()` - 49 edges
2. `compile_skill()` - 39 edges
3. `FakeProvider` - 39 edges
4. `compile_with_llm()` - 33 edges
5. `Settings` - 31 edges
6. `ProviderError` - 30 edges
7. `RunState` - 26 edges
8. `ProviderManager` - 25 edges
9. `Sandbox` - 24 edges
10. `_resolve_workspace()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Current 15-Skill Benchmark (`eval/results.json`)` --references--> `run_llm_baseline_arm()`  [INFERRED]
  README.md → src/skillvm/eval.py
- `Security and Sandboxing` --references--> `_validate_ir()`  [INFERRED]
  README.md → src/skillvm/compiler.py
- `Security and Sandboxing` --references--> `ApprovalNode`  [INFERRED]
  README.md → src/skillvm/ir.py
- `Security and Sandboxing` --references--> `_resolve_workspace()`  [INFERRED]
  README.md → src/skillvm/server.py
- `Security and Sandboxing` --references--> `Sandbox`  [INFERRED]
  README.md → src/skillvm/tools.py

## Import Cycles
- None detected.

## Communities (35 total, 23 thin omitted)

### Community 0 - "FakeProvider"
Cohesion: 0.05
Nodes (41): Settings, AuthError, BaseProvider, build_manager(), _classify_genai_error(), FakeProvider, GeminiProvider, ModelNotFoundError (+33 more)

### Community 1 - "compiler.py"
Cohesion: 0.06
Nodes (56): _build_nodes(), _check_postconditions(), compile_skill(), _has_cycle(), dfs(), _validate_ir(), CompileStatus, d() (+48 more)

### Community 2 - "execute_ir"
Cohesion: 0.07
Nodes (36): HTTP API Reference, DuplicateRunError, execute_ir(), NodeRecord, NodeState, _resolve_args(), _resolve_template(), resume_run() (+28 more)

### Community 3 - "eval.py"
Cohesion: 0.21
Nodes (12): _infer_tool(), _path_from_step(), _aggregate(), _ground_truth(), _load_fixture(), run_baseline_arm(), run_eval(), run_llm_baseline_arm() (+4 more)

### Community 4 - "SkillVM"
Cohesion: 0.07
Nodes (27): 1. Compile a Skill to Workflow IR, 2. Inspect the Execution Plan, 3. Execute a Workflow, 4. Safe Human-in-the-Loop Approval & Resumption, 5. Probe Configured Providers, 6. Run the Evaluation Harness, Architecture, Command-Line Interface (CLI) (+19 more)

### Community 5 - "json"
Cohesion: 0.20
Nodes (7): check(), check(), check(), check(), check(), check(), check()

### Community 6 - "ProviderManager"
Cohesion: 0.16
Nodes (6): ProviderManager, test_ground_truth_unknown_when_missing(), test_isolated_workspace_cleanup(), test_llm_baseline_arm_multi_turn_tool_use(), test_llm_baseline_detects_false_success_on_adversarial_task(), test_run_eval_accurately_reports_missing_credentials()

### Community 7 - "pytest"
Cohesion: 0.06
Nodes (36): Security and Sandboxing, _resolve_workspace(), _check_permission(), execute_tool(), PermissionError_, _run_check(), Sandbox, SandboxError (+28 more)

### Community 9 - "test_server.py"
Cohesion: 0.07
Nodes (12): _b(), _f(), _i(), load_settings(), settings(), _make_root_with_workspace(), test_absolute_path_workspace_rejected(), test_compile_llm_false_uses_deterministic() (+4 more)

### Community 10 - "compile_with_llm"
Cohesion: 0.13
Nodes (15): _build_prompt(), compile_with_llm(), _has_gemini(), _has_lmstudio(), _has_openrouter(), test_live_gemini_compile(), test_live_lmstudio_compile(), test_live_openrouter_compile() (+7 more)

### Community 11 - "redact.py"
Cohesion: 0.33
Nodes (5): check(), excerpt(), prompt_hash(), redact_obj(), redact_text()

### Community 12 - "cli.py"
Cohesion: 0.14
Nodes (8): approve(), compile(), eval(), _load_settings(), plan(), probe(), run(), serve()

## Knowledge Gaps
- **1 isolated node(s):** `skillvm`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 213 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `execute_ir()` connect `execute_ir` to `compiler.py`, `eval.py`, `cli.py`, `pytest`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `execute_ir()` (e.g. with `EffectType` and `WorkflowIR`) actually correct?**
  _`execute_ir()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `skillvm` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FakeProvider` be split into smaller, more focused modules?**
  _Cohesion score 0.051893408134642355 - nodes in this community are weakly interconnected._
- **Why does `Security and Sandboxing` connect `pytest` to `compiler.py`, `SkillVM`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `compile_skill()` (e.g. with `CompileStatus` and `Diagnostic`) actually correct?**
  _`compile_skill()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `compiler.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06139512661251792 - nodes in this community are weakly interconnected._