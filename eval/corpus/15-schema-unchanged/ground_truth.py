import json
from pathlib import Path

EXPECTED_KEYS = {"id", "name", "version"}

def check(workspace):
    p = Path(workspace) / "config.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return isinstance(data, dict) and set(data.keys()) == EXPECTED_KEYS
    except Exception:
        return False
