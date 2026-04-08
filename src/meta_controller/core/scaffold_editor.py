from __future__ import annotations

from meta_controller.core.models import JudgeResult, TaskSpec, WorkflowSpec
from meta_controller.core.memory_manager import MemoryManager


class ScaffoldEditor:
    def __init__(self, memory_manager: MemoryManager) -> None:
        self.memory_manager = memory_manager

    def propose_updates(
        self,
        task_spec: TaskSpec,
        workflow_spec: WorkflowSpec,
        judge_result: dict,
    ) -> list[dict]:
        result = JudgeResult(**judge_result)
        edits: list[dict] = []
        for suggestion in result.suggested_edits:
            edits.append(
                {
                    "scope": self._scope_for_suggestion(suggestion),
                    "task_domain": task_spec.domain,
                    "workflow_template": workflow_spec.template_name,
                    "suggestion": suggestion,
                }
            )
        if task_spec.domain == "coding" and "prototype-app" in task_spec.subdomains and result.verdict != "accept":
            edits.append(
                {
                    "scope": "workflow_template",
                    "task_domain": task_spec.domain,
                    "workflow_template": workflow_spec.template_name,
                    "suggestion": "consider switching between prototype_app_builder_verify and prototype_app_direct_builder_verify based on recent successful runs",
                }
            )
        if edits:
            self.memory_manager.write_scaffold_edits(edits)
        return edits

    def _scope_for_suggestion(self, suggestion: str) -> str:
        if "node" in suggestion or "template" in suggestion:
            return "workflow_template"
        if "retry" in suggestion or "model" in suggestion:
            return "retry_policy"
        return "role_prompt"
