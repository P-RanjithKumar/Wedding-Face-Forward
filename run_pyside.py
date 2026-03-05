"""
Temporary Launcher for Wedding FaceForward (PySide6 version)
Run this file from the root directory: python run_pyside.py
"""

import sys
import multiprocessing

# Add the root directory to sys.path to resolve relative imports in the package
from WeddingFFapp_pyside.main import run

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
