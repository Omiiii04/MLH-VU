# execute_ir

> 40 nodes · cohesion 0.10

## Key Concepts

- **execute_ir()** (31 connections) — `src/skillvm/runtime.py`
- **runtime.py** (26 connections) — `src/skillvm/runtime.py`
- **test_runtime.py** (16 connections) — `tests/test_runtime.py`
- **RunState** (13 connections) — `src/skillvm/runtime.py`
- **_compile()** (8 connections) — `tests/test_runtime.py`
- **Path** (8 connections)
- **run()** (7 connections) — `src/skillvm/cli.py`
- **NodeState** (6 connections) — `src/skillvm/runtime.py`
- **test_duplicate_idempotency_key_blocked()** (6 connections) — `tests/test_runtime.py`
- **test_verify_failure_no_verified_success()** (6 connections) — `tests/test_runtime.py`
- **test_forged_approval_rejected()** (6 connections) — `tests/test_security.py`
- **test_approval_blocks_without_token()** (5 connections) — `tests/test_runtime.py`
- **test_approval_with_token_succeeds()** (5 connections) — `tests/test_runtime.py`
- **test_illegal_state_transition_raises()** (5 connections) — `tests/test_runtime.py`
- **test_success_run()** (5 connections) — `tests/test_runtime.py`
- **test_tool_failure_propagates()** (5 connections) — `tests/test_runtime.py`
- **DuplicateRunError** (4 connections) — `src/skillvm/runtime.py`
- **NodeRecord** (4 connections) — `src/skillvm/runtime.py`
- **_resolve_args()** (4 connections) — `src/skillvm/runtime.py`
- **test_snapshot_restore()** (4 connections) — `tests/test_runtime.py`
- **.transition()** (3 connections) — `src/skillvm/runtime.py`
- **Enum** (3 connections)
- **_resolve_template()** (3 connections) — `src/skillvm/runtime.py`
- **workspace()** (3 connections) — `tests/test_runtime.py`
- **uuid** (3 connections)
- *... and 15 more nodes in this community*

## Relationships

- [eval.py](eval.py.md) (16 shared connections)
- [test_security.py](test_security.py.md) (10 shared connections)
- [compiler.py](compiler.py.md) (9 shared connections)
- [cli.py](cli.py.md) (8 shared connections)
- [compile_skill](compile_skill.md) (2 shared connections)
- [providers.py](providers.py.md) (1 shared connections)

## Source Files

- `src/skillvm/cli.py`
- `src/skillvm/runtime.py`
- `tests/test_runtime.py`
- `tests/test_security.py`

## Audit Trail

- EXTRACTED: 108 (85%)
- INFERRED: 19 (15%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*