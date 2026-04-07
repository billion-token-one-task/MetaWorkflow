from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
RUNS_DIR = PROJECT_ROOT / "runs"
EPISODES_DIR = RUNS_DIR / "episodes"
TEMPLATES_DIR = PACKAGE_ROOT / "graphs" / "templates"
