from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    """Zwraca katalog, wzgledem ktorego szukamy models/, tools/, .env.

    - Po zamrozeniu (PyInstaller onedir): katalog, w ktorym lezy .exe.
    - W trybie zrodlowym: katalog repo (rodzic src/ad_skipper).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # src/ad_skipper/paths.py -> src/ad_skipper -> src -> repo root
    return Path(__file__).resolve().parent.parent.parent


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)
