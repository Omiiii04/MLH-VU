# execute_ir()

> God node · 31 connections · `src/skillvm/runtime.py`

**Community:** [execute_ir](execute_ir.md)

## Connections by Relation

### calls
- [Sandbox](Sandbox.md) `EXTRACTED`
- [execute_tool()](execute_tool.md) `EXTRACTED`
- run_skillvm_arm() `EXTRACTED`
- run() `EXTRACTED`
- time `EXTRACTED`
- test_duplicate_idempotency_key_blocked() `EXTRACTED`
- test_verify_failure_no_verified_success() `EXTRACTED`
- test_forged_approval_rejected() `EXTRACTED`
- test_unauthorized_permission_blocked_at_runtime() `EXTRACTED`
- test_approval_blocks_without_token() `EXTRACTED`
- test_approval_with_token_succeeds() `EXTRACTED`
- test_success_run() `EXTRACTED`
- test_tool_failure_propagates() `EXTRACTED`
- test_prompt_injection_no_policy_effect() `EXTRACTED`
- DuplicateRunError `EXTRACTED`
- NodeRecord `EXTRACTED`
- _resolve_args() `EXTRACTED`
- .node_map() `INFERRED`
- uuid `EXTRACTED`
- _resolve_template() `EXTRACTED`
- *…and 1 more `calls` connection(s) not listed (lowest-degree first to go)*

### contains
- runtime.py `EXTRACTED`

### imports
- [eval.py](eval.py.md) `EXTRACTED`
- [cli.py](cli.py.md) `EXTRACTED`

### rationale_for
- Execute a compiled IR. Returns RunRecord with final state. `EXTRACTED`

### references
- Any `EXTRACTED`
- Exception `EXTRACTED`
- Path `EXTRACTED`

### uses
- WorkflowIR `INFERRED`
- EffectType `INFERRED`
- PermissionError_ `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*