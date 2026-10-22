"""conftest.py — redirect pytest tmp_path to local .pytest_tmp (Windows workaround)."""
import pytest
from pathlib import Path

def pytest_configure(config):
    # Avoid PermissionError on AppData\Local\Temp\pytest-of-* on some Windows setups
    basetemp = Path(__file__).parent.parent / ".pytest_tmp"
    basetemp.mkdir(exist_ok=True)
    config.option.basetemp = str(basetemp)
