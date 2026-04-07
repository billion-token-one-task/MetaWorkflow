from meta_controller.core.domain_router import DomainRouter
from meta_controller.core.task_analyzer import TaskAnalyzer
from meta_controller.core.workflow_synthesizer import WorkflowSynthesizer


def test_synthesizer_inserts_task_planner_for_heavy_coding() -> None:
    analyzer = TaskAnalyzer()
    router = DomainRouter()
    synthesizer = WorkflowSynthesizer()
    task = analyzer.analyze(
        user_text="Implement a dynamic workflow synthesizer in this repo, add tests, and support multi-agent planning.",
        project_path="/tmp/repo",
    )
    route = router.route(task)
    workflow = synthesizer.synthesize(task, route)
    roles = [node.role for node in workflow.nodes]
    assert route.mode == "coding_mode"
    assert "task_planner" in roles
    assert "reviewer" in roles
