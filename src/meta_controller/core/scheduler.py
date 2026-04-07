from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from meta_controller.core.judge import Judge
from meta_controller.core.memory_manager import MemoryManager
from meta_controller.core.models import EpisodeRecord, TaskSpec, WorkerResult, WorkflowNode, WorkflowSpec, WorkerRun
from meta_controller.runtime_config import load_runtime_config
from meta_controller.runtimes.claude_runtime import ClaudeRuntime
from meta_controller.runtimes.openhands_runtime import OpenHandsRuntime
from meta_controller.workers import build_worker


class Scheduler:
    def __init__(self, memory_manager: MemoryManager, judge: Judge, dry_run: bool = True) -> None:
        self.memory_manager = memory_manager
        self.judge = judge
        self.runtime_config = load_runtime_config()
        self.runtimes = {
            "claude_sdk": ClaudeRuntime(dry_run=dry_run),
            "openhands": OpenHandsRuntime(dry_run=dry_run),
        }

    def run(self, task_spec: TaskSpec, workflow_spec: WorkflowSpec) -> EpisodeRecord:
        node_map = {node.id: node for node in workflow_spec.nodes}
        incoming = defaultdict(int)
        outgoing = defaultdict(list)
        predecessors = defaultdict(list)
        for edge in workflow_spec.edges:
            incoming[edge.target] += 1
            outgoing[edge.source].append(edge.target)
            predecessors[edge.target].append(edge.source)
        ready = deque(sorted(node.id for node in workflow_spec.nodes if incoming[node.id] == 0))
        results = {}
        worker_runs: list[WorkerRun] = []

        while ready:
            node_id = ready.popleft()
            node = node_map[node_id]
            upstream = {pred: results[pred].structured_output for pred in predecessors[node_id] if pred in results}
            result, node_runs = self._run_node(
                node=node,
                task_spec=task_spec,
                workflow_spec=workflow_spec,
                upstream=upstream,
            )
            results[node_id] = result
            worker_runs.extend(node_runs)
            for child in outgoing[node_id]:
                incoming[child] -= 1
                if incoming[child] == 0:
                    ready.append(child)

        judge_result = self.judge.evaluate(task_spec=task_spec, workflow_spec=workflow_spec, worker_runs=worker_runs)
        final_artifacts = [artifact for run in worker_runs for artifact in run.result.artifacts]
        return EpisodeRecord(
            task_spec=task_spec.model_dump(mode="json"),
            workflow_spec=workflow_spec.model_dump(mode="json"),
            worker_runs=[run.model_dump(mode="json") for run in worker_runs],
            judge_result=judge_result.model_dump(mode="json"),
            final_artifacts=final_artifacts,
            success=judge_result.verdict == "accept",
        )

    def _run_node(
        self,
        node: WorkflowNode,
        task_spec: TaskSpec,
        workflow_spec: WorkflowSpec,
        upstream: Dict[str, Dict],
    ) -> Tuple[WorkerResult, List[WorkerRun]]:
        worker_runs: List[WorkerRun] = []
        retry_budget = self._retry_budget(node=node, workflow_spec=workflow_spec)
        current_runtime_name = node.runtime
        fallback_used = False
        attempt_index = 0
        final_result: WorkerResult | None = None

        while True:
            attempt_index += 1
            runtime = self.runtimes[current_runtime_name]
            worker = build_worker(node=node, runtime=runtime)
            started = datetime.now(timezone.utc)
            result = worker.run(
                task_spec=task_spec,
                upstream_results=upstream,
                memory_refs=task_spec.similar_memory_refs,
            )
            completed = datetime.now(timezone.utc)
            worker_runs.append(
                WorkerRun(
                    node_id=node.id,
                    role=node.role,
                    runtime=current_runtime_name,
                    requested_runtime=node.runtime,
                    fallback_from=node.runtime if current_runtime_name != node.runtime else None,
                    attempt_index=attempt_index,
                    started_at=started,
                    completed_at=completed,
                    duration_seconds=max(0.0, (completed - started).total_seconds()),
                    result=result,
                )
            )
            final_result = result
            if result.status == "success":
                return result, worker_runs

            fallback_runtime = self._fallback_runtime(
                current_runtime=current_runtime_name,
                failure_type=result.failure_type,
                fallback_used=fallback_used,
            )
            if fallback_runtime is not None:
                current_runtime_name = fallback_runtime
                fallback_used = True
                continue

            if retry_budget <= 0:
                break
            retry_budget -= 1

        assert final_result is not None
        return final_result, worker_runs

    def _retry_budget(self, node: WorkflowNode, workflow_spec: WorkflowSpec) -> int:
        configured = node.retry_limit
        matching_rules = [rule.max_retries for rule in workflow_spec.retry_rules if rule.node_id == node.id]
        if matching_rules:
            configured = max(configured, max(matching_rules))
        return max(0, configured)

    def _fallback_runtime(
        self,
        current_runtime: str,
        failure_type: str | None,
        fallback_used: bool,
    ) -> str | None:
        if fallback_used:
            return None
        if not self.runtime_config.scheduler.enable_runtime_fallback:
            return None
        for rule in self.runtime_config.scheduler.runtime_fallbacks:
            if rule.matches(current_runtime=current_runtime, failure_type=failure_type):
                return rule.to_runtime
        return None
