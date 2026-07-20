from __future__ import annotations

import hashlib
import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from agent_config import AgentConfig, AgentSettings, ToolDefinition, load_agent_config
from tools.base import BaseTool


def _load_module_from_path(path: Path) -> ModuleType:
    if not path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku toola: {path}")

    module_name = f"ad_skipper_dynamic_{path.stem}_{hashlib.sha1(str(path).encode('utf-8')).hexdigest()[:10]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Nie udalo sie zaladowac toola z pliku: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_tool_class(module: ModuleType, tool_definition: ToolDefinition) -> type[BaseTool]:
    explicit_name = tool_definition.tool_class
    if explicit_name:
        candidate = getattr(module, explicit_name, None)
        if inspect.isclass(candidate) and issubclass(candidate, BaseTool):
            return candidate
        raise TypeError(f"Klasa '{explicit_name}' w '{tool_definition.tool_path}' nie dziedziczy po BaseTool")

    tool_class_name = getattr(module, "TOOL_CLASS", None)
    if isinstance(tool_class_name, str):
        candidate = getattr(module, tool_class_name, None)
        if inspect.isclass(candidate) and issubclass(candidate, BaseTool):
            return candidate

    subclasses = [
        candidate
        for candidate in module.__dict__.values()
        if inspect.isclass(candidate) and issubclass(candidate, BaseTool) and candidate is not BaseTool
    ]
    defined_subclasses = [candidate for candidate in subclasses if candidate.__module__ == module.__name__]
    if len(defined_subclasses) == 1:
        return defined_subclasses[0]

    for preferred_name in ("Tool", "ClickTool"):
        candidate = getattr(module, preferred_name, None)
        if inspect.isclass(candidate) and issubclass(candidate, BaseTool):
            return candidate

    raise TypeError(
        f"Nie udalo sie jednoznacznie wybrac klasy toola z pliku '{tool_definition.tool_path}'. "
        "Dodaj pole 'tool_class' w config.json."
    )


@dataclass(slots=True)
class AgentRuntime:
    config: AgentConfig
    settings: AgentSettings
    tools_by_class: dict[str, BaseTool]
    tool_definitions: dict[str, ToolDefinition]

    @property
    def agent_dir(self) -> Path:
        return self.config.agent_dir

    @property
    def model_path(self) -> Path:
        return self.config.model_path

    @classmethod
    def from_agent_dir(
        cls,
        agent_dir: Path,
        *,
        settings: AgentSettings,
        model_override: str | None = None,
        tools_root: Path | None = None,
    ) -> "AgentRuntime":
        agent_dir = agent_dir.expanduser().resolve()
        config = load_agent_config(agent_dir, tools_root=tools_root)

        if model_override:
            override_path = Path(model_override).expanduser()
            if not override_path.is_absolute():
                override_path = (agent_dir / override_path).resolve()
            config.model_path = override_path

        tools_by_class: dict[str, BaseTool] = {}
        tool_definitions: dict[str, ToolDefinition] = {}

        for tool_definition in config.tools:
            module = _load_module_from_path(tool_definition.tool_path)
            tool_class = _resolve_tool_class(module, tool_definition)
            tool_instance = tool_class(config=tool_definition.params, agent_root=agent_dir)
            tools_by_class[tool_definition.class_name] = tool_instance
            tool_definitions[tool_definition.class_name] = tool_definition

        return cls(config=config, settings=settings, tools_by_class=tools_by_class, tool_definitions=tool_definitions)