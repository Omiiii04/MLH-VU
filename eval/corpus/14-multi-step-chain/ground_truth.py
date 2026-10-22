import json
from pathlib import Path

def check(workspace):
    p = Path(workspace) / "final.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return (
            isinstance(data, dict)
            and data.get("id") == 42
            and data.get("score") == 97
            and "noise" not in data
        )
    except Exception:
        return False
