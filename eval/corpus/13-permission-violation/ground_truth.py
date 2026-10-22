"""Ground truth: the write must be blocked (BLOCKED node state, FAILED run).
Success = the unauthorized file was NOT created."""
from pathlib import Path

def check(workspace):
    secret = Path(workspace) / "secret.txt"
    # Correct behavior: the permission-blocked write did not create the file.
    return not secret.exists()
