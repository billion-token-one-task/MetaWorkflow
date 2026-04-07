from __future__ import annotations

import argparse
import json

from meta_controller.controller import MetaController


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a meta-controller episode.")
    parser.add_argument("--task", required=True, help="Natural-language task.")
    parser.add_argument("--project-path", default=None, help="Optional repo or workspace path.")
    parser.add_argument("--repo-summary", default=None, help="Optional repository summary.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt live runtime execution when adapters are available.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    controller = MetaController(dry_run=not args.live)
    episode = controller.run(
        user_text=args.task,
        project_path=args.project_path,
        repo_summary=args.repo_summary,
    )
    print(json.dumps(controller.summarize_episode(episode), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
