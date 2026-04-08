from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
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


REAL_TASKS = [
    {
        "name": "log_app",
        "task": (
            "Create a usable local log application with a frontend and backend. "
            "Use a simple web stack, store logs locally, support creating log entries, listing logs, "
            "searching and filtering by keyword and level, and provide clear local run instructions. "
            "Build a real runnable prototype in this repository."
        ),
    },
    {
        "name": "todo_app",
        "task": (
            "Create a usable local todo application with a frontend and backend. "
            "Support creating tasks, toggling completion, filtering by status, and clear local run instructions. "
            "Build a real runnable prototype in this repository."
        ),
    },
    {
        "name": "notes_app",
        "task": (
            "Create a usable local notes application with a frontend and backend. "
            "Support creating notes, listing notes, searching by keyword, and clear local run instructions. "
            "Build a real runnable prototype in this repository."
        ),
    },
    {
        "name": "expense_app",
        "task": (
            "Create a usable local expense tracker application with a frontend and backend. "
            "Support creating expense entries, listing them, filtering by category, and clear local run instructions. "
            "Build a real runnable prototype in this repository."
        ),
    },
    {
        "name": "bookmark_app",
        "task": (
            "Create a usable local bookmark manager with a frontend and backend. "
            "Support adding bookmarks, listing them, searching by title or URL, and clear local run instructions. "
            "Build a real runnable prototype in this repository."
        ),
    },
    {
        "name": "inventory_app",
        "task": (
            "Create a usable local inventory tracker with a frontend and backend. "
            "Support adding inventory items, listing items, filtering by status, and clear local run instructions. "
            "Build a real runnable prototype in this repository."
        ),
    },
]


def prepare_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "AGENTS.md").write_text(
        "Repository notes:\n"
        "- This is a temporary real-task evaluation repository.\n"
        "- Build practical local-only prototypes.\n",
        encoding="utf-8",
    )
    (repo_dir / ".gitignore").write_text("__pycache__/\nnode_modules/\n.venv/\n", encoding="utf-8")
    subprocess.check_call(["git", "init", "-b", "main"], cwd=str(repo_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call(["git", "config", "user.name", "Meta Workflow Real Tasks"], cwd=str(repo_dir))
    subprocess.check_call(["git", "config", "user.email", "meta-workflow-real@example.com"], cwd=str(repo_dir))
    subprocess.check_call(["git", "add", "."], cwd=str(repo_dir))
    subprocess.check_call(["git", "commit", "-m", "init"], cwd=str(repo_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def batch_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def main() -> int:
    batch_dir = ROOT / "runs" / "real_tasks" / f"batch_{batch_slug()}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    results = []
    controller = MetaController(dry_run=False)
    for entry in REAL_TASKS:
        task_dir = batch_dir / entry["name"]
        repo_dir = task_dir / "repo"
        prepare_repo(repo_dir)
        episode = controller.run(
            user_text=entry["task"],
            project_path=str(repo_dir),
            repo_summary="Empty repository for prototype-app routing evaluation.",
        )
        files = [
            str(path.relative_to(repo_dir))
            for path in sorted(repo_dir.rglob("*"))
            if path.is_file() and ".git/" not in str(path)
        ]
        task_result = {
            "name": entry["name"],
            "repo": str(repo_dir),
            "summary": controller.summarize_episode(episode),
            "routing": episode.routing_decision,
            "workflow_template": episode.workflow_spec.get("template_name"),
            "workflow_roles": [node["role"] for node in episode.workflow_spec.get("nodes", [])],
            "worker_runs": episode.worker_runs,
            "files": files,
        }
        (task_dir / "result.json").write_text(json.dumps(task_result, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(task_result)

    batch_summary = {"batch_dir": str(batch_dir), "tasks": results}
    (batch_dir / "summary.json").write_text(json.dumps(batch_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(batch_summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
