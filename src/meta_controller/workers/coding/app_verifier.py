from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

from meta_controller.core.models import WorkerResult
from meta_controller.workers.base import RoleWorker


class AppVerifierWorker(RoleWorker):
    role = "app_verifier"
    objective = "verify that the generated application can be started locally and that its core user flows are wired up"
    output_fields = ["test_commands", "tests_passed", "failures", "verification_notes"]

    def build_task_input(self, task_spec, upstream_results, memory_refs):
        base = super().build_task_input(task_spec, upstream_results, memory_refs)
        return (
            base
            + "Verification requirements:\n"
            "- Prefer existing package manager or runtime commands from README/package.json/requirements.txt.\n"
            "- Check that the project has a runnable backend entrypoint and frontend assets when applicable.\n"
            "- If there is a health endpoint, call it.\n"
            "- If there are tests, run them with shell guards so failures are reported in JSON rather than crashing the run.\n"
            "- Summarize whether the app is runnable locally right now.\n"
        )

    def run(self, task_spec, upstream_results, memory_refs=None) -> WorkerResult:
        project_path = Path(task_spec.project_path or ".")
        failures: List[str] = []
        commands: List[str] = []
        notes: List[str] = []

        try:
            stack = self._detect_stack(project_path)
            notes.append(f"detected_stack={stack}")

            if stack == "node":
                commands.extend(self._verify_node(project_path, failures, notes))
            elif stack == "python":
                commands.extend(self._verify_python(project_path, failures, notes))
            else:
                failures.append("could not detect runnable app stack from repo files")

            tests_passed = not failures
            summary = "app prototype verified successfully" if tests_passed else "app prototype verification found issues"
            return WorkerResult(
                status="success" if tests_passed else "failed",
                summary=summary,
                artifacts=[str(path.relative_to(project_path)) for path in self._important_files(project_path)],
                structured_output={
                    "test_commands": commands,
                    "tests_passed": tests_passed,
                    "failures": failures,
                    "verification_notes": notes,
                },
                cost=0.0,
                token_usage={"input_tokens": 0, "output_tokens": 0},
                tool_trace=[
                    {"tool": "local_verify", "command": command, "runtime": "local_app", "node_id": self.node.id}
                    for command in commands
                ],
                confidence=0.95 if tests_passed else 0.4,
                failure_type=None if tests_passed else "verification_failed",
            )
        except Exception as exc:
            return WorkerResult(
                status="failed",
                summary=f"app verification crashed: {exc}",
                artifacts=[],
                structured_output={
                    "test_commands": commands,
                    "tests_passed": False,
                    "failures": failures + [str(exc)],
                    "verification_notes": notes,
                },
                cost=0.0,
                token_usage={"input_tokens": 0, "output_tokens": 0},
                tool_trace=[{"tool": "local_verify", "runtime": "local_app", "node_id": self.node.id}],
                confidence=0.0,
                failure_type="verification_failed",
            )

    def _detect_stack(self, project_path: Path) -> str:
        if (project_path / "package.json").exists():
            return "node"
        if (project_path / "requirements.txt").exists() or (project_path / "app.py").exists():
            return "python"
        return "unknown"

    def _verify_node(self, project_path: Path, failures: List[str], notes: List[str]) -> List[str]:
        commands: List[str] = []
        if not (project_path / "node_modules").exists():
            self._run_command(["npm", "install"], project_path, failures, notes)
            commands.append("npm install")
        test_cmd = ["npm", "test"]
        self._run_command(test_cmd, project_path, failures, notes)
        commands.append("npm test")
        self._probe_server(["node", "server.js"], project_path, failures, notes, port=3000)
        commands.append("node server.js")
        return commands

    def _verify_python(self, project_path: Path, failures: List[str], notes: List[str]) -> List[str]:
        commands: List[str] = []
        venv_python = project_path / ".venv" / "bin" / "python"
        if not venv_python.exists():
            self._run_command([sys.executable, "-m", "venv", ".venv"], project_path, failures, notes)
            commands.append(f"{sys.executable} -m venv .venv")
        pip = project_path / ".venv" / "bin" / "pip"
        self._run_command([str(pip), "install", "-r", "requirements.txt"], project_path, failures, notes)
        commands.append(".venv/bin/pip install -r requirements.txt")
        pytest_target = "tests"
        self._run_command([str(venv_python), "-m", "pytest", pytest_target, "-q"], project_path, failures, notes)
        commands.append(".venv/bin/python -m pytest tests -q")
        self._probe_server([str(venv_python), "app.py"], project_path, failures, notes, port=5000)
        commands.append(".venv/bin/python app.py")
        return commands

    def _run_command(self, command: List[str], cwd: Path, failures: List[str], notes: List[str]) -> None:
        completed = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True)
        notes.append(f"cmd={' '.join(command)} exit={completed.returncode}")
        if completed.returncode != 0:
            failures.append(f"{' '.join(command)} failed: {(completed.stdout + completed.stderr)[-400:]}")

    def _probe_server(self, command: List[str], cwd: Path, failures: List[str], notes: List[str], port: int) -> None:
        env = dict(os.environ)
        env["PORT"] = str(port)
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            started = False
            for _ in range(25):
                time.sleep(1)
                if process.poll() is not None:
                    break
                for url in (f"http://127.0.0.1:{port}/health", f"http://127.0.0.1:{port}/"):
                    try:
                        with urllib.request.urlopen(url, timeout=2) as response:
                            notes.append(f"healthcheck={url} status={response.status}")
                            started = True
                            break
                    except (urllib.error.URLError, TimeoutError, ConnectionError):
                        continue
                if started:
                    break
            if not started:
                output = ""
                if process.stdout is not None:
                    try:
                        output = process.stdout.read()
                    except Exception:
                        output = ""
                failures.append(f"server probe failed for {' '.join(command)} output={output[-400:]}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

    def _important_files(self, project_path: Path):
        candidates = [
            project_path / "README.md",
            project_path / "package.json",
            project_path / "server.js",
            project_path / "app.py",
            project_path / "db.py",
            project_path / "db.js",
        ]
        return [path for path in candidates if path.exists()]
