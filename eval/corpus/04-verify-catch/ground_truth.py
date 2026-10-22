from pathlib import Path
def check(workspace):
    return (Path(workspace) / "result.txt").exists()
