from meta_controller.core.domain_router import DomainRouter
from meta_controller.core.memory_manager import MemoryManager
from meta_controller.core.task_analyzer import TaskAnalyzer
from meta_controller.core.workflow_synthesizer import WorkflowSynthesizer


def test_prototype_app_task_routes_to_dedicated_workflow() -> None:
    task = (
        "Create a local log application with a frontend and backend, store logs locally, "
        "and provide run instructions."
    )
    analyzer = TaskAnalyzer()
    router = DomainRouter()
    synthesizer = WorkflowSynthesizer()
    spec = analyzer.analyze(task, project_path="/tmp/app")
    route = router.route(spec)
    workflow = synthesizer.synthesize(spec, route)
    assert "prototype-app" in spec.subdomains
    assert route.mode == "prototype_app_mode"
    assert route.template_name in {"prototype_app_builder_verify", "prototype_app_direct_builder_verify"}
    assert workflow.nodes[-1].role == "app_verifier"
    assert "fullstack_builder" in [node.role for node in workflow.nodes]


def test_workflow_index_written(tmp_path) -> None:
    manager = MemoryManager(base_dir=str(tmp_path / "runs"))
    from meta_controller.core.models import EpisodeRecord

    episode = EpisodeRecord(
        task_spec={"task_id": "task_1", "user_text": "build app", "domain": "coding", "subdomains": ["prototype-app"]},
        workflow_spec={"template_name": "prototype_app_builder_verify", "route_mode": "prototype_app_mode"},
        worker_runs=[],
        judge_result={"verdict": "accept"},
        final_artifacts=["README.md"],
        success=True,
    )
    manager.write_episode(episode)
    index_lines = manager.workflow_index_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(index_lines) == 1
    assert "prototype_app_builder_verify" in index_lines[0]
