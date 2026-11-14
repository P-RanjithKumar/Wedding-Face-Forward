"""
Share Links — manual fallback for the automatic WhatsApp sender (2026-11-14).

Lists every guest who registered with a phone number, with the automatic
sender's status, and per guest:
  * Open WhatsApp  - opens wa.me/<number> with the message filled in
                     (WhatsApp Desktop or WhatsApp Web); you press Send
  * Copy message   - message + link to the clipboard
  * QR             - QR code of the link, for the guest to scan on the spot

Link: the guest's Google Drive folder (works anywhere) when Drive is
connected and "Use Google Drive links" is ticked; otherwise a direct link to
their gallery on the guest page (works on this Wi-Fi while processing runs).
"""

import json
import re
import threading
import urllib.parse

from PySide6.QtCore import Qt, Signal, QObject, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QWidget, QAbstractItemView,
)

from ..theme import c

# Same wording as whatsapp_tool/db_whatsapp_sender.py DEFAULT_MESSAGE_TEMPLATE
MESSAGE_TEMPLATE = "Hello {name}! Here are your photos from the event: {link}\n\nEnjoy!"

STATUS_TEXT = {"sent": "Sent ✓", "failed": "Failed", "invalid": "Invalid number",
               "retry": "Retrying", None: "Not sent yet"}


def whatsapp_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def wa_me_url(phone: str, message: str) -> str:
    return f"https://wa.me/{whatsapp_digits(phone)}?text={urllib.parse.quote(message)}"


def load_guests():
    """Guests with a phone number, newest first."""
    from app.db import get_db
    conn = get_db().connect()
    rows = conn.execute("""
        SELECT e.id AS enrollment_id, e.user_name, e.phone, e.person_id, p.name AS folder_name
        FROM enrollments e JOIN persons p ON e.person_id = p.id
        WHERE e.phone IS NOT NULL AND e.phone != ''
        ORDER BY e.created_at DESC, e.id DESC
    """).fetchall()
    return [dict(r) for r in rows]


def load_whatsapp_state() -> dict:
    import dist_utils
    path = dist_utils.get_user_data_dir() / "whatsapp_data" / "message_state_db.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class _Bridge(QObject):
    link_ready = Signal(int, str, str)   # row, link ("" = failed), action


class ShareLinksDialog(QDialog):

    def __init__(self, mode="light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle("Share photo links")
        self.setMinimumSize(820, 520)
        self._bridge = _Bridge()
        self._bridge.link_ready.connect(self._on_link_ready)
        self._drive_links = {}            # enrollment_id -> Drive link
        self._cloud = None
        self._cloud_lock = threading.Lock()
        self._guests = []
        self._build()
        self._reload()

    # ── UI ───────────────────────────────────────────────────────────
    def _build(self):
        self.setStyleSheet(f"QDialog {{ background: {c('bg', self._mode)}; }}"
                           f"QLabel {{ color: {c('text_primary', self._mode)}; }}"
                           f"QCheckBox {{ color: {c('text_primary', self._mode)}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        title = QLabel("Share photo links")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)
        hint = QLabel("Use this if the automatic WhatsApp sender can't send. “Open WhatsApp” opens a chat "
                      "with the message ready; just press Send. “QR” lets a guest scan their link on the spot.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {c('text_secondary', self._mode)}; font-size: 12px;")
        root.addWidget(hint)

        self._use_drive = QCheckBox("Use Google Drive links (work anywhere). Untick to use guest-page links (this Wi-Fi only).")
        self._use_drive.setChecked(self._drive_connected())
        self._use_drive.setEnabled(self._drive_connected())
        if not self._drive_connected():
            self._use_drive.setText("Google Drive is not connected: guest-page links are used (they work on this Wi-Fi "
                                    "while processing runs).")
        root.addWidget(self._use_drive)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Guest", "Phone", "WhatsApp", ""])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {c('bg_card', self._mode)}; color: {c('text_primary', self._mode)}; "
            f"border: 1px solid {c('border', self._mode)}; border-radius: 8px; gridline-color: {c('border', self._mode)}; }}"
            f"QHeaderView::section {{ background: {c('bg', self._mode)}; color: {c('text_secondary', self._mode)}; "
            f"border: none; padding: 6px; font-weight: bold; }}")
        root.addWidget(self._table, 1)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {c('text_secondary', self._mode)}; font-size: 12px;")
        root.addWidget(self._status)

        bar = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._reload)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        bar.addWidget(refresh)
        bar.addStretch()
        bar.addWidget(close)
        root.addLayout(bar)

    def _small_button(self, text, slot):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background: {c('accent', self._mode)}; color: white; border: none; "
                        f"border-radius: 8px; padding: 4px 10px; font-size: 12px; }}")
        b.clicked.connect(slot)
        return b

    def _reload(self):
        try:
            self._guests = load_guests()
        except Exception as e:
            self._guests = []
            self._status.setText(f"Could not read the guest list: {e}")
        state = load_whatsapp_state()
        self._table.setRowCount(len(self._guests))
        for row, g in enumerate(self._guests):
            status = state.get(str(g["enrollment_id"]), {}).get("status")
            self._table.setItem(row, 0, QTableWidgetItem(g["user_name"]))
            self._table.setItem(row, 1, QTableWidgetItem(g["phone"]))
            self._table.setItem(row, 2, QTableWidgetItem(STATUS_TEXT.get(status, status or "Not sent yet")))
            cell = QWidget()
            lay = QHBoxLayout(cell)
            lay.setContentsMargins(4, 2, 4, 2)
            lay.setSpacing(6)
            lay.addWidget(self._small_button("Open WhatsApp", lambda _=False, r=row: self._act(r, "whatsapp")))
            lay.addWidget(self._small_button("Copy message", lambda _=False, r=row: self._act(r, "copy")))
            lay.addWidget(self._small_button("QR", lambda _=False, r=row: self._act(r, "qr")))
            self._table.setCellWidget(row, 3, cell)
        self._table.resizeRowsToContents()
        if self._guests:
            self._status.setText(f"{len(self._guests)} guest(s) with a phone number.")
        elif not self._status.text():
            self._status.setText("No guests with a phone number yet.")

    # ── links ────────────────────────────────────────────────────────
    def _drive_connected(self) -> bool:
        try:
            from app.cloud import get_auth_status
            st = get_auth_status()
            return bool(st.get("token_exists") and st.get("token_valid"))
        except Exception:
            return False

    def _local_link(self, guest) -> str:
        import dist_utils
        from app.gallery_access import gallery_link
        from .first_run_wizard import lan_ip
        return gallery_link(f"http://{lan_ip()}:{dist_utils.get_guest_port()}", guest["person_id"])

    def _act(self, row, action):
        guest = self._guests[row]
        if not self._use_drive.isChecked():
            self._do(row, action, self._local_link(guest))
            return
        cached = self._drive_links.get(guest["enrollment_id"])
        if cached:
            self._do(row, action, cached)
            return
        self._status.setText(f"Getting the Google Drive link for {guest['user_name']}...")
        threading.Thread(target=self._resolve_drive_link, args=(row, action), daemon=True).start()

    def _resolve_drive_link(self, row, action):
        guest = self._guests[row]
        link = ""
        try:
            with self._cloud_lock:
                if self._cloud is None:
                    from app.cloud import CloudManager
                    self._cloud = CloudManager()
                cloud = self._cloud
            if cloud.is_enabled:
                # Same steps as the automatic sender (setup_drive_folder)
                people_id = cloud.ensure_folder_path(["People"])
                folder_id = cloud._find_folder(guest["folder_name"], parent_id=people_id) if people_id else None
                if folder_id and cloud.share_folder_publicly(folder_id):
                    link = cloud.get_folder_link(folder_id) or ""
        except Exception:
            link = ""
        self._bridge.link_ready.emit(row, link, action)

    def _on_link_ready(self, row, link, action):
        guest = self._guests[row]
        if link:
            self._drive_links[guest["enrollment_id"]] = link
            self._status.setText("")
            self._do(row, action, link)
        else:
            self._status.setText(f"No Google Drive folder for {guest['user_name']} yet (photos may not be uploaded). "
                                 f"Using the guest-page link instead.")
            self._do(row, action, self._local_link(guest))

    def _do(self, row, action, link):
        guest = self._guests[row]
        message = MESSAGE_TEMPLATE.format(name=guest["user_name"], link=link)
        if action == "whatsapp":
            digits = whatsapp_digits(guest["phone"])
            if not 7 <= len(digits) <= 15:
                self._status.setText(f"{guest['phone']} doesn't look like a phone number with country code.")
                return
            QDesktopServices.openUrl(QUrl(wa_me_url(guest["phone"], message)))
            self._status.setText(f"Opened WhatsApp for {guest['user_name']}: press Send there.")
        elif action == "copy":
            QGuiApplication.clipboard().setText(message)
            self._status.setText(f"Message for {guest['user_name']} copied.")
        else:
            self._show_qr(guest, link)

    def _show_qr(self, guest, link):
        from .first_run_wizard import qr_pixmap
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{guest['user_name']} - scan to open photos")
        dlg.setStyleSheet("QDialog { background: white; } QLabel { color: #111; }")
        lay = QVBoxLayout(dlg)
        name = QLabel(f"{guest['user_name']}: scan with your phone camera")
        name.setStyleSheet("font-size: 16px; font-weight: bold;")
        lay.addWidget(name, 0, Qt.AlignmentFlag.AlignHCenter)
        qr = QLabel()
        qr.setPixmap(qr_pixmap(link, scale=8))
        lay.addWidget(qr, 0, Qt.AlignmentFlag.AlignHCenter)
        url = QLabel(link)
        url.setWordWrap(True)
        url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        url.setStyleSheet("font-size: 11px; color: #555;")
        lay.addWidget(url)
        dlg.exec()
