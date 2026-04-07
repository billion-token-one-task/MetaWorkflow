from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
env = os.environ.copy()
env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

raise SystemExit(
    subprocess.call(
        [python, "-m", "pytest"],
        cwd=str(ROOT),
        env=env,
    )
)
