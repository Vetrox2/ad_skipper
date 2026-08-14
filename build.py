"""Builds ad_skipper distribution with versioning into dist/ad_skipper_v<version>/."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_ROOT = ROOT / "dist"
VERSION_FILE = ROOT / "VERSION"
DEFAULT_INITIAL_VERSION = "0.1.0"


def parse_version(v: str) -> tuple[int, int, int]:
    cleaned = v.lstrip("vV").strip()
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", cleaned)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) is not None else 0
        return (major, minor, patch)
    return (0, 0, 0)


def bump_minor(version_str: str) -> str:
    major, minor, _ = parse_version(version_str)
    return f"{major}.{minor + 1}.0"


def get_latest_version() -> str:
    versions: list[str] = []

    if VERSION_FILE.exists():
        v = VERSION_FILE.read_text(encoding="utf-8").strip()
        if v:
            versions.append(v)

    if DIST_ROOT.exists():
        for item in DIST_ROOT.iterdir():
            if item.is_dir():
                m = re.search(r"(\d+\.\d+(?:\.\d+)?)", item.name)
                if m:
                    versions.append(m.group(1))

    if not versions:
        return DEFAULT_INITIAL_VERSION

    return max(versions, key=parse_version)


def get_dist_dir(version: str) -> Path:
    cleaned = version.strip()
    if not cleaned.startswith(("v", "V")):
        folder_name = f"ad_skipper_v{cleaned}"
    else:
        folder_name = f"ad_skipper_{cleaned}"
    return DIST_ROOT / folder_name


def run_pyinstaller(dist_folder_name: str) -> None:
    env = os.environ.copy()
    env["AD_SKIPPER_DIST_NAME"] = dist_folder_name

    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "ad_skipper.spec", "--noconfirm"],
        cwd=ROOT,
        env=env,
        check=True,
    )


def copy_tools(dist_dir: Path) -> None:
    src = ROOT / "src" / "ad_skipper" / "tools"
    dst = dist_dir / "tools"
    dst.mkdir(parents=True, exist_ok=True)
    for py_file in src.glob("*.py"):
        shutil.copy2(py_file, dst / py_file.name)
    print(f"  Copied tools/: {[f.name for f in src.glob('*.py')]}")


def ensure_models_dir(dist_dir: Path) -> None:
    models_dir = dist_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)


def copy_env_file(dist_dir: Path) -> None:
    example_src = ROOT / ".env.example"
    dst = dist_dir / ".env"
    if example_src.exists():
        shutil.copy2(example_src, dst)
        print("  Created .env from .env.example")


def copy_assets(dist_dir: Path) -> None:
    assets_src = ROOT / "assets"
    dst = dist_dir / "assets"
    if assets_src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(assets_src, dst)
        print(f"  Copied assets/: {[f.name for f in assets_src.glob('*')]}")



def create_readme(dist_dir: Path, version: str) -> None:
    readme_path = dist_dir / "README.txt"
    content = f"""================================================================================
                               AD SKIPPER (v{version.lstrip('vV')})
================================================================================

ABOUT THE PROJECT:
------------------
Ad Skipper is an automated bot designed to detect and skip/close advertisements
on Android emulators (e.g. BlueStacks) using an ADB connection and YOLOv8
object detection.

Key Architectural Concepts:
1. Custom Models (`models/` directory):
   You can train and add your own agents (weights `best.pt` + config `config.json`),
   which map detected objects and buttons to specific actions.
2. Custom Action Handlers (`tools/` directory):
   Python scripts in the `tools/` folder (e.g. `click.py`, `switch_app.py`) are loaded
   dynamically at runtime. You can modify existing handlers or add new ones
   without needing to recompile the application (.exe).


HOW TO CONFIGURE AND RUN:
-------------------------
1. Make sure BlueStacks (or your Android emulator) is running with ADB debugging enabled.
2. Place your model and configuration in a subfolder within `models/`, e.g.:
     models/my_agent/best.pt
     models/my_agent/config.json
3. Adjust the settings in the `.env` file located in the application root directory.
4. Launch `ad_skipper.exe`.


CONFIGURATION IN .ENV:
----------------------
You can configure the following parameters in `.env`:

- AD_SKIPPER_AGENT_DIR:
    Path to the selected agent directory (e.g. `models/badoo`). This directory
    must contain `best.pt` and `config.json`.

- AD_SKIPPER_MODEL_PATH:
    (Optional) Direct path to model weights `.pt`. If set, overrides the model
    specified in the agent's config.json.

- AD_SKIPPER_ADB_ADDRESS:
    ADB connection address and port for the emulator (default: 127.0.0.1:5555).

- AD_SKIPPER_CONF_THRESHOLD:
    Minimum YOLO confidence threshold (e.g. 0.3 for 30%). Detections below
    this threshold are ignored.

- AD_SKIPPER_SCAN_INTERVAL:
    Interval in seconds between consecutive screen captures (default: 2.0).

- AD_SKIPPER_CLICK_COOLDOWN:
    Cooldown time in seconds after performing an action/click before resuming
    screen scans (default: 4.0).

- AD_SKIPPER_ANOMALY_REPEATS:
    Number of consecutive clicks on the exact same coordinate without screen changes
    before considering it a false-positive loop (default: 5).

- AD_SKIPPER_ANOMALY_PAUSE:
    Pause duration in seconds when a loop anomaly is detected (default: 10.0).

- AD_SKIPPER_VERBOSE:
    Enable verbose DEBUG logging in console: true or false (default: false).
"""
    readme_path.write_text(content, encoding="utf-8")
    print("  README.txt generated in the root build directory")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ad_skipper distribution with versioning.")
    parser.add_argument(
        "version_pos",
        nargs="?",
        default=None,
        help="Target version (e.g. 1.2.0). If omitted, automatically increments the minor version.",
    )
    parser.add_argument(
        "-v",
        "--version",
        dest="version_flag",
        default=None,
        help="Target version (e.g. 1.2.0). If omitted, automatically increments the minor version.",
    )
    args = parser.parse_args()

    provided_version = args.version_flag or args.version_pos

    if provided_version:
        target_version = provided_version.strip()
    else:
        latest = get_latest_version()
        target_version = bump_minor(latest)

    normalized_version = target_version.lstrip("vV")
    target_dist = get_dist_dir(target_version)

    print(f"=== Building ad_skipper (version: v{normalized_version}) ===")
    print(f"Target directory: {target_dist}")

    print("1/5 PyInstaller...")
    run_pyinstaller(target_dist.name)

    print("2/5 Copying tools/...")
    copy_tools(target_dist)

    print("3/5 Creating models/ directory...")
    ensure_models_dir(target_dist)

    print("4/6 Generating .env...")
    copy_env_file(target_dist)

    print("5/6 Copying assets/...")
    copy_assets(target_dist)

    print("6/6 Generating README.txt...")
    create_readme(target_dist, target_version)


    VERSION_FILE.write_text(normalized_version + "\n", encoding="utf-8")

    print(f"\nBuild complete: {target_dist}")


if __name__ == "__main__":
    main()
