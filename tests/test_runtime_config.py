from meta_controller.runtime_config import _load_runtime_config_from_path


def test_runtime_config_loads_openai_provider(tmp_path) -> None:
    config_path = tmp_path / "runtime.toml"
    config_path.write_text(
        """
model_provider = "OpenAI"
model = "gpt-5.4"
review_model = "gpt-5.4"
model_reasoning_effort = "xhigh"

[scheduler]
enable_runtime_fallback = true

[[scheduler.runtime_fallbacks]]
from_runtime = "openhands"
to_runtime = "claude_sdk"
failure_types = ["runtime_error"]

[model_providers.OpenAI]
name = "OpenAI"
base_url = "http://example.test"
wire_api = "responses"
requires_openai_auth = true
api_key = "sk-test"
""".strip(),
        encoding="utf-8",
    )
    config = _load_runtime_config_from_path(config_path)
    assert config.model == "gpt-5.4"
    assert config.model_for_role("reviewer") == "gpt-5.4"
    assert config.provider() is not None
    assert config.provider().base_url == "http://example.test"
    assert config.scheduler.enable_runtime_fallback is True
    assert config.scheduler.runtime_fallbacks[0].from_runtime == "openhands"
    assert config.scheduler.runtime_fallbacks[0].failure_types == ["runtime_error"]
