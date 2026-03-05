"""
ProcessManager — Manages backend and frontend subprocesses.
COPIED UNCHANGED from WeddingFFapp.py lines 1193-1330.
Only change: this is now in its own module instead of the monolithic file.
"""

import os
import sys
import subprocess
import threading
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"


class ProcessManager:
    """Manages backend and frontend processes."""

    def __init__(self, on_output=None):
        self.worker_proc = None
        self.server_proc = None
        self.whatsapp_proc = None
        self.on_output = on_output
        self._reader_threads = []

    def start(self):
        """Start backend worker and frontend server."""
        if self.is_running():
            return

        env = os.environ.copy()
        env["PYTHONPATH"] = (
            str(BACKEND_DIR) + os.pathsep +
            str(FRONTEND_DIR) + os.pathsep +
            env.get("PYTHONPATH", "")
        )
        env["PYTHONUTF8"] = "1"

        try:
            self.worker_proc = subprocess.Popen(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0, 'backend'); from app.worker import main; main()"],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            t = threading.Thread(
                target=self._read_output,
                args=(self.worker_proc, "Worker"),
                daemon=True
            )
            t.start()
            self._reader_threads.append(t)
        except Exception as e:
            if self.on_output:
                self.on_output(f"Worker start failed: {e}", "error")
            return

        try:
            self.server_proc = subprocess.Popen(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0, 'backend'); sys.path.insert(0, 'frontend'); "
                 "from server import app; import uvicorn; "
                 "uvicorn.run(app, host='0.0.0.0', port=8000, log_level='warning')"],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            t = threading.Thread(
                target=self._read_output,
                args=(self.server_proc, "Server"),
                daemon=True
            )
            t.start()
            self._reader_threads.append(t)
        except Exception as e:
            if self.on_output:
                self.on_output(f"Server start failed: {e}", "error")

        try:
            self.whatsapp_proc = subprocess.Popen(
                [sys.executable, "whatsapp_tool/db_whatsapp_sender.py"],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            t = threading.Thread(
                target=self._read_output,
                args=(self.whatsapp_proc, "WhatsApp"),
                daemon=True
            )
            t.start()
            self._reader_threads.append(t)
        except Exception as e:
            if self.on_output:
                self.on_output(f"WhatsApp Sender start failed: {e}", "error")

    def _read_output(self, proc, name):
        """Read subprocess output and send to callback."""
        try:
            for line in iter(proc.stdout.readline, ''):
                if line and self.on_output:
                    line = line.strip()
                    if line:
                        line_lower = line.lower()
                        if "error" in line_lower or "exception" in line_lower or "traceback" in line_lower:
                            self.on_output(f"[{name}] {line}", "error")
                        elif "warning" in line_lower:
                            self.on_output(f"[{name}] {line}", "warning")
                        elif line.startswith("2026-") or line.startswith("2025-"):
                            parts = line.split("|", 2)
                            if len(parts) >= 3:
                                logger = parts[1].strip()
                                msg = parts[-1].strip()
                                self.on_output(f"[{name}] {logger} | {msg}", "info")
                            else:
                                self.on_output(f"[{name}] {line}", "info")
                        else:
                            self.on_output(f"[{name}] {line}", "info")
        except Exception as e:
            if self.on_output:
                self.on_output(f"[{name}] Output reader error: {e}", "error")

    def stop(self):
        """Stop all processes."""
        if self.worker_proc:
            self.worker_proc.terminate()
            try:
                self.worker_proc.wait(timeout=5)
            except Exception:
                self.worker_proc.kill()
            self.worker_proc = None

        if self.server_proc:
            self.server_proc.terminate()
            try:
                self.server_proc.wait(timeout=5)
            except Exception:
                self.server_proc.kill()
            self.server_proc = None

        if self.whatsapp_proc:
            self.whatsapp_proc.terminate()
            try:
                self.whatsapp_proc.wait(timeout=5)
            except Exception:
                self.whatsapp_proc.kill()
            self.whatsapp_proc = None

        self._reader_threads = []

    def is_running(self):
        """Check if processes are running."""
        worker_alive = self.worker_proc and self.worker_proc.poll() is None
        server_alive = self.server_proc and self.server_proc.poll() is None
        whatsapp_alive = self.whatsapp_proc and self.whatsapp_proc.poll() is None
        return worker_alive or server_alive or whatsapp_alive
