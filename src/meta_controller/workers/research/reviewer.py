from meta_controller.workers.base import RoleWorker


class ResearchReviewerWorker(RoleWorker):
    role = "research_reviewer"
    objective = "review novelty, evidence quality, experiment feasibility, and story coherence"
    output_fields = ["issues", "acceptance_recommendation", "suggested_revisions"]
