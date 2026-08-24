# Project: Ad Skipper

Automated advertisement skipper for BlueStacks and Android emulators utilizing ADB and YOLOv8 object detection.

## Project Structure
- `src/ad_skipper/bot.py` - Core bot loop capturing screens via ADB and running YOLO inference.
- `src/ad_skipper/adb.py` - ADB communication wrappers (`pure-python-adb` / adb CLI commands).
- `src/ad_skipper/config.py` - Agent configuration and dynamic tool path resolution.
- `src/ad_skipper/runtime.py` - Dynamic module loading for tools and `AgentRuntime` lifecycle.
- `src/ad_skipper/env_settings.py` - Environment configuration loading (`.env` parser).
- `src/ad_skipper/paths.py` - Application root path helper (frozen PyInstaller / development source mode).
- `src/ad_skipper/tools/` - Built-in action tools executed upon object detection:
  - `base.py` - `BaseTool` abstract base class, `DetectionContext`, `ToolServices`.
  - `click.py` - `ClickTool` for tapping detected target coordinates.
  - `switch_app.py` - `SwitchAppTool` for refocusing the target app and closing redirects.
- `src/ad_skipper/gui/` - GUI application module (PySide6):
  - `__main_gui__.py` - GUI entry point (`MainWindow`).
  - `main_window.py` - Main window (model selection, live log view, Start/Stop/Pause, Cooldown reset).
  - `bot_worker.py` - `BotWorker(QThread)` wrapping `AdSkipperBot` with thread-safe stop/pause/cooldown events.
  - `log_handler.py` - `QtLogHandler` logging handler emitting Qt signals to the UI.
  - `model_scanner.py` - `list_agents()` scanning `models/` for available agents.
- `models/<agent_name>/` - Agent directories containing `best.pt` weights and `config.json` action definitions.
- `dataset/` - Directory for raw YOLO datasets (e.g. Roboflow exports).
- `runs/` - Output directory from YOLO training runs.
- `dist/` - Output directory containing built distribution packages (`dist/ad_skipper_v<version>/`).
- `build.py` - PyInstaller distribution build script with automatic version bumping.
- `ad_skipper.spec` - PyInstaller spec configuration (windowed GUI entry point).
- `VERSION` - File storing current project version.

## Running and Building
Environment managed via `pipenv` (Python 3.12.2).
- Install dependencies: `pipenv install`
- Run GUI: `pipenv run gui`
- Run CLI bot: `pipenv run start` (or `python -m src.ad_skipper`)
- Train YOLO: `pipenv run yolo detect train data=dataset/data.yaml model=yolov8n.pt epochs=100 imgsz=640`
- Build distribution (.exe):
  - `pipenv run build` (or `python build.py`) - auto-increments minor version (+1)
  - `python build.py 1.0.0` (or `-v 1.0.0` / `--version 1.0.0`) - builds specific version
  - Build output is placed in `dist/ad_skipper_v<version>/` (contains `.exe`, `_internal/`, `tools/`, `models/`, `.env`, `README.txt`).

## Tool Architecture & Configuration
Each agent defines detection-to-action bindings in `config.json`:
```json
[
  {
    "class": "close_button",
    "tool_path": "tools/click.py",
    "tool_class": "ClickTool",
    "priority": 100,
    "params": {
      "sleep_s": 2.0
    }
  }
]
```
Tools receive `DetectionContext` (class name, confidence, bounding box, center coordinates, frame hash, extra params) and execute actions via `ToolServices`.

## AI Guidelines
- Keep responses concise and focused on the requested code or modifications.
- Do not explain obvious Python, YOLO, or ADB concepts unless explicitly requested.
- When modifying classes/functions, show primarily changed sections.
- Maintain modularity – adhere to `BaseTool` and unified service interfaces.
- Write code compliant with static typing in Python.
