import json
from pathlib import Path

def check(workspace):
    p = Path(workspace) / "output.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return isinstance(data, dict) and "value" in data
    except Exception:
        return False
