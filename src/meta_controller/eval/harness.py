from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from json import JSONDecoder
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from meta_controller.config import PROJECT_ROOT, RUNS_DIR


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class HarnessScenarioResult(BaseModel):
    scenario: str
    command: List[str]
    exit_code: int
    duration_seconds: float
    success: bool
    started_at: str
    completed_at: str
    stdout_path: str
    stderr_path: str
    payload_path: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class HarnessReport(BaseModel):
    harness_id: str
    started_at: str
    completed_at: str
    output_dir: str
    scenarios: List[HarnessScenarioResult]
    aggregate: Dict[str, Any]


@dataclass(frozen=True)
class HarnessScenario:
    name: str
    command: List[str]
    timeout_seconds: int
    metrics_fn: Callable[[Optional[Dict[str, Any]], int], Dict[str, Any]]


def build_default_scenarios(include_heavy: bool = False) -> List[HarnessScenario]:
    python = str(PROJECT_ROOT / ".venv" / "bin" / "python")
    scripts = PROJECT_ROOT / "scripts"
    scenarios = [
        HarnessScenario(
            name="runtime_smoke",
            command=[python, str(scripts / "run_runtime_smoke.py"), "--skip-openhands-direct"],
            timeout_seconds=480,
            metrics_fn=runtime_smoke_metrics,
        ),
        HarnessScenario(
            name="coding_smoke",
            command=[python, str(scripts / "run_coding_smoke.py")],
            timeout_seconds=900,
            metrics_fn=coding_smoke_metrics,
        ),
    ]
    if include_heavy:
        scenarios.append(
            HarnessScenario(
                name="coding_smoke_heavy",
                command=[python, str(scripts / "run_coding_smoke.py"), "--heavy"],
                timeout_seconds=1500,
                metrics_fn=coding_smoke_metrics,
            )
        )
    return scenarios


def run_harness(
    scenarios: List[HarnessScenario],
    output_root: Optional[Path] = None,
) -> HarnessReport:
    started_at = utc_now_iso()
    harness_id = f"harness_{timestamp_slug()}"
    output_dir = (output_root or (RUNS_DIR / "harness")) / harness_id
    output_dir.mkdir(parents=True, exist_ok=True)

    results: List[HarnessScenarioResult] = []
    for scenario in scenarios:
        results.append(_run_scenario(scenario=scenario, output_dir=output_dir))

    completed_at = utc_now_iso()
    aggregate = summarize_results(results)
    report = HarnessReport(
        harness_id=harness_id,
        started_at=started_at,
        completed_at=completed_at,
        output_dir=str(output_dir),
        scenarios=results,
        aggregate=aggregate,
    )
    (output_dir / "summary.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_markdown_report(report), encoding="utf-8")
    return report


def _run_scenario(scenario: HarnessScenario, output_dir: Path) -> HarnessScenarioResult:
    started = datetime.now(timezone.utc)
    proc = subprocess.run(
        scenario.command,
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        timeout=scenario.timeout_seconds,
    )
    completed = datetime.now(timezone.utc)

    scenario_dir = output_dir / scenario.name
    scenario_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = scenario_dir / "stdout.log"
    stderr_path = scenario_dir / "stderr.log"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")

    payload: Optional[Dict[str, Any]] = None
    payload_path: Optional[Path] = None
    parse_error: Optional[str] = None
    try:
        payload = extract_last_json_object(proc.stdout)
        payload_path = scenario_dir / "payload.json"
        payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except ValueError as exc:
        parse_error = str(exc)

    metrics = scenario.metrics_fn(payload, proc.returncode)
    success = bool(metrics.get("scenario_success", proc.returncode == 0))

    return HarnessScenarioResult(
        scenario=scenario.name,
        command=scenario.command,
        exit_code=proc.returncode,
        duration_seconds=max(0.0, (completed - started).total_seconds()),
        success=success,
        started_at=started.isoformat(),
        completed_at=completed.isoformat(),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        payload_path=str(payload_path) if payload_path else None,
        payload=payload,
        metrics=metrics,
        error=parse_error,
    )


def extract_last_json_object(text: str) -> Dict[str, Any]:
    decoder = JSONDecoder()
    candidates: List[Dict[str, Any]] = []
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        remainder = text[idx + end :].strip()
        if remainder:
            continue
        if isinstance(payload, dict):
            candidates.append(payload)
    if not candidates:
        raise ValueError("No trailing JSON object found in stdout.")
    return candidates[-1]


def runtime_smoke_metrics(payload: Optional[Dict[str, Any]], exit_code: int) -> Dict[str, Any]:
    if payload is None:
        return {"scenario_success": False, "exit_code": exit_code}

    claude_ok = payload.get("claude_runtime", {}).get("status") == "success"
    openhands_status = payload.get("openhands_runtime", {}).get("status")
    openhands_ok = openhands_status == "success"
    openhands_skipped = openhands_status == "skipped"
    fallback_ok = payload.get("scheduler_fallback_demo", {}).get("success") is True
    controller_ok = payload.get("controller", {}).get("success") is True
    return {
        "scenario_success": exit_code == 0 and claude_ok and fallback_ok and controller_ok,
        "claude_success": claude_ok,
        "openhands_direct_success": openhands_ok,
        "openhands_direct_skipped": openhands_skipped,
        "scheduler_fallback_success": fallback_ok,
        "controller_success": controller_ok,
        "exit_code": exit_code,
    }


def coding_smoke_metrics(payload: Optional[Dict[str, Any]], exit_code: int) -> Dict[str, Any]:
    if payload is None:
        return {"scenario_success": False, "exit_code": exit_code}

    episode = payload.get("episode", {})
    worker_runs = payload.get("worker_runs", [])
    calc_py = payload.get("calc_py", "")
    test_exit_code = payload.get("test_exit_code")
    fallback_count = sum(1 for run in worker_runs if run.get("fallback_from"))
    retry_count = max(0, len(worker_runs) - len({run.get("node_id") for run in worker_runs}))
    external_success = test_exit_code == 0 and "return a + b" in calc_py
    return {
        "scenario_success": external_success,
        "episode_success": bool(episode.get("success")),
        "tests_passed": test_exit_code == 0,
        "calc_fixed": "return a + b" in calc_py,
        "fallback_count": fallback_count,
        "retry_count": retry_count,
        "worker_run_count": len(worker_runs),
        "workflow_template": episode.get("workflow_template"),
        "external_success": external_success,
        "exit_code": exit_code,
    }


def summarize_results(results: List[HarnessScenarioResult]) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result.success)
    failed = total - passed
    return {
        "total_scenarios": total,
        "passed_scenarios": passed,
        "failed_scenarios": failed,
        "success_rate": (passed / total) if total else 0.0,
        "all_passed": failed == 0,
        "total_duration_seconds": round(sum(result.duration_seconds for result in results), 3),
    }


def render_markdown_report(report: HarnessReport) -> str:
    lines = [
        "# Harness Report",
        "",
        f"- Harness ID: `{report.harness_id}`",
        f"- Started: `{report.started_at}`",
        f"- Completed: `{report.completed_at}`",
        f"- Output Dir: `{report.output_dir}`",
        f"- Passed: `{report.aggregate['passed_scenarios']}` / `{report.aggregate['total_scenarios']}`",
        "",
        "| Scenario | Success | Exit | Duration (s) | Key Metrics |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for result in report.scenarios:
        metrics = ", ".join(f"{key}={value}" for key, value in sorted(result.metrics.items()) if key != "exit_code")
        lines.append(
            f"| `{result.scenario}` | `{'yes' if result.success else 'no'}` | `{result.exit_code}` | "
            f"{result.duration_seconds:.2f} | {metrics or '-'} |"
        )
    lines.extend(["", "## Raw Artifacts", ""])
    for result in report.scenarios:
        lines.append(f"- `{result.scenario}` stdout: `{result.stdout_path}`")
        lines.append(f"- `{result.scenario}` stderr: `{result.stderr_path}`")
        if result.payload_path:
            lines.append(f"- `{result.scenario}` payload: `{result.payload_path}`")
    lines.append("")
    return "\n".join(lines)
