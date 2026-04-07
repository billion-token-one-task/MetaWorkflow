from meta_controller.workers.base import RoleWorker


class IntegrationCheckerWorker(RoleWorker):
    role = "integration_checker"
    objective = "check cross-module integration and hidden dependency risk"
    output_fields = ["integration_risks", "dependency_notes", "release_readiness"]
