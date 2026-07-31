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


def switch_to_app(adb_address: str, package_name: str) -> bool:
    """Przelacza (przywraca na pierwszy plan) aplikacje o podanym package_name.

    Wykorzystuje `monkey -p <package> -c android.intent.category.LAUNCHER 1`,
    czyli standardowy trik ADB do wystrzelenia glownego (launcher) intenta
    aplikacji bez znajomosci pelnej nazwy Activity. Jesli aplikacja juz dziala
    w tle (typowy przypadek po przekierowaniu z reklamy do Google Play /
    przegladarki), Android z reguly przywraca istniejacy task na pierwszy
    plan zamiast tworzyc nowa instancje.
    """
    try:
        result = subprocess.run(
            [
                "adb",
                "-s",
                adb_address,
                "shell",
                "monkey",
                "-p",
                package_name,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        logging.warning("Timeout podczas przelaczania na aplikacje %s.", package_name)
        return False

    if result.returncode != 0:
        logging.warning(
            "Nie udalo sie przelaczyc na aplikacje %s (kod %s): %s",
            package_name,
            result.returncode,
            result.stderr.decode(errors="ignore").strip(),
        )
        return False

    output = result.stdout.decode(errors="ignore")
    if "No activities found" in output or "Events injected: 1" not in output:
        logging.warning(
            "Monkey nie potwierdzil przelaczenia na %s (prawdopodobnie zla nazwa pakietu): %s",
            package_name,
            output.strip(),
        )
        return False

    return True


def force_stop_app(adb_address: str, package_name: str) -> bool:
    """Opcjonalnie zamyka (force-stop) podana aplikacje - np. zrodlowa
    aplikacje (Google Play / przegladarke), z ktorej bot przelacza sie na
    cel. Nie jest wywolywane domyslnie, patrz `close_source_package` w
    konfiguracji toola switch_app.
    """
    try:
        result = subprocess.run(
            ["adb", "-s", adb_address, "shell", "am", "force-stop", package_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        logging.warning("Timeout podczas zamykania aplikacji %s.", package_name)
        return False

    if result.returncode != 0:
        logging.warning(
            "Nie udalo sie zamknac aplikacji %s: %s",
            package_name,
            result.stderr.decode(errors="ignore").strip(),
        )
        return False
    return True