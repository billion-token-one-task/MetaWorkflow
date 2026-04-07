from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any, Dict, List, Optional

from meta_controller.core.models import WorkerResult, WorkflowNode


class WorkerRuntime(ABC):
    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run

    @abstractmethod
    def run_worker(
        self,
        worker_spec: WorkflowNode,
        task_input: str,
        context: Dict[str, Any],
        output_fields: List[str],
    ) -> WorkerResult:
        raise NotImplementedError

    def simulate_result(
        self,
        runtime_name: str,
        worker_spec: WorkflowNode,
        task_input: str,
        context: Dict[str, Any],
        output_fields: List[str],
    ) -> WorkerResult:
        structured_output = {}
        for field in output_fields:
            structured_output[field] = self._synthetic_value(field, worker_spec, context)
        return WorkerResult(
            status="success",
            summary=f"[dry-run:{runtime_name}] completed role {worker_spec.role}",
            artifacts=[f"{worker_spec.id}.json"],
            structured_output=structured_output,
            cost=0.0,
            token_usage={"input_tokens": min(len(task_input.split()) * 2, 4096), "output_tokens": 256},
            tool_trace=[
                {
                    "tool": "dry_run",
                    "runtime": runtime_name,
                    "node_id": worker_spec.id,
                    "role": worker_spec.role,
                    "permission_mode": worker_spec.permission_mode,
                }
            ],
            confidence=0.72,
            failure_type=None,
        )

    def build_runtime_prompt(
        self,
        worker_spec: WorkflowNode,
        task_input: str,
        output_fields: List[str],
    ) -> str:
        field_lines = "\n".join(
            f'- "{field}": {json.dumps(self._default_json_value(field, worker_spec), ensure_ascii=False)}'
            for field in output_fields
        )
        return (
            f"{task_input}\n"
            "\nReturn exactly one JSON object and nothing else.\n"
            "Use this structure:\n"
            "{\n"
            '  "summary": "short plain-text summary",\n'
            '  "artifacts": ["artifact names or file paths if any"],\n'
            '  "structured_output": {\n'
            f"{field_lines}\n"
            "  },\n"
            '  "confidence": 0.0\n'
            "}\n"
            "Rules:\n"
            "- Keep valid JSON.\n"
            "- Include every structured_output key exactly once.\n"
            "- Use arrays for list-like fields.\n"
            "- If a field is unknown, return an empty but type-correct placeholder.\n"
        )

    def build_system_prompt(self, worker_spec: WorkflowNode) -> str:
        return (
            f"You are the workflow worker '{worker_spec.role}'. "
            "Follow the task instructions carefully, use only approved tools, "
            "and return strictly valid JSON."
        )

    def parse_payload(
        self,
        raw_text: str,
        output_fields: List[str],
        worker_spec: WorkflowNode,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        candidates = [raw_text.strip(), self._extract_json_object(raw_text)]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                payload = parsed
                break

        if not payload:
            payload = {"summary": raw_text.strip(), "structured_output": {}, "artifacts": []}

        structured_output = payload.get("structured_output", {})
        if not isinstance(structured_output, dict):
            structured_output = {}
        for field in output_fields:
            if field in payload and field not in structured_output:
                structured_output[field] = payload[field]
            structured_output.setdefault(field, self._default_json_value(field, worker_spec))

        artifacts = payload.get("artifacts", [])
        if not isinstance(artifacts, list):
            artifacts = [str(artifacts)]

        confidence = payload.get("confidence")
        if not isinstance(confidence, (float, int)):
            confidence = 0.55
        confidence = max(0.0, min(1.0, float(confidence)))

        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = f"completed role {worker_spec.role}"

        return {
            "summary": summary.strip(),
            "artifacts": [str(item) for item in artifacts],
            "structured_output": structured_output,
            "confidence": confidence,
        }

    def build_success_result(
        self,
        payload: Dict[str, Any],
        tool_trace: List[Dict[str, Any]],
        cost: Optional[float],
        token_usage: Optional[Dict[str, int]],
    ) -> WorkerResult:
        return WorkerResult(
            status="success",
            summary=payload["summary"],
            artifacts=payload["artifacts"],
            structured_output=payload["structured_output"],
            cost=cost,
            token_usage=token_usage,
            tool_trace=tool_trace,
            confidence=payload["confidence"],
            failure_type=None,
        )

    def build_failure_result(
        self,
        runtime_name: str,
        worker_spec: WorkflowNode,
        failure_type: str,
        message: str,
        tool_trace: Optional[List[Dict[str, Any]]] = None,
    ) -> WorkerResult:
        compact_message = self._compact_message(message)
        return WorkerResult(
            status="failed",
            summary=f"[{runtime_name}] {compact_message}",
            artifacts=[],
            structured_output={},
            cost=None,
            token_usage=None,
            tool_trace=tool_trace or [],
            confidence=0.0,
            failure_type=failure_type,
        )

    def normalize_token_usage(self, usage: Optional[Dict[str, Any]]) -> Optional[Dict[str, int]]:
        if not usage:
            return None
        flattened: Dict[str, int] = {}
        for key, value in usage.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                flattened[key] = value
            elif isinstance(value, dict):
                for subkey, subvalue in value.items():
                    if isinstance(subvalue, int):
                        flattened[f"{key}_{subkey}"] = subvalue
        return flattened or None

    def _extract_json_object(self, raw_text: str) -> str:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return ""
        return raw_text[start : end + 1]

    def _compact_message(self, message: str, limit: int = 600) -> str:
        compact = " ".join(message.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3] + "..."

    def _default_json_value(self, field: str, worker_spec: WorkflowNode) -> Any:
        return self._synthetic_value(field, worker_spec, {})

    def _synthetic_value(self, field: str, worker_spec: WorkflowNode, context: Dict[str, Any]) -> Any:
        if field.endswith("_list") or field in {"issues", "risks", "baselines", "queries"}:
            return [f"{worker_spec.role}:{field}:draft"]
        if "files" in field:
            return ["/workspace/example.py"]
        if "passed" in field:
            return True
        if "score" in field:
            return 0.75
        if "recommendation" in field or field.startswith("acceptance_"):
            return "revise"
        if "plan" in field:
            return f"{worker_spec.role} generated a draft plan"
        return f"{worker_spec.role}:{field}"
