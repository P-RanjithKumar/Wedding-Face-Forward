"""
ClusterMergeDialog — Side-by-side visual interface to merge person clusters.

The admin selects two persons (the one to KEEP and the one to MERGE INTO it).
Displays face thumbnails, names, face counts, and a sample photo grid for
each person so the admin can visually confirm they are the same person before
merging.
"""

import os
import sys
import shutil
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QComboBox, QSizePolicy, QGraphicsDropShadowEffect,
    QMessageBox, QApplication
)
from PySide6.QtGui import (
    QPixmap, QPainter, QPainterPath, QCursor, QColor,
    QFont, QLinearGradient, QBrush
)
from PySide6.QtCore import Qt, QTimer, QRectF, Signal, QObject

from ..theme import c, COLORS

# Lazy imports for backend
_db_module = None
_config_module = None
_cluster_module = None


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


def _merge_persons(keep_id, remove_id):
    global _cluster_module
    if _cluster_module is None:
        from app.cluster import merge_persons as _merge_func
        _cluster_module = _merge_func
    return _cluster_module(keep_id, remove_id)


def _make_rounded_pixmap(pixmap, width, height, radius=12):
    """Create a rounded-corner pixmap."""
    if pixmap.isNull():
        return pixmap

    # Scale to fill
    scaled = pixmap.scaled(
        width, height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation
    )

    # Center crop
    if scaled.width() > width or scaled.height() > height:
        x_off = (scaled.width() - width) // 2
        y_off = (scaled.height() - height) // 2
        scaled = scaled.copy(x_off, y_off, width, height)

    # Round corners
    rounded = QPixmap(width, height)
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return rounded


def _get_person_sample_photos(person_id, max_photos=6):
    """Get up to N sample photo paths for a person."""
    try:
        db = _get_db()
        conn = db.connect()
        cursor = conn.execute(
            """SELECT DISTINCT p.processed_path
               FROM faces f
               JOIN photos p ON f.photo_id = p.id
               WHERE f.person_id = ? AND p.processed_path IS NOT NULL
               ORDER BY p.id DESC
               LIMIT ?""",
            (person_id, max_photos)
        )
        rows = cursor.fetchall()
        conn.commit()
        return [row[0] for row in rows if row[0] and Path(row[0]).exists()]
    except Exception:
        return []


def _get_person_thumbnail_path(person_id, person_name):
    """Get the best thumbnail/selfie path for a person."""
    try:
        config = _get_config()

        # Check enrollment selfie
        db = _get_db()
        enrollment = db.get_enrollment_by_person(person_id)
        if enrollment:
            selfie = Path(enrollment.selfie_path)
            if selfie.exists():
                return str(selfie)

        # Check reference selfie
        person_dir = config.people_dir / person_name
        ref_selfie = person_dir / "00_REFERENCE_SELFIE.jpg"
        if ref_selfie.exists():
            return str(ref_selfie)

        # Check cached thumbnail
        cache_dir = config.people_dir / ".thumbnails"
        cache_dir.mkdir(exist_ok=True)
        thumb_path = cache_dir / f"person_{person_id}.jpg"
        if thumb_path.exists():
            return str(thumb_path)

        # Generate from face crop
        face_info = db.get_first_face_for_person(person_id)
        if not face_info or not face_info["processed_path"]:
            return None

        src_path = Path(face_info["processed_path"])
        if not src_path.exists():
            return None

        from PIL import Image
        img = Image.open(src_path)
        bx, by = face_info["bbox_x"], face_info["bbox_y"]
        bw, bh = face_info["bbox_w"], face_info["bbox_h"]

        pad = int(max(bw, bh) * 0.4)
        x1 = max(0, bx - pad)
        y1 = max(0, by - pad)
        x2 = min(img.width, bx + bw + pad)
        y2 = min(img.height, by + bh + pad)

        face_crop = img.crop((x1, y1, x2, y2))
        face_crop = face_crop.resize((200, 200), Image.LANCZOS)
        face_crop.save(str(thumb_path), "JPEG", quality=90)
        return str(thumb_path)

    except Exception:
        return None


# ─────────────────────────────────────────────────────────
# Person Card — one side of the merge UI
# ─────────────────────────────────────────────────────────

class PersonCard(QFrame):
    """
    Visual card showing a person's face thumbnail, name, face count,
    and a grid of sample photos from their cluster.
    """

    person_changed = Signal()  # Emitted when the dropdown selection changes

    def __init__(self, title: str, accent_color: str, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._accent = accent_color
        self._person_id = None
        self._person_name = None

        self.setObjectName("merge_person_card")
        self._apply_card_style()
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        # ── Header: title badge ──
        header = QHBoxLayout()
        self.title_badge = QLabel(title)
        self.title_badge.setStyleSheet(
            f"background: {accent_color}; color: white; font-size: 11px; "
            f"font-weight: bold; padding: 4px 14px; border-radius: 12px;"
        )
        self.title_badge.setFixedHeight(24)
        header.addWidget(self.title_badge)
        header.addStretch()
        layout.addLayout(header)

        # ── Dropdown ──
        self.combo = QComboBox()
        self.combo.setMinimumHeight(36)
        self.combo.setStyleSheet(self._combo_style())
        self.combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self.combo)

        # ── Face thumbnail ──
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(160, 160)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet(
            f"background: {c('stat_bg', self._mode)}; border-radius: 16px;"
        )
        thumb_container = QHBoxLayout()
        thumb_container.addStretch()
        thumb_container.addWidget(self.thumb_label)
        thumb_container.addStretch()
        layout.addLayout(thumb_container)

        # ── Info labels ──
        self.name_label = QLabel("—")
        self.name_label.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 16px; font-weight: bold;"
        )
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)

        info_row = QHBoxLayout()
        info_row.setSpacing(16)

        self.face_count_label = QLabel("0 faces")
        self.face_count_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px;"
        )
        self.face_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_row.addStretch()
        info_row.addWidget(self.face_count_label)

        self.enrolled_label = QLabel("")
        self.enrolled_label.setStyleSheet(
            f"color: {c('success', self._mode)}; font-size: 12px; font-weight: bold;"
        )
        info_row.addWidget(self.enrolled_label)
        info_row.addStretch()

        layout.addLayout(info_row)

        # ── Sample photos grid ──
        photos_title = QLabel("SAMPLE PHOTOS")
        photos_title.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 10px; "
            f"font-weight: bold; letter-spacing: 1px;"
        )
        layout.addWidget(photos_title)

        self.photos_grid = QGridLayout()
        self.photos_grid.setSpacing(4)
        photos_container = QWidget()
        photos_container.setLayout(self.photos_grid)
        photos_container.setStyleSheet("background: transparent;")
        layout.addWidget(photos_container)

        layout.addStretch()

    def _apply_card_style(self):
        bg = c("bg_card", self._mode)
        border = c("border", self._mode)
        self.setStyleSheet(
            f"QFrame#merge_person_card {{ "
            f"background-color: {bg}; "
            f"border: 2px solid {border}; "
            f"border-radius: 18px; }}"
        )

    def _combo_style(self):
        bg = c("stat_bg", self._mode)
        border = c("border", self._mode)
        text = c("text_primary", self._mode)
        return (
            f"QComboBox {{ background: {bg}; color: {text}; "
            f"border: 1px solid {border}; border-radius: 10px; "
            f"padding: 6px 12px; font-size: 13px; font-weight: bold; }}"
            f"QComboBox::drop-down {{ border: none; width: 28px; }}"
            f"QComboBox::down-arrow {{ image: none; border: none; }}"
            f"QComboBox QAbstractItemView {{ "
            f"background: {bg}; color: {text}; "
            f"border: 1px solid {border}; border-radius: 8px; "
            f"selection-background-color: {c('accent', self._mode)}; "
            f"selection-color: white; padding: 4px; }}"
        )

    def populate(self, persons, enrollments):
        """Fill the dropdown with person entries."""
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("— Select Person —", None)

        for person in persons:
            enrollment = enrollments.get(person.id)
            display = enrollment.user_name if enrollment else person.name
            label = f"{display}  ({person.face_count} faces)"
            if enrollment:
                label = f"✓ {label}"
            self.combo.addItem(label, person.id)

        self.combo.blockSignals(False)

    def _on_selection_changed(self, index):
        person_id = self.combo.itemData(index)
        if person_id is None:
            self._clear_display()
            self.person_changed.emit()
            return

        self._person_id = person_id

        try:
            db = _get_db()
            person = db.get_person_by_id(person_id)
            if not person:
                self._clear_display()
                return

            self._person_name = person.name
            enrollment = db.get_enrollment_by_person(person_id)

            # Name
            display_name = enrollment.user_name if enrollment else person.name
            self.name_label.setText(display_name)

            # Face count
            self.face_count_label.setText(f"{person.face_count} faces")

            # Enrolled badge
            if enrollment:
                self.enrolled_label.setText("✓ ENROLLED")
                self.enrolled_label.setStyleSheet(
                    f"color: {c('success', self._mode)}; font-size: 12px; font-weight: bold;"
                )
            else:
                self.enrolled_label.setText("NOT ENROLLED")
                self.enrolled_label.setStyleSheet(
                    f"color: {c('text_secondary', self._mode)}; font-size: 12px;"
                )

            # Thumbnail
            thumb_path = _get_person_thumbnail_path(person_id, person.name)
            if thumb_path:
                pix = QPixmap(thumb_path)
                if not pix.isNull():
                    rounded = _make_rounded_pixmap(pix, 150, 150, 16)
                    self.thumb_label.setPixmap(rounded)
                else:
                    self._set_placeholder_thumb()
            else:
                self._set_placeholder_thumb()

            # Sample photos
            self._load_sample_photos(person_id)

        except Exception:
            self._clear_display()

        self.person_changed.emit()

    def _set_placeholder_thumb(self):
        self.thumb_label.clear()
        self.thumb_label.setText("👤")
        self.thumb_label.setStyleSheet(
            f"background: {c('stat_bg', self._mode)}; border-radius: 16px; "
            f"font-size: 64px; color: {c('text_secondary', self._mode)};"
        )

    def _load_sample_photos(self, person_id):
        """Load sample photo thumbnails into the grid."""
        # Clear grid
        while self.photos_grid.count() > 0:
            item = self.photos_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        photos = _get_person_sample_photos(person_id, max_photos=6)
        if not photos:
            no_photos = QLabel("No photos available")
            no_photos.setStyleSheet(
                f"color: {c('text_secondary', self._mode)}; font-size: 11px;"
            )
            no_photos.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.photos_grid.addWidget(no_photos, 0, 0, 1, 3)
            return

        for i, photo_path in enumerate(photos):
            row_idx = i // 3
            col_idx = i % 3

            try:
                pix = QPixmap(photo_path)
                if not pix.isNull():
                    rounded = _make_rounded_pixmap(pix, 80, 60, 8)
                    lbl = QLabel()
                    lbl.setPixmap(rounded)
                    lbl.setFixedSize(80, 60)
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    lbl.setStyleSheet("background: transparent;")
                    self.photos_grid.addWidget(lbl, row_idx, col_idx)
            except Exception:
                pass

    def _clear_display(self):
        self._person_id = None
        self._person_name = None
        self.name_label.setText("—")
        self.face_count_label.setText("0 faces")
        self.enrolled_label.setText("")
        self._set_placeholder_thumb()

        while self.photos_grid.count() > 0:
            item = self.photos_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @property
    def selected_person_id(self):
        return self._person_id

    @property
    def selected_person_name(self):
        return self._person_name

    def set_mode(self, mode):
        self._mode = mode
        self._apply_card_style()
        self.combo.setStyleSheet(self._combo_style())


# ─────────────────────────────────────────────────────────
# Main Merge Dialog
# ─────────────────────────────────────────────────────────

class ClusterMergeDialog(QDialog):
    """
    Full-screen-ish dialog with side-by-side person cards.
    Left = Person to KEEP, Right = Person to REMOVE (merge into left).
    """

    merge_completed = Signal()  # Emitted after a successful merge

    def __init__(self, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode

        self.setWindowTitle("Cluster Merge — AURA")
        self.setMinimumSize(750, 620)
        self.resize(820, 680)
        self.setModal(True)

        bg = c("bg", self._mode)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ── Title ──
        title_row = QHBoxLayout()
        title_icon = QLabel("🔗")
        title_icon.setStyleSheet("font-size: 28px;")
        title_row.addWidget(title_icon)

        title = QLabel("Merge Person Clusters")
        title.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 22px; font-weight: bold;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        main_layout.addLayout(title_row)

        # ── Subtitle / Instructions ──
        subtitle = QLabel(
            "Select two person clusters to merge. All faces from the right side "
            "will be moved into the left person. The right person will be deleted."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px; line-height: 1.4;"
        )
        main_layout.addWidget(subtitle)

        # ── Side-by-Side Cards ──
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.keep_card = PersonCard(
            "✦  KEEP", c("success", self._mode), mode=self._mode
        )
        cards_layout.addWidget(self.keep_card, 1)

        # Center merge arrow
        arrow_layout = QVBoxLayout()
        arrow_layout.addStretch()

        self.arrow_label = QLabel("⟵")
        self.arrow_label.setStyleSheet(
            f"color: {c('accent', self._mode)}; font-size: 36px; font-weight: bold;"
        )
        self.arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_layout.addWidget(self.arrow_label)

        merge_hint = QLabel("MERGE\nINTO")
        merge_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        merge_hint.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 10px; "
            f"font-weight: bold; letter-spacing: 1px;"
        )
        arrow_layout.addWidget(merge_hint)

        arrow_layout.addStretch()
        cards_layout.addLayout(arrow_layout)

        self.remove_card = PersonCard(
            "✕  REMOVE", c("error", self._mode), mode=self._mode
        )
        cards_layout.addWidget(self.remove_card, 1)

        main_layout.addLayout(cards_layout, 1)

        # ── Merge Summary ──
        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("merge_summary")
        self.summary_frame.setFixedHeight(50)
        self.summary_frame.setStyleSheet(
            f"QFrame#merge_summary {{ background: {c('stat_bg', self._mode)}; "
            f"border-radius: 14px; border: 1px solid {c('border', self._mode)}; }}"
        )
        summary_layout = QHBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(16, 8, 16, 8)

        self.summary_label = QLabel("Select two different persons to merge")
        self.summary_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px;"
        )
        summary_layout.addWidget(self.summary_label)
        summary_layout.addStretch()
        main_layout.addWidget(self.summary_frame)

        # ── Button Row ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(110, 40)
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 13px; font-weight: bold; border: 1px solid {c('border', self._mode)}; }}"
            f"QPushButton:hover {{ background: {c('border', self._mode)}; }}"
        )
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(cancel_btn)

        self.merge_btn = QPushButton("🔗  MERGE")
        self.merge_btn.setFixedSize(150, 40)
        self.merge_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.merge_btn.setEnabled(False)
        self._style_merge_btn()
        self.merge_btn.clicked.connect(self._do_merge)
        btn_row.addWidget(self.merge_btn)

        main_layout.addLayout(btn_row)

        # ── Signals ──
        self.keep_card.person_changed.connect(self._update_merge_state)
        self.remove_card.person_changed.connect(self._update_merge_state)

        # Load data
        self._load_persons()

    def _style_merge_btn(self):
        if self.merge_btn.isEnabled():
            self.merge_btn.setStyleSheet(
                f"QPushButton {{ background: {c('accent', self._mode)}; "
                f"color: white; border-radius: 12px; "
                f"font-size: 14px; font-weight: bold; border: none; }}"
                f"QPushButton:hover {{ background: #0066dd; }}"
            )
        else:
            self.merge_btn.setStyleSheet(
                f"QPushButton {{ background: {c('text_secondary', self._mode)}; "
                f"color: white; border-radius: 12px; "
                f"font-size: 14px; font-weight: bold; border: none; "
                f"opacity: 0.5; }}"
            )

    def _load_persons(self):
        """Load persons from the database into both dropdowns."""
        try:
            db = _get_db()
            persons = db.get_all_persons()
            enrollments = {e.person_id: e for e in db.get_all_enrollments()}

            self.keep_card.populate(persons, enrollments)
            self.remove_card.populate(persons, enrollments)
        except Exception:
            pass

    def _update_merge_state(self):
        """Enable/disable merge button based on selection validity."""
        keep_id = self.keep_card.selected_person_id
        remove_id = self.remove_card.selected_person_id

        can_merge = (
            keep_id is not None
            and remove_id is not None
            and keep_id != remove_id
        )

        self.merge_btn.setEnabled(can_merge)
        self._style_merge_btn()

        if keep_id is not None and remove_id is not None and keep_id == remove_id:
            self.summary_label.setText("⚠  Cannot merge a person into themselves")
            self.summary_label.setStyleSheet(
                f"color: {c('warning', self._mode)}; font-size: 12px; font-weight: bold;"
            )
        elif can_merge:
            keep_name = self.keep_card.selected_person_name or "?"
            remove_name = self.remove_card.selected_person_name or "?"
            self.summary_label.setText(
                f"All faces from {remove_name} will merge into {keep_name}"
            )
            self.summary_label.setStyleSheet(
                f"color: {c('accent', self._mode)}; font-size: 12px; font-weight: bold;"
            )
        else:
            self.summary_label.setText("Select two different persons to merge")
            self.summary_label.setStyleSheet(
                f"color: {c('text_secondary', self._mode)}; font-size: 12px;"
            )

    def _do_merge(self):
        """Execute the merge after confirmation."""
        keep_id = self.keep_card.selected_person_id
        remove_id = self.remove_card.selected_person_id
        keep_name = self.keep_card.selected_person_name or f"Person_{keep_id:03d}"
        remove_name = self.remove_card.selected_person_name or f"Person_{remove_id:03d}"

        if not keep_id or not remove_id or keep_id == remove_id:
            return

        # Confirmation dialog
        reply = QMessageBox.warning(
            self,
            "Confirm Merge",
            f"Are you sure you want to merge?\n\n"
            f"• KEEP: {keep_name}\n"
            f"• REMOVE: {remove_name}\n\n"
            f"All of {remove_name}'s faces and photos will be moved to "
            f"{keep_name}. The {remove_name} folder will also be merged.\n\n"
            f"This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Disable UI during merge
        self.merge_btn.setEnabled(False)
        self.merge_btn.setText("Merging...")
        self._style_merge_btn()

        # Perform merge in background
        def merge_task():
            try:
                # 1. Database merge
                success = _merge_persons(keep_id, remove_id)

                if success:
                    # 2. Filesystem merge: move files from removed person's folder
                    self._merge_filesystem(keep_name, remove_name)

                QTimer.singleShot(0, lambda: self._on_merge_done(success, keep_name, remove_name))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_merge_error(str(e)))

        threading.Thread(target=merge_task, daemon=True).start()

    def _merge_filesystem(self, keep_name, remove_name):
        """Move photo files from the removed person's folder into the kept person's folder."""
        try:
            config = _get_config()
            keep_dir = config.people_dir / keep_name
            remove_dir = config.people_dir / remove_name

            if not remove_dir.exists():
                return

            keep_dir.mkdir(parents=True, exist_ok=True)

            for file in remove_dir.iterdir():
                if file.is_file():
                    dest = keep_dir / file.name
                    # Handle name conflicts
                    if dest.exists():
                        stem = file.stem
                        suffix = file.suffix
                        counter = 1
                        while dest.exists():
                            dest = keep_dir / f"{stem}_merged_{counter}{suffix}"
                            counter += 1
                    try:
                        shutil.move(str(file), str(dest))
                    except Exception:
                        pass

            # Try to remove the now-empty directory
            try:
                remove_dir.rmdir()
            except Exception:
                pass  # Not empty or permission issue

        except Exception:
            pass

    def _on_merge_done(self, success, keep_name, remove_name):
        """Handle merge completion on UI thread."""
        if success:
            self.summary_label.setText(
                f"✓  Successfully merged {remove_name} into {keep_name}!"
            )
            self.summary_label.setStyleSheet(
                f"color: {c('success', self._mode)}; font-size: 13px; font-weight: bold;"
            )

            # Refresh the dropdowns
            self._load_persons()
            self.keep_card._clear_display()
            self.remove_card._clear_display()

            self.merge_btn.setText("🔗  MERGE")
            self.merge_btn.setEnabled(False)
            self._style_merge_btn()

            self.merge_completed.emit()
        else:
            self._on_merge_error("Merge failed — one or both persons not found")

    def _on_merge_error(self, error_msg):
        """Handle merge error on UI thread."""
        self.summary_label.setText(f"✕  Error: {error_msg}")
        self.summary_label.setStyleSheet(
            f"color: {c('error', self._mode)}; font-size: 12px; font-weight: bold;"
        )
        self.merge_btn.setText("🔗  MERGE")
        self.merge_btn.setEnabled(True)
        self._style_merge_btn()

    def set_mode(self, mode):
        self._mode = mode
        bg = c("bg", self._mode)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")
        self.keep_card.set_mode(mode)
        self.remove_card.set_mode(mode)
