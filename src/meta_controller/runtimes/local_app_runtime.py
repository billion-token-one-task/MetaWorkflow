from __future__ import annotations

from typing import Any, Dict, List

from meta_controller.core.models import WorkerResult, WorkflowNode
from meta_controller.runtimes.base import WorkerRuntime


class LocalAppRuntime(WorkerRuntime):
    def run_worker(
        self,
        worker_spec: WorkflowNode,
        task_input: str,
        context: Dict[str, Any],
        output_fields: List[str],
    ) -> WorkerResult:
        return self.build_failure_result(
            runtime_name="local_app",
            worker_spec=worker_spec,
            failure_type="unsupported_worker",
            message="local_app runtime should be used only through dedicated workers that override run().",
        )
