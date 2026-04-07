from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from meta_controller.core.models import WorkerResult, WorkflowNode
from meta_controller.runtimes.base import WorkerRuntime
from meta_controller.runtime_config import load_runtime_config


class OpenHandsRuntime(WorkerRuntime):
    def __init__(self, dry_run: bool = True) -> None:
        super().__init__(dry_run=dry_run)
        self.sdk_available = self._detect_sdk()
        self.runtime_config = load_runtime_config()

    def run_worker(
        self,
        worker_spec: WorkflowNode,
        task_input: str,
        context: Dict[str, Any],
        output_fields: List[str],
    ) -> WorkerResult:
        if self.dry_run or not self.sdk_available:
            return self.simulate_result("openhands", worker_spec, task_input, context, output_fields)
        config_error = self._validate_live_config()
        if config_error:
            return self.build_failure_result(
                runtime_name="openhands",
                worker_spec=worker_spec,
                failure_type="configuration_error",
                message=config_error,
            )
        try:
            return self._run_live(worker_spec=worker_spec, task_input=task_input, context=context, output_fields=output_fields)
        except Exception as exc:
            return self.build_failure_result(
                runtime_name="openhands",
                worker_spec=worker_spec,
                failure_type="runtime_error",
                message=str(exc),
            )

    def _detect_sdk(self) -> bool:
        try:
            import openhands  # type: ignore  # noqa: F401
        except ImportError:
            return False
        return True

    def _run_live(
        self,
        worker_spec: WorkflowNode,
        task_input: str,
        context: Dict[str, Any],
        output_fields: List[str],
    ) -> WorkerResult:
        os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

        from openhands.sdk import Agent, Conversation, LLM, Tool
        from openhands.sdk.conversation.response_utils import get_agent_final_response
        from openhands.sdk.event import ActionEvent, ObservationEvent

        prompt = self.build_runtime_prompt(worker_spec=worker_spec, task_input=task_input, output_fields=output_fields)
        llm = LLM(
            model=self._resolve_model(worker_spec),
            api_key=self._resolve_api_key(),
            base_url=self._resolve_base_url(),
            max_output_tokens=self._resolve_max_output_tokens(worker_spec),
            reasoning_effort=self._map_reasoning_effort(worker_spec.model_tier),
            stream=False,
        )
        self._apply_provider_compat(llm)
        agent = Agent(
            llm=llm,
            tools=self._resolve_tools(worker_spec),
            tool_concurrency_limit=1,
        )
        conversation = Conversation(
            agent=agent,
            workspace=self._resolve_workspace(context),
            delete_on_close=True,
            max_iteration_per_run=max(8, worker_spec.retry_limit * 4 + 8),
        )
        try:
            conversation.send_message(prompt)
            conversation.run()
            events = list(conversation.state.events)
            response_text = get_agent_final_response(events)
            payload = self.parse_payload(raw_text=response_text, output_fields=output_fields, worker_spec=worker_spec)
            tool_trace: List[Dict[str, Any]] = []
            for event in events:
                if isinstance(event, ActionEvent):
                    tool_trace.append(
                        {
                            "tool": event.tool_name,
                            "input": getattr(event.action, "model_dump", lambda **_: {})(),
                            "runtime": "openhands",
                            "node_id": worker_spec.id,
                        }
                    )
                elif isinstance(event, ObservationEvent):
                    tool_trace.append(
                        {
                            "tool": event.tool_name,
                            "observation": str(getattr(event, "observation", ""))[:500],
                            "runtime": "openhands",
                            "node_id": worker_spec.id,
                        }
                    )

            metrics = conversation.conversation_stats.get_combined_metrics()
            token_usage = None
            if metrics.accumulated_token_usage is not None:
                token_usage = {
                    "input_tokens": int(metrics.accumulated_token_usage.prompt_tokens),
                    "output_tokens": int(metrics.accumulated_token_usage.completion_tokens),
                    "reasoning_tokens": int(metrics.accumulated_token_usage.reasoning_tokens),
                }
            return self.build_success_result(
                payload=payload,
                tool_trace=tool_trace,
                cost=metrics.accumulated_cost,
                token_usage=token_usage,
            )
        finally:
            conversation.close()

    def _validate_live_config(self) -> Optional[str]:
        if not self._resolve_model(None):
            return "Set OPENHANDS_MODEL or LLM_MODEL to enable live OpenHands execution."
        if self._resolve_api_key() is None and not self._resolve_base_url():
            return (
                "Set LLM_API_KEY or a provider API key such as ANTHROPIC_API_KEY/OPENAI_API_KEY, "
                "or point OPENHANDS_BASE_URL to a hosted inference endpoint."
            )
        return None

    def _resolve_model(self, worker_spec: Optional[WorkflowNode]) -> Optional[str]:
        if worker_spec is not None:
            configured = self.runtime_config.model_for_role(worker_spec.role)
            if configured:
                return configured
        return os.environ.get("OPENHANDS_MODEL") or os.environ.get("LLM_MODEL") or self.runtime_config.model

    def _resolve_api_key(self) -> Optional[str]:
        for key in ("LLM_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
            value = os.environ.get(key)
            if value:
                return value
        provider = self.runtime_config.provider()
        if provider and provider.api_key:
            return provider.api_key
        return None

    def _resolve_base_url(self) -> Optional[str]:
        return os.environ.get("OPENHANDS_BASE_URL") or os.environ.get("LLM_BASE_URL") or (
            self.runtime_config.provider().base_url if self.runtime_config.provider() else None
        )

    def _resolve_workspace(self, context: Dict[str, Any]) -> str:
        task_spec = context.get("task_spec", {})
        return str(Path(task_spec.get("project_path") or os.getcwd()))

    def _resolve_tools(self, worker_spec: WorkflowNode) -> List[Any]:
        from openhands.sdk import Tool
        from openhands.tools import FileEditorTool, TaskTrackerTool, TerminalTool, register_default_tools

        tools: List[Any] = []
        abstract = set(worker_spec.tools)
        register_default_tools(enable_browser=False)

        if worker_spec.permission_mode in {"edit", "execute"} or abstract.intersection({"bash", "python", "pytest", "git", "patch"}):
            tools.append(Tool(name=TerminalTool.name))
            tools.append(Tool(name=FileEditorTool.name))
        else:
            tools.append(Tool(name=TerminalTool.name))

        tools.append(Tool(name=TaskTrackerTool.name))
        return tools

    def _map_reasoning_effort(self, model_tier: str) -> str:
        if self.runtime_config.model_reasoning_effort:
            return self.runtime_config.model_reasoning_effort
        if model_tier == "fast":
            return "low"
        if model_tier == "strong":
            return "high"
        return "medium"

    def _resolve_max_output_tokens(self, worker_spec: WorkflowNode) -> Optional[int]:
        provider = self.runtime_config.provider()
        if provider and provider.wire_api == "responses":
            return None
        return min(worker_spec.budget_tokens, 8192)

    def _apply_provider_compat(self, llm: Any) -> None:
        provider = self.runtime_config.provider()
        if provider and provider.wire_api == "responses":
            llm._is_subscription = True
            llm.max_output_tokens = None
            llm.temperature = None
