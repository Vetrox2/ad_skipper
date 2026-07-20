from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Tuple

BoundingBox = Tuple[int, int, int, int]


@dataclass(slots=True)
class DetectionContext:
    class_name: str
    confidence: float
    bounding_box: BoundingBox
    center: Tuple[int, int]
    frame_hash: int
    iteration: int
    agent_root: Path
    frame: Any | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolResult:
    handled: bool = True
    sleep_s: float | None = None
    message: str = ""


@dataclass(slots=True)
class ToolServices:
    click: Callable[[int, int], bool]
    sleep: Callable[[float], None]
    logger: logging.Logger


class BaseTool(ABC):
    def __init__(self, *, config: dict[str, Any] | None = None, agent_root: Path | None = None) -> None:
        self.config = config or {}
        self.agent_root = agent_root

    @abstractmethod
    def handle(self, context: DetectionContext, services: ToolServices) -> ToolResult:
        raise NotImplementedError