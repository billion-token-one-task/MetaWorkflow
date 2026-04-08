from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from meta_controller.config import TEMPLATES_DIR
from meta_controller.core.models import (
    RetryRule,
    RoutingDecision,
    StopRule,
    TaskSpec,
    WorkflowEdge,
    WorkflowNode,
    WorkflowSpec,
)


class WorkflowSynthesizer:
    def __init__(self, templates_dir: Optional[Path] = None, max_nodes: int = 12) -> None:
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.max_nodes = max_nodes
        self.templates = self._load_templates()

    def synthesize(self, task_spec: TaskSpec, routing_decision: RoutingDecision) -> WorkflowSpec:
        raw_template = deepcopy(self.templates[routing_decision.template_name])
        workflow = self._to_workflow_spec(raw_template=raw_template, route_mode=routing_decision.mode)
        self._apply_runtime_preferences(workflow, routing_decision.runtime_preference)
        self._apply_budget_policy(workflow, task_spec)
        self._refine_for_task(workflow, task_spec)
        self._ensure_validation(workflow, task_spec)
        self._validate_workflow(workflow)
        return workflow

    def _load_templates(self) -> Dict[str, Dict[str, Any]]:
        templates: Dict[str, Dict[str, Any]] = {}
        for path in sorted(self.templates_dir.glob("*.yaml")):
            with path.open("r", encoding="utf-8") as handle:
                templates[path.stem] = yaml.safe_load(handle)
        if not templates:
            raise RuntimeError(f"no workflow templates found in {self.templates_dir}")
        return templates

    def _to_workflow_spec(self, raw_template: Dict[str, Any], route_mode: str) -> WorkflowSpec:
        nodes = [WorkflowNode(**node) for node in raw_template.get("nodes", [])]
        edges = [WorkflowEdge(**edge) for edge in raw_template.get("edges", [])]
        loopbacks = [WorkflowEdge(**edge) for edge in raw_template.get("loopbacks", [])]
        retry_rules = [RetryRule(**rule) for rule in raw_template.get("retry_rules", [])]
        stop_rules = [StopRule(**rule) for rule in raw_template.get("stop_rules", [])]
        return WorkflowSpec(
            template_name=raw_template["template_name"],
            route_mode=route_mode,
            nodes=nodes,
            edges=edges,
            loopbacks=loopbacks,
            retry_rules=retry_rules,
            stop_rules=stop_rules,
            budget_policy=raw_template.get("budget_policy", {}),
        )

    def _apply_runtime_preferences(self, workflow: WorkflowSpec, runtime_preference: str) -> None:
        for node in workflow.nodes:
            if runtime_preference == "openhands" and node.permission_mode in {"edit", "execute"}:
                node.runtime = "openhands"
            elif node.runtime not in {"claude_sdk", "openhands"}:
                node.runtime = runtime_preference

    def _apply_budget_policy(self, workflow: WorkflowSpec, task_spec: TaskSpec) -> None:
        workflow.budget_policy["max_total_cost_usd"] = task_spec.budget_usd
        workflow.budget_policy["max_runtime_minutes"] = task_spec.max_runtime_minutes
        difficulty_multiplier = {
            "trivial": 0.75,
            "normal": 1.0,
            "heavy": 1.5,
            "long-horizon": 2.0,
        }[task_spec.difficulty]
        for node in workflow.nodes:
            node.budget_tokens = int(node.budget_tokens * difficulty_multiplier)
            node.timeout_seconds = int(node.timeout_seconds * difficulty_multiplier)

    def _refine_for_task(self, workflow: WorkflowSpec, task_spec: TaskSpec) -> None:
        roles = {node.role for node in workflow.nodes}
        is_prototype_app = task_spec.domain == "coding" and "prototype-app" in task_spec.subdomains

        if is_prototype_app:
            for node in workflow.nodes:
                if node.role == "fullstack_builder":
                    node.runtime = "claude_sdk"
                    node.model_tier = "strong"
                    node.permission_mode = "execute"
                if node.role == "app_verifier":
                    node.runtime = "local_app"
                    node.permission_mode = "execute"
            return

        if task_spec.domain == "coding" and task_spec.difficulty in {"heavy", "long-horizon"} and "task_planner" not in roles:
            self._insert_after(
                workflow=workflow,
                predecessor_role="repo_explorer",
                new_node=WorkflowNode(
                    id="task_planner",
                    role="task_planner",
                    runtime="claude_sdk",
                    tools=["filesystem", "grep", "git"],
                    permission_mode="read_only",
                    model_tier="balanced",
                    budget_tokens=4_000,
                    timeout_seconds=240,
                    retry_limit=1,
                    description="turn exploration notes into an execution plan",
                ),
            )

        if task_spec.domain == "research" and task_spec.difficulty in {"heavy", "long-horizon"}:
            self._clone_worker(
                workflow=workflow,
                existing_role="paper_analyst",
                new_node_id="paper_analyst_parallel",
            )

        if task_spec.domain == "mixed" and task_spec.needs_repo:
            self._ensure_role(
                workflow=workflow,
                node=WorkflowNode(
                    id="implementer",
                    role="implementer",
                    runtime="openhands" if task_spec.difficulty in {"heavy", "long-horizon"} else "claude_sdk",
                    tools=["filesystem", "git", "patch", "python"],
                    permission_mode="edit",
                    model_tier="strong",
                    budget_tokens=6_000,
                    timeout_seconds=600,
                    retry_limit=2,
                    description="convert validated research plan into prototype code scaffolding",
                ),
                after_role="experiment_designer",
            )

    def _ensure_validation(self, workflow: WorkflowSpec, task_spec: TaskSpec) -> None:
        if not task_spec.needs_multi_stage_validation:
            return
        review_roles = {"reviewer", "research_reviewer", "judge", "integration_checker", "app_verifier"}
        if any(node.role in review_roles for node in workflow.nodes):
            return
        terminal = workflow.nodes[-1]
        reviewer = WorkflowNode(
            id="judge",
            role="judge",
            runtime="claude_sdk",
            tools=["read_only"],
            permission_mode="read_only",
            model_tier="balanced",
            budget_tokens=3_000,
            timeout_seconds=180,
            retry_limit=1,
            description="independent validator for workflow outputs",
        )
        workflow.nodes.append(reviewer)
        workflow.edges.append(WorkflowEdge(source=terminal.id, target=reviewer.id))

    def _ensure_role(self, workflow: WorkflowSpec, node: WorkflowNode, after_role: str) -> None:
        if any(existing.role == node.role for existing in workflow.nodes):
            return
        self._insert_after(workflow=workflow, predecessor_role=after_role, new_node=node)

    def _insert_after(self, workflow: WorkflowSpec, predecessor_role: str, new_node: WorkflowNode) -> None:
        predecessor = next((node for node in workflow.nodes if node.role == predecessor_role), None)
        if predecessor is None:
            workflow.nodes.append(new_node)
            return
        outgoing = [edge for edge in workflow.edges if edge.source == predecessor.id]
        workflow.edges = [edge for edge in workflow.edges if edge.source != predecessor.id]
        workflow.nodes.append(new_node)
        workflow.edges.append(WorkflowEdge(source=predecessor.id, target=new_node.id))
        for edge in outgoing:
            workflow.edges.append(WorkflowEdge(source=new_node.id, target=edge.target, condition=edge.condition))

    def _clone_worker(self, workflow: WorkflowSpec, existing_role: str, new_node_id: str) -> None:
        source_node = next((node for node in workflow.nodes if node.role == existing_role), None)
        if source_node is None or any(node.id == new_node_id for node in workflow.nodes):
            return
        clone = source_node.model_copy()
        clone.id = new_node_id
        workflow.nodes.append(clone)
        incoming = [edge for edge in workflow.edges if edge.target == source_node.id]
        outgoing = [edge for edge in workflow.edges if edge.source == source_node.id]
        workflow.edges.extend(WorkflowEdge(source=edge.source, target=clone.id, condition=edge.condition) for edge in incoming)
        workflow.edges.extend(WorkflowEdge(source=clone.id, target=edge.target, condition=edge.condition) for edge in outgoing)

    def _validate_workflow(self, workflow: WorkflowSpec) -> None:
        if len(workflow.nodes) > self.max_nodes:
            raise ValueError(f"workflow exceeds max_nodes={self.max_nodes}")
        node_ids = {node.id for node in workflow.nodes}
        if len(node_ids) != len(workflow.nodes):
            raise ValueError("workflow contains duplicate node ids")
        if not workflow.nodes:
            raise ValueError("workflow requires at least one node")
        for edge in workflow.edges + workflow.loopbacks:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError("workflow edge references an unknown node")
