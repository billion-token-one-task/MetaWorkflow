from __future__ import annotations

from typing import Any, Dict, List, Optional

from meta_controller.core.domain_router import DomainRouter
from meta_controller.core.judge import Judge
from meta_controller.core.memory_manager import MemoryManager
from meta_controller.core.models import EpisodeRecord
from meta_controller.core.scaffold_editor import ScaffoldEditor
from meta_controller.core.scheduler import Scheduler
from meta_controller.core.task_analyzer import TaskAnalyzer
from meta_controller.core.workflow_synthesizer import WorkflowSynthesizer


class MetaController:
    def __init__(self, runs_dir: Optional[str] = None, dry_run: bool = True) -> None:
        self.memory_manager = MemoryManager(base_dir=runs_dir)
        self.task_analyzer = TaskAnalyzer()
        self.domain_router = DomainRouter()
        self.workflow_synthesizer = WorkflowSynthesizer()
        self.judge = Judge()
        self.scheduler = Scheduler(
            memory_manager=self.memory_manager,
            judge=self.judge,
            dry_run=dry_run,
        )
        self.scaffold_editor = ScaffoldEditor(self.memory_manager)

    def run(
        self,
        user_text: str,
        project_path: Optional[str] = None,
        repo_summary: Optional[str] = None,
        available_tools: Optional[List[str]] = None,
    ) -> EpisodeRecord:
        similar = self.memory_manager.retrieve_similar_tasks(user_text=user_text, limit=3)
        task_spec = self.task_analyzer.analyze(
            user_text=user_text,
            project_path=project_path,
            repo_summary=repo_summary,
            available_tools=available_tools or [],
            similar_memories=similar,
        )
        routing_decision = self.domain_router.route(task_spec)
        workflow_spec = self.workflow_synthesizer.synthesize(task_spec, routing_decision)
        episode = self.scheduler.run(task_spec=task_spec, workflow_spec=workflow_spec)
        episode.routing_decision = routing_decision.model_dump()
        scaffold_edits = self.scaffold_editor.propose_updates(
            task_spec=task_spec,
            workflow_spec=workflow_spec,
            judge_result=episode.judge_result,
        )
        episode.scaffold_edits = scaffold_edits
        self.memory_manager.write_episode(episode)
        return episode

    def summarize_episode(self, episode: EpisodeRecord) -> Dict[str, Any]:
        return {
            "episode_id": episode.episode_id,
            "task_id": episode.task_spec.get("task_id"),
            "success": episode.success,
            "workflow_template": episode.workflow_spec.get("template_name"),
            "verdict": episode.judge_result.get("verdict"),
            "artifacts": episode.final_artifacts,
            "scaffold_edits": episode.scaffold_edits,
        }
