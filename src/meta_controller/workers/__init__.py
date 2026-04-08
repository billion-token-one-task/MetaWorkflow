from meta_controller.workers.base import GenericWorker, RoleWorker
from meta_controller.workers.coding.app_spec_extractor import AppSpecExtractorWorker
from meta_controller.workers.coding.app_verifier import AppVerifierWorker
from meta_controller.workers.coding.fullstack_builder import FullstackBuilderWorker
from meta_controller.workers.coding.implementer import ImplementerWorker
from meta_controller.workers.coding.integration_checker import IntegrationCheckerWorker
from meta_controller.workers.coding.repo_explorer import RepoExplorerWorker
from meta_controller.workers.coding.reviewer import ReviewerWorker
from meta_controller.workers.coding.task_planner import TaskPlannerWorker
from meta_controller.workers.coding.test_runner import TestRunnerWorker
from meta_controller.workers.research.experiment_designer import ExperimentDesignerWorker
from meta_controller.workers.research.hypothesis_generator import HypothesisGeneratorWorker
from meta_controller.workers.research.literature_scout import LiteratureScoutWorker
from meta_controller.workers.research.paper_analyst import PaperAnalystWorker
from meta_controller.workers.research.planner import ResearchPlannerWorker
from meta_controller.workers.research.reviewer import ResearchReviewerWorker


ROLE_REGISTRY = {
    "app_spec_extractor": AppSpecExtractorWorker,
    "fullstack_builder": FullstackBuilderWorker,
    "app_verifier": AppVerifierWorker,
    "repo_explorer": RepoExplorerWorker,
    "task_planner": TaskPlannerWorker,
    "implementer": ImplementerWorker,
    "test_runner": TestRunnerWorker,
    "reviewer": ReviewerWorker,
    "integration_checker": IntegrationCheckerWorker,
    "research_planner": ResearchPlannerWorker,
    "literature_scout": LiteratureScoutWorker,
    "paper_analyst": PaperAnalystWorker,
    "paper_analyst_parallel": PaperAnalystWorker,
    "hypothesis_generator": HypothesisGeneratorWorker,
    "experiment_designer": ExperimentDesignerWorker,
    "research_reviewer": ResearchReviewerWorker,
    "judge": ResearchReviewerWorker,
}


def build_worker(node, runtime):
    worker_cls = ROLE_REGISTRY.get(node.role, GenericWorker)
    return worker_cls(node=node, runtime=runtime)


__all__ = ["RoleWorker", "build_worker"]
