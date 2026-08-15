from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.ad_skipper.bot import AdSkipperBot, build_settings
from src.ad_skipper.env_settings import load_env_config
from src.ad_skipper.runtime import AgentRuntime


class BotWorker(QThread):
    status_changed = Signal(str)   # "running" | "paused" | "stopped"
    error_occurred = Signal(str)

    def __init__(self, agent_dir: Path, adb_address: str) -> None:
        super().__init__()
        self.agent_dir = agent_dir
        self.adb_address = adb_address
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.reset_cooldown_event = threading.Event()

    def run(self) -> None:
        try:
            env_config = load_env_config()
            settings = build_settings(env_config)
            runtime = AgentRuntime.from_agent_dir(self.agent_dir, settings=settings)
            bot = AdSkipperBot(runtime=runtime, adb_address=self.adb_address)
        except Exception as exc:  # noqa: BLE001
            logging.error("Blad inicjalizacji bota: %s", exc)
            self.error_occurred.emit(str(exc))
            return

        self.status_changed.emit("running")
        bot.run(
            stop_event=self.stop_event,
            pause_event=self.pause_event,
            reset_cooldown_event=self.reset_cooldown_event,
        )
        self.status_changed.emit("stopped")

    def request_stop(self) -> None:
        self.stop_event.set()

    def reset_cooldown(self) -> None:
        self.reset_cooldown_event.set()

    def toggle_pause(self) -> bool:
        """Toggleuje pauze. Zwraca True jesli bot jest teraz wstrzymany."""
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.status_changed.emit("running")
        else:
            self.pause_event.set()
            self.status_changed.emit("paused")
        return self.pause_event.is_set()
