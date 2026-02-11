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

import tkinter as tk
import math

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
# Processing Widget (Animated)
# =============================================================================
class ProcessingWidget(ctk.CTkFrame):
    """Animated processing status with visual feedback."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        
        self.title_label = ctk.CTkLabel(
            self, text="Processing", font=("SF Pro Display", 15, "bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(fill="x", padx=20, pady=(15, 10))
        
        # Canvas for animation
        self.canvas_size = 140
        self.canvas = ctk.CTkCanvas(
            self, width=self.canvas_size, height=self.canvas_size,
            bg=COLORS["bg_card"][0], highlightthickness=0
        )
        self.canvas.pack(pady=10)
        
        self.status_label = ctk.CTkLabel(
            self, text="Idle", font=("SF Pro Display", 13),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(pady=(0, 15))
        
        self._animating = False
        self._angle = 0
        self._mode = "light"  # Track mode for canvas bg
        
        self.draw_static_ring()

    def set_appearance_mode(self, mode):
        self._mode = mode.lower()
        bg = COLORS["bg_card"][1] if self._mode == "dark" else COLORS["bg_card"][0]
        self.canvas.configure(bg=bg)
        self.draw_static_ring()

    def draw_static_ring(self):
        self.canvas.delete("all")
        cx, cy = self.canvas_size / 2, self.canvas_size / 2
        r = 50
        # Draw base ring
        color = "#3a3a3c" if self._mode == "dark" else "#e5e5e5"
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=4)

    def start_processing(self):
        if not self._animating:
            self._animating = True
            self.status_label.configure(text="Processing...", text_color=COLORS["accent"])
            self._animate()

    def stop_processing(self):
        self._animating = False
        self.status_label.configure(text="Idle", text_color=COLORS["text_secondary"])
        self.draw_static_ring()

    def _animate(self):
        if not self._animating:
            return
            
        self.canvas.delete("all")
        cx, cy = self.canvas_size / 2, self.canvas_size / 2
        r = 50
        
        # Draw base ring
        bg_color = "#3a3a3c" if self._mode == "dark" else "#e5e5e5"
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=bg_color, width=4)
        
        # Draw rotating arc
        start = self._angle
        extent = 90
        arc_color = COLORS["accent"][1] if self._mode == "dark" else COLORS["accent"][0]
        self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start, extent=extent, outline=arc_color, width=4, style="arc")
        
        # Pulse effect (inner circle)
        pulse_r = r * (0.5 + 0.1 * math.sin(math.radians(self._angle * 2)))
        fill_color = COLORS["accent"][1] if self._mode == "dark" else COLORS["accent"][0]
        # Use stipple for transparency simulation if needed, or just solid small circle
        self.canvas.create_oval(cx-pulse_r, cy-pulse_r, cx+pulse_r, cy+pulse_r, fill=fill_color, outline="")

        self._angle = (self._angle + 10) % 360
        self.after(50, self._animate)


# =============================================================================
# Cloud Widget (Animated)
# =============================================================================
class CloudWidget(ctk.CTkFrame):
    """Animated cloud upload status."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        
        self.title_label = ctk.CTkLabel(
            self, text="Cloud Sync", font=("SF Pro Display", 15, "bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(fill="x", padx=20, pady=(15, 10))
        
        # Canvas
        self.canvas_size = 140
        self.canvas = ctk.CTkCanvas(
            self, width=self.canvas_size, height=self.canvas_size,
            bg=COLORS["bg_card"][0], highlightthickness=0
        )
        self.canvas.pack(pady=10)
        
        self.status_label = ctk.CTkLabel(
            self, text="Synced", font=("SF Pro Display", 13),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(pady=(0, 15))
        
        self._uploading = False
        self._offset = 0
        self._mode = "light"
        
        self.draw_static_cloud()

    def set_appearance_mode(self, mode):
        self._mode = mode.lower()
        bg = COLORS["bg_card"][1] if self._mode == "dark" else COLORS["bg_card"][0]
        self.canvas.configure(bg=bg)
        if not self._uploading:
            self.draw_static_cloud()

    def draw_static_cloud(self):
        self.canvas.delete("all")
        self._draw_cloud_icon(offset=0, color=COLORS["text_secondary"][1] if self._mode == "dark" else COLORS["text_secondary"][0])

    def start_uploading(self):
        if not self._uploading:
            self._uploading = True
            self.status_label.configure(text="Uploading...", text_color=COLORS["accent"])
            self._animate()

    def stop_uploading(self):
        if self._uploading:
            self._uploading = False
            self.status_label.configure(text="Synced", text_color=COLORS["success"])
            self.draw_static_cloud()

    def _draw_cloud_icon(self, offset=0, color="gray"):
        cx, cy = self.canvas_size / 2, self.canvas_size / 2
        
        # Simple cloud shape (circles)
        self.canvas.create_oval(cx-30, cy-10, cx+10, cy+20, fill=color, outline="")
        self.canvas.create_oval(cx-10, cy-20, cx+30, cy+10, fill=color, outline="")
        self.canvas.create_oval(cx+10, cy-10, cx+40, cy+20, fill=color, outline="")
        self.canvas.create_oval(cx-20, cy+5, cx+30, cy+20, fill=color, outline="")
        
        # Arrow (if animating)
        if self._uploading:
            arrow_y = cy + 10 - offset
            ac = COLORS["success"][1] if self._mode == "dark" else COLORS["success"][0]
            self.canvas.create_line(cx, arrow_y, cx, arrow_y-20, width=3, fill=ac, capstyle="round")
            self.canvas.create_line(cx, arrow_y-20, cx-8, arrow_y-12, width=3, fill=ac, capstyle="round")
            self.canvas.create_line(cx, arrow_y-20, cx+8, arrow_y-12, width=3, fill=ac, capstyle="round")

    def _animate(self):
        if not self._uploading:
            return
            
        self.canvas.delete("all")
        cloud_color = COLORS["text_primary"][1] if self._mode == "dark" else COLORS["text_primary"][0]
        self._draw_cloud_icon(offset=self._offset, color=cloud_color)
        
        self._offset = (self._offset + 2) % 20
        self.after(50, self._animate)

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
        
        # Define tags for coloring
        self.textbox.tag_config("proc", foreground="#5ac8fa")  # Light Blue
        self.textbox.tag_config("db", foreground="#ffcc00")    # Yellow
        self.textbox.tag_config("cloud", foreground="#af52de") # Purple
        self.textbox.tag_config("whatsapp", foreground="#34c759") # Green
        self.textbox.tag_config("server", foreground="#007aff") # Blue
        self.textbox.tag_config("error", foreground="#ff3b30") # Red
        self.textbox.tag_config("timestamp", foreground=COLORS["text_secondary"][0])
    
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Default icon/style
        icon = "•"
        tag = "info"
        display_msg = message

        # Parse source and assign icon
        # Message format usually: "[Source] Content" or "[Source] Logger | Content"
        lower_msg = message.lower()
        
        if "app.processor" in lower_msg or "processing" in lower_msg:
            icon = "⚙️" # Gear
            tag = "proc"
            # Clean up message for cleaner display
            display_msg = message.replace("app.processor |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Processor | {display_msg}"
            
        elif "app.db" in lower_msg or "database" in lower_msg:
            icon = "🗄️" # File Cabinet
            tag = "db"
            display_msg = message.replace("app.db |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Database | {display_msg}"
            
        elif "app.cloud" in lower_msg or "drive" in lower_msg:
            icon = "☁️" # Cloud
            tag = "cloud"
            display_msg = message.replace("app.cloud |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Cloud | {display_msg}"
            
        elif "whatsapp" in lower_msg:
            icon = "💬" # Speech Balloon
            tag = "whatsapp"
            if display_msg.startswith("[WhatsApp]"): display_msg = display_msg.replace("[WhatsApp]", "").strip()
            display_msg = f"WhatsApp | {display_msg}"
            
        elif "server" in lower_msg:
            icon = "🌐" # Globe
            tag = "server"
            if display_msg.startswith("[Server]"): display_msg = display_msg.replace("[Server]", "").strip()
            display_msg = f"Server | {display_msg}"
            
        elif level == "error":
            icon = "✗"
            tag = "error"
        elif level == "success":
            icon = "✓"
            tag = "whatsapp" # Use green for success generally

        self.textbox.configure(state="normal")
        
        self.textbox.configure(state="normal")
        
        # Insert message in default color first at the top
        self.textbox.insert("1.0", f"{display_msg}\n")
        
        # Then insert the colored prefix at the very beginning (pushing the message to the right)
        prefix = f"{timestamp}  {icon}  "
        self.textbox.insert("1.0", prefix, (tag,))
        
        
        # No line limit - keep all logs for full history
        
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
        # We need to detect specific changes to highlight them
        current_counts = {}
        for p in persons:
            name = enrollments.get(p.id).user_name if p.id in enrollments else p.name
            current_counts[name] = p.face_count

        # Check for changes if we have history
        changes = []
        if hasattr(self, "_last_counts"):
            for name, count in current_counts.items():
                old_count = self._last_counts.get(name, 0)
                if count > old_count:
                    changes.append(name)
        
        self._last_counts = current_counts

        # Check if we need to rebuild the layout
        data_hash = str([(p.id, p.name, p.face_count) for p in persons])
        if data_hash == self._last_hash:
            # Even if hash matches (unlikely if counts changed), we might still want to highlight if we missed it?
            # Actually, if count changed, hash changed.
            pass
        else:
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
        
        # Trigger highlights for changes
        for name in changes:
            self.highlight_person(name)
    
    def highlight_person(self, name_to_find):
        """Find and highlight a person in the list."""
        # Normalize search name
        search = name_to_find.lower().strip()
        found_widget = None
        
        # Search through children rows
        for row in self.winfo_children():
            # The structure is Frame -> [Label(name), Label(count)]
            # We need to access the name label
            children = row.winfo_children()
            if not children: continue
            
            # First child is the name label (usually)
            name_lbl = children[0]
            if not isinstance(name_lbl, ctk.CTkLabel): continue
            
            # Check text
            txt = name_lbl.cget("text").lower()
            # Remove "✓ " prefix if present
            if txt.startswith("✓ "): txt = txt[2:]
            
            if search in txt:
                found_widget = row
                break
        
        if found_widget:
            # Flash animation
            orig_color = found_widget.cget("fg_color")
            flash_color = COLORS["accent"]
            
            def flash(step):
                if step > 5:
                    found_widget.configure(fg_color="transparent") # Reset
                    return
                # Toggle
                c = flash_color if step % 2 == 0 else "transparent"
                found_widget.configure(fg_color=c)
                self.after(200, lambda: flash(step + 1))
            
            flash(0)
            
            # Scroll to make visible (rudimentary)
            # CTkScrollableFrame doesn't expose easy 'scroll_to' for arbitrary widgets easily 
            # without accessing internal canvas. 
            # We'll just highlight for now.


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
                                logger = parts[1].strip()
                                msg = parts[-1].strip()
                                self.on_output(f"[{name}] {logger} | {msg}", "info")
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
        
        # Create timestamped session log file in logs/ directory
        logs_dir = BASE_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)  # Create logs directory if it doesn't exist
        
        session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_log_path = logs_dir / f"session_{session_timestamp}.txt"
        try:
            self.session_log_file = open(self.session_log_path, 'w', encoding='utf-8', buffering=1)  # Line buffering
            self.session_log_file.write(f"=== Wedding Face Forward Session Log ===\n")
            self.session_log_file.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.session_log_file.write(f"=" * 50 + "\n\n")
        except Exception as e:
            print(f"Warning: Could not create session log file: {e}")
            self.session_log_file = None
        
        self._create_ui()
        
        # Create process manager with output callback
        self.process_manager = ProcessManager(on_output=self._on_worker_output)
        
        self.running = True
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        self.after(100, self._refresh_stats)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_worker_output(self, message, level):
        """Handle output from worker/server processes."""
        # Add to UI
        self.after(0, lambda: self.activity_log.add_log(message, level))
        
        # Write to session log file
        if self.session_log_file:
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.session_log_file.write(f"{timestamp}  •  {message}\n")
            except Exception as e:
                print(f"Warning: Could not write to session log: {e}")
    
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
        
        # Main Content - Modular Layout with PanedWindow
        # We need a container for the PanedWindow that respects CTk geometry
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=30, pady=(0, 15))
        
        # Use tkinter.PanedWindow for resizability
        # We must align bg color with theme. 
        # Note: 'bg' in PanedWindow doesn't update automatically on theme change easily without recreation/config.
        # We'll set a neutral or match light mode initially, and update in _toggle_theme.
        self.paned_window = tk.PanedWindow(
            container, orient="horizontal", 
            sashwidth=6, sashrelief="flat",
            bg=COLORS["bg"][0], # Initial light mode bg
            bd=0
        )
        self.paned_window.pack(fill="both", expand=True)

        # --- LEFT PANE (Operations) ---
        self.left_pane = ctk.CTkFrame(self.paned_window, fg_color="transparent")
        # No pack/grid here, paned_window manages it
        
        # Top Left: Status Modules (Processing & Cloud)
        # We'll put these in a sub-frame
        status_modules = ctk.CTkFrame(self.left_pane, fg_color="transparent")
        status_modules.pack(fill="x", pady=(0, 10))
        status_modules.columnconfigure(0, weight=1)
        status_modules.columnconfigure(1, weight=1)
        
        self.proc_widget = ProcessingWidget(status_modules)
        self.proc_widget.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.cloud_widget = CloudWidget(status_modules)
        self.cloud_widget.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # Activity Log (Below status modules)
        self.activity_log = ActivityLog(self.left_pane)
        self.activity_log.pack(fill="both", expand=True)
        self.activity_log.add_log("App started", "success")
        
        # Add Left Pane to PanedWindow
        # We can't add CTk widgets directly to PanedWindow easily because they anticipate pack/grid geometry managers usually?
        # Actually standard tkinter widgets work. CTkFrame is a subclass of Frame (usually).
        # Let's try adding directly.
        self.paned_window.add(self.left_pane, minsize=300)

        # --- RIGHT PANE (Data/People) ---
        self.right_pane = ctk.CTkFrame(self.paned_window, fg_color="transparent")
        
        people_header = ctk.CTkFrame(self.right_pane, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        people_header.pack(fill="both", expand=True)
        
        ctk.CTkLabel(people_header, text="People", font=("SF Pro Display", 15, "bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(15, 10))
        
        self.people_list = PeopleList(people_header)
        self.people_list.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.paned_window.add(self.right_pane, minsize=300)
        
    def _update_paned_window_bg(self):
        mode = ctk.get_appearance_mode()
        bg = COLORS["bg"][1] if mode == "Dark" else COLORS["bg"][0]
        self.paned_window.configure(bg=bg)
    
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
            
            self.proc_widget.status_label.configure(text=f"Queue: {incoming}")

            if processing > 0:
                self.proc_widget.start_processing()
                self.proc_widget.status_label.configure(text=f"Processing {processing}...")
            else:
                self.proc_widget.stop_processing()
                if incoming > 0:
                    self.proc_widget.status_label.configure(text="Waiting...", text_color=COLORS["warning"])
            # self.queue_section.update_row("completed", str(completed))
            # self.queue_section.update_row("errors", str(errors))
            
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
                
                if uploading_total > 0:
                    self.cloud_widget.start_uploading()
                    self.cloud_widget.status_label.configure(text=f"Uploading {uploading_total}...")
                else:
                    self.cloud_widget.stop_uploading()
                    self.cloud_widget.status_label.configure(text="Synced")

                # self.cloud_section.update_row("pending", str(pending_total))
                # self.cloud_section.update_row("uploading", str(uploading_total))
                # Show unique photos / total files for clarity when different
                # if completed_unique != completed_total:
                #     self.cloud_section.update_row("uploaded", f"{completed_unique} ({completed_total})")
                # else:
                #     self.cloud_section.update_row("uploaded", str(completed_total))
                # self.cloud_section.update_row("failed", str(failed_total))
                self.last_upload_stats = upload_stats
            
            if total > self.last_photo_count:
                self.activity_log.add_log(f"{total - self.last_photo_count} new photo(s)", "info")
            if stats.get("total_faces", 0) > self.last_face_count:
                self.activity_log.add_log(f"{stats['total_faces'] - self.last_face_count} face(s) detected", "success")
            if stats.get("total_persons", 0) > self.last_person_count:
                # New person identified
                new_count = stats.get("total_persons", 0) - self.last_person_count
                self.activity_log.add_log(f"{new_count} New person(s) identified", "success")
                
                # Try to highlight new people if we can find them in the logs or list
                # Since we don't have the exact name here easily without querying DB diffs, 
                # we'll just flash the list or log.
                # Ideally, we should fetch the latest person added.
                pass
            
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
        self._update_paned_window_bg()
        self.proc_widget.set_appearance_mode(new_mode)
        self.cloud_widget.set_appearance_mode(new_mode)

    def _on_close(self):
        """Handle window close - also stop services."""
        if self.process_manager.is_running():
            self.activity_log.add_log("Shutting down...", "info")
            self.process_manager.stop()
        
        # Close session log file
        if hasattr(self, 'session_log_file') and self.session_log_file:
            try:
                self.session_log_file.write(f"\n{'=' * 50}\n")
                self.session_log_file.write(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.session_log_file.close()
            except Exception as e:
                print(f"Warning: Could not close session log: {e}")
        
        self.running = False
        self.destroy()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = WeddingFFApp()
    app.mainloop()
