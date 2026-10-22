# Sandbox

> God node · 18 connections · `src/skillvm/tools.py`

**Community:** [eval.py](eval.py.md)

## Connections by Relation

### calls
- [execute_ir()](execute_ir_2.md) `EXTRACTED`
- [run_baseline_arm()](run_baseline_arm.md) `EXTRACTED`

### contains
- tools.py `EXTRACTED`

### imports
- [eval.py](eval.py.md) `EXTRACTED`
- runtime.py `EXTRACTED`

### method
- ._safe_path() `EXTRACTED`
- .__init__() `EXTRACTED`
- .snapshot() `EXTRACTED`
- .restore() `EXTRACTED`
- .cleanup_snapshot() `EXTRACTED`

### rationale_for
- Copy of the authorized workspace directory. Restore = re-copy snapshot. `EXTRACTED`

### references
- [execute_tool()](execute_tool.md) `EXTRACTED`
- _run_check() `EXTRACTED`

### uses
- test_symlink_escape_blocked() `INFERRED`
- test_path_traversal_blocked() `INFERRED`
- test_unauthorized_tool_blocked() `INFERRED`
- test_unknown_tool_blocked() `INFERRED`
- test_snapshot_restore() `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*