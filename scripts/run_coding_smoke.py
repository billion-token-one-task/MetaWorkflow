from __future__ import annotations

import json
import os
import argparse
import subprocess
import sys
import tempfile
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

from meta_controller.controller import MetaController


def _write_scratch_repo(repo_dir: Path) -> None:
    (repo_dir / "AGENTS.md").write_text(
        "Repository notes:\n"
        "- This is a temporary smoke-test repository.\n"
        "- Keep edits minimal and focused on the requested fix.\n"
        "- Temporary execution artifacts such as __pycache__/ and _run_tests.sh are not source changes.\n",
        encoding="utf-8",
    )
    (repo_dir / ".gitignore").write_text(
        "__pycache__/\n"
        "_run_tests.sh\n",
        encoding="utf-8",
    )
    (repo_dir / "calc.py").write_text(
        "def add_numbers(a: int, b: int) -> int:\n"
        "    raise NotImplementedError('implement me')\n",
        encoding="utf-8",
    )
    (repo_dir / "test_calc.py").write_text(
        "import unittest\n\n"
        "from calc import add_numbers\n\n\n"
        "class AddNumbersTest(unittest.TestCase):\n"
        "    def test_positive(self):\n"
        "        self.assertEqual(add_numbers(2, 3), 5)\n\n"
        "    def test_negative(self):\n"
        "        self.assertEqual(add_numbers(-2, 1), -1)\n\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    (repo_dir / "README.md").write_text(
        "Use this command for verification:\n"
        f"{VENV_PYTHON} -m unittest discover -v\n",
        encoding="utf-8",
    )
    subprocess.check_call(["git", "init", "-b", "main"], cwd=str(repo_dir))
    subprocess.check_call(["git", "config", "user.name", "Meta Controller Smoke"], cwd=str(repo_dir))
    subprocess.check_call(["git", "config", "user.email", "meta-controller-smoke@example.com"], cwd=str(repo_dir))
    subprocess.check_call(["git", "add", "."], cwd=str(repo_dir))
    subprocess.check_call(["git", "commit", "-m", "initial scratch repo"], cwd=str(repo_dir))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a live coding smoke task against a scratch repo.")
    parser.add_argument(
        "--heavy",
        action="store_true",
        help="Use the heavier coding route that may exercise OpenHands and runtime fallback.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    with tempfile.TemporaryDirectory(prefix="meta-controller-coding-smoke-") as tmp:
        repo_dir = Path(tmp)
        _write_scratch_repo(repo_dir)

        controller = MetaController(dry_run=False)
        task = (
            "Fix the failing `add_numbers` implementation in `calc.py`, keep edits minimal, "
            "maintain the existing unittest structure, and run "
            f"`{VENV_PYTHON} -m unittest discover -v` in this repository."
        )
        if args.heavy:
            task += " Treat this as a heavy dynamic workflow coding task."
        episode = controller.run(
            user_text=task,
            project_path=str(repo_dir),
            repo_summary="Tiny scratch Python repo for coding smoke validation.",
        )
        test_result = subprocess.run(
            [str(VENV_PYTHON), "-m", "unittest", "discover", "-v"],
            cwd=str(repo_dir),
            text=True,
            capture_output=True,
        )

        payload = {
            "mode": "heavy" if args.heavy else "default",
            "episode": controller.summarize_episode(episode),
            "worker_runs": episode.worker_runs,
            "calc_py": (repo_dir / "calc.py").read_text(encoding="utf-8"),
            "test_exit_code": test_result.returncode,
            "test_stdout": test_result.stdout,
            "test_stderr": test_result.stderr,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if (test_result.returncode == 0 and "return a + b" in payload["calc_py"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
