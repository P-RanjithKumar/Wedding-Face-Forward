"""
AuraApp — Main application window (QMainWindow).
Ported from CustomTkinter WeddingFFApp(ctk.CTk) class.

Layout zones:
  Zone 1: Header (title + controls)
  Zone 2: Top statistics row (5 stat cards)
  Zone 3: Main content (left: status row + activity log, right: people sidebar)
"""

import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSizePolicy, QApplication,
    QMenuBar, QMenu
)
from PySide6.QtGui import QCursor, QIcon, QAction
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QGraphicsOpacityEffect

from .theme import COLORS, c, LIGHT_QSS, DARK_QSS
from .worker_bridge import WorkerBridge
from .process_manager import ProcessManager

from .widgets.status_indicator import StatusIndicator
from .widgets.system_health import SystemHealthIndicator
from .widgets.stat_card import StatCard
from .widgets.sync_status_card import SyncStatusCard
from .widgets.status_card import StatusCard
from .widgets.processing_widget import ProcessingWidget
from .widgets.cloud_widget import CloudWidget
from .widgets.stuck_photos import StuckPhotosCard
from .widgets.whatsapp_tracker import WhatsAppTrackerWidget
from .widgets.activity_log import ActivityLog
from .widgets.people_list import PeopleList
from .widgets.merge_dialog import ClusterMergeDialog
from .widgets.settings_dialog import SettingsDialog
from .widgets.health_monitor import HealthMonitorDialog
from .widgets.self_healing_dialog import SelfHealingDialog
from .widgets.auth_dialog import AuthDialog
from .splash_screen import PremiumSplashScreen

# Backend imports — use dist_utils for path resolution
import dist_utils
BASE_DIR = dist_utils.get_project_root()
BACKEND_DIR = dist_utils.get_backend_dir()
FRONTEND_DIR = dist_utils.get_frontend_dir()
# sys.path already set up by dist_utils.setup_sys_path() on import

from app.config import get_config
from app.db import get_db


class StatsWorker(QObject):
    """Runs DB queries on a background thread and emits results as a signal.

    Usage (idiomatic PySide6 QThread pattern):
      - Create a 'trigger' signal on the main thread side.
      - Connect trigger → fetch() AFTER moveToThread so the connection
        is cross-thread (QueuedConnection) and fetch() runs on the worker
        thread's event loop, not the main thread.
    """
    finished = Signal(dict)   # result payload → main thread
    trigger  = Signal()       # kick-off signal  ← emitted by main thread

    def __init__(self, get_db_fn, get_config_fn):
        super().__init__()
        self._get_db = get_db_fn
        self._get_config = get_config_fn
        # Connect trigger → fetch now (before moveToThread so it's auto
        # QueuedConnection once the worker lives on another thread)
        self.trigger.connect(self.fetch)

    def fetch(self):
        """Runs on the worker QThread — performs all DB queries."""
        try:
            db = self._get_db()
            stats = db.get_stats()
            photos_by_status = stats.get("photos_by_status", {})
            upload_stats = db.get_upload_stats_unique()
            persons = db.get_all_persons()
            enrollments = {e.person_id: e for e in db.get_all_enrollments()}
            pinned_ids = set(db.get_pinned_person_ids())

            incoming = 0
            config = self._get_config()
            if config.incoming_dir.exists():
                incoming = len([
                    f for f in config.incoming_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in config.supported_extensions
                ])

            payload = {
                "stats": stats,
                "photos_by_status": photos_by_status,
                "upload_stats": upload_stats,
                "persons": persons,
                "enrollments": enrollments,
                "pinned_ids": pinned_ids,
                "incoming": incoming,
            }
            self.finished.emit(payload)
        except Exception:
            pass  # Silent fail — non-critical background fetch


class AuraApp(QMainWindow):
    """Main application window — Design Guide Layout."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("AURA")
        self.resize(980, 720)
        self.setMinimumSize(820, 560)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._mode = "light"

        self.config = get_config()

        self.last_photo_count = 0
        self.last_face_count = 0
        self.last_person_count = 0
        self.last_upload_stats = {}

        # Session log
        logs_dir = dist_utils.get_user_data_dir() / "logs"
        logs_dir.mkdir(exist_ok=True)
        session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_log_path = logs_dir / f"session_{session_timestamp}.txt"
        try:
            self.session_log_file = open(self.session_log_path, 'w', encoding='utf-8', buffering=1)
            self.session_log_file.write("=== AURA Session Log ===\n")
            self.session_log_file.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.session_log_file.write("=" * 50 + "\n\n")
        except Exception:
            self.session_log_file = None

        # Worker bridge for thread-safe UI updates
        self.bridge = WorkerBridge()
        self.bridge.log_received.connect(self._on_log_received)
        self.bridge.system_started.connect(self._on_system_started)
        self.bridge.system_stopped.connect(self._on_system_stopped)
        self.bridge.start_error.connect(self._on_start_error)
        self.bridge.restart_requested.connect(self._restart_app)

        # Build UI
        self._create_ui()

        # Process manager
        self.process_manager = ProcessManager(on_output=self._on_worker_output)

        # Background stats worker + thread
        self._stats_thread = QThread(self)
        self._stats_worker = StatsWorker(get_db, get_config)
        self._stats_worker.moveToThread(self._stats_thread)
        self._stats_worker.finished.connect(self._on_stats_ready)
        self._stats_thread.start()

        # Main-thread refresh timer — fires every 2 s and queues a worker fetch
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)  # 2 seconds
        self._refresh_timer.timeout.connect(self._trigger_stats_fetch)
        self._refresh_timer.start()

        # Initial fetch after 300 ms so the window is fully painted first
        QTimer.singleShot(300, self._trigger_stats_fetch)

        # First-time GPU prompt (500ms after launch so window is visible)
        QTimer.singleShot(500, self._check_first_time_gpu)

        # Create overlay splash screen — parented to QMainWindow itself
        # so it covers the ENTIRE window (including menu bar).
        self.splash_overlay = PremiumSplashScreen(self)
        self.splash_overlay.setGeometry(0, 0, self.width(), self.height())
        self.splash_overlay.raise_()
        self.splash_overlay.show()
        
        # Clear reference when destroyed to avoid "Internal C++ object already deleted"
        self.splash_overlay.destroyed.connect(lambda: setattr(self, 'splash_overlay', None))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Safely wrap in try-except and check for existence
        try:
            if getattr(self, 'splash_overlay', None) and self.splash_overlay.isVisible():
                self.splash_overlay.setGeometry(0, 0, self.width(), self.height())
        except RuntimeError:
            self.splash_overlay = None  # Reference still exists but C++ object is gone

    def _on_worker_output(self, message, level):
        """Handle output from worker/server processes — called from background thread."""
        # Use signal to marshal to UI thread
        self.bridge.log_received.emit(message, level)

        if self.session_log_file:
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.session_log_file.write(f"{timestamp}  •  {message}\n")
            except Exception:
                pass

    def _on_log_received(self, message, level):
        """Handle log message on the UI thread."""
        self.activity_log.add_log(message, level)

    def _create_ui(self):
        # =====================================================================
        # MENU BAR — flat top-level actions (no sub-menus)
        # =====================================================================
        menu_bar = self.menuBar()

        # ── Process Health Monitor ─────────────────────────────────────────────
        act_monitor = QAction("Monitor", self)
        act_monitor.setStatusTip("Open real-time CPU/GPU and processing graphs")
        act_monitor.triggered.connect(self._open_health_monitor)
        menu_bar.addAction(act_monitor)

        # ── Open Event Folder ─────────────────────────────────────────────────
        act_folder = QAction("Folder", self)
        act_folder.setStatusTip("Open the event root folder in Explorer")
        act_folder.triggered.connect(self._open_event_folder)
        menu_bar.addAction(act_folder)

        # ── Merge Clusters ────────────────────────────────────────────────────
        act_merge = QAction("Merge", self)
        act_merge.setStatusTip("Visually compare and merge two person clusters")
        act_merge.triggered.connect(self._open_merge_dialog)
        menu_bar.addAction(act_merge)

        # ── Settings ─────────────────────────────────────────────────────────
        act_settings = QAction("Settings", self)
        act_settings.setStatusTip("Configure application settings")
        act_settings.triggered.connect(self._open_settings_dialog)
        menu_bar.addAction(act_settings)

        # ── Erase Data ────────────────────────────────────────────────────────
        act_erase = QAction("Erase Data", self)
        act_erase.setStatusTip("Completely reset the database and delete all photos")
        act_erase.triggered.connect(self._open_erase_data_confirmation)
        menu_bar.addAction(act_erase)

        # ── Repair Database ───────────────────────────────────────────────────
        act_repair = QAction("Repair", self)
        act_repair.setStatusTip("Run self-healing database diagnostics and repair")
        act_repair.triggered.connect(self._open_self_healing)
        menu_bar.addAction(act_repair)

        # ── Auth Manager ──────────────────────────────────────────────────────
        self.act_auth = QAction("Auth  ●", self)
        self.act_auth.setStatusTip("Manage Google Drive OAuth token")
        self.act_auth.triggered.connect(self._open_auth_dialog)
        menu_bar.addAction(self.act_auth)
        QTimer.singleShot(200, self._update_auth_btn_state)

        # ── Theme toggle ──────────────────────────────────────────────────────
        self.act_theme = QAction("Light", self)
        self.act_theme.setStatusTip("Toggle between light and dark mode")
        self.act_theme.triggered.connect(self._toggle_theme)
        menu_bar.addAction(self.act_theme)

        # ── Open Session Log ──────────────────────────────────────────────────
        act_logs = QAction("Log", self)
        act_logs.setStatusTip("Open the current session log file")
        act_logs.triggered.connect(self._open_session_log)
        menu_bar.addAction(act_logs)

        # =====================================================================
        # CENTRAL WIDGET
        # =====================================================================
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 14, 20, 14)
        main_layout.setSpacing(10)

        # =====================================================================
        # ZONE 1: Header  — title · health · status · start/stop only
        # =====================================================================
        header = QHBoxLayout()
        header.setSpacing(12)

        # Title
        title = QLabel("AURA")
        title.setObjectName("app_title")
        header.addWidget(title)

        header.addStretch()

        # GPU status toast (temporary, fades away after a few seconds)
        self._gpu_toast = QLabel()
        self._gpu_toast.setFixedHeight(24)
        self._gpu_toast.setVisible(False)
        self._gpu_toast_opacity = QGraphicsOpacityEffect(self._gpu_toast)
        self._gpu_toast_opacity.setOpacity(1.0)
        self._gpu_toast.setGraphicsEffect(self._gpu_toast_opacity)
        header.addWidget(self._gpu_toast)

        # GPU mode badge (permanent tiny pill)
        self._gpu_badge = QLabel()
        self._gpu_badge.setFixedHeight(24)
        self._gpu_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 2px 10px; "
            "border-radius: 12px; background: #f0f0f5; color: #86868b;"
        )
        self._update_gpu_badge()
        header.addWidget(self._gpu_badge)

        # System health indicator
        self.health_indicator = SystemHealthIndicator()
        header.addWidget(self.health_indicator)

        # Status indicator
        self.status_indicator = StatusIndicator()
        header.addWidget(self.status_indicator)

        # START / STOP button  (the only button that stays in the header)
        self.start_stop_btn = QPushButton("▶  START")
        self.start_stop_btn.setObjectName("start_btn")
        self.start_stop_btn.setFixedSize(110, 36)
        self.start_stop_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_stop_btn.clicked.connect(self._toggle_system)
        header.addWidget(self.start_stop_btn)

        main_layout.addLayout(header)

        # =====================================================================
        # ZONE 2: Top Statistics Row (5 cards)
        # =====================================================================
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(6)

        self.photos_card = StatCard("Total Photos", "0")
        stats_layout.addWidget(self.photos_card)

        self.faces_card = StatCard("Total Faces", "0")
        stats_layout.addWidget(self.faces_card)

        self.people_card = StatCard("No of Persons", "0")
        stats_layout.addWidget(self.people_card)

        self.enrolled_card = StatCard("Enrolled", "0")
        stats_layout.addWidget(self.enrolled_card)

        self.match_card = SyncStatusCard()
        stats_layout.addWidget(self.match_card)

        main_layout.addLayout(stats_layout)

        # =====================================================================
        # ZONE 3: Main Content (Left ~70% + Right ~30%)
        # =====================================================================
        content = QGridLayout()
        content.setSpacing(10)
        content.setColumnStretch(0, 7)
        content.setColumnStretch(1, 3)

        # ----- LEFT COLUMN -----

        # Status area: left stack (Processing + Cloud) | right pair (Stuck + WhatsApp)
        status_row = QHBoxLayout()
        status_row.setSpacing(5)

        # Left — vertical stack: Processing on top, Cloud below
        left_stack = QVBoxLayout()
        left_stack.setSpacing(5)

        self.proc_widget = ProcessingWidget()
        left_stack.addWidget(self.proc_widget)

        self.cloud_widget = CloudWidget()
        left_stack.addWidget(self.cloud_widget)

        status_row.addLayout(left_stack, 5)

        # Right — Stuck Photos and WhatsApp side by side
        self.stuck_card = StuckPhotosCard()
        status_row.addWidget(self.stuck_card, 2)

        self.wa_tracker = WhatsAppTrackerWidget()
        status_row.addWidget(self.wa_tracker, 2)

        status_container = QWidget()
        status_container.setLayout(status_row)
        content.addWidget(status_container, 0, 0)

        # Activity log
        self.activity_log = ActivityLog()
        content.addWidget(self.activity_log, 1, 0)
        self.activity_log.add_log("App started", "success")

        # ----- RIGHT COLUMN (Sidebar — People List) -----
        right_sidebar = QFrame()
        right_sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(right_sidebar)
        sidebar_layout.setContentsMargins(10, 14, 10, 12)
        sidebar_layout.setSpacing(8)

        sidebar_title = QLabel("PEOPLE")
        sidebar_title.setObjectName("sidebar_title")
        sidebar_layout.addWidget(sidebar_title)

        self.people_list = PeopleList()
        sidebar_layout.addWidget(self.people_list)

        content.addWidget(right_sidebar, 0, 1, 2, 1)

        main_layout.addLayout(content)

    # =====================================================================
    # System Control
    # =====================================================================
    def _toggle_system(self):
        """Start or stop the system."""
        if self.process_manager.is_running():
            self._stop_system()
        else:
            self._start_system()

    def _start_system(self):
        """Start the backend and frontend."""
        self.status_indicator.set_starting()
        self.start_stop_btn.setEnabled(False)
        self.start_stop_btn.setText("Starting...")
        self.activity_log.add_log("Starting system...", "info")
        self._log_to_session("[APP] User clicked START button")

        def start_async():
            try:
                self.process_manager.start()
                time.sleep(2)
                self.bridge.system_started.emit()
            except Exception as e:
                self.bridge.start_error.emit(str(e))

        threading.Thread(target=start_async, daemon=True).start()

    def _on_system_started(self):
        """Called when system has started — on UI thread via signal."""
        self.status_indicator.set_running()
        self.start_stop_btn.setEnabled(True)
        self.start_stop_btn.setText("■  STOP")
        self.start_stop_btn.setObjectName("stop_btn")
        # Force re-apply style for the new object name
        self.start_stop_btn.style().unpolish(self.start_stop_btn)
        self.start_stop_btn.style().polish(self.start_stop_btn)
        self.activity_log.add_log("System running! Worker + Web server active", "success")
        self.activity_log.add_log("Web UI: http://localhost:8000", "info")
        self._log_to_session("[APP] System started successfully")
        self.wa_tracker.set_system_active(True)

    def _on_start_error(self, error: str):
        """Called on start error — on UI thread via signal."""
        self.status_indicator.set_stopped()
        self.start_stop_btn.setEnabled(True)
        self.start_stop_btn.setText("▶  START")
        self.start_stop_btn.setObjectName("start_btn")
        self.start_stop_btn.style().unpolish(self.start_stop_btn)
        self.start_stop_btn.style().polish(self.start_stop_btn)
        self.activity_log.add_log(f"Start failed: {error}", "error")

    def _stop_system(self):
        """Stop the backend and frontend."""
        self.status_indicator.set_stopping()
        self.start_stop_btn.setEnabled(False)
        self.start_stop_btn.setText("Stopping...")
        self.activity_log.add_log("Stopping system...", "info")
        self._log_to_session("[APP] User clicked STOP button")

        def stop_async():
            self.process_manager.stop()
            time.sleep(1)
            self.bridge.system_stopped.emit()

        threading.Thread(target=stop_async, daemon=True).start()

    def _on_system_stopped(self):
        """Called when system has stopped — on UI thread via signal."""
        self.status_indicator.set_stopped()
        self.start_stop_btn.setEnabled(True)
        self.start_stop_btn.setText("▶  START")
        self.start_stop_btn.setObjectName("start_btn")
        self.start_stop_btn.style().unpolish(self.start_stop_btn)
        self.start_stop_btn.style().polish(self.start_stop_btn)
        self.activity_log.add_log("System stopped", "info")
        self._log_to_session("[APP] System stopped successfully")
        self.wa_tracker.set_system_active(False)

    # =====================================================================
    # Stats Refresh
    # =====================================================================
    def _trigger_stats_fetch(self):
        """Emit the trigger signal to kick off a DB fetch on the worker thread.
        Because the worker lives on a different QThread, Qt automatically uses
        a QueuedConnection — fetch() runs on the worker thread, never the UI thread.
        """
        self._stats_worker.trigger.emit()

    def _on_stats_ready(self, payload: dict):
        """Receive stats from the background worker and update all UI widgets.
        This slot always runs on the main (UI) thread via Qt's signal/slot mechanism.
        """
        try:
            stats = payload["stats"]
            photos_by_status = payload["photos_by_status"]
            upload_stats = payload["upload_stats"]
            persons = payload["persons"]
            enrollments = payload["enrollments"]
            incoming = payload["incoming"]

            total = sum(photos_by_status.values())
            completed = photos_by_status.get("completed", 0) + photos_by_status.get("no_faces", 0)
            errors = photos_by_status.get("error", 0)
            processing = photos_by_status.get("processing", 0)
            pending = photos_by_status.get("pending", 0)

            # ── Stat cards ────────────────────────────────────────────────────
            self.photos_card.update_value(str(total))
            self.faces_card.update_value(str(stats.get("total_faces", 0)))
            self.people_card.update_value(str(stats.get("total_persons", 0)))
            self.enrolled_card.update_value(str(stats.get("total_enrollments", 0)))

            # ── Processing ring ───────────────────────────────────────────────
            session_total = completed + errors + processing + pending
            session_done = completed + errors
            self.proc_widget.update_progress(session_done, session_total)

            if processing > 0:
                self.proc_widget.start_processing()
            elif session_done >= session_total and session_total > 0:
                self.proc_widget.stop_processing()
            elif incoming > 0:
                self.proc_widget.start_processing()
                self.proc_widget.status_label.setText("Waiting...")
                self.proc_widget.status_label.setStyleSheet(
                    f"color: {c('warning', self._mode)};"
                )

            # ── Cloud upload stats ────────────────────────────────────────────
            if upload_stats != self.last_upload_stats:
                by_status = upload_stats.get('by_status', {})
                uploading_total = by_status.get('uploading', 0)
                uploads_completed = by_status.get('completed', 0)
                uploads_pending   = by_status.get('pending', 0)
                uploads_failed    = by_status.get('failed', 0)
                uploads_total = uploads_completed + uploads_pending + uploading_total + uploads_failed

                # m / n progress counter (same style as Processing widget)
                self.cloud_widget.update_progress(uploads_completed, uploads_total)

                if uploading_total > 0:
                    self.cloud_widget.start_uploading()
                    self.cloud_widget.status_label.setText(f"Uploading {uploading_total}...")
                else:
                    self.cloud_widget.stop_uploading()
                    self.cloud_widget.status_label.setText("Synced")

                self.last_upload_stats = upload_stats

            # ── Cloud & Local match card ───────────────────────────────────────
            self._update_cloud_local_match_from_data(photos_by_status, upload_stats)

            # ── Stuck photos ──────────────────────────────────────────────────
            self._update_stuck_photos_from_data(photos_by_status)

            # ── WhatsApp delivery tracker ─────────────────────────────────────
            self.wa_tracker.refresh(stats.get("total_enrollments", 0))

            # ── System health ─────────────────────────────────────────────────
            self._update_system_health(processing, pending, incoming, upload_stats)

            # ── Activity log — new detections ─────────────────────────────────
            if total > self.last_photo_count:
                self.activity_log.add_log(
                    f"{total - self.last_photo_count} new photo(s)", "info"
                )
            if stats.get("total_faces", 0) > self.last_face_count:
                self.activity_log.add_log(
                    f"{stats['total_faces'] - self.last_face_count} face(s) detected", "success"
                )
            if stats.get("total_persons", 0) > self.last_person_count:
                new_count = stats.get("total_persons", 0) - self.last_person_count
                self.activity_log.add_log(
                    f"{new_count} New person(s) identified", "success"
                )

            self.last_photo_count = total
            self.last_face_count = stats.get("total_faces", 0)
            self.last_person_count = stats.get("total_persons", 0)

            # ── People list ────────────────────────────────────────────────────
            pinned_ids = payload.get("pinned_ids", set())
            self.people_list.update_persons(persons, enrollments, pinned_ids)

        except Exception:
            pass  # Silent fail — non-critical UI update

    def _update_cloud_local_match_from_data(self, photos_by_status, upload_stats):
        """Check if cloud uploads match local repository state — animated state transitions."""
        try:
            from .widgets.sync_status_card import (
                STATE_IDLE, STATE_SYNCING, STATE_MATCHED,
                STATE_FAILED, STATE_WARNING
            )

            completed_photos = photos_by_status.get("completed", 0) + photos_by_status.get("no_faces", 0)

            if completed_photos == 0:
                self.match_card.set_sync_state(STATE_IDLE, "—")
                return

            by_status = upload_stats.get('by_status', {}) if upload_stats else {}

            uploads_pending = by_status.get('pending', 0)
            uploads_uploading = by_status.get('uploading', 0)
            uploads_completed = by_status.get('completed', 0)
            uploads_failed = by_status.get('failed', 0)

            total_uploads = uploads_pending + uploads_uploading + uploads_completed + uploads_failed

            if total_uploads == 0 and completed_photos > 0:
                self.match_card.set_sync_state(STATE_WARNING, "NO")
                return

            all_uploaded = (
                uploads_pending == 0 and
                uploads_uploading == 0 and
                uploads_failed == 0 and
                uploads_completed > 0
            )

            if all_uploaded:
                self.match_card.set_sync_state(STATE_MATCHED, "YES ✓")
            elif uploads_failed > 0:
                self.match_card.set_sync_state(STATE_FAILED, "NO ✗")
            else:
                self.match_card.set_sync_state(STATE_SYNCING, "SYNCING")
        except Exception:
            self.match_card.set_sync_state(STATE_IDLE, "—")

    def _update_stuck_photos_from_data(self, photos_by_status):
        """Update stuck photos count (no DB call — data already fetched)."""
        try:
            proc_stuck = photos_by_status.get("processing", 0)
            by_status = self.last_upload_stats.get('by_status', {})
            cloud_stuck = by_status.get('uploading', 0)
            self.stuck_card.update_stuck(proc_stuck, cloud_stuck)
        except Exception:
            pass

    def _update_system_health(self, processing, pending, incoming, upload_stats):
        """Update system health indicator."""
        try:
            if not self.process_manager.is_running():
                self.health_indicator.set_offline()
                return

            by_status = upload_stats.get('by_status', {}) if upload_stats else {}
            image_analysis_busy = (processing > 0 or pending > 0)
            cloud_upload_busy = (
                by_status.get('pending', 0) > 0 or
                by_status.get('uploading', 0) > 0
            )

            if image_analysis_busy or cloud_upload_busy:
                self.health_indicator.set_busy()
            else:
                self.health_indicator.set_idle()
        except Exception:
            pass

    # =====================================================================
    # Utility
    # =====================================================================
    def _log_to_session(self, message: str):
        """Write a message directly to the session log file."""
        if self.session_log_file:
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.session_log_file.write(f"{timestamp}  •  {message}\n")
            except Exception:
                pass

    def _open_health_monitor(self):
        """Open the process health monitor dialog."""
        dialog = HealthMonitorDialog(mode=self._mode, parent=self)
        dialog.show()  # Non-modal — user can keep working
        self.activity_log.add_log("Opened health monitor", "info")
        self._log_to_session("[APP] Admin opened health monitor")

    def _open_merge_dialog(self):
        """Open the cluster merge dialog."""
        dialog = ClusterMergeDialog(mode=self._mode, parent=self)
        dialog.merge_completed.connect(self._on_merge_completed)
        dialog.exec()

    def _open_settings_dialog(self):
        """Open the settings configuration dialog."""
        dialog = SettingsDialog(mode=self._mode, parent=self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _open_self_healing(self):
        """Open the self-healing database dialog."""
        dialog = SelfHealingDialog(mode=self._mode, parent=self)
        dialog.repair_completed.connect(self._on_repair_completed)
        dialog.exec()

    def _open_erase_data_confirmation(self):
        """Prompt to erase all data and reset the system."""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.warning(
            self,
            "⚠️ COMPREHENSIVE SYSTEM RESET ⚠️",
            "This will PERMANENTLY delete:\n\n"
            "1. All photos (Incoming, Processed, People/Folders)\n"
            "2. All guest records, face fingerprints, and match data\n"
            "3. All cloud upload history\n"
            "4. All log files\n\n"
            "Are you ABSOLUTELY sure you want to proceed?\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._execute_erase_data()

    def _execute_erase_data(self):
        """Execute the thorough data erasure and alert the user when done."""
        # Stop background UI refresh to release any SQLite locks
        self._refresh_timer.stop()
        
        self.activity_log.add_log("Stopping workers and erasing system data...", "warning")
        self._log_to_session("[APP] Admin initiated complete system reset")

        # Properly close the session log handle so it can be deleted
        if self.session_log_file:
            try:
                self.session_log_file.close()
            except Exception:
                pass
            self.session_log_file = None

        if self.process_manager.is_running():
            self._stop_system()

        def _do_erase():
            # Wait until the process manager confirms all background workers are dead
            while self.process_manager.is_running():
                time.sleep(0.5)
            
            # Tell the StatsWorker thread to exit to help garbage collect its connections
            self._stats_thread.quit()
            self._stats_thread.wait(1000)
            
            # Close the main thread's DB connection globally
            try:
                from app.db import get_db
                get_db().close()
            except Exception:
                pass

            # Additional small grace period for file handle releases
            time.sleep(1)
            
            try:
                # Import dynamically to ensure cleanly segregated execution
                import erase_all_data
                erase_all_data.main(auto_confirm=True)
                
                # Use signal to avoid cross-thread UI updates
                self.bridge.log_received.emit("System reset complete. Restarting application...", "success")
                
                # Give the user 2 seconds to see the message before restarting
                time.sleep(2)
                self.bridge.restart_requested.emit()
            except Exception as e:
                self.bridge.log_received.emit(f"Error erasing data: {e}", "error")

        import threading
        threading.Thread(target=_do_erase, daemon=True).start()

    def _restart_app(self):
        """Prompt user and re-launch the current application."""
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.information(
            self,
            "Reset Complete",
            "System reset is complete!\n\n"
            "It is highly recommended to restart the application now to ensure "
            "all database connections and logs are cleanly initialized for a fresh start.\n\n"
            "Would you like to restart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.No:
            self.activity_log.add_log("Restart declined. Manual restart is recommended.", "warning")
            return

        self._log_to_session("[APP] User initiated automatic restart")
        if self.session_log_file:
            try:
                self.session_log_file.close()
            except Exception:
                pass
        
        import subprocess
        
        # In PyInstaller, sys.executable is the .exe itself. In dev mode, it's python.exe.
        if getattr(sys, 'frozen', False):
            subprocess.Popen([sys.executable])
        else:
            subprocess.Popen([sys.executable] + sys.argv)
        
        # Give a moment for the new process to start, then quit this one
        QApplication.quit()

    def _open_auth_dialog(self):
        """Open the Google Drive Auth Manager dialog."""
        dialog = AuthDialog(mode=self._mode, parent=self)
        dialog.auth_updated.connect(self._on_auth_updated)
        dialog.exec()

    def _on_auth_updated(self):
        """Called when the auth dialog successfully refreshes or re-authenticates."""
        self.activity_log.add_log("Google Drive token updated successfully ✓", "success")
        self._log_to_session("[APP] Admin refreshed/re-authenticated Google Drive token via GUI")
        # Re-check token health and update button
        QTimer.singleShot(100, self._update_auth_btn_state)

    def _update_auth_btn_state(self):
        """Update the Auth Manager menu action text to show token health status."""
        try:
            import sys
            sys.path.insert(0, str(BACKEND_DIR))
            from app.cloud import get_auth_status
            status = get_auth_status()
            if status.get("token_exists") and not status.get("token_expired"):
                self.act_auth.setText("Auth  \u2713")
            else:
                self.act_auth.setText("Auth  \u2717")
        except Exception:
            pass  # Silent — non-critical UI decoration

    def _on_repair_completed(self):
        """Handle repair completion — refresh stats and log."""
        self.activity_log.add_log("Database repair action completed", "success")
        self._log_to_session("[APP] Admin ran self-healing database repair")
        QTimer.singleShot(100, self._refresh_stats)

    def _on_settings_saved(self):
        """Handle settings being saved — reload config and log."""
        from app.config import reset_config
        reset_config()
        self.config = get_config()
        self.activity_log.add_log("Settings saved — config reloaded", "success")
        self._log_to_session("[APP] Admin saved settings via GUI")

    def _on_merge_completed(self):
        """Handle successful merge — refresh stats and log."""
        self.activity_log.add_log("Clusters merged successfully", "success")
        self._log_to_session("[APP] Admin merged two person clusters")
        QTimer.singleShot(100, self._refresh_stats)

    def _open_event_folder(self):
        os.startfile(str(self.config.event_root))
        self.activity_log.add_log("Opened folder", "info")

    def _toggle_theme(self):
        """Toggle between light and dark mode."""
        self._set_theme("dark" if self._mode == "light" else "light")

    def _set_theme(self, mode: str):
        """Switch to the given theme ('light' or 'dark') and update the toggle label."""
        if mode == self._mode:
            return
        self._mode = mode
        if mode == "dark":
            QApplication.instance().setStyleSheet(DARK_QSS)
            self.act_theme.setText("Dark")
        else:
            QApplication.instance().setStyleSheet(LIGHT_QSS)
            self.act_theme.setText("Light")

        # Update all widgets that track mode
        self.proc_widget.set_mode(self._mode)
        self.cloud_widget.set_mode(self._mode)
        self.photos_card.set_mode(self._mode)
        self.faces_card.set_mode(self._mode)
        self.people_card.set_mode(self._mode)
        self.enrolled_card.set_mode(self._mode)
        self.match_card.set_mode(self._mode)
        self.stuck_card.set_mode(self._mode)
        self.wa_tracker.set_mode(self._mode)
        self.status_indicator.set_mode(self._mode)
        self.health_indicator.set_mode(self._mode)
        self.people_list.set_mode(self._mode)
        self._update_gpu_badge()

    # =====================================================================
    # GPU Integration
    # =====================================================================
    def _update_gpu_badge(self):
        """Update the GPU mode badge in the header."""
        try:
            from app.gpu_manager import get_execution_config
            exec_cfg = get_execution_config(
                gpu_enabled=self.config.gpu_acceleration,
                gpu_device_id=self.config.gpu_device_id,
            )
            if "CUDAExecutionProvider" in exec_cfg.providers:
                self._gpu_badge.setText("⚡ GPU")
                if self._mode == "dark":
                    self._gpu_badge.setStyleSheet(
                        "font-size: 11px; font-weight: bold; padding: 2px 10px; "
                        "border-radius: 12px; background: #0d3d30; color: #30d158;"
                    )
                else:
                    self._gpu_badge.setStyleSheet(
                        "font-size: 11px; font-weight: bold; padding: 2px 10px; "
                        "border-radius: 12px; background: #ecfdf5; color: #059669;"
                    )
            else:
                self._gpu_badge.setText("● CPU")
                if self._mode == "dark":
                    self._gpu_badge.setStyleSheet(
                        "font-size: 11px; font-weight: bold; padding: 2px 10px; "
                        "border-radius: 12px; background: #2c2c2e; color: #98989d;"
                    )
                else:
                    self._gpu_badge.setStyleSheet(
                        "font-size: 11px; font-weight: bold; padding: 2px 10px; "
                        "border-radius: 12px; background: #f0f0f5; color: #86868b;"
                    )
        except Exception:
            self._gpu_badge.setText("● CPU")

    def _show_gpu_toast(self, text: str, color_type: str = "blue"):
        """Show a temporary GPU status toast in the header that fades after 5 seconds.
        color_type: 'blue' (CPU/no GPU), 'green' (GPU active), 'amber' (GPU but needs setup)
        """
        if color_type == "green":
            if self._mode == "dark":
                style = ("font-size: 11px; font-weight: bold; padding: 2px 12px; "
                         "border-radius: 12px; background: #0d3d30; color: #30d158;")
            else:
                style = ("font-size: 11px; font-weight: bold; padding: 2px 12px; "
                         "border-radius: 12px; background: #ecfdf5; color: #059669;")
        elif color_type == "amber":
            if self._mode == "dark":
                style = ("font-size: 11px; font-weight: bold; padding: 2px 12px; "
                         "border-radius: 12px; background: #3d2e0d; color: #f5a623;")
            else:
                style = ("font-size: 11px; font-weight: bold; padding: 2px 12px; "
                         "border-radius: 12px; background: #fef9ec; color: #b45309;")
        else:  # blue
            if self._mode == "dark":
                style = ("font-size: 11px; font-weight: bold; padding: 2px 12px; "
                         "border-radius: 12px; background: #0d2d3d; color: #4da6ff;")
            else:
                style = ("font-size: 11px; font-weight: bold; padding: 2px 12px; "
                         "border-radius: 12px; background: #eff6ff; color: #2563eb;")

        self._gpu_toast.setText(text)
        self._gpu_toast.setStyleSheet(style)
        self._gpu_toast_opacity.setOpacity(1.0)
        self._gpu_toast.setVisible(True)

        # Start fade-out after 5 seconds
        QTimer.singleShot(5000, self._fade_gpu_toast)

    def _fade_gpu_toast(self):
        """Smoothly fade out the GPU toast over 1.5 seconds then hide it."""
        self._gpu_toast_anim = QPropertyAnimation(self._gpu_toast_opacity, b"opacity")
        self._gpu_toast_anim.setDuration(1500)
        self._gpu_toast_anim.setStartValue(1.0)
        self._gpu_toast_anim.setEndValue(0.0)
        self._gpu_toast_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._gpu_toast_anim.finished.connect(lambda: self._gpu_toast.setVisible(False))
        self._gpu_toast_anim.start()

    def _check_first_time_gpu(self):
        """On first launch, show GPU toast and optionally offer GPU setup."""
        try:
            from app.gpu_manager import get_full_gpu_status
            gpu_info = get_full_gpu_status()

            # ── Already running on GPU ──
            if self.config.gpu_acceleration and gpu_info.cuda_provider_available:
                self._show_gpu_toast(
                    f"⚡ GPU found · using {gpu_info.gpu_name}", "green"
                )
                self.activity_log.add_log(
                    f"⚡ GPU acceleration active — {gpu_info.gpu_name}", "success"
                )
                return

            # ── GPU found & whitelisted but not fully set up — show wizard popup ──
            if gpu_info.gpu_found and gpu_info.is_whitelisted:
                self._show_gpu_toast(
                    f"🖥️ {gpu_info.gpu_name} detected · setup needed", "amber"
                )
                self.activity_log.add_log(
                    f"GPU detected: {gpu_info.gpu_name} ({gpu_info.gpu_architecture}) — not yet enabled", "info"
                )

                # Show first-time prompt (unless dismissed or already started wizard)
                if (not self.config.gpu_prompt_dismissed
                        and self.config.gpu_wizard_step in ("not_started",)):
                    from .widgets.gpu_wizard import GPUDiscoveryPrompt
                    prompt = GPUDiscoveryPrompt(
                        gpu_info, mode=self._mode, parent=self
                    )
                    prompt.setup_requested.connect(self._open_gpu_wizard)
                    prompt.exec()
                return

            # ── GPU found but unsupported ──
            if gpu_info.gpu_found and not gpu_info.is_whitelisted:
                self._show_gpu_toast("No compatible GPU · using CPU", "blue")
                self.activity_log.add_log(
                    f"● GPU found ({gpu_info.gpu_name}) but not supported — running in CPU mode", "info"
                )
                return

            # ── No GPU at all ──
            self._show_gpu_toast("No GPU found · using CPU", "blue")
            self.activity_log.add_log(
                "● No GPU detected — running in CPU mode", "info"
            )

        except Exception:
            self._show_gpu_toast("No GPU found · using CPU", "blue")
            self.activity_log.add_log(
                "● Running in CPU mode", "info"
            )

    def _open_gpu_wizard(self):
        """Open the GPU setup wizard dialog."""
        try:
            from .widgets.gpu_wizard import GPUWizardDialog
            wizard = GPUWizardDialog(mode=self._mode, parent=self)
            wizard.gpu_enabled.connect(self._on_gpu_state_changed)
            wizard.gpu_disabled.connect(self._on_gpu_state_changed)
            wizard.exec()
        except ImportError as e:
            self.activity_log.add_log(f"Failed to open GPU wizard: {e}", "error")

    def _on_gpu_state_changed(self):
        """Handle GPU enable/disable — reload config and update badge."""
        from app.config import reset_config
        reset_config()
        self.config = get_config()
        self._update_gpu_badge()
        mode_str = "GPU" if self.config.gpu_acceleration else "CPU"
        self.activity_log.add_log(
            f"Hardware acceleration mode changed to {mode_str}. Restart required.", "success"
        )
        self._log_to_session(f"[APP] GPU state changed: {mode_str}")

    def _open_session_log(self):
        """Open the current session log file in the default text editor."""
        if hasattr(self, 'session_log_path') and self.session_log_path.exists():
            os.startfile(str(self.session_log_path))
            self.activity_log.add_log("Opened session log", "info")
        else:
            self.activity_log.add_log("Session log not found", "warning")

    def closeEvent(self, event):
        """Handle window close — stop services first."""
        if self.process_manager.is_running():
            self.activity_log.add_log("Shutting down...", "info")
            self.process_manager.stop()

        # Stop the refresh timer and background stats thread cleanly
        self._refresh_timer.stop()
        self._stats_thread.quit()
        self._stats_thread.wait(2000)  # Give it 2 s to finish gracefully

        if hasattr(self, 'session_log_file') and self.session_log_file:
            try:
                self.session_log_file.write(f"\n{'=' * 50}\n")
                self.session_log_file.write(
                    f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                self.session_log_file.close()
            except Exception:
                pass

        event.accept()
