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
        is_prototype_app = task_spec.domain == "coding" and "prototype-app" in task_spec.subdomains

        if task_spec.domain in {"coding", "mixed"} and not is_prototype_app and "test_runner" not in roles:
            issues.append("test coverage stage missing")
            suggested_edits.append("add test_runner node before final reviewer")
            score -= 0.2

        if is_prototype_app and "app_verifier" not in roles:
            issues.append("app verification stage missing")
            suggested_edits.append("add app_verifier node after fullstack_builder")
            score -= 0.2

        if is_prototype_app and "fullstack_builder" not in roles:
            issues.append("fullstack builder stage missing")
            suggested_edits.append("add fullstack_builder node for prototype app tasks")
            score -= 0.2

        app_verifier_succeeded = False
        if is_prototype_app:
            latest_runs = {}
            for run in worker_runs:
                previous = latest_runs.get(run.node_id)
                if previous is None or run.attempt_index >= previous.attempt_index:
                    latest_runs[run.node_id] = run
            verifier = latest_runs.get("app_verifier")
            if verifier is None:
                issues.append("app verifier did not run")
                suggested_edits.append("ensure app_verifier executes after fullstack_builder")
                score -= 0.2
            else:
                verifier_output = verifier.result.structured_output
                tests_passed = verifier_output.get("tests_passed")
                if tests_passed is not True:
                    issues.append("app verifier did not confirm runnable prototype")
                    suggested_edits.append("improve app startup verification and health checks")
                    score -= 0.2
                else:
                    app_verifier_succeeded = True

        if task_spec.domain in {"research", "mixed"} and "literature_scout" not in roles:
            issues.append("literature search stage missing")
            suggested_edits.append("add literature_scout node for evidence gathering")
            score -= 0.2

        if task_spec.needs_experiment and "experiment_designer" not in roles:
            issues.append("experiment design stage missing")
            suggested_edits.append("add experiment_designer node with benchmark rubric")
            score -= 0.2

        if task_spec.needs_multi_stage_validation and not roles.intersection({"reviewer", "research_reviewer", "judge", "app_verifier"}):
            issues.append("independent validation node missing")
            suggested_edits.append("insert judge or reviewer node near workflow tail")
            score -= 0.2

        latest_runs = {}
        for run in worker_runs:
            previous = latest_runs.get(run.node_id)
            if previous is None or run.attempt_index >= previous.attempt_index:
                latest_runs[run.node_id] = run

        for run in latest_runs.values():
            if is_prototype_app and app_verifier_succeeded and run.role in {"fullstack_builder"} and run.result.status != "success":
                continue
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
