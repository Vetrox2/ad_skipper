from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.ad_skipper.gui.bot_worker import BotWorker
from src.ad_skipper.gui.log_handler import QtLogHandler
from src.ad_skipper.gui.model_scanner import AgentEntry, list_agents
from src.ad_skipper.paths import get_app_root

MAX_LOG_LINES = 1000


def get_window_icon() -> QIcon | None:
    root = get_app_root()
    candidates = [
        root / "assets" / "icon.ico",
        root / "assets" / "icon.png",
        root / "icon.ico",
        root / "icon.png",
    ]
    for path in candidates:
        if path.exists():
            return QIcon(str(path))
    return None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ad Skipper")
        self.setMinimumSize(760, 560)
        self.resize(900, 640)

        icon = get_window_icon()
        if icon and not icon.isNull():
            self.setWindowIcon(icon)

        self._worker: BotWorker | None = None
        self._models_root: Path = get_app_root() / "models"
        self._adb_address: str = "127.0.0.1:5555"

        self._setup_log_handler()
        self._build_ui()
        self._refresh_models()


    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_log_handler(self) -> None:
        self._log_handler = QtLogHandler()
        self._log_handler.log_line.connect(self._append_log)
        logging.getLogger().addHandler(self._log_handler)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Model selector row ---
        model_row = QHBoxLayout()
        model_row.setSpacing(8)

        model_label = QLabel("Model:")
        model_label.setFixedWidth(48)
        model_row.addWidget(model_label)

        self._model_combo = QComboBox()
        self._model_combo.setObjectName("model_combo")
        self._model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        model_row.addWidget(self._model_combo)

        self._refresh_btn = QPushButton("Odśwież")
        self._refresh_btn.setObjectName("refresh_btn")
        self._refresh_btn.setFixedWidth(88)
        self._refresh_btn.clicked.connect(self._refresh_models)
        model_row.addWidget(self._refresh_btn)

        layout.addLayout(model_row)

        # --- Status bar ---
        status_frame = QFrame()
        status_frame.setObjectName("status_frame")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 6, 10, 6)
        status_layout.setSpacing(8)

        status_dot_label = QLabel("Status:")
        status_layout.addWidget(status_dot_label)

        self._status_label = QLabel("Zatrzymany")
        self._status_label.setObjectName("status_label")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        layout.addWidget(status_frame)

        # --- Log view ---
        self._log_view = QPlainTextEdit()
        self._log_view.setObjectName("log_view")
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(MAX_LOG_LINES)
        log_font = QFont("Consolas", 9)
        log_font.setStyleHint(QFont.StyleHint.Monospace)
        self._log_view.setFont(log_font)
        self._log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._log_view)

        # --- Control buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._reset_cooldown_btn = QPushButton("Resetuj cooldown")
        self._reset_cooldown_btn.setObjectName("reset_cooldown_btn")
        self._reset_cooldown_btn.setFixedWidth(130)
        self._reset_cooldown_btn.setEnabled(False)
        self._reset_cooldown_btn.clicked.connect(self._on_reset_cooldown_clicked)
        btn_row.addWidget(self._reset_cooldown_btn)

        self._pause_btn = QPushButton("Pauza")
        self._pause_btn.setObjectName("pause_btn")
        self._pause_btn.setFixedWidth(110)
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._on_pause_clicked)
        btn_row.addWidget(self._pause_btn)

        self._start_stop_btn = QPushButton("▶  Start")
        self._start_stop_btn.setObjectName("start_stop_btn")
        self._start_stop_btn.setFixedWidth(130)
        self._start_stop_btn.clicked.connect(self._on_start_stop_clicked)
        btn_row.addWidget(self._start_stop_btn)

        layout.addLayout(btn_row)

        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QLabel {
                color: #c0c0c0;
            }
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                padding: 5px 10px;
                color: #e0e0e0;
                min-height: 28px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #444;
                selection-background-color: #3a6bc9;
                color: #e0e0e0;
            }
            QFrame#status_frame {
                background-color: #222;
                border: 1px solid #333;
                border-radius: 5px;
            }
            QLabel#status_label {
                font-weight: bold;
                color: #909090;
            }
            QPlainTextEdit#log_view {
                background-color: #111;
                border: 1px solid #2e2e2e;
                border-radius: 5px;
                color: #b8c8a0;
                padding: 4px;
                selection-background-color: #2d4a7a;
            }
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                padding: 6px 14px;
                color: #d0d0d0;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #333;
                border-color: #555;
            }
            QPushButton:pressed {
                background-color: #222;
            }
            QPushButton:disabled {
                color: #555;
                border-color: #2a2a2a;
            }
            QPushButton#start_stop_btn {
                background-color: #1e5c2e;
                border-color: #27763b;
                color: #c8f0d0;
                font-weight: bold;
            }
            QPushButton#start_stop_btn:hover {
                background-color: #236832;
            }
            QPushButton#start_stop_btn[running="true"] {
                background-color: #7a1c1c;
                border-color: #a02525;
                color: #f0c8c8;
            }
            QPushButton#start_stop_btn[running="true"]:hover {
                background-color: #8e2020;
            }
            QPushButton#pause_btn:enabled {
                background-color: #3a3a1c;
                border-color: #5a5a25;
                color: #e8e0a0;
            }
            QPushButton#reset_cooldown_btn:enabled {
                background-color: #2b3a42;
                border-color: #3e5866;
                color: #cde4ec;
            }
            QPushButton#reset_cooldown_btn:enabled:hover {
                background-color: #364954;
            }
            QPushButton#refresh_btn {
                background-color: #1e2e50;
                border-color: #2a4080;
                color: #a8c8f0;
            }
            QPushButton#refresh_btn:hover {
                background-color: #243460;
            }
        """)

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def _refresh_models(self) -> None:
        self._model_combo.clear()
        agents = list_agents(self._models_root)
        for agent in agents:
            self._model_combo.addItem(agent.display_name, userData=agent)
        if not agents:
            self._model_combo.addItem("— brak modeli w models/ —", userData=None)
            self._start_stop_btn.setEnabled(False)
        else:
            self._start_stop_btn.setEnabled(True)

    def _current_agent(self) -> AgentEntry | None:
        return self._model_combo.currentData()

    # ------------------------------------------------------------------
    # Bot control
    # ------------------------------------------------------------------

    def _on_start_stop_clicked(self) -> None:
        if self._worker is None or not self._worker.isRunning():
            self._start_bot()
        else:
            self._stop_bot()

    def _start_bot(self) -> None:
        agent = self._current_agent()
        if agent is None:
            QMessageBox.warning(self, "Brak modelu", "Wybierz model przed uruchomieniem bota.")
            return

        self._log_view.clear()
        self._worker = BotWorker(agent.path, self._adb_address)
        self._worker.status_changed.connect(self._on_status_changed)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

        self._model_combo.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        self._reset_cooldown_btn.setEnabled(True)
        self._pause_btn.setEnabled(True)
        self._pause_btn.setText("Pauza")
        self._start_stop_btn.setText("■  Stop")
        self._start_stop_btn.setProperty("running", "true")
        self._start_stop_btn.style().unpolish(self._start_stop_btn)
        self._start_stop_btn.style().polish(self._start_stop_btn)

    def _stop_bot(self) -> None:
        if self._worker is None:
            return
        self._set_status("Zatrzymuję...", "#c09030")
        self._start_stop_btn.setEnabled(False)
        self._pause_btn.setEnabled(False)
        self._reset_cooldown_btn.setEnabled(False)
        self._worker.request_stop()
        # Nieblokujące – on_worker_finished wywoła się gdy QThread skończy
        QTimer.singleShot(100, self._poll_worker_stop)

    def _poll_worker_stop(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            QTimer.singleShot(200, self._poll_worker_stop)
        else:
            self._on_worker_finished()

    def _on_pause_clicked(self) -> None:
        if self._worker is None:
            return
        is_paused = self._worker.toggle_pause()
        self._pause_btn.setText("Wznów" if is_paused else "Pauza")

    def _on_reset_cooldown_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.reset_cooldown()
            logging.info("Zadanie natychmiastowego resetu cooldownu wyslane do bota.")

    def _on_worker_finished(self) -> None:
        self._model_combo.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        self._reset_cooldown_btn.setEnabled(False)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("Pauza")
        self._start_stop_btn.setEnabled(True)
        self._start_stop_btn.setText("▶  Start")
        self._start_stop_btn.setProperty("running", "false")
        self._start_stop_btn.style().unpolish(self._start_stop_btn)
        self._start_stop_btn.style().polish(self._start_stop_btn)
        self._set_status("Zatrzymany", "#909090")

    # ------------------------------------------------------------------
    # Status & log helpers
    # ------------------------------------------------------------------

    def _on_status_changed(self, status: str) -> None:
        mapping = {
            "running": ("Działa", "#40c060"),
            "paused": ("Wstrzymany", "#c0a030"),
            "stopped": ("Zatrzymany", "#909090"),
        }
        text, color = mapping.get(status, ("Nieznany", "#909090"))
        self._set_status(text, color)

    def _set_status(self, text: str, color: str) -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"font-weight: bold; color: {color};")

    def _on_error(self, message: str) -> None:
        logging.error("BotWorker error: %s", message)
        QMessageBox.critical(self, "Błąd uruchamiania bota", message)

    def _append_log(self, line: str) -> None:
        self._log_view.appendPlainText(line)
        self._log_view.moveCursor(QTextCursor.MoveOperation.End)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(5000)
        super().closeEvent(event)
