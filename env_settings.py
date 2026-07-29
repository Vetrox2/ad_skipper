from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv  # pip install python-dotenv
except ImportError:  # pragma: no cover - dziala tez bez zainstalowanego python-dotenv
    load_dotenv = None


# Domyslnie szukamy .env obok tego pliku (czyli w katalogu projektu).
DEFAULT_ENV_PATH = Path(__file__).resolve().parent / ".env"


def _load_env_file(env_path: Path) -> None:
    """Wczytuje plik .env do os.environ. Nie nadpisuje juz ustawionych zmiennych srodowiskowych."""
    if load_dotenv is not None:
        load_dotenv(dotenv_path=env_path, override=False)
        return

    # Prosty fallback bez zaleznosci python-dotenv: linie KEY=VALUE, '#' to komentarz.
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _get_str(name: str, default: str | None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _get_float(name: str, default: float | None) -> float | None:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int | None) -> int | None:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in ("1", "true", "tak", "yes", "on")


@dataclass(slots=True)
class EnvConfig:
    agent_dir: str
    model_override: str | None
    adb_address: str
    conf_threshold: float | None
    scan_interval: float
    click_cooldown: float
    anomaly_repeats: int
    anomaly_pause_s: float
    verbose: bool


def load_env_config(env_path: Path | None = None) -> EnvConfig:
    """Wczytuje ustawienia bota z pliku .env (lub ze zmiennych srodowiskowych, jesli juz ustawione).

    Kazde ustawienie jest opcjonalne - brak wpisu w .env oznacza uzycie tej samej
    wartosci domyslnej, ktora wczesniej byla domyslna wartoscia w argparse.
    """
    _load_env_file(env_path or DEFAULT_ENV_PATH)

    return EnvConfig(
        agent_dir=_get_str("AD_SKIPPER_AGENT_DIR", "models") or "models",
        model_override=_get_str("AD_SKIPPER_MODEL_PATH", None),
        adb_address=_get_str("AD_SKIPPER_ADB_ADDRESS", "127.0.0.1:5555") or "127.0.0.1:5555",
        conf_threshold=_get_float("AD_SKIPPER_CONF_THRESHOLD", None),
        scan_interval=_get_float("AD_SKIPPER_SCAN_INTERVAL", 2.0) or 2.0,
        click_cooldown=_get_float("AD_SKIPPER_CLICK_COOLDOWN", 4.0) or 4.0,
        anomaly_repeats=_get_int("AD_SKIPPER_ANOMALY_REPEATS", 5) or 5,
        anomaly_pause_s=_get_float("AD_SKIPPER_ANOMALY_PAUSE", 10.0) or 10.0,
        verbose=_get_bool("AD_SKIPPER_VERBOSE", False),
    )
