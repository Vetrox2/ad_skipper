import ctypes
import logging
import sys

from PySide6.QtWidgets import QApplication

from src.ad_skipper.bot import configure_logging
from src.ad_skipper.gui.main_window import MainWindow, get_window_icon


def main() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("vetrox2.adskipper.gui.1.0")
        except Exception:
            pass

    configure_logging(verbose=False)
    app = QApplication(sys.argv)
    app.setApplicationName("Ad Skipper")

    icon = get_window_icon()
    if icon and not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

