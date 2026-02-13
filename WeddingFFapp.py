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
import webbrowser

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
# Color Theme - Design Guide Palette
# =============================================================================
COLORS = {
    "bg":              ("#ffffff", "#1c1c1e"),       # White / Dark
    "bg_card":         ("#ffffff", "#2c2c2e"),
    "border":          ("#e0e0e0", "#3a3a3c"),
    "accent":          ("#007aff", "#0a84ff"),
    "success":         ("#34c759", "#30d158"),
    "warning":         ("#ff9500", "#ff9f0a"),
    "error":           ("#ff3b30", "#ff453a"),
    "text_primary":    ("#1d1d1f", "#ffffff"),
    "text_secondary":  ("#86868b", "#98989d"),
    # Design guide specific
    "stat_bg":         ("#FCEFCD", "#3a3227"),       # Light peach / dark variant
    "stat_highlight":  ("#F6E9B2", "#4a4020"),       # Darker yellow-beige / dark variant
    "thick_border":    ("#000000", "#555555"),        # Thick black borders
    "log_outer":       ("#7A7A7A", "#4a4a4a"),       # Dark grey activity log bg
    "log_inner":       ("#000000", "#111111"),        # Black terminal
}


# =============================================================================
# Animated Status Indicator
# =============================================================================
class StatusIndicator(ctk.CTkFrame):
    """Animated status dot with label."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.dot = ctk.CTkLabel(self, text="●", font=("Segoe UI", 14), text_color=COLORS["text_secondary"])
        self.dot.pack(side="left", padx=(0, 6))
        
        self.label = ctk.CTkLabel(self, text="Stopped", font=("Segoe UI", 13), text_color=COLORS["text_secondary"])
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
        
        colors = [COLORS["success"], ("#5fd47a", "#4cd964"), COLORS["success"], ("#2aa64a", "#248a3d")]
        if "Stopping" in self.label.cget("text") or "Starting" in self.label.cget("text"):
            colors = [COLORS["warning"], ("#ffaa33", "#ffb340"), COLORS["warning"], ("#cc7700", "#d98816")]
        
        self.dot.configure(text_color=colors[self._pulse_step % len(colors)])
        self._pulse_step += 1
        
        self.after(400, self._pulse)


# =============================================================================
# System Health Indicator (All Workers Status)
# =============================================================================
class SystemHealthIndicator(ctk.CTkFrame):
    """Shows overall system health: green = all idle, red/orange = workers busy."""
    
    def __init__(self, parent):
        super().__init__(
            parent, 
            fg_color=COLORS["bg_card"], 
            corner_radius=20,
            border_width=2,
            border_color=COLORS["border"]
        )
        
        # Inner container for padding
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=12, pady=6)
        
        self.dot = ctk.CTkLabel(inner, text="●", font=("Segoe UI", 14), text_color=COLORS["text_secondary"])
        self.dot.pack(side="left", padx=(0, 8))
        
        self.label = ctk.CTkLabel(
            inner, text="System Idle", 
            font=("Segoe UI", 11, "bold"), 
            text_color=COLORS["text_secondary"]
        )
        self.label.pack(side="left")
        
        self._state = "offline"  # "offline", "idle", or "busy"
        self._pulsing = False
        self._pulse_step = 0
        self._scale = 1.0
        self._target_scale = 1.0
    
    def set_idle(self):
        """All workers are idle - show green pulsating dot."""
        if self._state == "idle":
            return  # Already idle, no change
        
        self._state = "idle"
        self._pulsing = True
        self._target_scale = 1.0
        self.configure(border_color=COLORS["success"])
        self.label.configure(text="System Idle", text_color=COLORS["success"])
        self._pulse()
    
    def set_busy(self):
        """At least one worker is busy - show red/orange pulsating dot."""
        if self._state == "busy":
            return  # Already busy, no change
        
        self._state = "busy"
        self._pulsing = True
        self._target_scale = 1.05
        self.configure(border_color=COLORS["warning"])
        self.label.configure(text="Workers Active", text_color=COLORS["warning"])
        self._pulse()
    
    def set_offline(self):
        """System is stopped - show grey static dot."""
        if self._state == "offline":
            return  # Already offline
        
        self._state = "offline"
        self._pulsing = False
        self._target_scale = 1.0
        self.configure(border_color=COLORS["border"])
        self.dot.configure(text_color=COLORS["text_secondary"])
        self.label.configure(text="System Offline", text_color=COLORS["text_secondary"])
    
    def _pulse(self):
        if not self._pulsing:
            return
        
        if self._state == "busy":
            # Red/Orange pulsating for busy
            colors = [
                COLORS["error"], 
                ("#ff6b60", "#ff6b60"), 
                COLORS["warning"], 
                ("#ffaa33", "#ffb340")
            ]
        else:
            # Green pulsating for idle
            colors = [
                COLORS["success"], 
                ("#5fd47a", "#4cd964"), 
                COLORS["success"], 
                ("#2aa64a", "#248a3d")
            ]
        
        self.dot.configure(text_color=colors[self._pulse_step % len(colors)])
        self._pulse_step += 1
        
        self.after(500, self._pulse)


# =============================================================================
# Stat Card Widget (Design Guide Style)
# =============================================================================
class StatCard(ctk.CTkFrame):
    """A stat card with big number and label — peach/beige background."""
    
    def __init__(self, parent, title: str, value: str = "0", highlight: bool = False):
        bg_color = COLORS["stat_highlight"] if highlight else COLORS["stat_bg"]
        super().__init__(
            parent, fg_color=bg_color, corner_radius=10,
            border_width=0
        )
        
        self._bg_color = bg_color
        self.value_label = ctk.CTkLabel(
            self, text=value, font=("Segoe UI", 28, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.value_label.pack(pady=(18, 4))
        
        self.title_label = ctk.CTkLabel(
            self, text=title.upper(), font=("Segoe UI", 11, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(pady=(0, 16))
        
        self._last_value = value
    
    def update_value(self, value: str):
        if value != self._last_value:
            self.value_label.configure(text_color=COLORS["accent"])
            self.after(300, lambda: self.value_label.configure(text_color=COLORS["text_primary"]))
            self.value_label.configure(text=value)
            self._last_value = value


# =============================================================================
# Status Card (Thick Black Border) — for PROCESSING, CLOUD SYNC, STUCK
# =============================================================================
class StatusCard(ctk.CTkFrame):
    """Status card with thick black border, white bg, bold text — matches design guide."""
    
    def __init__(self, parent, title: str):
        super().__init__(
            parent, fg_color=COLORS["bg_card"], corner_radius=12,
            border_width=3, border_color=COLORS["thick_border"]
        )
        
        self.title_label = ctk.CTkLabel(
            self, text=title.upper(), font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(pady=(12, 4))
        
        self.value_label = ctk.CTkLabel(
            self, text="—", font=("Segoe UI", 22, "bold"),
            text_color=COLORS["text_secondary"]
        )
        self.value_label.pack(pady=(0, 4))
        
        self.detail_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 10),
            text_color=COLORS["text_secondary"]
        )
        self.detail_label.pack(pady=(0, 10))
    
    def set_status(self, value: str, detail: str = "", color=None):
        self.value_label.configure(
            text=value,
            text_color=color or COLORS["text_primary"]
        )
        self.detail_label.configure(text=detail)


# =============================================================================
# Processing Widget (Circular Progress Bar)
# =============================================================================
class ProcessingWidget(ctk.CTkFrame):
    """Animated circular progress bar with percentage and status."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12, border_width=3, border_color=COLORS["thick_border"])
        
        self.title_label = ctk.CTkLabel(
            self, text="PROCESSING", font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(fill="x", padx=20, pady=(12, 4))
        
        # Canvas for circular progress
        self.canvas_size = 120
        self.canvas = ctk.CTkCanvas(
            self, width=self.canvas_size, height=self.canvas_size,
            bg=COLORS["bg_card"][0], highlightthickness=0
        )
        self.canvas.pack(pady=4)
        
        self.progress_label = ctk.CTkLabel(
            self, text="0 / 0 Photos", font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        )
        self.progress_label.pack(pady=(0, 2))
        
        self.status_label = ctk.CTkLabel(
            self, text="Idle", font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(pady=(0, 10))
        
        self._animating = False
        self._angle = 0
        self._mode = "light"
        
        self._target_progress = 0.0
        self._current_progress = 0.0
        self._completed = 0
        self._total = 0
        
        self._draw_ring()

    def set_appearance_mode(self, mode):
        self._mode = mode.lower()
        bg = COLORS["bg_card"][1] if self._mode == "dark" else COLORS["bg_card"][0]
        self.canvas.configure(bg=bg)
        self._draw_ring()

    def _draw_ring(self):
        """Draw the circular progress ring with current state."""
        self.canvas.delete("all")
        cx, cy = self.canvas_size / 2, self.canvas_size / 2
        r = 45
        line_w = 6
        
        track_color = "#3a3a3c" if self._mode == "dark" else "#e0e0e0"
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=track_color, width=line_w)
        
        progress = self._current_progress
        if progress > 0:
            extent = progress * 360
            
            if progress >= 1.0:
                arc_color = COLORS["success"][1] if self._mode == "dark" else COLORS["success"][0]
            else:
                arc_color = COLORS["accent"][1] if self._mode == "dark" else COLORS["accent"][0]
            
            self.canvas.create_arc(
                cx-r, cy-r, cx+r, cy+r,
                start=90, extent=-extent,
                outline=arc_color, width=line_w, style="arc"
            )
            
            if 0 < progress < 1.0:
                angle_rad = math.radians(90 - extent)
                dot_x = cx + r * math.cos(angle_rad)
                dot_y = cy - r * math.sin(angle_rad)
                dot_r = 4
                self.canvas.create_oval(
                    dot_x-dot_r, dot_y-dot_r, dot_x+dot_r, dot_y+dot_r,
                    fill=arc_color, outline=""
                )
        
        pct_color = COLORS["text_primary"][1] if self._mode == "dark" else COLORS["text_primary"][0]
        
        if self._total == 0 and not self._animating:
            self.canvas.create_text(
                cx, cy - 4, text="--",
                fill=track_color, font=("Segoe UI", 24, "bold")
            )
            self.canvas.create_text(
                cx, cy + 16, text="IDLE",
                fill=track_color, font=("Segoe UI", 9)
            )
        elif progress >= 1.0:
            done_color = COLORS["success"][1] if self._mode == "dark" else COLORS["success"][0]
            self.canvas.create_text(
                cx, cy - 2, text="DONE",
                fill=done_color, font=("Segoe UI", 18, "bold")
            )
        else:
            pct = int(progress * 100)
            self.canvas.create_text(
                cx, cy - 6, text=f"{pct}",
                fill=pct_color, font=("Segoe UI", 28, "bold")
            )
            self.canvas.create_text(
                cx, cy + 16, text="%",
                fill=COLORS["text_secondary"][1] if self._mode == "dark" else COLORS["text_secondary"][0],
                font=("Segoe UI", 11)
            )

    def update_progress(self, completed: int, total: int):
        """Update progress bar with current counts."""
        self._completed = completed
        self._total = total
        
        if total > 0:
            self._target_progress = min(completed / total, 1.0)
        else:
            self._target_progress = 0.0
        
        if total == 0:
            self.progress_label.configure(text="No photos queued")
            self.status_label.configure(text="Idle", text_color=COLORS["text_secondary"])
        elif completed >= total:
            self.progress_label.configure(text=f"{completed} / {total} Photos")
            self.status_label.configure(text="All Done!", text_color=COLORS["success"])
        else:
            self.progress_label.configure(text=f"{completed} / {total} Photos")
            self.status_label.configure(text="Processing...", text_color=COLORS["accent"])

    def start_processing(self):
        if not self._animating:
            self._animating = True
            self._animate()

    def stop_processing(self):
        self._animating = False
        if self._total == 0:
            self.status_label.configure(text="Idle", text_color=COLORS["text_secondary"])
            self._current_progress = 0
            self._target_progress = 0
            self._draw_ring()

    def draw_static_ring(self):
        """Legacy compatibility."""
        self._draw_ring()

    def _animate(self):
        if not self._animating:
            return
        
        diff = self._target_progress - self._current_progress
        if abs(diff) > 0.002:
            self._current_progress += diff * 0.12
        else:
            self._current_progress = self._target_progress
        
        self._draw_ring()
        self.after(33, self._animate)


# =============================================================================
# Cloud Widget (Animated)
# =============================================================================
class CloudWidget(ctk.CTkFrame):
    """Animated cloud upload status."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12, border_width=3, border_color=COLORS["thick_border"])
        
        self.title_label = ctk.CTkLabel(
            self, text="CLOUD SYNC", font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(fill="x", padx=20, pady=(12, 4))
        
        self.canvas_size = 120
        self.canvas = ctk.CTkCanvas(
            self, width=self.canvas_size, height=self.canvas_size,
            bg=COLORS["bg_card"][0], highlightthickness=0
        )
        self.canvas.pack(pady=4)
        
        self.status_label = ctk.CTkLabel(
            self, text="Synced", font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(pady=(0, 10))
        
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
        
        self.canvas.create_oval(cx-30, cy-10, cx+10, cy+20, fill=color, outline="")
        self.canvas.create_oval(cx-10, cy-20, cx+30, cy+10, fill=color, outline="")
        self.canvas.create_oval(cx+10, cy-10, cx+40, cy+20, fill=color, outline="")
        self.canvas.create_oval(cx-20, cy+5, cx+30, cy+20, fill=color, outline="")
        
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


# =============================================================================
# Stuck Photos Card
# =============================================================================
class StuckPhotosCard(ctk.CTkFrame):
    """Shows stuck photos in processing — both image analysis and cloud upload."""
    
    def __init__(self, parent):
        super().__init__(
            parent, fg_color=COLORS["bg_card"], corner_radius=12,
            border_width=3, border_color=COLORS["thick_border"]
        )
        
        self.title_label = ctk.CTkLabel(
            self, text="STUCK PHOTOS", font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(pady=(12, 8))
        
        # Processing stuck
        proc_frame = ctk.CTkFrame(self, fg_color="transparent")
        proc_frame.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            proc_frame, text="Image Analysis", font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        ).pack(side="left")
        self.proc_stuck_label = ctk.CTkLabel(
            proc_frame, text="0", font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.proc_stuck_label.pack(side="right")
        
        # Cloud stuck
        cloud_frame = ctk.CTkFrame(self, fg_color="transparent")
        cloud_frame.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            cloud_frame, text="Cloud Upload", font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        ).pack(side="left")
        self.cloud_stuck_label = ctk.CTkLabel(
            cloud_frame, text="0", font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.cloud_stuck_label.pack(side="right")
        
        # Total
        sep = ctk.CTkFrame(self, fg_color=COLORS["border"], height=1)
        sep.pack(fill="x", padx=16, pady=(6, 4))
        
        total_frame = ctk.CTkFrame(self, fg_color="transparent")
        total_frame.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(
            total_frame, text="Total Stuck", font=("Segoe UI", 11, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")
        self.total_stuck_label = ctk.CTkLabel(
            total_frame, text="0", font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.total_stuck_label.pack(side="right")
    
    def update_stuck(self, proc_stuck: int, cloud_stuck: int):
        total = proc_stuck + cloud_stuck
        
        self.proc_stuck_label.configure(
            text=str(proc_stuck),
            text_color=COLORS["warning"] if proc_stuck > 0 else COLORS["success"]
        )
        self.cloud_stuck_label.configure(
            text=str(cloud_stuck),
            text_color=COLORS["warning"] if cloud_stuck > 0 else COLORS["success"]
        )
        self.total_stuck_label.configure(
            text=str(total),
            text_color=COLORS["error"] if total > 0 else COLORS["success"]
        )


# =============================================================================
# Activity Log (Dark Grey Container + Black Terminal)
# =============================================================================
class ActivityLog(ctk.CTkFrame):
    """Activity log with dark grey bg and black terminal — per design guide."""
    
    def __init__(self, parent):
        super().__init__(
            parent, fg_color=COLORS["log_outer"], corner_radius=12,
            border_width=3, border_color=COLORS["thick_border"]
        )
        
        self.title_label = ctk.CTkLabel(
            self, text="ACTIVITY LOG", font=("Segoe UI", 14, "bold"),
            text_color=("#000000", "#ffffff"), anchor="w"
        )
        self.title_label.pack(fill="x", padx=16, pady=(12, 8))
        
        # Black terminal inside
        self.textbox = ctk.CTkTextbox(
            self, font=("Consolas", 11),
            fg_color=COLORS["log_inner"],
            text_color=("#b0b0b0", "#a0a0a0"),
            corner_radius=8, height=120
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.textbox.configure(state="disabled")
        
        # Define tags for coloring
        self.textbox.tag_config("proc", foreground="#5ac8fa")
        self.textbox.tag_config("db", foreground="#ffcc00")
        self.textbox.tag_config("cloud", foreground="#af52de")
        self.textbox.tag_config("whatsapp", foreground="#34c759")
        self.textbox.tag_config("server", foreground="#007aff")
        self.textbox.tag_config("error", foreground="#ff3b30")
        self.textbox.tag_config("timestamp", foreground="#888888")
    
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        icon = "•"
        tag = "info"
        display_msg = message

        lower_msg = message.lower()
        
        if "app.processor" in lower_msg or "processing" in lower_msg:
            icon = "⚙️"
            tag = "proc"
            display_msg = message.replace("app.processor |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Processor | {display_msg}"
            
        elif "app.db" in lower_msg or "database" in lower_msg:
            icon = "🗄️"
            tag = "db"
            display_msg = message.replace("app.db |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Database | {display_msg}"
            
        elif "app.cloud" in lower_msg or "drive" in lower_msg:
            icon = "☁️"
            tag = "cloud"
            display_msg = message.replace("app.cloud |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Cloud | {display_msg}"
            
        elif "whatsapp" in lower_msg:
            icon = "💬"
            tag = "whatsapp"
            if display_msg.startswith("[WhatsApp]"): display_msg = display_msg.replace("[WhatsApp]", "").strip()
            display_msg = f"WhatsApp | {display_msg}"
            
        elif "server" in lower_msg:
            icon = "🌐"
            tag = "server"
            if display_msg.startswith("[Server]"): display_msg = display_msg.replace("[Server]", "").strip()
            display_msg = f"Server | {display_msg}"
            
        elif level == "error":
            icon = "✗"
            tag = "error"
        elif level == "success":
            icon = "✓"
            tag = "whatsapp"

        self.textbox.configure(state="normal")
        
        self.textbox.insert("1.0", f"{display_msg}\n")
        
        prefix = f"{timestamp}  {icon}  "
        self.textbox.insert("1.0", prefix, (tag,))
        
        self.textbox.configure(state="disabled")


# =============================================================================
# Folder Choice Popup (Hover Menu)
# =============================================================================
class FolderChoicePopup(ctk.CTkToplevel):
    """Small floating menu to choose between Local and Cloud folders."""
    
    def __init__(self, parent, x, y, person_name, on_local, on_cloud):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Windows-specific transparency fix for rounded corners
        if sys.platform.startswith("win"):
            self.attributes("-transparentcolor", "#000001")
            self.configure(fg_color="#000001")
        else:
            self.configure(fg_color="transparent")
        
        # Match appearance mode
        curr_mode = ctk.get_appearance_mode()
        bg_color = COLORS["bg_card"][1] if curr_mode == "Dark" else COLORS["bg_card"][0]
        
        # Border frame (black/dark border)
        self.outer_frame = ctk.CTkFrame(self, fg_color=COLORS["thick_border"], corner_radius=12)
        self.outer_frame.pack(padx=0, pady=0)
        
        self.frame = ctk.CTkFrame(self.outer_frame, fg_color=bg_color, corner_radius=10, border_width=0)
        self.frame.pack(padx=2, pady=2)
        
        # Position slightly overlapping with cursor so we are 'inside' it immediately
        self.geometry(f"+{x-5}+{y-5}")
        
        # Buttons
        self.btn_local = ctk.CTkButton(
            self.frame, text="📁  Local Explorer", height=32, width=150, corner_radius=6,
            fg_color="transparent", hover_color=("#f0f0f0", "#3a3a3c"),
            text_color=COLORS["text_primary"], anchor="w",
            font=("Segoe UI", 11),
            command=lambda: [on_local(), self.destroy()]
        )
        self.btn_local.pack(pady=(8, 2), padx=8)
        
        self.btn_cloud = ctk.CTkButton(
            self.frame, text="☁  Cloud Drive", height=32, width=150, corner_radius=6,
            fg_color="transparent", hover_color=("#f0f0f0", "#3a3a3c"),
            text_color=COLORS["text_primary"], anchor="w",
            font=("Segoe UI", 11),
            command=lambda: [on_cloud(), self.destroy()]
        )
        self.btn_cloud.pack(pady=(2, 8), padx=8)
        
        # Allow a small grace period before enabling auto-close on leave
        # This prevents the popup from vanishing if it spawns and immediately 
        # triggers a 'Leave' because of cursor jitter.
        self._can_close = False
        self.after(200, self._enable_close)
        
        # Bind leave to the outer container
        self.outer_frame.bind("<Leave>", self._on_mouse_leave)
        self.btn_local.bind("<Enter>", lambda e: self._cancel_close())
        self.btn_cloud.bind("<Enter>", lambda e: self._cancel_close())

    def _enable_close(self):
        self._can_close = True
        # Start periodic position checking
        self._check_position_loop()

    def _on_mouse_leave(self, event):
        if self._can_close:
            # Short delay to check if we really left (vs moving between buttons)
            self.after(100, self._check_really_left)

    def _check_really_left(self):
        if not self.winfo_exists(): return
        
        # Get mouse position relative to screen
        mx = self.winfo_pointerx()
        my = self.winfo_pointery()
        
        # Get window geometry
        wx = self.winfo_rootx()
        wy = self.winfo_rooty()
        ww = self.winfo_width()
        wh = self.winfo_height()
        
        # If mouse is outside the window bounds plus a small padding
        padding = 10
        if not (wx-padding <= mx <= wx+ww+padding and wy-padding <= my <= wy+wh+padding):
            self.destroy()

    def _check_position_loop(self):
        """Continuously check if mouse is still near the popup."""
        if not self.winfo_exists(): return
        
        try:
            mx = self.winfo_pointerx()
            my = self.winfo_pointery()
            
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            ww = self.winfo_width()
            wh = self.winfo_height()
            
            # Larger padding for continuous check
            padding = 20
            if not (wx-padding <= mx <= wx+ww+padding and wy-padding <= my <= wy+wh+padding):
                self.destroy()
                return
            
            # Check again in 100ms
            self.after(100, self._check_position_loop)
        except:
            # If any error, just close
            try:
                self.destroy()
            except:
                pass

    def _cancel_close(self):
        # Prevent closing if mouse is over buttons
        pass


# =============================================================================
# People List (Pill-shaped items per Design Guide)
# =============================================================================
class PeopleList(ctk.CTkScrollableFrame):
    """Person list with pill-shaped items — thick black border, white bg."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=12)
        self._last_hash = None
        self._hover_id = None
        self._popup = None
    

    def _open_person_folder(self, person_name):
        """Open the specific person's folder in file explorer."""
        try:
            from app.config import get_config
            config = get_config()
            folder_path = config.people_dir / person_name
            if folder_path.exists():
                os.startfile(str(folder_path))
        except Exception:
            pass

    def _open_cloud_folder(self, person_name):
        """Determine cloud URL and open in browser."""
        def task():
            try:
                from app.cloud import get_cloud
                cloud = get_cloud()
                if cloud.is_enabled:
                    # This might take a second if not cached
                    folder_id = cloud.ensure_folder_path(["People", person_name])
                    if folder_id:
                        url = f"https://drive.google.com/drive/folders/{folder_id}"
                        webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=task, daemon=True).start()

    def _close_popup(self):
        """Close the popup if it exists."""
        if self._popup and self._popup.winfo_exists():
            try:
                self._popup.destroy()
            except:
                pass
        self._popup = None

    def _show_choice_popup(self, x, y, person_name):
        """Show the floating choice menu."""
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        
        self._popup = FolderChoicePopup(
            self, x, y, person_name,
            on_local=lambda: self._open_person_folder(person_name),
            on_cloud=lambda: self._open_cloud_folder(person_name)
        )

    def update_persons(self, persons: list, enrollments: dict):
        current_counts = {}
        for p in persons:
            name = enrollments.get(p.id).user_name if p.id in enrollments else p.name
            current_counts[name] = p.face_count

        changes = []
        if hasattr(self, "_last_counts"):
            for name, count in current_counts.items():
                old_count = self._last_counts.get(name, 0)
                if count > old_count:
                    changes.append(name)
        
        self._last_counts = current_counts

        data_hash = str([(p.id, p.name, p.face_count) for p in persons])
        if data_hash == self._last_hash:
            pass
        else:
            self._last_hash = data_hash
            
            for w in self.winfo_children():
                w.destroy()
            
            if not persons:
                ctk.CTkLabel(self, text="No people detected yet", font=("Segoe UI", 13), text_color=COLORS["text_secondary"]).pack(pady=20)
                return
            
            for person in persons:
                enrollment = enrollments.get(person.id)
                name = enrollment.user_name if enrollment else person.name
                icon = "✓ " if enrollment else ""
                p_name = person.name # Current folder name
                
                # Pill-shaped row: thick black border, fully rounded, white bg
                row = ctk.CTkFrame(
                    self, fg_color=COLORS["bg_card"], corner_radius=50,
                    border_width=2, border_color=COLORS["thick_border"],
                    height=36
                )
                row.pack(fill="x", padx=4, pady=3)
                row.pack_propagate(False)
                row.configure(cursor="hand2")
                
                # Hover effect & Popup trigger
                def on_enter(e, r=row, pn=p_name): 
                    r.configure(fg_color=("#f2f2f2", "#3a3a3c"))
                    # Start timer for popup
                    if self._hover_id: self.after_cancel(self._hover_id)
                    self._hover_id = self.after(600, lambda: self._show_choice_popup(e.x_root, e.y_root, pn))

                def on_leave(e, r=row): 
                    r.configure(fg_color=COLORS["bg_card"])
                    # Cancel timer if popup hasn't appeared yet
                    if self._hover_id:
                        self.after_cancel(self._hover_id)
                        self._hover_id = None
                    # Don't close popup immediately - let the popup's own tracking handle it
                
                # Click handler (still opens local immediately as quick action)
                def on_click(e, pn=p_name): 
                    if self._hover_id: self.after_cancel(self._hover_id)
                    self._open_person_folder(pn)
                
                row.bind("<Enter>", on_enter)
                row.bind("<Leave>", on_leave)
                row.bind("<Button-1>", on_click)
                
                name_lbl = ctk.CTkLabel(
                    row, text=f"{icon}{name}", font=("Segoe UI", 12),
                    text_color=COLORS["text_primary"]
                )
                name_lbl.pack(side="left", padx=(16, 5), pady=4)
                name_lbl.bind("<Button-1>", on_click)
                name_lbl.bind("<Enter>", on_enter)
                
                count_lbl = ctk.CTkLabel(
                    row, text=f"{person.face_count}", font=("Segoe UI", 12),
                    text_color=COLORS["text_secondary"]
                )
                count_lbl.pack(side="right", padx=(5, 16), pady=4)
                count_lbl.bind("<Button-1>", on_click)
                count_lbl.bind("<Enter>", on_enter)
        
        for name in changes:
            self.highlight_person(name)
    
    def highlight_person(self, name_to_find):
        """Find and highlight a person in the list."""
        search = name_to_find.lower().strip()
        found_widget = None
        
        for row in self.winfo_children():
            children = row.winfo_children()
            if not children: continue
            
            name_lbl = children[0]
            if not isinstance(name_lbl, ctk.CTkLabel): continue
            
            txt = name_lbl.cget("text").lower()
            if txt.startswith("✓ "): txt = txt[2:]
            
            if search in txt:
                found_widget = row
                break
        
        if found_widget:
            orig_color = found_widget.cget("fg_color")
            flash_color = COLORS["accent"]
            
            def flash(step):
                try:
                    if not found_widget.winfo_exists():
                        return
                except Exception:
                    return
                
                if step > 5:
                    try:
                        found_widget.configure(fg_color=COLORS["bg_card"])
                    except Exception:
                        pass
                    return
                c = flash_color if step % 2 == 0 else COLORS["bg_card"]
                try:
                    found_widget.configure(fg_color=c)
                except Exception:
                    return
                self.after(200, lambda: flash(step + 1))
            
            flash(0)


# =============================================================================
# Process Manager
# =============================================================================
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
        env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + str(FRONTEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        
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
            t = threading.Thread(target=self._read_output, args=(self.worker_proc, "Worker"), daemon=True)
            t.start()
            self._reader_threads.append(t)
        except Exception as e:
            if self.on_output:
                self.on_output(f"Worker start failed: {e}", "error")
            return
        
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
                    line = line.strip()
                    if line:
                        line_lower = line.lower()
                        if "error" in line_lower or "exception" in line_lower or "traceback" in line_lower:
                            self.on_output(f"[{name}] {line}", "error")
                        elif "warning" in line_lower:
                            self.on_output(f"[{name}] {line}", "warning")
                        elif line.startswith("2026-"):
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
    """Main application window — Design Guide Layout."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Wedding FaceForward")
        self.geometry("1050x800")
        self.configure(fg_color=COLORS["bg"])
        
        ctk.set_appearance_mode("light")
        
        self.config = get_config()
        
        self.last_photo_count = 0
        self.last_face_count = 0
        self.last_person_count = 0
        self.last_upload_stats = {}
        
        # Session log
        logs_dir = BASE_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_log_path = logs_dir / f"session_{session_timestamp}.txt"
        try:
            self.session_log_file = open(self.session_log_path, 'w', encoding='utf-8', buffering=1)
            self.session_log_file.write(f"=== Wedding Face Forward Session Log ===\n")
            self.session_log_file.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.session_log_file.write(f"=" * 50 + "\n\n")
        except Exception as e:
            print(f"Warning: Could not create session log file: {e}")
            self.session_log_file = None
        
        self._create_ui()
        
        self.process_manager = ProcessManager(on_output=self._on_worker_output)
        
        self.running = True
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        self.after(100, self._refresh_stats)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_worker_output(self, message, level):
        """Handle output from worker/server processes."""
        self.after(0, lambda: self.activity_log.add_log(message, level))
        
        if self.session_log_file:
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.session_log_file.write(f"{timestamp}  •  {message}\n")
            except Exception as e:
                print(f"Warning: Could not write to session log: {e}")
    
    def _create_ui(self):
        # =====================================================================
        # ZONE 1: Header
        # =====================================================================
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 12))
        
        # Title
        ctk.CTkLabel(
            header, text="Wedding FaceForward",
            font=("Segoe UI", 26, "bold"), text_color=COLORS["text_primary"]
        ).pack(side="left")
        
        # Right controls
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right")
        
        # System health indicator (all workers)
        self.health_indicator = SystemHealthIndicator(controls)
        self.health_indicator.pack(side="left", padx=(0, 16))
        
        self.status_indicator = StatusIndicator(controls)
        self.status_indicator.pack(side="left", padx=(0, 16))
        
        # START button — pill-shaped, bright green
        self.start_stop_btn = ctk.CTkButton(
            controls, text="START", width=110, height=38, corner_radius=50,
            fg_color=COLORS["success"], hover_color=("#2aa64a", "#248a3d"),
            font=("Segoe UI", 13, "bold"), text_color="#ffffff",
            command=self._toggle_system
        )
        self.start_stop_btn.pack(side="left", padx=(0, 10))
        
        # Theme toggle — circular with sun icon
        self.theme_btn = ctk.CTkButton(
            controls, text="☀", width=38, height=38, corner_radius=50,
            fg_color=COLORS["bg_card"], text_color=("#cc8800", "#ffcc00"),
            hover_color=("#e5e5e5", "#3a3a3c"), font=("Segoe UI", 18),
            border_width=2, border_color=COLORS["thick_border"],
            command=self._toggle_theme
        )
        self.theme_btn.pack(side="left", padx=(0, 10))
        
        # OPEN FOLDER — pill-shaped, light grey
        ctk.CTkButton(
            controls, text="OPEN FOLDER", width=120, height=38, corner_radius=50,
            fg_color=("#e0e0e0", "#3a3a3c"), hover_color=("#d0d0d0", "#48484a"),
            text_color=COLORS["text_primary"], font=("Segoe UI", 13, "bold"),
            command=self._open_event_folder
        ).pack(side="left")
        
        # =====================================================================
        # ZONE 2: Top Statistics Row (5 cards)
        # =====================================================================
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=24, pady=(0, 12))
        for i in range(5):
            stats_frame.columnconfigure(i, weight=1)
        
        self.photos_card = StatCard(stats_frame, "Total Photos", "0")
        self.photos_card.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        
        self.faces_card = StatCard(stats_frame, "Total Faces", "0")
        self.faces_card.grid(row=0, column=1, padx=6, sticky="nsew")
        
        self.people_card = StatCard(stats_frame, "No of Persons", "0")
        self.people_card.grid(row=0, column=2, padx=6, sticky="nsew")
        
        self.enrolled_card = StatCard(stats_frame, "Enrolled", "0")
        self.enrolled_card.grid(row=0, column=3, padx=6, sticky="nsew")
        
        # Card 5: Cloud & Local Match? (highlighted)
        self.match_card = StatCard(stats_frame, "Cloud & Local\nMatch?", "—", highlight=True)
        self.match_card.grid(row=0, column=4, padx=(6, 0), sticky="nsew")
        
        # =====================================================================
        # ZONE 3: Main Content Area (Left ~70% + Right ~30%)
        # =====================================================================
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        main_content.columnconfigure(0, weight=7)
        main_content.columnconfigure(1, weight=3)
        main_content.rowconfigure(0, weight=0)
        main_content.rowconfigure(1, weight=1)
        
        # ----- LEFT COLUMN -----
        
        # 3A Top: Status Cards Row (Processing, Cloud Sync, Stuck Photos)
        status_row = ctk.CTkFrame(main_content, fg_color="transparent")
        status_row.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        status_row.columnconfigure(0, weight=1)
        status_row.columnconfigure(1, weight=1)
        status_row.columnconfigure(2, weight=1)
        
        self.proc_widget = ProcessingWidget(status_row)
        self.proc_widget.grid(row=0, column=0, padx=(0, 5), sticky="nsew")
        
        self.cloud_widget = CloudWidget(status_row)
        self.cloud_widget.grid(row=0, column=1, padx=5, sticky="nsew")
        
        self.stuck_card = StuckPhotosCard(status_row)
        self.stuck_card.grid(row=0, column=2, padx=(5, 0), sticky="nsew")
        
        # 3A Bottom: Activity Log
        self.activity_log = ActivityLog(main_content)
        self.activity_log.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.activity_log.add_log("App started", "success")
        
        # ----- RIGHT COLUMN (Sidebar — People List) -----
        right_sidebar = ctk.CTkFrame(
            main_content, fg_color=COLORS["bg_card"], corner_radius=12,
            border_width=3, border_color=COLORS["thick_border"]
        )
        right_sidebar.grid(row=0, column=1, rowspan=2, sticky="nsew")
        
        ctk.CTkLabel(
            right_sidebar, text="PEOPLE", font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=16, pady=(14, 8))
        
        self.people_list = PeopleList(right_sidebar)
        self.people_list.pack(fill="both", expand=True, padx=10, pady=(0, 12))
    
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
        self._log_to_session("[APP] User clicked START button")
        
        def start_async():
            try:
                self.process_manager.start()
                time.sleep(2)
                self.after(0, self._on_system_started)
            except Exception as e:
                self.after(0, lambda: self._on_start_error(str(e)))
        
        threading.Thread(target=start_async, daemon=True).start()
    
    def _on_system_started(self):
        """Called when system has started."""
        self.status_indicator.set_running()
        self.start_stop_btn.configure(
            state="normal", text="■  STOP",
            fg_color=COLORS["error"], hover_color=("#cc2222", "#d63a3a")
        )
        self.activity_log.add_log("System running! Worker + Web server active", "success")
        self.activity_log.add_log("Web UI: http://localhost:8000", "info")
        self._log_to_session("[APP] System started successfully")
    
    def _on_start_error(self, error: str):
        """Called on start error."""
        self.status_indicator.set_stopped()
        self.start_stop_btn.configure(
            state="normal", text="START",
            fg_color=COLORS["success"], hover_color=("#2aa64a", "#248a3d")
        )
        self.activity_log.add_log(f"Start failed: {error}", "error")
    
    def _stop_system(self):
        """Stop the backend and frontend."""
        self.status_indicator.set_stopping()
        self.start_stop_btn.configure(state="disabled", text="Stopping...")
        self.activity_log.add_log("Stopping system...", "info")
        self._log_to_session("[APP] User clicked STOP button")
        
        def stop_async():
            self.process_manager.stop()
            time.sleep(1)
            self.after(0, self._on_system_stopped)
        
        threading.Thread(target=stop_async, daemon=True).start()
    
    def _on_system_stopped(self):
        """Called when system has stopped."""
        self.status_indicator.set_stopped()
        self.start_stop_btn.configure(
            state="normal", text="START",
            fg_color=COLORS["success"], hover_color=("#2aa64a", "#248a3d")
        )
        self.activity_log.add_log("System stopped", "info")
        self._log_to_session("[APP] System stopped successfully")
    
    def _refresh_loop(self):
        while self.running:
            time.sleep(1)
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
            pending = photos_by_status.get("pending", 0)
            
            self.photos_card.update_value(str(total))
            self.faces_card.update_value(str(stats.get("total_faces", 0)))
            self.people_card.update_value(str(stats.get("total_persons", 0)))
            self.enrolled_card.update_value(str(stats.get("total_enrollments", 0)))
            
            incoming = 0
            if self.config.incoming_dir.exists():
                incoming = len([f for f in self.config.incoming_dir.iterdir() if f.is_file() and f.suffix.lower() in self.config.supported_extensions])
            
            # Progress ring
            session_total = completed + errors + processing + pending
            session_done = completed + errors
            
            self.proc_widget.update_progress(session_done, session_total)

            if processing > 0:
                self.proc_widget.start_processing()
            elif session_done >= session_total and session_total > 0:
                self.proc_widget.stop_processing()
            elif incoming > 0:
                self.proc_widget.start_processing()
                self.proc_widget.status_label.configure(text="Waiting...", text_color=COLORS["warning"])
            
            # Cloud upload stats
            upload_stats = db.get_upload_stats_unique()
            if upload_stats != self.last_upload_stats:
                by_status = upload_stats.get('by_status', {})
                unique_by_status = upload_stats.get('unique_by_status', {})
                
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

                self.last_upload_stats = upload_stats
            
            # ----- NEW FEATURE 1: Cloud & Local Match Check -----
            # Cloud "completed" uploads should match the expected uploads from completed photos.
            # Expected = all completed photos should have all their file copies uploaded.
            # We check: all completed photos have ALL their upload_queue entries as 'completed'.
            self._update_cloud_local_match(db, photos_by_status, upload_stats)
            
            # ----- NEW FEATURE 2: Stuck Photos -----
            self._update_stuck_photos(db, photos_by_status)
            
            # ----- NEW FEATURE 3: System Health Indicator -----
            self._update_system_health(processing, pending, incoming, upload_stats)
            
            if total > self.last_photo_count:
                self.activity_log.add_log(f"{total - self.last_photo_count} new photo(s)", "info")
            if stats.get("total_faces", 0) > self.last_face_count:
                self.activity_log.add_log(f"{stats['total_faces'] - self.last_face_count} face(s) detected", "success")
            if stats.get("total_persons", 0) > self.last_person_count:
                new_count = stats.get("total_persons", 0) - self.last_person_count
                self.activity_log.add_log(f"{new_count} New person(s) identified", "success")
            
            self.last_photo_count = total
            self.last_face_count = stats.get("total_faces", 0)
            self.last_person_count = stats.get("total_persons", 0)
            
            persons = db.get_all_persons()
            enrollments = {e.person_id: e for e in db.get_all_enrollments()}
            self.people_list.update_persons(persons, enrollments)
            
        except Exception as e:
            pass  # Silent fail on refresh
    
    def _update_cloud_local_match(self, db, photos_by_status, upload_stats):
        """Check if cloud uploads match local repository state."""
        try:
            completed_photos = photos_by_status.get("completed", 0) + photos_by_status.get("no_faces", 0)
            
            if completed_photos == 0:
                self.match_card.update_value("—")
                return
            
            by_status = upload_stats.get('by_status', {}) if upload_stats else {}
            
            uploads_pending = by_status.get('pending', 0)
            uploads_uploading = by_status.get('uploading', 0)
            uploads_completed = by_status.get('completed', 0)
            uploads_failed = by_status.get('failed', 0)
            
            total_uploads = uploads_pending + uploads_uploading + uploads_completed + uploads_failed
            
            if total_uploads == 0 and completed_photos > 0:
                # No uploads queued yet but photos are completed — not matched
                self.match_card.update_value("NO")
                self.match_card.value_label.configure(text_color=COLORS["warning"])
                return
            
            # Check: Are all uploads completed (no pending, no uploading, no failed)?
            all_uploaded = (uploads_pending == 0 and uploads_uploading == 0 and uploads_failed == 0 and uploads_completed > 0)
            
            if all_uploaded:
                self.match_card.update_value("YES ✓")
                self.match_card.value_label.configure(text_color=COLORS["success"])
            elif uploads_failed > 0:
                # Some failed — mismatch detected
                self.match_card.update_value("NO ✗")
                self.match_card.value_label.configure(text_color=COLORS["error"])
            else:
                # Still uploading / pending
                self.match_card.update_value("SYNCING")
                self.match_card.value_label.configure(text_color=COLORS["warning"])
        except Exception:
            self.match_card.update_value("—")
    
    def _update_stuck_photos(self, db, photos_by_status):
        """Update stuck photos count — processing + cloud stuck."""
        try:
            # Stuck in image analysis processing: photos in 'processing' status
            # (these should transition to completed quickly, if stuck > 10 min they're stuck)
            proc_stuck = photos_by_status.get("processing", 0)
            
            # Stuck in cloud: uploads in 'uploading' status (should be transient)
            # NOTE: We do NOT count 'failed' uploads as "stuck" - those are errors, not active work
            by_status = self.last_upload_stats.get('by_status', {}) if self.last_upload_stats else {}
            cloud_stuck = by_status.get('uploading', 0)
            
            self.stuck_card.update_stuck(proc_stuck, cloud_stuck)
        except Exception:
            pass
    
    def _update_system_health(self, processing, pending, incoming, upload_stats):
        """Update system health indicator based on all worker states."""
        try:
            if not self.process_manager.is_running():
                self.health_indicator.set_offline()
                return
            
            # Check if ANY worker is ACTIVELY busy (not just has completed work)
            # Use fresh upload_stats, not cached data
            by_status = upload_stats.get('by_status', {}) if upload_stats else {}
            
            # Image analysis is busy if: processing photos OR pending photos in database
            # NOTE: We do NOT check 'incoming' folder - those might be already processed!
            image_analysis_busy = (processing > 0 or pending > 0)
            
            # Cloud upload is busy ONLY if actively uploading or pending (not if just completed)
            cloud_upload_busy = (by_status.get('pending', 0) > 0 or by_status.get('uploading', 0) > 0)
            
            if image_analysis_busy or cloud_upload_busy:
                self.health_indicator.set_busy()
            else:
                self.health_indicator.set_idle()
        except Exception:
            pass
    
    def _log_to_session(self, message: str):
        """Write a message directly to the session log file."""
        if self.session_log_file:
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.session_log_file.write(f"{timestamp}  •  {message}\n")
            except Exception as e:
                print(f"Warning: Could not write to session log: {e}")
    
    def _open_event_folder(self):
        os.startfile(str(self.config.event_root))
        self.activity_log.add_log("Opened folder", "info")
    
    def _toggle_theme(self):
        """Toggle between light and dark mode."""
        curr = ctk.get_appearance_mode()
        new_mode = "Dark" if curr == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)
        self.proc_widget.set_appearance_mode(new_mode)
        self.cloud_widget.set_appearance_mode(new_mode)
        
        # Update theme button icon
        if new_mode == "Dark":
            self.theme_btn.configure(text="🌙")
        else:
            self.theme_btn.configure(text="☀")

    def _on_close(self):
        """Handle window close — also stop services."""
        if self.process_manager.is_running():
            self.activity_log.add_log("Shutting down...", "info")
            self.process_manager.stop()
        
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
