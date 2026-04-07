from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


Domain = Literal["research", "coding", "ops", "retrieval", "mixed", "direct_answer"]
Difficulty = Literal["trivial", "normal", "heavy", "long-horizon"]
RiskLevel = Literal["low", "medium", "high"]
PermissionMode = Literal["read_only", "edit", "execute"]
Verdict = Literal["accept", "revise", "fail"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(default_factory=lambda: new_id("task"))
    user_text: str
    domain: Domain
    subdomains: List[str] = Field(default_factory=list)
    difficulty: Difficulty = "normal"
    needs_tools: bool = True
    needs_repo: bool = False
    needs_web: bool = False
    needs_experiment: bool = False
    needs_multi_stage_validation: bool = False
    deliverables: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    budget_usd: float = 10.0
    max_runtime_minutes: int = 30
    risk_level: RiskLevel = "medium"
    recommended_mode: str = "dynamic_workflow"
    project_path: Optional[str] = None
    repo_summary: Optional[str] = None
    similar_memory_refs: List[str] = Field(default_factory=list)
    available_tools: List[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    template_name: str
    candidate_templates: List[str] = Field(default_factory=list)
    runtime_preference: str = "claude_sdk"
    reason: str


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: str
    runtime: str
    tools: List[str] = Field(default_factory=list)
    permission_mode: PermissionMode = "read_only"
    model_tier: str = "balanced"
    budget_tokens: int = 4_000
    timeout_seconds: int = 300
    retry_limit: int = 1
    description: Optional[str] = None


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    condition: Optional[str] = None


class RetryRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    max_retries: int
    trigger: str


class StopRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: str
    action: str


class WorkflowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(default_factory=lambda: new_id("wf"))
    template_name: str
    route_mode: str
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge] = Field(default_factory=list)
    loopbacks: List[WorkflowEdge] = Field(default_factory=list)
    retry_rules: List[RetryRule] = Field(default_factory=list)
    stop_rules: List[StopRule] = Field(default_factory=list)
    budget_policy: Dict[str, Any] = Field(default_factory=dict)


class WorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    summary: str
    artifacts: List[str] = Field(default_factory=list)
    structured_output: Dict[str, Any] = Field(default_factory=dict)
    cost: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None
    tool_trace: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float] = None
    failure_type: Optional[str] = None


class WorkerRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    role: str
    runtime: str
    requested_runtime: Optional[str] = None
    fallback_from: Optional[str] = None
    attempt_index: int = 1
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    duration_seconds: float = 0.0
    result: WorkerResult


class JudgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    score: float
    issues: List[str] = Field(default_factory=list)
    suggested_edits: List[str] = Field(default_factory=list)


class EpisodeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(default_factory=lambda: new_id("episode"))
    created_at: datetime = Field(default_factory=utc_now)
    task_spec: Dict[str, Any]
    workflow_spec: Dict[str, Any]
    worker_runs: List[Dict[str, Any]]
    judge_result: Dict[str, Any]
    final_artifacts: List[str] = Field(default_factory=list)
    success: bool
    routing_decision: Optional[Dict[str, Any]] = None
    scaffold_edits: List[Dict[str, Any]] = Field(default_factory=list)
