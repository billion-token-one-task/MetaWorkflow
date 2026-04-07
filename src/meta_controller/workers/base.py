from __future__ import annotations

from abc import ABC
from typing import Any, Dict, List, Optional

from meta_controller.core.models import TaskSpec, WorkerResult, WorkflowNode
from meta_controller.runtimes.base import WorkerRuntime


class RoleWorker(ABC):
    role = "generic"
    objective = "produce a structured contribution for the workflow"
    output_fields: List[str] = ["summary"]

    def __init__(self, node: WorkflowNode, runtime: WorkerRuntime) -> None:
        self.node = node
        self.runtime = runtime

    def run(
        self,
        task_spec: TaskSpec,
        upstream_results: Dict[str, Any],
        memory_refs: Optional[List[str]] = None,
    ) -> WorkerResult:
        task_input = self.build_task_input(
            task_spec=task_spec,
            upstream_results=upstream_results,
            memory_refs=memory_refs or [],
        )
        context = {
            "task_spec": task_spec.model_dump(mode="json"),
            "upstream_results": upstream_results,
            "memory_refs": memory_refs or [],
            "worker_role": self.node.role,
            "objective": self.objective,
        }
        return self.runtime.run_worker(
            worker_spec=self.node,
            task_input=task_input,
            context=context,
            output_fields=self.output_fields,
        )

    def build_task_input(
        self,
        task_spec: TaskSpec,
        upstream_results: Dict[str, Any],
        memory_refs: List[str],
    ) -> str:
        return (
            f"Role: {self.node.role}\n"
            f"Objective: {self.objective}\n"
            f"Task: {task_spec.user_text}\n"
            f"Project path: {task_spec.project_path or '(not provided)'}\n"
            f"Deliverables: {', '.join(task_spec.deliverables)}\n"
            f"Upstream: {upstream_results}\n"
            f"Memory refs: {memory_refs}\n"
            "Use the provided project path as the canonical workspace root. "
            "Do not guess alternate roots like /workspace unless you have verified them.\n"
        )


class GenericWorker(RoleWorker):
    output_fields = ["summary", "notes"]
