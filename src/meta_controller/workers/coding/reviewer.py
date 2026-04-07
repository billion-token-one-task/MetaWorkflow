from meta_controller.workers.base import RoleWorker


class ReviewerWorker(RoleWorker):
    role = "reviewer"
    objective = "independently inspect correctness, regressions, and code quality risks"
    output_fields = ["issues", "approval_recommendation", "follow_up_actions"]
