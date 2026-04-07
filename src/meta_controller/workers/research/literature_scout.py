from meta_controller.workers.base import RoleWorker


class LiteratureScoutWorker(RoleWorker):
    role = "literature_scout"
    objective = "search for candidate papers, benchmarks, and repositories relevant to the task"
    output_fields = ["queries", "candidate_papers", "evidence_gaps"]
