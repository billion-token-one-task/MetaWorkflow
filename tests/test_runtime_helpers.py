from meta_controller.core.models import WorkflowNode
from meta_controller.runtimes.claude_runtime import ClaudeRuntime


def build_node(permission_mode: str, tools: list[str]) -> WorkflowNode:
    return WorkflowNode(
        id="n1",
        role="repo_explorer",
        runtime="claude_sdk",
        tools=tools,
        permission_mode=permission_mode,
        model_tier="balanced",
        budget_tokens=1000,
        timeout_seconds=60,
        retry_limit=1,
    )


def test_claude_tool_mapping_for_read_only_worker() -> None:
    runtime = ClaudeRuntime(dry_run=True)
    tools = runtime._map_allowed_tools(["filesystem", "grep"], "read_only")
    assert "Read" in tools
    assert "Grep" in tools
    assert "Bash" not in tools


def test_claude_tool_mapping_for_execute_worker() -> None:
    runtime = ClaudeRuntime(dry_run=True)
    tools = runtime._map_allowed_tools(["filesystem", "python", "pytest", "git", "patch"], "execute")
    assert "Bash" in tools
    assert "Edit" in tools
    assert "Write" in tools


def test_runtime_prompt_parser_fills_missing_fields() -> None:
    runtime = ClaudeRuntime(dry_run=True)
    node = build_node("read_only", ["filesystem"])
    payload = runtime.parse_payload('{"summary":"ok","structured_output":{"issues":["a"]},"confidence":0.7}', ["issues", "approval_recommendation"], node)
    assert payload["summary"] == "ok"
    assert payload["structured_output"]["issues"] == ["a"]
    assert "approval_recommendation" in payload["structured_output"]
