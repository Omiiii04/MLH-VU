import json
from pathlib import Path

def check(workspace):
    p = Path(workspace) / "user_slim.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # Must have name and email but NOT password (privacy).
        return (
            isinstance(data, dict)
            and "name" in data
            and "email" in data
            and "password" not in data
        )
    except Exception:
        return False
