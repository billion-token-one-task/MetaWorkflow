from meta_controller.workers.base import RoleWorker


class PaperAnalystWorker(RoleWorker):
    role = "paper_analyst"
    objective = "extract methods, assumptions, limitations, and reusable components from key papers"
    output_fields = ["paper_takeaways", "limitations", "reusable_modules"]
