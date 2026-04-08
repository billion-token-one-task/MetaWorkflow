from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from meta_controller.config import RUNS_DIR
from meta_controller.core.models import EpisodeRecord, TaskSpec


class MemoryManager:
    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else RUNS_DIR
        self.episodes_dir = self.base_dir / "episodes"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        self.negative_memory_path = self.base_dir / "negative_memory.jsonl"
        self.scaffold_edits_path = self.base_dir / "scaffold_edits.jsonl"
        self.workflow_index_path = self.base_dir / "workflow_index.jsonl"
        self.evolution_log_path = self.base_dir / "evolution_log.jsonl"

    def write_episode(self, episode: EpisodeRecord) -> Path:
        target = self.episodes_dir / f"{episode.episode_id}.json"
        payload = episode.model_dump(mode="json")
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        self._append_jsonl(
            self.workflow_index_path,
            {
                "episode_id": episode.episode_id,
                "task_id": episode.task_spec.get("task_id"),
                "task_text": episode.task_spec.get("user_text"),
                "domain": episode.task_spec.get("domain"),
                "subdomains": episode.task_spec.get("subdomains", []),
                "workflow_template": episode.workflow_spec.get("template_name"),
                "route_mode": episode.workflow_spec.get("route_mode"),
                "success": episode.success,
                "verdict": episode.judge_result.get("verdict"),
                "artifacts": episode.final_artifacts,
                "created_at": payload.get("created_at"),
            },
        )
        if not episode.success:
            self._append_jsonl(
                self.negative_memory_path,
                {
                    "episode_id": episode.episode_id,
                    "task_id": episode.task_spec.get("task_id"),
                    "issues": episode.judge_result.get("issues", []),
                    "workflow_template": episode.workflow_spec.get("template_name"),
                },
            )
        return target

    def write_scaffold_edits(self, edits: List[Dict[str, Any]]) -> None:
        for edit in edits:
            self._append_jsonl(self.scaffold_edits_path, edit)

    def get_route_hints(self, task_spec: TaskSpec) -> Dict[str, Any]:
        entries = self._load_jsonl(self.workflow_index_path)
        query_tokens = set(self._tokenize(task_spec.user_text))
        template_scores: Dict[str, float] = {}
        matched_entries = 0
        for entry in entries:
            if entry.get("domain") != task_spec.domain:
                continue
            prior_subdomains = set(entry.get("subdomains", []))
            if task_spec.subdomains and not prior_subdomains.intersection(task_spec.subdomains):
                continue
            prior_tokens = set(self._tokenize(entry.get("task_text", "")))
            overlap = len(query_tokens & prior_tokens)
            if overlap == 0:
                continue
            matched_entries += 1
            template = entry.get("workflow_template")
            if not template:
                continue
            weight = 1.0 + min(overlap, 8) / 10.0
            success = bool(entry.get("success"))
            template_scores[template] = template_scores.get(template, 0.0) + (weight if success else -0.75 * weight)

        preferred_template = None
        if template_scores:
            preferred_template = max(template_scores.items(), key=lambda item: item[1])[0]

        return {
            "matched_history_count": matched_entries,
            "template_scores": template_scores,
            "preferred_template": preferred_template,
        }

    def write_evolution_event(self, payload: Dict[str, Any]) -> None:
        self._append_jsonl(self.evolution_log_path, payload)

    def retrieve_similar_tasks(self, user_text: str, limit: int = 3) -> List[Dict[str, str]]:
        query_tokens = set(self._tokenize(user_text))
        scored: List[Tuple[int, Dict[str, str]]] = []
        for path in self.episodes_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            prior_text = payload.get("task_spec", {}).get("user_text", "")
            overlap = len(query_tokens & set(self._tokenize(prior_text)))
            if overlap <= 0:
                continue
            scored.append(
                (
                    overlap,
                    {
                        "episode_id": payload.get("episode_id", path.stem),
                        "task_id": payload.get("task_spec", {}).get("task_id", ""),
                        "user_text": prior_text,
                    },
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def _append_jsonl(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _tokenize(self, text: str) -> List[str]:
        return [token for token in text.lower().replace("_", " ").split() if len(token) > 2]
