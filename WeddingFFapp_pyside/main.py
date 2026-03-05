"""
Wedding FaceForward — PySide6 Desktop Admin Dashboard
Entry point: creates QApplication, applies theme, and runs the main window.
"""

import sys
import multiprocessing

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from .theme import LIGHT_QSS
from .app_window import WeddingFFApp


def run():
    """Launch the Wedding FaceForward admin dashboard."""
    multiprocessing.freeze_support()

    import ctypes
    myappid = u'wedding_faceforward.admin.1.0'  # unique string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)

    # Set global font
    app.setFont(QFont("Segoe UI", 10))

    # Apply light theme by default
    app.setStyleSheet(LIGHT_QSS)

    # Create and show main window
    window = WeddingFFApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
