from meta_controller.core.judge import Judge
from meta_controller.core.memory_manager import MemoryManager
from meta_controller.core.models import TaskSpec, WorkerResult, WorkflowNode, WorkflowSpec
from meta_controller.core.scheduler import Scheduler


class FakeRuntime:
    def __init__(self, result: WorkerResult) -> None:
        self.result = result

    def run_worker(self, worker_spec, task_input, context, output_fields):
        return self.result


def test_scheduler_falls_back_from_openhands_to_claude(tmp_path) -> None:
    scheduler = Scheduler(
        memory_manager=MemoryManager(base_dir=str(tmp_path / "runs")),
        judge=Judge(),
        dry_run=True,
    )
    scheduler.runtimes = {
        "openhands": FakeRuntime(
            WorkerResult(
                status="failed",
                summary="openhands failed",
                structured_output={},
                failure_type="configuration_error",
            )
        ),
        "claude_sdk": FakeRuntime(
            WorkerResult(
                status="success",
                summary="claude recovered",
                structured_output={"issues": [], "approval_recommendation": "accept"},
                confidence=0.9,
            )
        ),
    }

    task = TaskSpec(user_text="Explain the system.", domain="direct_answer")
    workflow = WorkflowSpec(
        template_name="single_shot",
        route_mode="direct_answer_mode",
        nodes=[
            WorkflowNode(
                id="n1",
                role="reviewer",
                runtime="openhands",
                tools=["filesystem"],
                permission_mode="read_only",
                retry_limit=0,
            )
        ],
    )

    episode = scheduler.run(task_spec=task, workflow_spec=workflow)
    assert episode.success is True
    assert len(episode.worker_runs) == 2
    assert episode.worker_runs[0]["runtime"] == "openhands"
    assert episode.worker_runs[1]["runtime"] == "claude_sdk"
    assert episode.worker_runs[1]["fallback_from"] == "openhands"
