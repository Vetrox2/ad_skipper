# Ad Skipper

Automated advertisement skipper for BlueStacks and Android emulators using ADB and YOLOv8 object detection.

## Requirements

- Python 3.12.2
- `adb` available in `PATH`
- Running BlueStacks (or another Android emulator) with ADB debugging enabled
- Trained YOLOv8 model weights (`best.pt`) and `config.json` inside the agent's directory (e.g. `models/badoo/`)

## Installation

1. Install dependencies using Pipenv:
   ```bash
   pipenv install
   ```

2. Configure environment settings:
   Copy `.env.example` to `.env` and adjust the settings as needed:
   ```bash
   cp .env.example .env
   ```

## Running

### GUI Mode (Recommended)
Launch the graphical interface:
```bash
pipenv run gui
```
Features available in the GUI:
- Model selector dropdown (scans `models/` directory)
- Live execution logs
- **Start / Stop** execution
- **Pause / Resume** bot scanning
- **Reset cooldown** (skips current delay and triggers an immediate scan)

### CLI Mode (Headless)
Run the bot directly in the terminal using configuration from `.env`:
```bash
pipenv run start
```
*(or `python -m src.ad_skipper`)*

## Dataset Preparation & Training

1. Export raw YOLO dataset (e.g. from Roboflow) into `dataset/`:
   ```text
   ├── dataset/
   │   ├── data.yaml
   │   ├── train/
   │   │   ├── images/
   │   │   └── labels/
   │   ├── valid/
   │   │   ├── images/
   │   │   └── labels/
   │   └── test/
   │       ├── images/
   │       └── labels/
   └── runs/detect/train/weights/best.pt  ← Resulting weights after training
   ```

2. Train the model:
   ```bash
   pipenv run yolo detect train data=dataset/data.yaml model=yolov8n.pt epochs=100 imgsz=640
   ```

3. Copy the resulting `best.pt` into your agent directory (e.g. `models/<agent_name>/`) and create a `config.json` mapping detected classes to action tools.

## Configuration (`.env`)

Settings used by the CLI runner and default bot runtime:

| Variable | Default | Description |
|---|---|---|
| `AD_SKIPPER_AGENT_DIR` | `models/badoo` | Path to the agent folder containing `best.pt` and `config.json` |
| `AD_SKIPPER_MODEL_PATH` | *(empty)* | Optional direct override path to model weights (`.pt`) |
| `AD_SKIPPER_ADB_ADDRESS` | `127.0.0.1:5555` | Emulator ADB network address |
| `AD_SKIPPER_CONF_THRESHOLD` | `0.3` | Minimum YOLO detection confidence threshold |
| `AD_SKIPPER_SCAN_INTERVAL` | `2.0` | Interval in seconds between screen captures |
| `AD_SKIPPER_CLICK_COOLDOWN` | `4.0` | Cooldown period (in seconds) after executing an action |
| `AD_SKIPPER_ANOMALY_REPEATS` | `5` | Repeated identical clicks before triggering anomaly protection |
| `AD_SKIPPER_ANOMALY_PAUSE` | `10.0` | Pause duration (seconds) when a false-positive loop is detected |
| `AD_SKIPPER_VERBOSE` | `false` | Enable verbose DEBUG logging |

## Agent Structure & Tools

Each agent directory contains its model weights and action mapping:
```text
models/badoo/
├── best.pt
└── config.json
```

### Example `config.json`:
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
  },
  {
    "class": "store_logo",
    "tool_path": "tools/switch_app.py",
    "tool_class": "SwitchAppTool",
    "priority": 80,
    "params": {
      "package": "com.badoo.mobile",
      "sleep_s": 4.0,
      "close_source_package": "com.android.vending"
    }
  }
]
```

### Tool Resolution Order
Tool scripts (e.g. `tools/click.py`) are resolved in the following priority:
1. `tools/` in application root (or `src/ad_skipper/tools/`)
2. `models/<agent_name>/tools/` (for agent-specific custom tools)

### Available Built-in Tools
- **`ClickTool` (`tools/click.py`)**: Computes bounding box center and performs an ADB tap. Supports custom `sleep_s` cooldown in `params`.
- **`SwitchAppTool` (`tools/switch_app.py`)**: Returns to the target application (`params.package`) if an ad redirects to external stores or apps. Optionally force-stops the redirect source (`params.close_source_package`).

## Safeguards & Anomaly Detection

- **Automatic ADB Reconnection**: Re-initializes ADB connection on screencap failure.
- **False-Positive Loop Detection**: If the exact same coordinate is clicked repeatedly on an unchanged frame hash, execution pauses for `AD_SKIPPER_ANOMALY_PAUSE` seconds.

## Building Standalone Executable (.exe)

Build a self-contained Windows distribution via PyInstaller:
```bash
pipenv run build
# Or build with a specific version:
python build.py 1.0.0
```
The output package is placed in `dist/ad_skipper_v<version>/` and includes:
- `ad_skipper.exe` (windowed GUI application)
- `_internal/` (PyInstaller runtime bundle)
- `tools/` (editable action scripts, loaded dynamically)
- `models/` (model directories)
- `.env` (configuration file)
- `assets/` & `README.txt`

## Releasing on GitHub

1. *(Optional)* Add your changelog into `release_notes.md` in the project root.
2. Deploy the release:
   ```bash
   pipenv run release
   # Or release a specific version:
   python release.py 1.0.0
   ```
This compresses the distribution directory into `dist/ad_skipper_v<version>.zip` and creates/updates a GitHub Release with the ZIP asset and release notes. Authentication is handled automatically via your logged-in Git session (Git Credential Manager), `gh` CLI, or optional `GITHUB_TOKEN`.
