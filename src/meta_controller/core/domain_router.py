from __future__ import annotations

from meta_controller.core.models import RoutingDecision, TaskSpec


class DomainRouter:
    def route(self, task_spec: TaskSpec, route_hints: dict | None = None) -> RoutingDecision:
        is_prototype_app = task_spec.domain == "coding" and "prototype-app" in task_spec.subdomains
        route_hints = route_hints or {}

        if task_spec.domain == "direct_answer":
            template = "single_shot" if task_spec.difficulty in {"trivial", "normal"} else "planner_executor_reviewer"
            return RoutingDecision(
                mode="direct_answer_mode",
                template_name=template,
                candidate_templates=[template, "single_shot"],
                runtime_preference="claude_sdk",
                reason="answer-oriented task should stay on the lightweight Claude runtime path",
            )

        if is_prototype_app:
            candidate_templates = [
                "prototype_app_direct_builder_verify",
                "prototype_app_builder_verify",
                "repo_explore_implement_test_review",
            ]
            preferred_template = route_hints.get("preferred_template")
            template = preferred_template if preferred_template in candidate_templates else "prototype_app_builder_verify"
            if template == "prototype_app_builder_verify" and any(
                token in task_spec.user_text.lower() for token in ("log application", "todo application", "notes application", "local log", "local todo", "local notes")
            ):
                template = "prototype_app_direct_builder_verify"
            return RoutingDecision(
                mode="prototype_app_mode",
                template_name=template,
                candidate_templates=candidate_templates,
                runtime_preference="claude_sdk",
                reason="prototype app generation should adapt between direct builder and spec-driven builder flows based on task shape and prior outcomes",
            )

        if task_spec.domain == "coding":
            template = "repo_explore_implement_test_review"
            if "bug" in task_spec.user_text.lower() or "fix" in task_spec.user_text.lower():
                template = "issue_triage_fix_test"
            runtime = "openhands" if task_spec.difficulty in {"heavy", "long-horizon"} else "claude_sdk"
            return RoutingDecision(
                mode="coding_mode",
                template_name=template,
                candidate_templates=[
                    template,
                    "planner_executor_reviewer",
                    "repo_explore_implement_test_review",
                ],
                runtime_preference=runtime,
                reason="coding task with repo interaction and multi-stage validation",
            )

        if task_spec.domain == "research":
            template = "research_survey_synthesis"
            if task_spec.needs_experiment:
                template = "research_experiment_judge"
            return RoutingDecision(
                mode="research_mode",
                template_name=template,
                candidate_templates=[
                    template,
                    "research_survey_synthesis",
                    "benchmark_design_run_analyze",
                ],
                runtime_preference="claude_sdk",
                reason="research task requiring literature synthesis and structured critique",
            )

        if task_spec.domain == "mixed":
            runtime = "openhands" if task_spec.difficulty in {"heavy", "long-horizon"} else "claude_sdk"
            return RoutingDecision(
                mode="hybrid_mode",
                template_name="hybrid_research_to_code",
                candidate_templates=[
                    "hybrid_research_to_code",
                    "research_experiment_judge",
                    "repo_explore_implement_test_review",
                ],
                runtime_preference=runtime,
                reason="task mixes research synthesis with code prototype delivery",
            )

        if task_spec.domain == "retrieval":
            return RoutingDecision(
                mode="retrieval_mode",
                template_name="planner_executor_reviewer",
                candidate_templates=["planner_executor_reviewer", "single_shot"],
                runtime_preference="claude_sdk",
                reason="retrieval-heavy task benefits from a planner and reviewer loop",
            )

        return RoutingDecision(
            mode="ops_mode",
            template_name="planner_executor_reviewer",
            candidate_templates=["planner_executor_reviewer"],
            runtime_preference="openhands",
            reason="default operational path prefers explicit planning and validation",
        )
