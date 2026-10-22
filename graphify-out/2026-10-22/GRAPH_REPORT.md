# Graph Report - MLH-VU  (2026-10-22)

## Corpus Check
- 72 files · ~21,671 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .example 1)

## Summary
- 494 nodes · 1204 edges · 26 communities (11 shown, 15 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 159 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3db651f9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- providers.py
- compiler.py
- execute_ir
- eval.py
- SkillVM
- json
- compile_skill
- pytest
- skillvm
- server.py
- compile_with_llm
- cli.py
- 05-field-pick/skill.md
- 06-schema-validate/skill.md
- 07-schema-validate-fail/skill.md
- 08-file-list/skill.md
- 09-field-merge/skill.md
- 10-missing-source/skill.md
- 11-checksum/skill.md
- 12-bad-json/skill.md
- 13-permission-violation/skill.md
- 14-multi-step-chain/skill.md
- 15-schema-unchanged/skill.md

## God Nodes (most connected - your core abstractions)
1. `execute_ir()` - 44 edges
2. `compile_skill()` - 38 edges
3. `FakeProvider` - 34 edges
4. `compile_with_llm()` - 27 edges
5. `Settings` - 24 edges
6. `ProviderError` - 24 edges
7. `RunState` - 24 edges
8. `Sandbox` - 19 edges
9. `_build_nodes()` - 18 edges
10. `_resolve_workspace()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Testing` --references--> `FakeProvider`  [INFERRED]
  README.md → src/skillvm/providers.py
- `Security and Sandboxing` --references--> `ApprovalNode`  [INFERRED]
  README.md → src/skillvm/ir.py
- `Security and Sandboxing` --references--> `_validate_ir()`  [INFERRED]
  README.md → src/skillvm/compiler.py
- `Testing` --references--> `test_symlink_escape_blocked()`  [EXTRACTED]
  README.md → tests/test_security.py
- `Security and Sandboxing` --references--> `_check_permission()`  [INFERRED]
  README.md → src/skillvm/tools.py

## Import Cycles
- None detected.

## Communities (26 total, 15 thin omitted)

### Community 0 - "providers.py"
Cohesion: 0.05
Nodes (43): Settings, AuthError, BaseProvider, build_manager(), _classify_genai_error(), FakeProvider, GeminiProvider, ModelNotFoundError (+35 more)

### Community 1 - "compiler.py"
Cohesion: 0.09
Nodes (37): check(), _build_nodes(), _check_postconditions(), _has_cycle(), dfs(), _validate_ir(), CompileStatus, d() (+29 more)

### Community 2 - "execute_ir"
Cohesion: 0.07
Nodes (30): DuplicateRunError, execute_ir(), NodeRecord, NodeState, _resolve_args(), _resolve_template(), RunRecord, RunState (+22 more)

### Community 3 - "eval.py"
Cohesion: 0.27
Nodes (10): _infer_tool(), _path_from_step(), _aggregate(), _ground_truth(), _load_fixture(), run_baseline_arm(), run_eval(), run_skillvm_arm() (+2 more)

### Community 4 - "SkillVM"
Cohesion: 0.07
Nodes (26): 1. Compile a Skill to Workflow IR, 2. Inspect the Execution Plan, 3. Execute a Workflow, 4. Generate an Approval Token, 5. Probe Configured Providers, 6. Run the Evaluation Harness, Architecture, Command-Line Interface (CLI) (+18 more)

### Community 5 - "json"
Cohesion: 0.06
Nodes (14): check(), check(), check(), check(), check(), check(), check(), check() (+6 more)

### Community 6 - "compile_skill"
Cohesion: 0.21
Nodes (14): compile_skill(), test_ambiguity_needs_review(), test_bad_binding_type_error(), test_bad_metadata_rejected(), test_cycle_rejected(), test_golden_copy_json(), test_irreversible_requires_approval(), test_llm_node_requires_schema_and_verify() (+6 more)

### Community 7 - "pytest"
Cohesion: 0.05
Nodes (28): _resolve_workspace(), _blocked_or_failed(), _make_settings(), test_absolute_path_rejected(), test_client_cannot_override_root_via_workspace(), test_etc_rejected_before_contents_returned(), test_forged_approval_rejected(), test_missing_workspace_rejected() (+20 more)

### Community 9 - "server.py"
Cohesion: 0.10
Nodes (18): _b(), _f(), _i(), load_settings(), approve_run(), ApproveRequest, compile_endpoint(), CompileRequest (+10 more)

### Community 10 - "compile_with_llm"
Cohesion: 0.26
Nodes (7): _mgr(), test_llm_ir_passes_same_validator_as_deterministic(), test_malformed_ir_both_attempts_falls_back_to_deterministic(), test_malformed_ir_triggers_repair_then_valid(), test_provider_failure_falls_back_to_deterministic(), test_provider_failure_no_fallback_rejects(), test_valid_llm_output_compiles()

### Community 12 - "cli.py"
Cohesion: 0.14
Nodes (8): approve(), compile(), eval(), _load_settings(), plan(), probe(), run(), serve()

## Knowledge Gaps
- **1 isolated node(s):** `skillvm`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 181 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SkillVM` connect `SkillVM` to `json`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `execute_ir()` (e.g. with `.node_map()` and `.cleanup_snapshot()`) actually correct?**
  _`execute_ir()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `skillvm` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `providers.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05327281414237936 - nodes in this community are weakly interconnected._
- **Why does `execute_ir()` connect `execute_ir` to `compiler.py`, `eval.py`, `json`, `pytest`, `server.py`, `cli.py`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `compile_skill()` (e.g. with `CompileStatus` and `Diagnostic`) actually correct?**
  _`compile_skill()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Should `compiler.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08997668997668998 - nodes in this community are weakly interconnected._