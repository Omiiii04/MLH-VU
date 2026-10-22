"""Ground truth: the input file was intentionally missing.
Success = the runtime correctly failed (did NOT produce a spurious output file).
Never treat a missing ground-truth checker as success."""
from pathlib import Path

def check(workspace):
    # Source does not exist -> runtime must FAIL and output must NOT be produced.
    out = Path(workspace) / "out.json"
    # Correct behavior: output does not exist (read failed, nothing written).
    return not out.exists()
