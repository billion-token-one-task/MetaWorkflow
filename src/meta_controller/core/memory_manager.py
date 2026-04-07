from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from meta_controller.config import RUNS_DIR
from meta_controller.core.models import EpisodeRecord


class MemoryManager:
    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else RUNS_DIR
        self.episodes_dir = self.base_dir / "episodes"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        self.negative_memory_path = self.base_dir / "negative_memory.jsonl"
        self.scaffold_edits_path = self.base_dir / "scaffold_edits.jsonl"

    def write_episode(self, episode: EpisodeRecord) -> Path:
        target = self.episodes_dir / f"{episode.episode_id}.json"
        payload = episode.model_dump(mode="json")
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
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

    def _tokenize(self, text: str) -> List[str]:
        return [token for token in text.lower().replace("_", " ").split() if len(token) > 2]
