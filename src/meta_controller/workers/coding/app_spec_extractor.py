from meta_controller.workers.base import RoleWorker


class AppSpecExtractorWorker(RoleWorker):
    role = "app_spec_extractor"
    objective = "turn the product request into concrete frontend pages, backend endpoints, storage needs, and run instructions"
    output_fields = ["feature_map", "api_plan", "runbook_outline"]
