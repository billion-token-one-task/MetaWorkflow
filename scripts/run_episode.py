from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
if (
    VENV_PYTHON.exists()
    and Path(sys.executable).resolve() != VENV_PYTHON.resolve()
    and not os.environ.get("META_CONTROLLER_SKIP_VENV_REEXEC")
):
    env = dict(os.environ)
    env["META_CONTROLLER_SKIP_VENV_REEXEC"] = "1"
    os.execve(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]], env)

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meta_controller.app.main import main


if __name__ == "__main__":
    raise SystemExit(main())
