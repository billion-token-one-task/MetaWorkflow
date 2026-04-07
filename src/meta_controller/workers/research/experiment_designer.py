from meta_controller.workers.base import RoleWorker


class ExperimentDesignerWorker(RoleWorker):
    role = "experiment_designer"
    objective = "design datasets, metrics, baselines, and ablations for the proposed hypothesis"
    output_fields = ["experiment_plan", "baselines", "evaluation_risks"]
