from meta_controller.workers.base import RoleWorker


class TestRunnerWorker(RoleWorker):
    role = "test_runner"
    objective = "run targeted verification and summarize pass fail status"
    output_fields = ["test_commands", "tests_passed", "failures"]
