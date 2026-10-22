import hashlib
from pathlib import Path

EXPECTED = "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"

def check(workspace):
    p = Path(workspace) / "data.txt"
    if not p.exists():
        return False
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    return actual == EXPECTED
