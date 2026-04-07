from meta_controller.core.task_analyzer import TaskAnalyzer


def test_task_analyzer_identifies_hybrid_task() -> None:
    analyzer = TaskAnalyzer()
    task = analyzer.analyze(
        user_text=(
            "Build a multi-agent research prototype with literature review, experiment plan, "
            "workflow graph, code scaffold, and tests for a repository."
        ),
        project_path="/tmp/repo",
    )
    assert task.domain == "mixed"
    assert task.difficulty in {"heavy", "long-horizon"}
    assert task.needs_repo is True
    assert task.needs_web is True
    assert "prototype_code" in task.deliverables
    assert "workflow_spec" in task.deliverables
