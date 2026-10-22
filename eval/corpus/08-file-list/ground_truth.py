import json
from pathlib import Path

def check(workspace):
    p = Path(workspace) / "listing.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        return len(entries) >= 3
    except Exception:
        return False
