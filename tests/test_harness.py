from meta_controller.eval.harness import (
    HarnessScenarioResult,
    coding_smoke_metrics,
    extract_last_json_object,
    summarize_results,
)


def test_extract_last_json_object_from_noisy_stdout() -> None:
    text = "log line\nanother log\n{\"ok\": true, \"value\": 3}\n"
    assert extract_last_json_object(text) == {"ok": True, "value": 3}


def test_coding_smoke_metrics_capture_fix_and_retries() -> None:
    payload = {
        "episode": {"success": True, "workflow_template": "issue_triage_fix_test"},
        "worker_runs": [
            {"node_id": "implementer", "fallback_from": None},
            {"node_id": "implementer", "fallback_from": None},
            {"node_id": "test_runner", "fallback_from": "openhands"},
        ],
        "calc_py": "def add_numbers(a, b):\n    return a + b\n",
        "test_exit_code": 0,
    }
    metrics = coding_smoke_metrics(payload, exit_code=0)
    assert metrics["scenario_success"] is True
    assert metrics["calc_fixed"] is True
    assert metrics["retry_count"] == 1
    assert metrics["fallback_count"] == 1


def test_summarize_results_counts_pass_and_fail() -> None:
    results = [
        HarnessScenarioResult(
            scenario="a",
            command=["python", "a.py"],
            exit_code=0,
            duration_seconds=1.0,
            success=True,
            started_at="2026-01-01T00:00:00+00:00",
            completed_at="2026-01-01T00:00:01+00:00",
            stdout_path="/tmp/a.out",
            stderr_path="/tmp/a.err",
        ),
        HarnessScenarioResult(
            scenario="b",
            command=["python", "b.py"],
            exit_code=1,
            duration_seconds=2.0,
            success=False,
            started_at="2026-01-01T00:00:02+00:00",
            completed_at="2026-01-01T00:00:04+00:00",
            stdout_path="/tmp/b.out",
            stderr_path="/tmp/b.err",
        ),
    ]
    summary = summarize_results(results)
    assert summary["passed_scenarios"] == 1
    assert summary["failed_scenarios"] == 1
    assert summary["all_passed"] is False
