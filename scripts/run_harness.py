from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
if (
    VENV_PYTHON.exists()
    and Path(sys.executable).resolve() != VENV_PYTHON.resolve()
    and not os.environ.get("META_CONTROLLER_SKIP_VENV_REEXEC")
):
    env = dict(os.environ)
    env["META_CONTROLLER_SKIP_VENV_REEXEC"] = "1"
    os.execve(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]], env)

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meta_controller.eval.harness import build_default_scenarios, run_harness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the meta-controller evaluation harness.")
    parser.add_argument(
        "--include-heavy",
        action="store_true",
        help="Include the heavier coding scenario that exercises OpenHands and fallback behavior.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=["runtime_smoke", "runtime_smoke_full", "coding_smoke", "coding_smoke_heavy"],
        help="Run only selected scenarios. May be repeated.",
    )
    parser.add_argument(
        "--include-full-runtime-probe",
        action="store_true",
        help="Also run the slower direct OpenHands runtime probe scenario.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    scenarios = build_default_scenarios(include_heavy=args.include_heavy)
    if args.include_full_runtime_probe:
        scenarios.append(
            build_default_scenarios(include_heavy=False)[0].__class__(
                name="runtime_smoke_full",
                command=[str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "scripts" / "run_runtime_smoke.py")],
                timeout_seconds=900,
                metrics_fn=scenarios[0].metrics_fn,
            )
        )
    if args.scenario:
        selected = set(args.scenario)
        scenarios = [scenario for scenario in scenarios if scenario.name in selected]
    report = run_harness(scenarios)
    print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0 if report.aggregate["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
