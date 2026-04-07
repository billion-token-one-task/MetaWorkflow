from meta_controller.core.domain_router import DomainRouter
from meta_controller.core.task_analyzer import TaskAnalyzer
from meta_controller.core.workflow_synthesizer import WorkflowSynthesizer


def test_heavy_research_workflow_adds_parallel_analysis() -> None:
    analyzer = TaskAnalyzer()
    router = DomainRouter()
    synthesizer = WorkflowSynthesizer()
    task = analyzer.analyze(
        user_text=(
            "Create a multi-agent research prototype with literature review, paper analysis, "
            "novel hypothesis generation, experiment plan, and reviewer feedback loop."
        )
    )
    route = router.route(task)
    workflow = synthesizer.synthesize(task, route)
    roles = [node.role for node in workflow.nodes]
    assert route.mode == "research_mode"
    assert roles.count("paper_analyst") + roles.count("paper_analyst_parallel") >= 2
    assert "research_reviewer" in roles
