from meta_controller.workers.base import RoleWorker


class ImplementerWorker(RoleWorker):
    role = "implementer"
    objective = "prepare or apply the code changes required by the task"
    output_fields = ["patch_plan", "changed_files", "implementation_notes"]
