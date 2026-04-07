from __future__ import annotations

import json
import os
import sys
import argparse
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
from meta_controller.core.judge import Judge
from meta_controller.core.memory_manager import MemoryManager
from meta_controller.core.models import TaskSpec, WorkflowSpec
from meta_controller.core.scheduler import Scheduler
from meta_controller.core.models import WorkflowNode
from meta_controller.runtimes.claude_runtime import ClaudeRuntime
from meta_controller.runtimes.openhands_runtime import OpenHandsRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run runtime smoke checks.")
    parser.add_argument(
        "--skip-openhands-direct",
        action="store_true",
        help="Skip the direct OpenHands probe and only validate Claude plus scheduler fallback.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_path = str(ROOT)

    claude = ClaudeRuntime(dry_run=False)
    openhands = OpenHandsRuntime(dry_run=False)

    review_node = WorkflowNode(
        id="smoke_reviewer",
        role="reviewer",
        runtime="claude_sdk",
        tools=["filesystem"],
        permission_mode="read_only",
        model_tier="balanced",
        budget_tokens=800,
        timeout_seconds=120,
        retry_limit=1,
    )
    openhands_node = review_node.model_copy(update={"id": "smoke_openhands", "runtime": "openhands"})

    results = {
        "claude_runtime": claude.run_worker(
            worker_spec=review_node,
            task_input="Explain in one sentence why dynamic workflows can outperform fixed workflows.",
            context={"task_spec": {"project_path": project_path}},
            output_fields=["issues", "approval_recommendation"],
        ).model_dump(mode="json"),
    }
    if args.skip_openhands_direct:
        results["openhands_runtime"] = {"status": "skipped"}
    else:
        results["openhands_runtime"] = openhands.run_worker(
            worker_spec=openhands_node,
            task_input="Explain in one sentence why dynamic workflows can outperform fixed workflows.",
            context={"task_spec": {"project_path": project_path}},
            output_fields=["issues", "approval_recommendation"],
        ).model_dump(mode="json")

    scheduler = Scheduler(
        memory_manager=MemoryManager(base_dir=str(ROOT / "runs" / "smoke")),
        judge=Judge(),
        dry_run=False,
    )
    fallback_episode = scheduler.run(
        task_spec=TaskSpec(
            user_text="Explain in one sentence why dynamic workflows can outperform fixed workflows.",
            domain="direct_answer",
            project_path=project_path,
        ),
        workflow_spec=WorkflowSpec(
            template_name="smoke_fallback",
            route_mode="direct_answer_mode",
            nodes=[
                WorkflowNode(
                    id="smoke_openhands_fallback",
                    role="generic_probe",
                    runtime="openhands",
                    tools=["filesystem"],
                    permission_mode="read_only",
                    model_tier="balanced",
                    budget_tokens=800,
                    timeout_seconds=120,
                    retry_limit=1,
                )
            ],
        ),
    )
    results["scheduler_fallback_demo"] = {
        "success": fallback_episode.success,
        "judge_result": fallback_episode.judge_result,
        "worker_runs": fallback_episode.worker_runs,
    }

    controller = MetaController(dry_run=False)
    episode = controller.run(
        user_text="Why can adaptive plans beat static plans?",
        project_path=project_path,
    )
    results["controller"] = controller.summarize_episode(episode)

    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
