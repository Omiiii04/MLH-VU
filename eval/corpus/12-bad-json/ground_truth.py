"""Ground truth: malformed JSON -> runtime must FAIL, not fabricate success."""
from pathlib import Path

def check(workspace):
    # The input is intentionally malformed. Correct outcome: runtime FAILED.
    # This checker always returns True because the correct behavior is to fail
    # the run (which the eval harness checks via run_rec.state != VERIFIED_SUCCESS).
    # We verify the input file was not modified (no write-back of garbage).
    p = Path(workspace) / "malformed.json"
    if not p.exists():
        return False
    content = p.read_text(encoding="utf-8")
    return "{not valid json!!!" in content  # untouched
