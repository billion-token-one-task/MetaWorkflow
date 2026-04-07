from meta_controller.workers.base import RoleWorker


class TaskPlannerWorker(RoleWorker):
    role = "task_planner"
    objective = "turn exploration evidence into a concrete implementation plan"
    output_fields = ["implementation_plan", "milestones", "test_strategy"]
