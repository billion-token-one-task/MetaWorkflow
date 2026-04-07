from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
PYTHON = shutil.which("python3.12") or shutil.which("python3.11") or shutil.which("python3.10")


def main() -> int:
    if PYTHON is None:
        raise SystemExit("python3.10+ is required to bootstrap this project.")

    if not VENV_DIR.exists():
        subprocess.check_call([PYTHON, "-m", "venv", str(VENV_DIR)])

    python = str(VENV_DIR / "bin" / "python")
    subprocess.check_call([python, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    subprocess.check_call([python, "-m", "pip", "install", "-e", ".[dev]"], cwd=str(ROOT))
    print(f"Environment ready at {VENV_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
