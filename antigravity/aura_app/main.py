"""
AURA — PySide6 Desktop Admin Dashboard (by DARK intelligence)
Entry point: creates QApplication, applies theme, and runs the main window.
"""

import sys
import multiprocessing

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from .theme import LIGHT_QSS
from .app_window import AuraApp


def run():
    """Launch the AURA admin dashboard."""
    multiprocessing.freeze_support()

    import ctypes
    myappid = u'dark_intelligence.aura.admin.2.0.0'  # unique string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)

    # Set global font
    app.setFont(QFont("Segoe UI", 10))

    # Apply light theme by default
    app.setStyleSheet(LIGHT_QSS)

    # Create and show main window
    window = AuraApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
