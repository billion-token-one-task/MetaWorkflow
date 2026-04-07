from meta_controller.core.domain_router import DomainRouter
from meta_controller.core.task_analyzer import TaskAnalyzer


def test_heavy_direct_answer_stays_on_claude() -> None:
    analyzer = TaskAnalyzer()
    router = DomainRouter()
    task = analyzer.analyze("Explain why dynamic workflow synthesis helps multi-agent systems.")
    route = router.route(task)
    assert task.domain == "direct_answer"
    assert route.mode == "direct_answer_mode"
    assert route.runtime_preference == "claude_sdk"
