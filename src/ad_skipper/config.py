from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Katalog projektu (tam, gdzie lezy wspolny pakiet `tools/`), a nie katalog
# konkretnego agenta. Agenci (models/<nazwa>/) maja wlasne best.pt i config.json,
# ale odwoluja sie do tego samego, wspoldzielonego zestawu tooli.
PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(slots=True)
class ToolDefinition:
    class_name: str
    tool_path: Path
    tool_class: str | None = None
    priority: int = 0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentConfig:
    agent_dir: Path
    model_path: Path
    tools: list[ToolDefinition]
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def tool_classes(self) -> set[str]:
        return {tool.class_name for tool in self.tools}


@dataclass(slots=True)
class AgentSettings:
    conf_threshold: float = 0.6
    scan_interval: float = 1.5
    click_cooldown: float = 2.0
    anomaly_repeats: int = 5
    anomaly_pause_s: float = 10.0


def _resolve_tool_path(tools_root: Path, agent_dir: Path, tool_path_value: str, class_name: str) -> Path:
    tool_path = Path(tool_path_value)
    if tool_path.is_absolute():
        return tool_path

    # Domyslnie toole sa wspoldzielone przez wszystkich agentow i leza w
    # tools/ w katalogu projektu (np. tools/click.py).
    shared_candidate = tools_root / tool_path
    if shared_candidate.exists():
        return shared_candidate

    # Pozwala agentowi na wlasny, niestandardowy tool trzymany w jego wlasnym
    # katalogu (np. models/badoo/tools/custom_swipe.py), jesli nie ma go
    # we wspolnym tools/.
    agent_candidate = agent_dir / tool_path
    if agent_candidate.exists():
        return agent_candidate

    raise FileNotFoundError(
        f"Nie znaleziono pliku toola dla klasy '{class_name}'. Sprawdzone sciezki: "
        f"{shared_candidate}, {agent_candidate}"
    )


def _coerce_tool_definition(tools_root: Path, agent_dir: Path, entry: dict[str, Any]) -> ToolDefinition:
    class_name = entry.get("class") or entry.get("class_name") or entry.get("target_class")
    if not class_name:
        raise ValueError(f"Brak pola 'class' w definicji toola: {entry}")

    tool_path_value = entry.get("tool_path")
    if not tool_path_value:
        raise ValueError(f"Brak pola 'tool_path' dla klasy '{class_name}'")

    tool_path = _resolve_tool_path(tools_root, agent_dir, tool_path_value, str(class_name))

    return ToolDefinition(
        class_name=str(class_name),
        tool_path=tool_path,
        tool_class=entry.get("tool_class") or entry.get("handler_class"),
        priority=int(entry.get("priority", 0)),
        params=dict(entry.get("params", {})),
    )


def load_agent_config(agent_dir: Path, tools_root: Path | None = None) -> AgentConfig:
    tools_root = tools_root if tools_root is not None else PROJECT_ROOT

    config_path = agent_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Nie znaleziono config.json w katalogu agenta: {config_path}")

    raw_data = json.loads(config_path.read_text(encoding="utf-8"))
    if isinstance(raw_data, list):
        config_data: dict[str, Any] = {}
        tool_entries = raw_data
    elif isinstance(raw_data, dict):
        config_data = raw_data
        tool_entries = raw_data.get("tools", [])
    else:
        raise ValueError("config.json musi byc lista definicji tooli albo obiektem JSON")

    tools = [_coerce_tool_definition(tools_root, agent_dir, entry) for entry in tool_entries]
    tool_classes = [tool.class_name for tool in tools]
    if len(tool_classes) != len(set(tool_classes)):
        duplicates = sorted({name for name in tool_classes if tool_classes.count(name) > 1})
        raise ValueError(f"Znaleziono zduplikowane klasy tooli w configu: {', '.join(duplicates)}")

    model_name = config_data.get("model_path") or config_data.get("model_file") or "best.pt"
    model_path = Path(model_name)
    if not model_path.is_absolute():
        model_path = agent_dir / model_path

    return AgentConfig(
        agent_dir=agent_dir,
        model_path=model_path,
        tools=tools,
        raw=config_data,
    )