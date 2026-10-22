import json
from pathlib import Path

def check(workspace):
    p = Path(workspace) / "merged.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # patch must override base for key 'b'; 'c' must appear; 'a' must be preserved.
        return (
            isinstance(data, dict)
            and data.get("a") == 1
            and data.get("b") == 99
            and data.get("c") == 3
        )
    except Exception:
        return False
