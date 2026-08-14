from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AgentEntry:
    dir_name: str
    display_name: str
    path: Path


def list_agents(models_root: Path) -> list[AgentEntry]:
    if not models_root.exists():
        return []

    entries: list[AgentEntry] = []
    for candidate in sorted(models_root.iterdir()):
        if not candidate.is_dir():
            continue
        config_path = candidate / "config.json"
        if not config_path.exists():
            continue

        display_name = candidate.name
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("display_name"):
                display_name = str(raw["display_name"])
        except Exception as exc:  # noqa: BLE001
            logging.warning("Nie udalo sie odczytac %s: %s", config_path, exc)
            continue

        entries.append(AgentEntry(dir_name=candidate.name, display_name=display_name, path=candidate))

    return entries
