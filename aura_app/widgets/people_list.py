"""
PeopleList — Scrollable person list with pill-shaped rows, hover popups, VIP pinning, and thumbnails.
Ported from CustomTkinter PeopleList class.
"""

import os
import sys
import threading
import webbrowser
import hashlib
from pathlib import Path

from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QScrollArea, QWidget, QSizePolicy, QMenu
)
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt, QTimer, QPoint

from ..theme import c, COLORS
from .folder_popup import FolderChoicePopup

# Lazy imports for backend (avoids import errors if run standalone)
_db_module = None
_config_module = None


def _get_db():
    global _db_module
    if _db_module is None:
        from app.db import get_db as _get_db_func
        _db_module = _get_db_func
    return _db_module()


def _get_config():
    global _config_module
    if _config_module is None:
        from app.config import get_config as _get_config_func
        _config_module = _get_config_func
    return _config_module()


class PeopleList(QFrame):
    """Person list with pill-shaped items inside a scroll area.
    
    Supports VIP Pinning:
      - Right-click any row to Pin/Unpin as VIP
      - Pinned persons appear at the top under a gold 'VIP' section header
      - Pin state is persisted in the database
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("people_list_container")
        self.setStyleSheet("QFrame#people_list_container { background: transparent; border: none; }")

        self._mode = "light"
        self._last_hash = None
        self._last_counts = {}
        self._hover_timer_id = None
        self._popup = None
        self._thumb_cache = {}
        self._rows = []
        self._pinned_ids: set = set()  # Locally tracked pinned set for fast lookup

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setObjectName("people_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        main_layout.addWidget(self.scroll)

        # Scroll content widget
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(4, 0, 4, 0)
        self.scroll_layout.setSpacing(3)
        self.scroll_layout.addStretch()

        self.scroll.setWidget(self.scroll_content)

    # ─────────────────────────────────────────────────────────────────────────
    # Thumbnail helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_person_thumbnail(self, person_id, person_name, enrollment=None):
        """Get or generate a face thumbnail for a person."""
        if person_id in self._thumb_cache:
            cached = self._thumb_cache[person_id]
            if cached and Path(cached).exists():
                return cached

        try:
            config = _get_config()

            # Enrollment selfie
            if enrollment:
                selfie = Path(enrollment.selfie_path)
                if selfie.exists():
                    self._thumb_cache[person_id] = str(selfie)
                    return str(selfie)

            # Reference selfie
            person_dir = config.people_dir / person_name
            ref_selfie = person_dir / "00_REFERENCE_SELFIE.jpg"
            if ref_selfie.exists():
                self._thumb_cache[person_id] = str(ref_selfie)
                return str(ref_selfie)

            # Auto-generate from face bbox
            cache_dir = config.people_dir / ".thumbnails"
            cache_dir.mkdir(exist_ok=True)
            thumb_path = cache_dir / f"person_{person_id}.jpg"

            if thumb_path.exists():
                self._thumb_cache[person_id] = str(thumb_path)
                return str(thumb_path)

            # Generate: crop face from source photo
            db = _get_db()
            face_info = db.get_first_face_for_person(person_id)
            if not face_info or not face_info["processed_path"]:
                self._thumb_cache[person_id] = None
                return None

            src_path = Path(face_info["processed_path"])
            if not src_path.exists():
                self._thumb_cache[person_id] = None
                return None

            from PIL import Image
            img = Image.open(src_path)
            bx = face_info["bbox_x"]
            by = face_info["bbox_y"]
            bw = face_info["bbox_w"]
            bh = face_info["bbox_h"]

            pad = int(max(bw, bh) * 0.4)
            x1 = max(0, bx - pad)
            y1 = max(0, by - pad)
            x2 = min(img.width, bx + bw + pad)
            y2 = min(img.height, by + bh + pad)

            face_crop = img.crop((x1, y1, x2, y2))
            face_crop = face_crop.resize((120, 120), Image.LANCZOS)
            face_crop.save(str(thumb_path), "JPEG", quality=85)

            self._thumb_cache[person_id] = str(thumb_path)
            return str(thumb_path)

        except Exception:
            self._thumb_cache[person_id] = None
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Folder / cloud actions
    # ─────────────────────────────────────────────────────────────────────────

    def _open_person_folder(self, person_name):
        """Open the specific person's folder in file explorer."""
        try:
            config = _get_config()
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
                    folder_id = cloud.ensure_folder_path(["People", person_name])
                    if folder_id:
                        url = f"https://drive.google.com/drive/folders/{folder_id}"
                        webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=task, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    # Hover popup
    # ─────────────────────────────────────────────────────────────────────────

    def _close_popup(self):
        """Close the popup if it exists."""
        try:
            if self._popup:
                self._popup._safe_destroy()
        except Exception:
            pass
        self._popup = None

    def _show_choice_popup(self, x, y, person_name, person_id=None, enrollment=None):
        """Show the floating choice menu with optional face thumbnail."""
        self._close_popup()

        thumb = None
        if person_id is not None:
            thumb = self._get_person_thumbnail(person_id, person_name, enrollment)

        try:
            self._popup = FolderChoicePopup(
                x, y, person_name,
                on_local=lambda: self._open_person_folder(person_name),
                on_cloud=lambda: self._open_cloud_folder(person_name),
                thumbnail_path=thumb,
                mode=self._mode,
            )
        except Exception:
            self._popup = None

    # ─────────────────────────────────────────────────────────────────────────
    # VIP Pin / Unpin
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_pin(self, person_id, person_name):
        """Pin or unpin a person — persists to DB and forces a list rebuild."""
        def task():
            try:
                db = _get_db()
                if person_id in self._pinned_ids:
                    db.unpin_person(person_id)
                    self._pinned_ids.discard(person_id)
                else:
                    db.pin_person(person_id)
                    self._pinned_ids.add(person_id)
            except Exception:
                pass
            # Force a full rebuild on the UI thread by clearing the hash
            self._last_hash = None

        threading.Thread(target=task, daemon=True).start()

    def _load_pinned_ids(self):
        """Load VIP pin set from the DB (called from background thread in update_persons)."""
        try:
            db = _get_db()
            ids = db.get_pinned_person_ids()
            self._pinned_ids = set(ids)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Public update entry point
    # ─────────────────────────────────────────────────────────────────────────

    def update_persons(self, persons: list, enrollments: dict, pinned_ids: set = None):
        """Update the people list. Uses hash-based change detection.
        
        Args:
            persons: List of Person objects from the DB.
            enrollments: Dict mapping person_id -> Enrollment.
            pinned_ids: Set of pinned person IDs (fetched by background worker).
        """
        # Accept pinned_ids from the caller (background worker) or keep the
        # locally cached set if not provided (e.g., called standalone).
        if pinned_ids is not None:
            self._pinned_ids = pinned_ids

        current_counts = {}
        for p in persons:
            name = enrollments.get(p.id).user_name if p.id in enrollments else p.name
            current_counts[name] = p.face_count

        changes = []
        if self._last_counts:
            for name, count in current_counts.items():
                old_count = self._last_counts.get(name, 0)
                if count > old_count:
                    changes.append(name)

        self._last_counts = current_counts

        data_hash = str([(p.id, p.name, p.face_count, p.id in self._pinned_ids) for p in persons])
        if data_hash == self._last_hash:
            pass
        else:
            self._last_hash = data_hash
            self._rebuild_list(persons, enrollments)

        for name in changes:
            self.highlight_person(name)

    # ─────────────────────────────────────────────────────────────────────────
    # List building
    # ─────────────────────────────────────────────────────────────────────────

    def _rebuild_list(self, persons, enrollments):
        """Rebuild the entire list from scratch — pinned persons first, then rest."""
        # Clear existing
        self._rows.clear()
        while self.scroll_layout.count() > 0:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not persons:
            empty = QLabel("No people detected yet")
            empty.setStyleSheet(f"color: {c('text_secondary', self._mode)}; font-size: 13px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(empty)
            self.scroll_layout.addStretch()
            return

        # Separate pinned vs normal
        pinned_persons = [p for p in persons if p.id in self._pinned_ids]
        normal_persons = [p for p in persons if p.id not in self._pinned_ids]

        # ── VIP Section ─────────────────────────────────────────────────────
        if pinned_persons:
            for person in pinned_persons:
                row = self._make_person_row(person, enrollments, is_pinned=True)
                self.scroll_layout.addWidget(row)
                self._rows.append(row)

        # ── Normal Section ───────────────────────────────────────────────────
        for person in normal_persons:
            row = self._make_person_row(person, enrollments, is_pinned=False)
            self.scroll_layout.addWidget(row)
            self._rows.append(row)

        self.scroll_layout.addStretch()


    def _make_person_row(self, person, enrollments: dict, is_pinned: bool) -> QFrame:
        """Create a single pill-shaped person row widget."""
        enrollment = enrollments.get(person.id)
        name = enrollment.user_name if enrollment else person.name
        icon = "✓ " if enrollment else ""
        p_name = person.name  # Folder name

        # Pill-shaped row
        row = QFrame()
        row.setObjectName("person_row_vip" if is_pinned else "person_row")
        row.setFixedHeight(36)
        row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Enable right-click context menu
        row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, r=row: self._show_context_menu(pos, r)
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 4, 12, 4)
        row_layout.setSpacing(5)

        # Pin star badge (VIP only)
        if is_pinned:
            star = QLabel("⭐")
            star.setStyleSheet("font-size: 11px; background: transparent;")
            star.setFixedWidth(18)
            row_layout.addWidget(star)

        name_lbl = QLabel(f"{icon}{name}")
        name_lbl.setObjectName("person_name")
        row_layout.addWidget(name_lbl)

        row_layout.addStretch()

        count_lbl = QLabel(str(person.face_count))
        count_lbl.setObjectName("person_photos")
        row_layout.addWidget(count_lbl)

        # Store metadata for event handlers
        row.setProperty("p_name", p_name)
        row.setProperty("person_id", person.id)
        row.setProperty("enrollment", enrollment)
        row.setProperty("display_name", f"{icon}{name}")
        row.setProperty("is_pinned", is_pinned)

        # Install event filter for hover and click
        row.installEventFilter(self)

        return row

    # ─────────────────────────────────────────────────────────────────────────
    # Context menu (right-click)
    # ─────────────────────────────────────────────────────────────────────────

    def _show_context_menu(self, local_pos: QPoint, row: QFrame):
        """Show the right-click context menu for a person row."""
        person_id = row.property("person_id")
        p_name = row.property("p_name")
        is_pinned = person_id in self._pinned_ids

        menu = QMenu(self)

        # Styling
        bg = c("bg_card", self._mode)
        text = c("text_primary", self._mode)
        border = c("border", self._mode)
        accent = c("accent", self._mode)
        menu.setStyleSheet(
            f"QMenu {{ background: {bg}; color: {text}; border: 1px solid {border}; "
            f"border-radius: 10px; padding: 4px; font-size: 12px; }}"
            f"QMenu::item {{ padding: 8px 20px; border-radius: 6px; }}"
            f"QMenu::item:selected {{ background: {accent}; color: white; }}"
        )

        if is_pinned:
            pin_action = menu.addAction("📌  Unpin from VIP")
        else:
            pin_action = menu.addAction("⭐  Pin as VIP")

        menu.addSeparator()
        folder_action = menu.addAction("📁  Open Local Folder")
        cloud_action = menu.addAction("☁  Open Cloud Folder")

        # Show at cursor
        global_pos = row.mapToGlobal(local_pos)
        chosen = menu.exec(global_pos)

        if chosen == pin_action:
            self._toggle_pin(person_id, p_name)
        elif chosen == folder_action:
            self._open_person_folder(p_name)
        elif chosen == cloud_action:
            self._open_cloud_folder(p_name)

    # ─────────────────────────────────────────────────────────────────────────
    # Event filter (hover popup + click)
    # ─────────────────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        """Handle hover and click events on person rows."""
        if not isinstance(obj, QFrame) or obj.objectName() not in ("person_row", "person_row_vip"):
            return super().eventFilter(obj, event)

        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Type.Enter:
            p_name = obj.property("p_name")
            pid = obj.property("person_id")
            enr = obj.property("enrollment")

            # Cancel previous hover timer
            if self._hover_timer_id is not None:
                self._hover_timer_id = None

            # Start new hover timer for popup
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(600)
            global_pos = QCursor.pos()
            timer.timeout.connect(
                lambda: self._show_choice_popup(global_pos.x(), global_pos.y(), p_name, pid, enr)
            )
            timer.start()
            self._hover_timer_id = timer
            return False

        elif event.type() == QEvent.Type.Leave:
            # Cancel hover timer
            if self._hover_timer_id is not None:
                if isinstance(self._hover_timer_id, QTimer):
                    self._hover_timer_id.stop()
                self._hover_timer_id = None
            return False

        return super().eventFilter(obj, event)

    # ─────────────────────────────────────────────────────────────────────────
    # Highlight (flash animation)
    # ─────────────────────────────────────────────────────────────────────────

    def highlight_person(self, name_to_find):
        """Find and highlight a person in the list with flash animation."""
        search = name_to_find.lower().strip()
        found_widget = None

        for row in self._rows:
            display = row.property("display_name") or ""
            txt = display.lower()
            if txt.startswith("✓ "):
                txt = txt[2:]
            if search in txt:
                found_widget = row
                break

        if found_widget:
            accent = c("accent", self._mode)
            bg_card = c("bg_card", self._mode)
            is_pinned = found_widget.objectName() == "person_row_vip"

            def flash(step):
                try:
                    if not found_widget.isVisible():
                        return
                except Exception:
                    return

                if step > 5:
                    found_widget.setStyleSheet("")  # Reset to QSS defaults
                    return

                color = accent if step % 2 == 0 else bg_card
                obj_name = "person_row_vip" if is_pinned else "person_row"
                found_widget.setStyleSheet(
                    f"QFrame#{obj_name} {{ background-color: {color}; border-radius: 22px; }}"
                )
                QTimer.singleShot(200, lambda: flash(step + 1))

            flash(0)

    # ─────────────────────────────────────────────────────────────────────────
    # Theme
    # ─────────────────────────────────────────────────────────────────────────

    def set_mode(self, mode: str):
        self._mode = mode.lower()
        # Force rebuild on next update
        self._last_hash = None
