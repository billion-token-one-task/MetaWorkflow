from __future__ import annotations

import asyncio
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from meta_controller.core.models import WorkerResult, WorkflowNode
from meta_controller.runtimes.base import WorkerRuntime


class ClaudeRuntime(WorkerRuntime):
    KNOWN_TOOLS = ["Bash", "Read", "Write", "Edit", "MultiEdit", "LS", "Glob", "Grep", "WebSearch", "WebFetch"]

    def __init__(self, dry_run: bool = True) -> None:
        super().__init__(dry_run=dry_run)
        self.sdk_available = self._detect_sdk()
        self.model_override = os.environ.get("META_CONTROLLER_CLAUDE_MODEL")

    def run_worker(
        self,
        worker_spec: WorkflowNode,
        task_input: str,
        context: Dict[str, Any],
        output_fields: List[str],
    ) -> WorkerResult:
        if self.dry_run or not self.sdk_available:
            return self.simulate_result("claude_sdk", worker_spec, task_input, context, output_fields)
        try:
            return asyncio.run(
                self._run_live_query(
                    worker_spec=worker_spec,
                    task_input=task_input,
                    context=context,
                    output_fields=output_fields,
                )
            )
        except Exception as exc:
            return self.build_failure_result(
                runtime_name="claude_sdk",
                worker_spec=worker_spec,
                failure_type="runtime_error",
                message=str(exc),
            )

    def _detect_sdk(self) -> bool:
        try:
            import claude_code_sdk  # type: ignore  # noqa: F401
        except ImportError:
            return False
        return True

    async def _run_live_query(
        self,
        worker_spec: WorkflowNode,
        task_input: str,
        context: Dict[str, Any],
        output_fields: List[str],
    ) -> WorkerResult:
        from claude_code_sdk import ClaudeCodeOptions, query
        from claude_code_sdk.types import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

        prompt = self.build_runtime_prompt(worker_spec=worker_spec, task_input=task_input, output_fields=output_fields)
        allowed_tools = self._map_allowed_tools(worker_spec.tools, worker_spec.permission_mode)
        disallowed_tools = [tool for tool in self.KNOWN_TOOLS if tool not in allowed_tools]
        debug_stderr = io.StringIO()
        options = ClaudeCodeOptions(
            allowed_tools=allowed_tools,
            disallowed_tools=disallowed_tools,
            system_prompt=self.build_system_prompt(worker_spec),
            permission_mode=self._map_permission_mode(worker_spec.permission_mode, allowed_tools),
            cwd=self._resolve_cwd(context),
            max_turns=max(2, worker_spec.retry_limit + 2),
            model=self.model_override,
            include_partial_messages=False,
            debug_stderr=debug_stderr,
        )

        tool_trace: List[Dict[str, Any]] = []
        assistant_text: List[str] = []
        result_message: Optional[ResultMessage] = None

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            assistant_text.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            tool_trace.append(
                                {
                                    "tool": block.name,
                                    "input": block.input,
                                    "runtime": "claude_sdk",
                                    "node_id": worker_spec.id,
                                }
                            )
                elif isinstance(message, ResultMessage):
                    result_message = message
        except Exception as exc:
            debug_output = debug_stderr.getvalue().strip()
            return self.build_failure_result(
                runtime_name="claude_sdk",
                worker_spec=worker_spec,
                failure_type="runtime_error",
                message=debug_output or str(exc),
                tool_trace=tool_trace,
            )

        raw_text = ""
        if result_message and result_message.result:
            raw_text = result_message.result
        elif assistant_text:
            raw_text = "\n".join(assistant_text)

        if result_message and result_message.is_error:
            debug_output = debug_stderr.getvalue().strip()
            return self.build_failure_result(
                runtime_name="claude_sdk",
                worker_spec=worker_spec,
                failure_type="sdk_error",
                message=(raw_text or debug_output or "Claude SDK returned an error result."),
                tool_trace=tool_trace,
            )

        payload = self.parse_payload(raw_text=raw_text, output_fields=output_fields, worker_spec=worker_spec)
        token_usage = self.normalize_token_usage(result_message.usage if result_message else None)
        cost = result_message.total_cost_usd if result_message else None
        return self.build_success_result(
            payload=payload,
            tool_trace=tool_trace,
            cost=cost,
            token_usage=token_usage,
        )

    def _resolve_cwd(self, context: Dict[str, Any]) -> str:
        task_spec = context.get("task_spec", {})
        project_path = task_spec.get("project_path")
        if project_path:
            return str(Path(project_path))
        return os.getcwd()

    def _map_permission_mode(self, permission_mode: str, allowed_tools: List[str]) -> str:
        override = os.environ.get("META_CONTROLLER_CLAUDE_PERMISSION_MODE")
        if override:
            return override
        if permission_mode == "read_only":
            return "default"
        if permission_mode == "edit" and not any(tool.startswith("Bash") or tool == "Bash" for tool in allowed_tools):
            return "acceptEdits"
        return "bypassPermissions"

    def _map_allowed_tools(self, abstract_tools: List[str], permission_mode: str) -> List[str]:
        toolset: List[str] = []
        abstract = set(abstract_tools)

        if abstract.intersection({"filesystem", "read_only", "repo", "pdf"}):
            toolset.extend(["Read", "LS", "Glob", "Grep"])
        if "grep" in abstract:
            toolset.extend(["Grep", "Glob"])
        if abstract.intersection({"patch"}):
            toolset.extend(["Edit", "MultiEdit", "Write"])
        if permission_mode in {"edit", "execute"}:
            toolset.extend(["Read", "LS", "Glob", "Grep", "Edit", "MultiEdit", "Write"])
        if abstract.intersection({"web", "paper_search"}):
            toolset.extend(["WebSearch", "WebFetch"])
        if abstract.intersection({"bash", "python", "pytest"}):
            toolset.append("Bash")
        if not toolset:
            toolset.extend(["Read"])

        seen = set()
        ordered: List[str] = []
        for tool in toolset:
            if tool not in seen:
                ordered.append(tool)
                seen.add(tool)
        return ordered

    def build_system_prompt(self, worker_spec: WorkflowNode) -> str:
        base = super().build_system_prompt(worker_spec)
        bash_guidance = (
            " If you use Bash, never let the command terminate the session with a non-zero exit code "
            "during exploration or test inspection. Wrap risky commands with shell guards such as "
            "`|| true`, and still return the requested JSON even when you discover failures."
        )
        read_only_guidance = (
            " Prefer Read, LS, Glob, and Grep for repository inspection before considering Bash."
        )
        if worker_spec.permission_mode == "read_only":
            return base + read_only_guidance + bash_guidance
        return base + bash_guidance
