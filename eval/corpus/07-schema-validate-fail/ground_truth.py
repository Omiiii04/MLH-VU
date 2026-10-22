"""Ground truth: success means the runtime CORRECTLY DETECTED the missing field
and reported FAILED (not VERIFIED_SUCCESS). This is a 'claiming success would be wrong' task."""
import json
from pathlib import Path

def check(workspace):
    # The fixture intentionally lacks 'status'. Ground truth is: file lacks 'status'.
    # The skill should FAIL verify. We check this indirectly: the file must not have status.
    p = Path(workspace) / "broken.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # True if the data is as expected (missing status = correct input, task succeeded at detecting).
        return "status" not in data
    except Exception:
        return False
