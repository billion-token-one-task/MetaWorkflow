from meta_controller.workers.base import RoleWorker


class HypothesisGeneratorWorker(RoleWorker):
    role = "hypothesis_generator"
    objective = "generate testable hypotheses grounded in the literature evidence"
    output_fields = ["hypotheses", "novelty_claims", "failure_risks"]
