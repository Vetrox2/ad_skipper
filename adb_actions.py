from __future__ import annotations

import logging
import subprocess


def tap(adb_address: str, x: int, y: int) -> bool:
    try:
        result = subprocess.run(
            ["adb", "-s", adb_address, "shell", "input", "tap", str(x), str(y)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        logging.warning("Timeout podczas wykonywania klikniecia ADB.")
        return False

    if result.returncode != 0:
        logging.warning("Nie udalo sie wykonac klikniecia ADB: %s", result.stderr.decode(errors="ignore").strip())
        return False
    return True