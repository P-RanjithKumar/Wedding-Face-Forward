"""
WeddingFFapp - Visual Admin Dashboard
Wedding Face Forward Photo Processing System

A user-friendly desktop application for monitoring and controlling
the photo processing pipeline. Designed for non-developers.
"""

import sys
import os
import subprocess
import threading
import time
import multiprocessing
from pathlib import Path
from datetime import datetime

# Add backend to path for imports
BASE_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(FRONTEND_DIR))

try:
    import customtkinter as ctk
except ImportError:
    print("CustomTkinter not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from app.config import get_config
from app.db import get_db


# =============================================================================
# Color Theme - Minimal White
# =============================================================================
COLORS = {
    "bg": ("#f5f5f7", "#1c1c1e"),
    "bg_card": ("#ffffff", "#2c2c2e"),
    "border": ("#e0e0e0", "#3a3a3c"),
    "accent": ("#007aff", "#0a84ff"),
    "success": ("#34c759", "#30d158"),
    "warning": ("#ff9500", "#ff9f0a"),
    "error": ("#ff3b30", "#ff453a"),
    "text_primary": ("#1d1d1f", "#ffffff"),
    "text_secondary": ("#86868b", "#98989d"),
}


# =============================================================================
# Animated Status Indicator
# =============================================================================
class StatusIndicator(ctk.CTkFrame):
    """Animated status dot with label."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.dot = ctk.CTkLabel(self, text="●", font=("SF Pro Display", 14), text_color=COLORS["text_secondary"])
        self.dot.pack(side="left", padx=(0, 6))
        
        self.label = ctk.CTkLabel(self, text="Stopped", font=("SF Pro Display", 13), text_color=COLORS["text_secondary"])
        self.label.pack(side="left")
        
        self._pulsing = False
        self._pulse_step = 0
    
    def set_running(self):
        self._pulsing = True
        self.label.configure(text="Running", text_color=COLORS["success"])
        self._pulse()
    
    def set_starting(self):
        self._pulsing = True
        self.label.configure(text="Starting...", text_color=COLORS["warning"])
        self._pulse()
    
    def set_stopping(self):
        self._pulsing = True
        self.label.configure(text="Stopping...", text_color=COLORS["warning"])
        self._pulse()
    
    def set_stopped(self):
        self._pulsing = False
        self.dot.configure(text_color=COLORS["text_secondary"])
        self.label.configure(text="Stopped", text_color=COLORS["text_secondary"])
    
    def _pulse(self):
        if not self._pulsing:
            return
        
        # Pulse between dim and bright
        # Pulse between dim and bright (Light, Dark)
        colors = [COLORS["success"], ("#5fd47a", "#4cd964"), COLORS["success"], ("#2aa64a", "#248a3d")]
        if "Stopping" in self.label.cget("text") or "Starting" in self.label.cget("text"):
            colors = [COLORS["warning"], ("#ffaa33", "#ffb340"), COLORS["warning"], ("#cc7700", "#d98816")]
        
        self.dot.configure(text_color=colors[self._pulse_step % len(colors)])
        self._pulse_step += 1
        
        self.after(400, self._pulse)


# =============================================================================
# Animated Button
# =============================================================================
class AnimatedButton(ctk.CTkButton):
    """Button with smooth hover transition."""
    
    def __init__(self, parent, **kwargs):
        self._base_color = kwargs.get("fg_color", COLORS["accent"])

        self._hover_color = kwargs.get("hover_color", ("#005ecb", "#006bd6"))
        super().__init__(parent, **kwargs)
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    
    def _on_enter(self, e=None):
        self._animate_color(self._base_color, self._hover_color, 0)
    
    def _on_leave(self, e=None):
        self._animate_color(self._hover_color, self._base_color, 0)
    
    def _animate_color(self, start, end, step):
        if step > 5:
            return
        # Simple fade effect - just switch at step 2
        if step == 2:
            self.configure(fg_color=end)
        self.after(20, lambda: self._animate_color(start, end, step + 1))


# =============================================================================
# Stat Card Widget
# =============================================================================
class StatCard(ctk.CTkFrame):
    """A simple stat card with number and label."""
    
    def __init__(self, parent, title: str, value: str = "0", color: str = None):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        
        self._color = color or COLORS["text_primary"]
        self.value_label = ctk.CTkLabel(
            self, text=value, font=("SF Pro Display", 32, "bold"),
            text_color=self._color
        )
        self.value_label.pack(pady=(20, 5))
        
        self.title_label = ctk.CTkLabel(
            self, text=title, font=("SF Pro Display", 13),
            text_color=COLORS["text_secondary"]
        )
        self.title_label.pack(pady=(0, 20))
        
        self._last_value = value
    
    def update_value(self, value: str):
        if value != self._last_value:
            # Brief highlight animation on change
            self.value_label.configure(text_color=COLORS["accent"])
            self.after(300, lambda: self.value_label.configure(text_color=self._color))
            self.value_label.configure(text=value)
            self._last_value = value


# =============================================================================
# Status Section Widget
# =============================================================================
class StatusSection(ctk.CTkFrame):
    """A section with title and status rows."""
    
    def __init__(self, parent, title: str):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        
        self.title_label = ctk.CTkLabel(
            self, text=title, font=("SF Pro Display", 15, "bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(fill="x", padx=20, pady=(15, 10))
        
        self.rows = {}
    
    def add_row(self, key: str, label: str, value: str = "0"):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=3)
        
        lbl = ctk.CTkLabel(frame, text=label, font=("SF Pro Display", 13), text_color=COLORS["text_secondary"])
        lbl.pack(side="left")
        
        val = ctk.CTkLabel(frame, text=value, font=("SF Pro Display", 13, "bold"), text_color=COLORS["text_primary"])
        val.pack(side="right")
        
        self.rows[key] = val
        return val
    
    def update_row(self, key: str, value: str):
        if key in self.rows:
            self.rows[key].configure(text=value)
    
    def add_padding(self):
        ctk.CTkFrame(self, fg_color="transparent", height=10).pack()


# =============================================================================
# Activity Log Panel
# =============================================================================
class ActivityLog(ctk.CTkFrame):
    """Simple scrollable log."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        
        self.title_label = ctk.CTkLabel(
            self, text="Activity", font=("SF Pro Display", 15, "bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(fill="x", padx=20, pady=(15, 10))
        
        self.textbox = ctk.CTkTextbox(
            self, font=("SF Mono", 11),
            fg_color=COLORS["bg"],
            text_color=COLORS["text_secondary"],
            corner_radius=8, height=120
        )
        self.textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.textbox.configure(state="disabled")
        
        self.messages = []
    
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        icons = {"success": "✓", "warning": "!", "error": "✗", "info": "•"}
        icon = icons.get(level, "•")
        
        self.messages.insert(0, f"{timestamp}  {icon}  {message}")
        if len(self.messages) > 50:
            self.messages = self.messages[:50]
        
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", "\n".join(self.messages))
        self.textbox.configure(state="disabled")


# =============================================================================
# People List
# =============================================================================
class PeopleList(ctk.CTkScrollableFrame):
    """Simple list of identified persons."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12)
        self._last_hash = None
    
    def update_persons(self, persons: list, enrollments: dict):
        data_hash = str([(p.id, p.name, p.face_count) for p in persons])
        if data_hash == self._last_hash:
            return
        self._last_hash = data_hash
        
        for w in self.winfo_children():
            w.destroy()
        
        if not persons:
            ctk.CTkLabel(self, text="No people detected yet", font=("SF Pro Display", 13), text_color=COLORS["text_secondary"]).pack(pady=20)
            return
        
        for person in persons:
            enrollment = enrollments.get(person.id)
            name = enrollment.user_name if enrollment else person.name
            icon = "✓ " if enrollment else ""
            
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)
            
            ctk.CTkLabel(row, text=f"{icon}{name}", font=("SF Pro Display", 13), text_color=COLORS["text_primary"]).pack(side="left")
            ctk.CTkLabel(row, text=f"{person.face_count} photos", font=("SF Pro Display", 12), text_color=COLORS["text_secondary"]).pack(side="right")


# =============================================================================
# Process Manager
# =============================================================================
class ProcessManager:
    """Manages backend and frontend processes."""
    
    def __init__(self, on_output=None):
        self.worker_proc = None
        self.server_proc = None
        self.whatsapp_proc = None
        self.on_output = on_output  # Callback for output lines
        self._reader_threads = []
    
    def start(self):
        """Start backend worker and frontend server."""
        if self.is_running():
            return
        
        # Environment with PYTHONPATH set to include backend
        env = os.environ.copy()
        env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + str(FRONTEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        
        # Start worker process from project root (so EventRoot path is correct)
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
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            # Start output reader thread
            t = threading.Thread(target=self._read_output, args=(self.worker_proc, "Worker"), daemon=True)
            t.start()
            self._reader_threads.append(t)
        except Exception as e:
            if self.on_output:
                self.on_output(f"Worker start failed: {e}", "error")
            return
        
        # Start frontend server from project root
        try:
            self.server_proc = subprocess.Popen(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0, 'backend'); sys.path.insert(0, 'frontend'); from server import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000, log_level='warning')"],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            t = threading.Thread(target=self._read_output, args=(self.server_proc, "Server"), daemon=True)
            t.start()
            self._reader_threads.append(t)
        except Exception as e:
            if self.on_output:
                self.on_output(f"Server start failed: {e}", "error")

        # Start WhatsApp Sender
        try:
            self.whatsapp_proc = subprocess.Popen(
                [sys.executable, "whatsapp_tool/db_whatsapp_sender.py"],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            t = threading.Thread(target=self._read_output, args=(self.whatsapp_proc, "WhatsApp"), daemon=True)
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
                    # Clean up the line
                    line = line.strip()
                    if line:
                        # Show all output for debugging, with level based on content
                        line_lower = line.lower()
                        if "error" in line_lower or "exception" in line_lower or "traceback" in line_lower:
                            self.on_output(f"[{name}] {line}", "error")
                        elif "warning" in line_lower:
                            self.on_output(f"[{name}] {line}", "warning")
                        elif line.startswith("2026-"):  # Timestamped log
                            # Extract message after timestamp
                            parts = line.split("|", 2)
                            if len(parts) >= 3:
                                msg = parts[-1].strip()
                                self.on_output(f"[{name}] {msg}", "info")
                            else:
                                self.on_output(f"[{name}] {line}", "info")
                        else:
                            self.on_output(f"[{name}] {line}", "info")
        except Exception as e:
            self.on_output(f"[{name}] Output reader error: {e}", "error")
    
    def stop(self):
        """Stop all processes."""
        if self.worker_proc:
            self.worker_proc.terminate()
            try:
                self.worker_proc.wait(timeout=5)
            except:
                self.worker_proc.kill()
            self.worker_proc = None
        
        if self.server_proc:
            self.server_proc.terminate()
            try:
                self.server_proc.wait(timeout=5)
            except:
                self.server_proc.kill()
            self.server_proc = None
        
        if self.whatsapp_proc:
            self.whatsapp_proc.terminate()
            try:
                self.whatsapp_proc.wait(timeout=5)
            except:
                self.whatsapp_proc.kill()
            self.whatsapp_proc = None
        
        self._reader_threads = []
    
    def is_running(self):
        """Check if processes are running."""
        worker_alive = self.worker_proc and self.worker_proc.poll() is None
        server_alive = self.server_proc and self.server_proc.poll() is None
        whatsapp_alive = self.whatsapp_proc and self.whatsapp_proc.poll() is None
        return worker_alive or server_alive or whatsapp_alive


# =============================================================================
# Main Application
# =============================================================================
class WeddingFFApp(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.title("WeddingFFapp")
        self.geometry("900x750")
        self.configure(fg_color=COLORS["bg"])
        
        ctk.set_appearance_mode("light")
        
        self.config = get_config()
        # Don't keep persistent DB connection in main app to avoid conflicts with worker
        # Use get_db() on-demand instead
        
        self.last_photo_count = 0
        self.last_face_count = 0
        self.last_person_count = 0
        self.last_upload_stats = {}
        
        self._create_ui()
        
        # Create process manager with output callback
        self.process_manager = ProcessManager(on_output=self._on_worker_output)
        
        self.running = True
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        self.after(100, self._refresh_stats)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_worker_output(self, message, level):
        """Handle output from worker/server processes."""
        self.after(0, lambda: self.activity_log.add_log(message, level))
    
    def _create_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(25, 15))
        
        ctk.CTkLabel(header, text="Wedding Face Forward", font=("SF Pro Display", 24, "bold"), text_color=COLORS["text_primary"]).pack(side="left")
        
        # Right side controls
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right")
        
        self.status_indicator = StatusIndicator(controls)
        self.status_indicator.pack(side="left", padx=(0, 15))
        
        self.theme_btn = AnimatedButton(
            controls, text="◑  Theme", width=100, height=36, corner_radius=8,
            fg_color=COLORS["bg_card"], text_color=COLORS["text_primary"],
            hover_color=("#e5e5e5", "#3a3a3c"), font=("SF Pro Display", 13),
            command=self._toggle_theme
        )
        self.theme_btn.pack(side="left", padx=(0, 10))

        self.start_stop_btn = AnimatedButton(
            controls, text="▶  Start", width=100, height=36, corner_radius=8,
            fg_color=COLORS["success"], hover_color=("#2aa64a", "#248a3d"),
            font=("SF Pro Display", 13, "bold"),
            command=self._toggle_system
        )
        self.start_stop_btn.pack(side="left", padx=(0, 10))
        
        AnimatedButton(
            controls, text="Open Folder", width=100, height=36, corner_radius=8,
            fg_color=COLORS["border"], text_color=COLORS["text_primary"],
            hover_color=("#d0d0d0", "#48484a"), font=("SF Pro Display", 13),
            command=self._open_event_folder
        ).pack(side="left")
        
        # Stats Row
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=30, pady=(0, 15))
        for i in range(4):
            stats_frame.columnconfigure(i, weight=1)
        
        self.photos_card = StatCard(stats_frame, "Photos", "0")
        self.photos_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        
        self.faces_card = StatCard(stats_frame, "Faces", "0")
        self.faces_card.grid(row=0, column=1, padx=8, sticky="nsew")
        
        self.people_card = StatCard(stats_frame, "People", "0")
        self.people_card.grid(row=0, column=2, padx=8, sticky="nsew")
        
        self.enrolled_card = StatCard(stats_frame, "Enrolled", "0", COLORS["accent"])
        self.enrolled_card.grid(row=0, column=3, padx=(8, 0), sticky="nsew")
        
        # Main Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=(0, 15))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        
        # Left: Status Sections
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        
        self.queue_section = StatusSection(left, "Processing")
        self.queue_section.add_row("incoming", "Incoming", "0")
        self.queue_section.add_row("processing", "Processing", "Idle")
        self.queue_section.add_row("completed", "Completed", "0")
        self.queue_section.add_row("errors", "Errors", "0")
        self.queue_section.add_padding()
        self.queue_section.pack(fill="x", pady=(0, 10))
        
        self.cloud_section = StatusSection(left, "Cloud Sync")
        self.cloud_section.add_row("pending", "Pending", "0")
        self.cloud_section.add_row("uploading", "Uploading", "0")
        self.cloud_section.add_row("uploaded", "Uploaded", "0")
        self.cloud_section.add_row("failed", "Failed", "0")
        self.cloud_section.add_padding()
        self.cloud_section.pack(fill="x")
        
        # Right: People
        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        
        people_header = ctk.CTkFrame(right, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        people_header.pack(fill="both", expand=True)
        
        ctk.CTkLabel(people_header, text="People", font=("SF Pro Display", 15, "bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(15, 10))
        
        self.people_list = PeopleList(people_header)
        self.people_list.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Activity Log
        self.activity_log = ActivityLog(self)
        self.activity_log.pack(fill="x", padx=30, pady=(0, 25))
        
        self.activity_log.add_log("App started", "success")
    
    def _toggle_system(self):
        """Start or stop the system."""
        if self.process_manager.is_running():
            self._stop_system()
        else:
            self._start_system()
    
    def _start_system(self):
        """Start the backend and frontend."""
        self.status_indicator.set_starting()
        self.start_stop_btn.configure(state="disabled", text="Starting...")
        self.activity_log.add_log("Starting system...", "info")
        
        def start_async():
            try:
                self.process_manager.start()
                time.sleep(2)  # Give processes time to start
                self.after(0, self._on_system_started)
            except Exception as e:
                self.after(0, lambda: self._on_start_error(str(e)))
        
        threading.Thread(target=start_async, daemon=True).start()
    
    def _on_system_started(self):
        """Called when system has started."""
        self.status_indicator.set_running()
        self.start_stop_btn.configure(
            state="normal", text="■  Stop",
            fg_color=COLORS["error"], hover_color=("#cc2222", "#d63a3a")
        )
        self.activity_log.add_log("System running! Worker + Web server active", "success")
        self.activity_log.add_log("Web UI: http://localhost:8000", "info")
    
    def _on_start_error(self, error: str):
        """Called on start error."""
        self.status_indicator.set_stopped()
        self.start_stop_btn.configure(
            state="normal", text="▶  Start",

            fg_color=COLORS["success"], hover_color=("#2aa64a", "#248a3d")
        )
        self.activity_log.add_log(f"Start failed: {error}", "error")
    
    def _stop_system(self):
        """Stop the backend and frontend."""
        self.status_indicator.set_stopping()
        self.start_stop_btn.configure(state="disabled", text="Stopping...")
        self.activity_log.add_log("Stopping system...", "info")
        
        def stop_async():
            self.process_manager.stop()
            time.sleep(1)
            self.after(0, self._on_system_stopped)
        
        threading.Thread(target=stop_async, daemon=True).start()
    
    def _on_system_stopped(self):
        """Called when system has stopped."""
        self.status_indicator.set_stopped()
        self.start_stop_btn.configure(
            state="normal", text="▶  Start",

            fg_color=COLORS["success"], hover_color=("#2aa64a", "#248a3d")
        )
        self.activity_log.add_log("System stopped", "info")
    
    def _refresh_loop(self):
        while self.running:
            time.sleep(5)
            if self.running:
                self.after(0, self._refresh_stats)
    
    def _refresh_stats(self):
        try:
            db = get_db()
            stats = db.get_stats()
            photos_by_status = stats.get("photos_by_status", {})
            
            total = sum(photos_by_status.values())
            completed = photos_by_status.get("completed", 0) + photos_by_status.get("no_faces", 0)
            errors = photos_by_status.get("error", 0)
            processing = photos_by_status.get("processing", 0)
            
            self.photos_card.update_value(str(total))
            self.faces_card.update_value(str(stats.get("total_faces", 0)))
            self.people_card.update_value(str(stats.get("total_persons", 0)))
            self.enrolled_card.update_value(str(stats.get("total_enrollments", 0)))
            
            incoming = 0
            if self.config.incoming_dir.exists():
                incoming = len([f for f in self.config.incoming_dir.iterdir() if f.is_file() and f.suffix.lower() in self.config.supported_extensions])
            
            self.queue_section.update_row("incoming", str(incoming))
            self.queue_section.update_row("processing", f"{processing}..." if processing else "Idle")
            self.queue_section.update_row("completed", str(completed))
            self.queue_section.update_row("errors", str(errors))
            
            # Get upload stats with unique photo count
            upload_stats = db.get_upload_stats_unique()
            if upload_stats != self.last_upload_stats:
                by_status = upload_stats.get('by_status', {})
                unique_by_status = upload_stats.get('unique_by_status', {})
                
                # Get counts
                pending_total = by_status.get('pending', 0)
                uploading_total = by_status.get('uploading', 0)
                completed_total = by_status.get('completed', 0)
                failed_total = by_status.get('failed', 0)
                completed_unique = unique_by_status.get('completed', 0)
                
                self.cloud_section.update_row("pending", str(pending_total))
                self.cloud_section.update_row("uploading", str(uploading_total))
                # Show unique photos / total files for clarity when different
                if completed_unique != completed_total:
                    self.cloud_section.update_row("uploaded", f"{completed_unique} ({completed_total})")
                else:
                    self.cloud_section.update_row("uploaded", str(completed_total))
                self.cloud_section.update_row("failed", str(failed_total))
                self.last_upload_stats = upload_stats
            
            if total > self.last_photo_count:
                self.activity_log.add_log(f"{total - self.last_photo_count} new photo(s)", "info")
            if stats.get("total_faces", 0) > self.last_face_count:
                self.activity_log.add_log(f"{stats['total_faces'] - self.last_face_count} face(s) detected", "success")
            if stats.get("total_persons", 0) > self.last_person_count:
                self.activity_log.add_log(f"New person identified", "success")
            
            self.last_photo_count = total
            self.last_face_count = stats.get("total_faces", 0)
            self.last_person_count = stats.get("total_persons", 0)
            
            persons = db.get_all_persons()
            enrollments = {e.person_id: e for e in db.get_all_enrollments()}
            self.people_list.update_persons(persons, enrollments)
            
        except Exception as e:
            pass  # Silent fail on refresh
    
    def _open_event_folder(self):
        os.startfile(str(self.config.event_root))
        self.activity_log.add_log("Opened folder", "info")
    
    def _toggle_theme(self):
        """Toggle frame between light and dark mode."""
        curr = ctk.get_appearance_mode()
        new_mode = "Dark" if curr == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)

    def _on_close(self):
        """Handle window close - also stop services."""
        if self.process_manager.is_running():
            self.activity_log.add_log("Shutting down...", "info")
            self.process_manager.stop()
        self.running = False
        self.destroy()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = WeddingFFApp()
    app.mainloop()
