from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Optional

from meta_controller.core.models import TaskSpec


class TaskAnalyzer:
    CODING_TERMS = {
        "repo",
        "repository",
        "file",
        "files",
        "bug",
        "fix",
        "implement",
        "feature",
        "refactor",
        "test",
        "tests",
        "module",
        "class",
        "function",
        "code",
        "patch",
        "api",
        "sdk",
    }
    RESEARCH_TERMS = {
        "paper",
        "papers",
        "literature",
        "survey",
        "hypothesis",
        "experiment",
        "ablation",
        "benchmark",
        "novelty",
        "dataset",
        "arxiv",
        "citation",
        "research",
        "reviewer",
        "baseline",
    }
    OPS_TERMS = {
        "deploy",
        "deployment",
        "infra",
        "incident",
        "service",
        "kubernetes",
        "docker",
        "production",
        "monitor",
        "ops",
    }
    RETRIEVAL_TERMS = {
        "search",
        "retrieve",
        "lookup",
        "compare",
        "find",
        "gather",
        "collect",
    }

    DELIVERABLE_HINTS = {
        "report": {"report", "summary", "survey"},
        "experiment_plan": {"experiment plan", "ablation", "baseline", "benchmark"},
        "prototype_code": {"prototype", "code skeleton", "scaffold"},
        "patch": {"patch", "fix", "implement"},
        "tests": {"test", "tests"},
        "workflow_spec": {"workflow", "dag", "graph"},
    }

    def analyze(
        self,
        user_text: str,
        project_path: Optional[str] = None,
        repo_summary: Optional[str] = None,
        available_tools: Optional[List[str]] = None,
        similar_memories: Optional[List[Dict[str, str]]] = None,
    ) -> TaskSpec:
        text = user_text.lower()
        counts = self._count_signals(text)
        domain = self._choose_domain(counts)
        deliverables = self._extract_deliverables(text=text, domain=domain)
        difficulty = self._estimate_difficulty(text=text, domain=domain, deliverables=deliverables)
        needs_repo = bool(project_path) or counts["coding"] > 0 or "repo" in text or "仓库" in user_text
        needs_web = counts["research"] > 0 or any(token in text for token in ("web", "browse", "literature", "paper"))
        needs_experiment = counts["research"] > 0 and any(
            token in text for token in ("experiment", "benchmark", "ablation", "prototype")
        )
        needs_tools = any([needs_repo, needs_web, needs_experiment, counts["ops"] > 0, counts["retrieval"] > 0])
        needs_validation = difficulty in {"heavy", "long-horizon"} or domain in {"coding", "research", "mixed"}
        subdomains = self._extract_subdomains(text)
        risk_level = self._estimate_risk(text=text, domain=domain, difficulty=difficulty)
        budget_usd = {"trivial": 3.0, "normal": 10.0, "heavy": 25.0, "long-horizon": 40.0}[difficulty]
        max_runtime_minutes = {"trivial": 10, "normal": 25, "heavy": 60, "long-horizon": 120}[difficulty]
        success_criteria = self._build_success_criteria(domain=domain, deliverables=deliverables, needs_validation=needs_validation)
        similar_refs = [entry["episode_id"] for entry in (similar_memories or []) if "episode_id" in entry]
        return TaskSpec(
            user_text=user_text,
            domain=domain,
            subdomains=subdomains,
            difficulty=difficulty,
            needs_tools=needs_tools,
            needs_repo=needs_repo,
            needs_web=needs_web,
            needs_experiment=needs_experiment,
            needs_multi_stage_validation=needs_validation,
            deliverables=deliverables,
            success_criteria=success_criteria,
            budget_usd=budget_usd,
            max_runtime_minutes=max_runtime_minutes,
            risk_level=risk_level,
            project_path=project_path,
            repo_summary=repo_summary,
            similar_memory_refs=similar_refs,
            available_tools=available_tools or [],
        )

    def _count_signals(self, text: str) -> Counter:
        counts: Counter[str] = Counter()
        counts["coding"] = sum(term in text for term in self.CODING_TERMS)
        counts["research"] = sum(term in text for term in self.RESEARCH_TERMS)
        counts["ops"] = sum(term in text for term in self.OPS_TERMS)
        counts["retrieval"] = sum(term in text for term in self.RETRIEVAL_TERMS)
        return counts

    def _choose_domain(self, counts: Counter) -> str:
        coding = counts["coding"]
        research = counts["research"]
        ops = counts["ops"]
        retrieval = counts["retrieval"]
        if coding > 0 and research > 0:
            return "mixed"
        if research >= max(coding, ops, retrieval) and research > 0:
            return "research"
        if coding >= max(research, ops, retrieval) and coding > 0:
            return "coding"
        if ops > 0:
            return "ops"
        if retrieval > 0:
            return "retrieval"
        return "direct_answer"

    def _extract_deliverables(self, text: str, domain: str) -> List[str]:
        deliverables: List[str] = []
        for name, hints in self.DELIVERABLE_HINTS.items():
            if any(hint in text for hint in hints):
                deliverables.append(name)
        if domain == "research":
            deliverables.extend(item for item in ["report", "experiment_plan"] if item not in deliverables)
        if domain == "coding":
            deliverables.extend(item for item in ["patch", "tests"] if item not in deliverables)
        if domain == "mixed":
            for item in ["report", "experiment_plan", "prototype_code", "workflow_spec"]:
                if item not in deliverables:
                    deliverables.append(item)
        if not deliverables:
            deliverables = ["answer"] if domain == "direct_answer" else ["report"]
        return deliverables

    def _estimate_difficulty(self, text: str, domain: str, deliverables: List[str]) -> str:
        heavy_markers = [
            "end-to-end",
            "dynamic workflow",
            "prototype",
            "multi-agent",
            "闭环",
            "并行",
            "week",
            "完整方案",
            "系统",
        ]
        long_markers = ["long-horizon", "cloud", "persistent memory", "dashboard", "benchmark harness"]
        if any(marker in text for marker in long_markers):
            return "long-horizon"
        if any(marker in text for marker in heavy_markers):
            return "heavy"
        if domain in {"mixed", "research"} and len(deliverables) >= 3:
            return "heavy"
        if len(text.split()) < 12 and domain == "direct_answer":
            return "trivial"
        return "normal"

    def _estimate_risk(self, text: str, domain: str, difficulty: str) -> str:
        if any(token in text for token in ("production", "security", "permission", "destructive")):
            return "high"
        if difficulty in {"heavy", "long-horizon"} or domain == "mixed":
            return "high"
        if domain in {"coding", "research", "ops"}:
            return "medium"
        return "low"

    def _extract_subdomains(self, text: str) -> List[str]:
        known = {
            "llm-agents": r"\b(llm|agent|multi-agent)\b",
            "benchmark-analysis": r"\b(benchmark|ablation|baseline)\b",
            "runtime-orchestration": r"\b(runtime|orchestrator|scheduler)\b",
            "repo-engineering": r"\b(repo|repository|patch|code)\b",
            "scientific-workflows": r"\b(research|paper|hypothesis|experiment)\b",
            "memory-systems": r"\b(memory|experience|retrieval)\b",
        }
        matches = [name for name, pattern in known.items() if re.search(pattern, text)]
        return matches or ["general"]

    def _build_success_criteria(self, domain: str, deliverables: List[str], needs_validation: bool) -> List[str]:
        criteria = [f"produce_{item}" for item in deliverables]
        if domain in {"coding", "mixed"}:
            criteria.append("preserve_patch_trace")
        if domain in {"research", "mixed"}:
            criteria.append("document_evidence_and_assumptions")
        if needs_validation:
            criteria.append("include_independent_validation")
        return criteria
