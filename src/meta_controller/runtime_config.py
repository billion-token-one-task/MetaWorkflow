from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from meta_controller.config import PROJECT_ROOT


REVIEW_ROLES = {"reviewer", "research_reviewer", "judge"}


@dataclass
class ProviderConfig:
    name: str
    base_url: Optional[str] = None
    wire_api: Optional[str] = None
    requires_openai_auth: bool = False
    api_key: Optional[str] = None


@dataclass
class RuntimeFallbackRule:
    from_runtime: str
    to_runtime: str
    failure_types: list[str] = field(default_factory=list)

    def matches(self, current_runtime: str, failure_type: Optional[str]) -> bool:
        if self.from_runtime != current_runtime:
            return False
        if not self.failure_types:
            return True
        return failure_type in self.failure_types


@dataclass
class SchedulerConfig:
    enable_runtime_fallback: bool = True
    runtime_fallbacks: list[RuntimeFallbackRule] = field(
        default_factory=lambda: [
            RuntimeFallbackRule(
                from_runtime="openhands",
                to_runtime="claude_sdk",
                failure_types=["configuration_error", "runtime_error"],
            )
        ]
    )


@dataclass
class RuntimeConfig:
    model_provider: Optional[str] = None
    model: Optional[str] = None
    review_model: Optional[str] = None
    model_reasoning_effort: Optional[str] = None
    disable_response_storage: bool = False
    network_access: Optional[str] = None
    windows_wsl_setup_acknowledged: bool = False
    model_context_window: Optional[int] = None
    model_auto_compact_token_limit: Optional[int] = None
    model_providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)

    def provider(self) -> Optional[ProviderConfig]:
        if not self.model_provider:
            return None
        return self.model_providers.get(self.model_provider)

    def model_for_role(self, role: str) -> Optional[str]:
        if role in REVIEW_ROLES and self.review_model:
            return self.review_model
        return self.model


def _candidate_paths() -> list[Path]:
    paths = []
    env_path = os.environ.get("META_CONTROLLER_RUNTIME_CONFIG")
    if env_path:
        paths.append(Path(env_path))
    paths.append(PROJECT_ROOT / "config" / "runtime.local.toml")
    paths.append(PROJECT_ROOT / "config" / "runtime.toml")
    return paths


@lru_cache(maxsize=1)
def load_runtime_config() -> RuntimeConfig:
    for path in _candidate_paths():
        if path.exists():
            return _load_runtime_config_from_path(path)
    return RuntimeConfig()


def _load_runtime_config_from_path(path: Path) -> RuntimeConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    providers: Dict[str, ProviderConfig] = {}
    for provider_name, provider_data in data.get("model_providers", {}).items():
        providers[provider_name] = ProviderConfig(
            name=str(provider_data.get("name", provider_name)),
            base_url=provider_data.get("base_url"),
            wire_api=provider_data.get("wire_api"),
            requires_openai_auth=bool(provider_data.get("requires_openai_auth", False)),
            api_key=provider_data.get("api_key"),
        )
    scheduler_data = data.get("scheduler", {})
    fallback_rules = [
        RuntimeFallbackRule(
            from_runtime=str(rule.get("from_runtime")),
            to_runtime=str(rule.get("to_runtime")),
            failure_types=[str(item) for item in rule.get("failure_types", [])],
        )
        for rule in scheduler_data.get("runtime_fallbacks", [])
        if rule.get("from_runtime") and rule.get("to_runtime")
    ]
    scheduler = SchedulerConfig(
        enable_runtime_fallback=bool(scheduler_data.get("enable_runtime_fallback", True)),
        runtime_fallbacks=fallback_rules or SchedulerConfig().runtime_fallbacks,
    )

    return RuntimeConfig(
        model_provider=data.get("model_provider"),
        model=data.get("model"),
        review_model=data.get("review_model"),
        model_reasoning_effort=data.get("model_reasoning_effort"),
        disable_response_storage=bool(data.get("disable_response_storage", False)),
        network_access=data.get("network_access"),
        windows_wsl_setup_acknowledged=bool(data.get("windows_wsl_setup_acknowledged", False)),
        model_context_window=data.get("model_context_window"),
        model_auto_compact_token_limit=data.get("model_auto_compact_token_limit"),
        model_providers=providers,
        scheduler=scheduler,
    )
