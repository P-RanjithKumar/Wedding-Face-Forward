"""
First-run setup wizard (added 2026-11-14).

Opens once, after the intro video, until finished or skipped
(FIRST_RUN_DONE=true in .env). Can be reopened from the "Setup" menu.

Steps:
  1. Welcome
  2. Photos folder   - where event photos live (EVENT_ROOT); new installs get
                       Pictures\\AURA instead of the hidden AppData folder
  3. Speed check     - GPU vs CPU test (backend/app/compute.py), plain result
  4. Google Drive    - connect now (existing Auth dialog) or skip
  5. Guests          - guest page link + QR code for phones on the same Wi-Fi
                       (if port 8000 is taken the port can differ; the dashboard
                       log shows the current link when processing starts)
  6. Done
"""

import io
import os
import socket
import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QFont, QPixmap, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QFileDialog, QProgressBar, QFrame, QLineEdit,
)

from ..theme import c

EVENT_SUBFOLDERS = ["Incoming", "Processed", "People",
                    "Admin/NoFaces", "Admin/Errors", "Admin/Uploads"]


def lan_ip() -> str:
    """This computer's address on the local network (no data is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 9))  # picks the outgoing interface only
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def guest_url() -> str:
    """Guest page address; the port is the one picked when processing last
    started (first free from 8000, see dist_utils.pick_guest_port)."""
    import dist_utils
    return f"http://{lan_ip()}:{dist_utils.get_guest_port()}"


def guest_page_running(timeout: float = 0.4) -> bool:
    """True if the guest web server answers on this PC right now."""
    import urllib.request
    import dist_utils
    try:
        url = f"http://127.0.0.1:{dist_utils.get_guest_port()}/api/health"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def qr_pixmap(text: str, scale: int = 7) -> QPixmap:
    import segno
    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="png", scale=scale, border=2)
    pix = QPixmap()
    pix.loadFromData(buf.getvalue(), "PNG")
    return pix


class _Bridge(QObject):
    speed_done = Signal(object)


class FirstRunWizard(QDialog):
    """Six-step setup guide for non-technical users."""

    completed = Signal()

    def __init__(self, mode="light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle("Set up AURA")
        self.setModal(True)
        self.setMinimumSize(620, 560)
        self._bridge = _Bridge()
        self._bridge.speed_done.connect(self._on_speed_done)
        self._speed_started = False

        import dist_utils
        from app.config import get_config
        cfg = get_config()
        env_root = os.getenv("EVENT_ROOT", "./EventRoot")
        if dist_utils.is_frozen() and not Path(env_root).is_absolute():
            self._folder = Path.home() / "Pictures" / "AURA"
        else:
            self._folder = Path(cfg.event_root)

        self._build()
        self._go(0)

    # ── layout helpers ───────────────────────────────────────────────
    def _title(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {c('text_primary', self._mode)};")
        lbl.setWordWrap(True)
        return lbl

    def _text(self, text, small=False):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setStyleSheet(f"color: {c('text_secondary' if small else 'text_primary', self._mode)}; "
                          f"font-size: {12 if small else 14}px; line-height: 1.4;")
        return lbl

    def _button(self, text, primary=False):
        b = QPushButton(text)
        b.setMinimumHeight(38)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if primary:
            b.setStyleSheet(f"QPushButton {{ background: {c('accent', self._mode)}; color: white; border: none; "
                            f"border-radius: 12px; font-size: 13px; font-weight: bold; padding: 0 20px; }}"
                            f"QPushButton:disabled {{ background: {c('border', self._mode)}; }}")
        else:
            b.setStyleSheet(f"QPushButton {{ background: {c('bg_card', self._mode)}; color: {c('text_primary', self._mode)}; "
                            f"border: 1px solid {c('border', self._mode)}; border-radius: 12px; font-size: 13px; padding: 0 16px; }}")
        return b

    def _page(self, *widgets):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(14)
        for w in widgets:
            if isinstance(w, QHBoxLayout):
                lay.addLayout(w)
            else:
                lay.addWidget(w)
        lay.addStretch()
        return page

    # ── pages ────────────────────────────────────────────────────────
    def _build(self):
        self.setStyleSheet(f"QDialog {{ background: {c('bg', self._mode)}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        self._step_label = QLabel()
        self._step_label.setStyleSheet(f"color: {c('accent', self._mode)}; font-size: 12px; font-weight: bold;")
        root.addWidget(self._step_label)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # 1. Welcome
        self._stack.addWidget(self._page(
            self._title("Welcome to AURA"),
            self._text("AURA finds every guest's photos automatically. Guests take a selfie on their "
                       "phone and get their own private gallery."),
            self._text("This short setup takes about a minute:\n"
                       "  1.  Choose where event photos are kept\n"
                       "  2.  A quick speed check of this computer\n"
                       "  3.  Connect Google Drive (optional)\n"
                       "  4.  Get the link and QR code for your guests"),
            self._text("You can change everything later in Settings, or open this guide again from the "
                       "Setup menu.", small=True),
        ))

        # 2. Photos folder
        self._folder_edit = QLineEdit(str(self._folder))
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setMinimumHeight(36)
        self._folder_edit.setStyleSheet(f"QLineEdit {{ background: {c('bg_card', self._mode)}; color: {c('text_primary', self._mode)}; "
                                        f"border: 1px solid {c('border', self._mode)}; border-radius: 8px; padding: 0 10px; font-size: 13px; }}")
        choose = self._button("Choose another folder...")
        choose.clicked.connect(self._choose_folder)
        row = QHBoxLayout()
        row.addWidget(self._folder_edit, 1)
        row.addWidget(choose)
        self._stack.addWidget(self._page(
            self._title("Where should event photos be kept?"),
            self._text("AURA keeps the event photos in this folder and sorts them into one folder per person."),
            row,
            self._text("How to use it: copy (or export from your camera software) the event photos into the "
                       "“Incoming” folder inside it. AURA picks them up automatically while processing is running.",
                       small=True),
            self._text("Pick a drive with plenty of free space. Photos stay here even if AURA is uninstalled.", small=True),
        ))

        # 3. Speed check
        self._speed_text = self._text("Checking how fast this computer can match faces...")
        self._speed_detail = self._text("", small=True)
        self._speed_bar = QProgressBar()
        self._speed_bar.setRange(0, 0)
        self._speed_bar.setFixedHeight(6)
        self._speed_bar.setTextVisible(False)
        self._stack.addWidget(self._page(
            self._title("Speed check"),
            self._text("AURA can use the graphics card (NVIDIA, AMD or Intel) or the processor. "
                       "It tests both once and keeps the faster one. Nothing to install."),
            self._speed_bar, self._speed_text, self._speed_detail,
        ))

        # 4. Google Drive
        self._drive_status = self._text("")
        connect = self._button("Connect Google Drive", primary=True)
        connect.clicked.connect(self._connect_drive)
        drive_row = QHBoxLayout()
        drive_row.addWidget(connect)
        drive_row.addStretch()
        self._stack.addWidget(self._page(
            self._title("Back up and share with Google Drive (optional)"),
            self._text("AURA can upload each guest's photos to an “AURA” folder in your Google Drive, "
                       "so guests can download them later (for example by WhatsApp link)."),
            drive_row, self._drive_status,
            self._text("Your browser opens Google's sign-in page. Choose your account and click Allow. "
                       "You can skip this and connect later from the Auth menu.", small=True),
        ))

        # 5. Guests
        url = guest_url()
        self._url_label = QLabel(url)
        self._url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._url_label.setStyleSheet(f"color: {c('accent', self._mode)}; font-size: 20px; font-weight: bold;")
        qr = QLabel()
        try:
            qr.setPixmap(qr_pixmap(url))
        except Exception:
            qr.setText("(QR code unavailable)")
        qr.setFixedSize(220, 220)
        qr.setScaledContents(True)
        qr.setStyleSheet("background: white; border-radius: 8px;")
        copy = self._button("Copy link")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(url))
        guest_col = QVBoxLayout()
        guest_col.addWidget(self._text("Guests open this on their phone:"))
        guest_col.addWidget(self._url_label)
        guest_col.addWidget(copy, 0, Qt.AlignmentFlag.AlignLeft)
        # Live status: the link only works while processing runs (START).
        # Owner scanned the QR during setup, before START, and it "didn't
        # work" (2026-11-14), so say it plainly here.
        self._guest_status = QLabel()
        self._guest_status.setWordWrap(True)
        guest_col.addWidget(self._guest_status)
        self._guest_timer = QTimer(self)
        self._guest_timer.setInterval(2000)
        self._guest_timer.timeout.connect(self._refresh_guest_status)
        guest_col.addWidget(self._text(
            "• Phones must be on the same Wi-Fi as this computer.\n"
            "• Processing must be running (Start button on the dashboard).\n"
            "• The first time, Windows asks whether AURA may use the network: "
            "tick “Private networks” and click Allow.\n"
            "• Print the QR code and put it on the tables.", small=True))
        guest_col.addStretch()
        guest_row = QHBoxLayout()
        guest_row.addWidget(qr, 0, Qt.AlignmentFlag.AlignTop)
        guest_row.addSpacing(16)
        guest_row.addLayout(guest_col, 1)
        self._stack.addWidget(self._page(self._title("Your guests' link"), guest_row))

        # 6. Done
        self._stack.addWidget(self._page(
            self._title("All set!"),
            self._text("Press Start on the dashboard, then copy the event photos into the “Incoming” "
                       "folder. People appear on the dashboard as AURA finds them."),
            self._text("Open this guide again any time from the Setup menu.", small=True),
        ))

        # Bottom bar
        bar = QHBoxLayout()
        self._skip_btn = QPushButton("Skip setup")
        self._skip_btn.setFlat(True)
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.setStyleSheet(f"color: {c('text_secondary', self._mode)}; border: none; font-size: 12px;")
        self._skip_btn.clicked.connect(self._finish)
        self._back_btn = self._button("Back")
        self._back_btn.clicked.connect(lambda: self._go(self._stack.currentIndex() - 1))
        self._next_btn = self._button("Next", primary=True)
        self._next_btn.clicked.connect(self._next)
        bar.addWidget(self._skip_btn)
        bar.addStretch()
        bar.addWidget(self._back_btn)
        bar.addWidget(self._next_btn)
        root.addLayout(bar)

    # ── navigation ───────────────────────────────────────────────────
    def _go(self, index):
        index = max(0, min(index, self._stack.count() - 1))
        self._stack.setCurrentIndex(index)
        last = index == self._stack.count() - 1
        self._step_label.setText(f"STEP {index + 1} OF {self._stack.count()}")
        self._back_btn.setVisible(index > 0)
        self._next_btn.setText("Finish" if last else "Next")
        self._skip_btn.setVisible(not last)
        if index == 2:
            self._start_speed_check()
        if index == 3:
            self._refresh_drive_status()
        if index == 4:
            self._refresh_guest_status()
            self._guest_timer.start()
        else:
            self._guest_timer.stop()

    def _next(self):
        index = self._stack.currentIndex()
        if index == 1 and not self._apply_folder():
            return
        if index == self._stack.count() - 1:
            self._finish()
        else:
            self._go(index + 1)

    def _finish(self):
        import dist_utils
        dist_utils.set_env_values({"FIRST_RUN_DONE": "true"})
        self.completed.emit()
        self.accept()

    # ── step logic ───────────────────────────────────────────────────
    def _choose_folder(self):
        start = str(self._folder if self._folder.exists() else Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Choose the folder for event photos", start)
        if chosen:
            self._folder = Path(chosen)
            self._folder_edit.setText(str(self._folder))

    def _apply_folder(self) -> bool:
        import dist_utils
        from app.config import get_config, reset_config
        try:
            for sub in EVENT_SUBFOLDERS:
                (self._folder / sub).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._folder_edit.setText(f"Cannot use this folder: {e}")
            return False
        if self._folder.resolve() != Path(get_config().event_root).resolve():
            dist_utils.set_env_values({"EVENT_ROOT": str(self._folder.resolve())})
            reset_config()
        return True

    def _start_speed_check(self):
        if self._speed_started:
            return
        self._speed_started = True
        from app.compute import describe_current, requested_device
        info = describe_current()
        if requested_device() != "auto" or not info["dml_available"] or info["tested"]:
            self._show_speed(info)
            return
        self._speed_text.setText("Checking how fast this computer can match faces... (about 30 seconds)")

        def work():
            from app.compute import benchmark_in_subprocess
            try:
                benchmark_in_subprocess()
            finally:
                self._bridge.speed_done.emit(None)
        threading.Thread(target=work, daemon=True).start()

    def _on_speed_done(self, _):
        from app.compute import describe_current
        self._show_speed(describe_current())

    def _show_speed(self, info):
        self._speed_bar.setRange(0, 1)
        self._speed_bar.setValue(1)
        rate_ms = info["gpu_ms"] if info["device"] == "gpu" else info["cpu_ms"]
        rate = f" — about {1000 / rate_ms:.1f} photos per second" if rate_ms else ""
        if info["device"] == "gpu":
            self._speed_text.setText(f"⚡ Your graphics card ({info['gpu_name'] or 'DirectML'}) "
                                     f"will do the face matching{rate}.")
        else:
            self._speed_text.setText(f"Your processor will do the face matching{rate}.")
        detail = info["reason"]
        if info["gpus"]:
            detail += f"\nGraphics found: {', '.join(info['gpus'])}"
        self._speed_detail.setText(detail + "\nYou can change this in Settings > Processing Speed.")

    def _refresh_guest_status(self):
        if guest_page_running():
            text, colour = ("🟢  Guest page is ON: phones on this Wi-Fi can open the link now.", c('success', self._mode))
        else:
            text, colour = ("🟠  Guest page is OFF right now. Finish this setup and press START on the dashboard; "
                            "the link and QR code work while processing is running.", c('warning', self._mode))
        self._guest_status.setText(text)
        self._guest_status.setStyleSheet(f"color: {colour}; font-size: 13px; font-weight: bold;")

    def _refresh_drive_status(self):
        try:
            from app.cloud import get_auth_status
            st = get_auth_status()
            if st.get("token_exists") and st.get("token_valid"):
                self._drive_status.setText("✓ Google Drive is connected.")
                self._drive_status.setStyleSheet(f"color: {c('success', self._mode)}; font-size: 14px; font-weight: bold;")
                return
        except Exception:
            pass
        self._drive_status.setText("Not connected yet.")
        self._drive_status.setStyleSheet(f"color: {c('text_secondary', self._mode)}; font-size: 14px;")

    def _connect_drive(self):
        from .auth_dialog import AuthDialog
        dlg = AuthDialog(mode=self._mode, parent=self)
        dlg.auth_updated.connect(self._refresh_drive_status)
        dlg.exec()
        self._refresh_drive_status()
