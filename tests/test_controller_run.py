from meta_controller.controller import MetaController


def test_controller_runs_end_to_end(tmp_path) -> None:
    controller = MetaController(runs_dir=str(tmp_path / "runs"), dry_run=True)
    episode = controller.run(
        user_text=(
            "Create a research and coding prototype for a meta-controller with literature synthesis, "
            "workflow generation, code scaffold, and tests."
        ),
        project_path=str(tmp_path / "repo"),
    )
    assert episode.workflow_spec["template_name"] == "hybrid_research_to_code"
    assert episode.worker_runs
    assert episode.judge_result["verdict"] in {"accept", "revise"}
    assert (tmp_path / "runs" / "episodes" / f"{episode.episode_id}.json").exists()
