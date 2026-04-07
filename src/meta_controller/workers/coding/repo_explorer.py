from meta_controller.workers.base import RoleWorker


class RepoExplorerWorker(RoleWorker):
    role = "repo_explorer"
    objective = "map repository structure, candidate files, and likely change surfaces"
    output_fields = ["files_of_interest", "architecture_notes", "risks"]
