# Graph Report - MLH-VU  (2026-10-22)

## Corpus Check
- 75 files · ~27,403 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .example 1)

## Summary
- 573 nodes · 1418 edges · 41 communities (16 shown, 25 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 216 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bd7ba6c4`
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
- Settings
- 13-path-traversal/skill.md
- server.py
- ProviderError
- ProviderExhaustedError

## God Nodes (most connected - your core abstractions)
1. `execute_ir()` - 48 edges
2. `compile_skill()` - 39 edges
3. `FakeProvider` - 38 edges
4. `compile_with_llm()` - 33 edges
5. `ProviderError` - 30 edges
6. `RunState` - 26 edges
7. `Settings` - 26 edges
8. `ProviderManager` - 24 edges
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
- `HTTP API Reference` --references--> `workspace()`  [INFERRED]
  README.md → tests/test_runtime.py

## Import Cycles
- None detected.

## Communities (41 total, 25 thin omitted)

### Community 0 - "FakeProvider"
Cohesion: 0.12
Nodes (18): FakeProvider, _mgr(), test_actual_rate_limit_error_maps_correctly(), test_all_fail_raises_is_subclass_of_provider_error(), test_all_fail_raises_provider_exhausted(), test_attempt_records_contain_provider_and_outcome(), test_auth_error_outcome(), test_auth_error_recorded_no_retry() (+10 more)

### Community 1 - "compiler.py"
Cohesion: 0.09
Nodes (43): _build_nodes(), _check_postconditions(), compile_skill(), _has_cycle(), dfs(), _validate_ir(), CompileStatus, d() (+35 more)

### Community 2 - "execute_ir"
Cohesion: 0.05
Nodes (43): Security and Sandboxing, run(), DuplicateRunError, execute_ir(), NodeRecord, NodeState, _resolve_args(), _resolve_template() (+35 more)

### Community 3 - "eval.py"
Cohesion: 0.21
Nodes (12): _infer_tool(), _path_from_step(), _aggregate(), _ground_truth(), _load_fixture(), run_baseline_arm(), run_eval(), run_llm_baseline_arm() (+4 more)

### Community 4 - "SkillVM"
Cohesion: 0.06
Nodes (29): 1. Compile a Skill to Workflow IR, 2. Inspect the Execution Plan, 3. Execute a Workflow, 4. Safe Human-in-the-Loop Approval & Resumption, 5. Probe Configured Providers, 6. Run the Evaluation Harness, Architecture, Command-Line Interface (CLI) (+21 more)

### Community 5 - "json"
Cohesion: 0.20
Nodes (7): check(), check(), check(), check(), check(), check(), check()

### Community 6 - "ProviderManager"
Cohesion: 0.14
Nodes (7): build_manager(), ProviderManager, test_ground_truth_unknown_when_missing(), test_isolated_workspace_cleanup(), test_llm_baseline_arm_multi_turn_tool_use(), test_llm_baseline_detects_false_success_on_adversarial_task(), test_run_eval_accurately_reports_missing_credentials()

### Community 7 - "pytest"
Cohesion: 0.07
Nodes (28): _resolve_workspace(), _blocked_or_failed(), _make_settings(), test_absolute_path_rejected(), test_client_cannot_override_root_via_workspace(), test_dot_workspace_rejected(), test_drive_absolute_path_rejected(), test_empty_workspace_rejected() (+20 more)

### Community 9 - "test_server.py"
Cohesion: 0.07
Nodes (12): _b(), _f(), _i(), load_settings(), settings(), _make_root_with_workspace(), test_absolute_path_workspace_rejected(), test_compile_llm_false_uses_deterministic() (+4 more)

### Community 10 - "compile_with_llm"
Cohesion: 0.13
Nodes (16): _build_prompt(), compile_with_llm(), _has_gemini(), _has_lmstudio(), _has_openrouter(), test_live_fallback_chain(), test_live_gemini_compile(), test_live_lmstudio_compile() (+8 more)

### Community 11 - "redact.py"
Cohesion: 0.19
Nodes (9): check(), ProviderAttempt, ProviderResult, SchemaInvalidError, excerpt(), prompt_hash(), redact_obj(), redact_text() (+1 more)

### Community 12 - "cli.py"
Cohesion: 0.15
Nodes (7): approve(), compile(), eval(), _load_settings(), plan(), probe(), serve()

### Community 33 - "Settings"
Cohesion: 0.11
Nodes (6): Settings, BaseProvider, GeminiProvider, OpenAICompatProvider, test_gemini_timeout_sdk_transport_enforcement(), test_lmstudio_model_and_key_are_separate()

### Community 35 - "server.py"
Cohesion: 0.16
Nodes (13): approve_run(), ApproveRequest, compile_endpoint(), CompileRequest, CompileResponse, create_run(), get_run(), health() (+5 more)

### Community 36 - "ProviderError"
Cohesion: 0.42
Nodes (5): AuthError, _classify_genai_error(), ModelNotFoundError, ProviderError, RateLimitError

### Community 37 - "ProviderExhaustedError"
Cohesion: 0.18
Nodes (6): ProviderExhaustedError, test_fallback_disabled_stops_at_first_failure(), test_generate_containing_word_not_rate_limit(), generate(), test_overall_deadline_stops_execution(), generate()

## Knowledge Gaps
- **1 isolated node(s):** `skillvm`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 216 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `execute_ir()` connect `execute_ir` to `compiler.py`, `eval.py`, `server.py`, `pytest`, `cli.py`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `execute_ir()` (e.g. with `.node_map()` and `PermissionError_`) actually correct?**
  _`execute_ir()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `skillvm` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FakeProvider` be split into smaller, more focused modules?**
  _Cohesion score 0.12298387096774194 - nodes in this community are weakly interconnected._
- **Why does `Security and Sandboxing` connect `execute_ir` to `compiler.py`, `SkillVM`, `pytest`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `compile_skill()` (e.g. with `CompileStatus` and `Diagnostic`) actually correct?**
  _`compile_skill()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `compiler.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0865424430641822 - nodes in this community are weakly interconnected._