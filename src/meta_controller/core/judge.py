from __future__ import annotations

from meta_controller.core.models import EpisodeRecord, JudgeResult, TaskSpec, WorkflowSpec, WorkerRun


class Judge:
    def evaluate(
        self,
        task_spec: TaskSpec,
        workflow_spec: WorkflowSpec,
        worker_runs: list[WorkerRun],
    ) -> JudgeResult:
        issues: list[str] = []
        suggested_edits: list[str] = []
        score = 1.0
        roles = {node.role for node in workflow_spec.nodes}

        if task_spec.domain in {"coding", "mixed"} and "test_runner" not in roles:
            issues.append("test coverage stage missing")
            suggested_edits.append("add test_runner node before final reviewer")
            score -= 0.2

        if task_spec.domain in {"research", "mixed"} and "literature_scout" not in roles:
            issues.append("literature search stage missing")
            suggested_edits.append("add literature_scout node for evidence gathering")
            score -= 0.2

        if task_spec.needs_experiment and "experiment_designer" not in roles:
            issues.append("experiment design stage missing")
            suggested_edits.append("add experiment_designer node with benchmark rubric")
            score -= 0.2

        if task_spec.needs_multi_stage_validation and not roles.intersection({"reviewer", "research_reviewer", "judge"}):
            issues.append("independent validation node missing")
            suggested_edits.append("insert judge or reviewer node near workflow tail")
            score -= 0.2

        latest_runs = {}
        for run in worker_runs:
            previous = latest_runs.get(run.node_id)
            if previous is None or run.attempt_index >= previous.attempt_index:
                latest_runs[run.node_id] = run

        for run in latest_runs.values():
            if run.result.status != "success":
                issues.append(f"worker {run.node_id} failed with {run.result.failure_type or 'unknown_failure'}")
                suggested_edits.append(f"add retry or stronger model for {run.node_id}")
                score -= 0.15

        executed_node_ids = set(latest_runs)
        expected_node_ids = {node.id for node in workflow_spec.nodes}
        if executed_node_ids != expected_node_ids:
            issues.append("scheduler did not execute all workflow nodes")
            suggested_edits.append("inspect dependency handling in scheduler")
            score -= 0.2

        score = max(0.0, round(score, 2))
        verdict = "accept" if not issues else "revise" if score >= 0.5 else "fail"
        return JudgeResult(
            verdict=verdict,
            score=score,
            issues=issues,
            suggested_edits=suggested_edits,
        )

    def accept(self, episode: EpisodeRecord) -> bool:
        return episode.judge_result.get("verdict") == "accept"
