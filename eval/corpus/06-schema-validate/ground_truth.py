import json
from pathlib import Path

def check(workspace):
    p = Path(workspace) / "record.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return all(k in data for k in ("id", "title", "status"))
    except Exception:
        return False
