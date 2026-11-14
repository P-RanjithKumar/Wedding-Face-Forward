"""
ProcessManager — starts and supervises the background processes:
worker (photo processing), server (guest web page) and WhatsApp sender.

2026-11-14 changes:
  * Guest port: the first free port from 8000 up is picked at start
    (dist_utils.pick_guest_port) instead of a hardcoded 8000 that silently
    failed when another program used it.
  * Supervisor: if the worker or server exits unexpectedly it is restarted
    (with a clear message and its last output lines). After MAX_RESTARTS
    crashes within RESTART_WINDOW_S it stops retrying and says so. WhatsApp
    is only reported, not restarted (closing its browser is often deliberate).
"""

import os
import sys
import time
import subprocess
import threading
from collections import deque
from pathlib import Path

import dist_utils

BASE_DIR = dist_utils.get_project_root()
BACKEND_DIR = dist_utils.get_backend_dir()
FRONTEND_DIR = dist_utils.get_frontend_dir()

CHECK_INTERVAL_S = 3
MAX_RESTARTS = 3
RESTART_WINDOW_S = 600
SUPERVISED = ("Worker", "Server")


class ProcessManager:
    """Manages backend and frontend processes."""

    def __init__(self, on_output=None):
        self.worker_proc = None
        self.server_proc = None
        self.whatsapp_proc = None
        self.on_output = on_output
        self.guest_port = dist_utils.get_guest_port()
        self._reader_threads = []
        self._env = None
        self._stopping = False
        self._supervisor = None
        self._recent = {}                     # name -> deque of last output lines
        self._restarts = {n: deque() for n in SUPERVISED}
        self._given_up = set()

    # ── commands ─────────────────────────────────────────────────────
    def _command(self, name):
        frozen = getattr(sys, 'frozen', False)
        if name == "Worker":
            return [sys.executable, "--run-worker"] if frozen else \
                [sys.executable, "-c", "import sys; sys.path.insert(0, 'backend'); from app.worker import main; main()"]
        if name == "Server":
            return [sys.executable, "--run-server"] if frozen else \
                [sys.executable, "-c",
                 "import os, sys; sys.path.insert(0, 'backend'); sys.path.insert(0, 'frontend'); "
                 "from server import app; import uvicorn; "
                 "uvicorn.run(app, host='0.0.0.0', port=int(os.environ['AURA_GUEST_PORT']), log_level='warning')"]
        return [sys.executable, "--run-whatsapp"] if frozen else \
            [sys.executable, "whatsapp_tool/db_whatsapp_sender.py"]

    def _launch(self, name):
        """Start one process and its output reader. Returns the Popen or None."""
        kwargs = dict(
            cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=self._env, bufsize=1, universal_newlines=True,
            encoding='utf-8', errors='replace',
        )
        if name == "WhatsApp":
            kwargs["stdin"] = subprocess.DEVNULL   # No stdin needed; avoids pipe issues
            # Do NOT use CREATE_NO_WINDOW here: Playwright's Chromium window must
            # be visible so the user can scan the QR code and see messages.
            kwargs["creationflags"] = 0
        else:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            proc = subprocess.Popen(self._command(name), **kwargs)
        except Exception as e:
            self._emit(f"{name} start failed: {e}", "error")
            return None
        self._recent[name] = deque(maxlen=15)
        t = threading.Thread(target=self._read_output, args=(proc, name), daemon=True)
        t.start()
        self._reader_threads.append(t)
        return proc

    def _set_proc(self, name, proc):
        setattr(self, {"Worker": "worker_proc", "Server": "server_proc", "WhatsApp": "whatsapp_proc"}[name], proc)

    def _get_proc(self, name):
        return {"Worker": self.worker_proc, "Server": self.server_proc, "WhatsApp": self.whatsapp_proc}[name]

    # ── public API (unchanged for callers) ───────────────────────────
    def start(self):
        """Start backend worker, guest web server and WhatsApp sender."""
        if self.is_running():
            return

        env = os.environ.copy()
        env["PYTHONPATH"] = (
            str(BACKEND_DIR) + os.pathsep +
            str(FRONTEND_DIR) + os.pathsep +
            env.get("PYTHONPATH", "")
        )
        env["PYTHONUTF8"] = "1"

        self.guest_port = dist_utils.pick_guest_port()
        env["AURA_GUEST_PORT"] = str(self.guest_port)
        if self.guest_port != dist_utils.DEFAULT_GUEST_PORT:
            self._emit(f"Port {dist_utils.DEFAULT_GUEST_PORT} is in use by another program; "
                       f"guest page uses port {self.guest_port} instead", "warning")
        self._env = env
        self._stopping = False
        self._given_up.clear()
        for q in self._restarts.values():
            q.clear()

        for name in ("Worker", "Server", "WhatsApp"):
            proc = self._launch(name)
            self._set_proc(name, proc)
            if proc is None and name == "Worker":
                return

        if self._supervisor is None or not self._supervisor.is_alive():
            self._supervisor = threading.Thread(target=self._supervise, daemon=True, name="ProcessSupervisor")
            self._supervisor.start()

    def stop(self):
        """Stop all processes."""
        self._stopping = True
        for name in ("Worker", "Server", "WhatsApp"):
            proc = self._get_proc(name)
            if proc:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
                self._set_proc(name, None)
        self._reader_threads = []

    def is_running(self):
        """Check if processes are running."""
        return any(p is not None and p.poll() is None
                   for p in (self.worker_proc, self.server_proc, self.whatsapp_proc))

    def guest_url(self, host="localhost"):
        return f"http://{host}:{self.guest_port}"

    # ── supervision ──────────────────────────────────────────────────
    def _supervise(self):
        reported_whatsapp = False
        while not self._stopping:
            time.sleep(CHECK_INTERVAL_S)
            if self._stopping:
                break
            for name in SUPERVISED:
                proc = self._get_proc(name)
                if proc is None or proc.poll() is None or name in self._given_up:
                    continue
                self._handle_crash(name, proc.returncode)
            wa = self.whatsapp_proc
            if wa is not None and wa.poll() is not None and not reported_whatsapp:
                reported_whatsapp = True
                self._emit(f"WhatsApp sender stopped (exit code {wa.returncode}). "
                           f"Stop and start processing to run it again.", "warning")

    def _handle_crash(self, name, code):
        last = " | ".join(list(self._recent.get(name, []))[-3:]) or "no output"
        self._emit(f"{name} stopped unexpectedly (exit code {code}). Last output: {last}", "error")
        now = time.time()
        history = self._restarts[name]
        while history and now - history[0] > RESTART_WINDOW_S:
            history.popleft()
        if len(history) >= MAX_RESTARTS:
            self._given_up.add(name)
            what = "photo processing" if name == "Worker" else "the guest page"
            self._emit(f"{name} crashed {MAX_RESTARTS + 1} times in {RESTART_WINDOW_S // 60} minutes; "
                       f"not restarting {what} again. Use Log to see the details, then Stop and Start.", "error")
            return
        history.append(now)
        self._emit(f"Restarting {name} (attempt {len(history)} of {MAX_RESTARTS})...", "warning")
        self._set_proc(name, self._launch(name))

    # ── output ───────────────────────────────────────────────────────
    def _emit(self, message, level):
        if self.on_output:
            self.on_output(message, level)

    def _read_output(self, proc, name):
        """Read subprocess output and send to callback."""
        recent = self._recent.get(name)
        try:
            for line in iter(proc.stdout.readline, ''):
                line = line.strip() if line else ""
                if not line:
                    continue
                if recent is not None:
                    recent.append(line[:200])
                if not self.on_output:
                    continue
                line_lower = line.lower()
                if "error" in line_lower or "exception" in line_lower or "traceback" in line_lower:
                    self.on_output(f"[{name}] {line}", "error")
                elif "warning" in line_lower:
                    self.on_output(f"[{name}] {line}", "warning")
                elif line[:2] == "20" and line[4:5] == "-":   # "2026-..." log line
                    parts = line.split("|", 2)
                    if len(parts) >= 3:
                        self.on_output(f"[{name}] {parts[1].strip()} | {parts[-1].strip()}", "info")
                    else:
                        self.on_output(f"[{name}] {line}", "info")
                else:
                    self.on_output(f"[{name}] {line}", "info")
        except Exception as e:
            self._emit(f"[{name}] Output reader error: {e}", "error")
