"""
FolderChoicePopup — Frameless floating popup with face thumbnail + Local/Cloud buttons.
Ported from CustomTkinter FolderChoicePopup class.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QSizePolicy
)
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QCursor
from PySide6.QtCore import Qt, QTimer, QRectF, QPoint

from ..theme import c


class FolderChoicePopup(QWidget):
    """Floating popup: face thumbnail + Local / Cloud buttons."""

    THUMB_W = 230
    THUMB_H = 290
    BTN_AREA_H = 30
    PADDING = 4

    def __init__(self, x, y, person_name, on_local, on_cloud,
                 thumbnail_path=None, mode="light", parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        self._mode = mode
        self._destroying = False
        self._can_close = False

        bg_color = c("bg_card", self._mode)

        has_thumb = thumbnail_path and Path(thumbnail_path).exists()
        popup_w = self.THUMB_W + self.PADDING * 2 + 4
        popup_h = (
            (self.THUMB_H + self.BTN_AREA_H + self.PADDING * 3 + 4)
            if has_thumb
            else (self.BTN_AREA_H + self.PADDING * 2 + 4)
        )

        # Outer border frame
        self.outer_frame = QFrame(self)
        self.outer_frame.setObjectName("popup_outer")
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.outer_frame)

        # Inner card
        self.inner_frame = QFrame(self.outer_frame)
        self.inner_frame.setObjectName("popup_inner")
        inner_outer = QVBoxLayout(self.outer_frame)
        inner_outer.setContentsMargins(2, 2, 2, 2)
        inner_outer.addWidget(self.inner_frame)

        inner_layout = QVBoxLayout(self.inner_frame)
        inner_layout.setContentsMargins(self.PADDING, self.PADDING, self.PADDING, self.PADDING)
        inner_layout.setSpacing(3)

        # Thumbnail
        if has_thumb:
            try:
                pixmap = QPixmap(thumbnail_path)
                if not pixmap.isNull():
                    # Scale to fill
                    scaled = pixmap.scaled(
                        self.THUMB_W, self.THUMB_H,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    # Center crop
                    if scaled.width() > self.THUMB_W or scaled.height() > self.THUMB_H:
                        x_off = (scaled.width() - self.THUMB_W) // 2
                        y_off = (scaled.height() - self.THUMB_H) // 2
                        scaled = scaled.copy(x_off, y_off, self.THUMB_W, self.THUMB_H)

                    # Round corners
                    rounded = QPixmap(self.THUMB_W, self.THUMB_H)
                    rounded.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(rounded)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(0, 0, self.THUMB_W, self.THUMB_H), 10, 10)
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, scaled)
                    painter.end()

                    thumb_label = QLabel()
                    thumb_label.setPixmap(rounded)
                    thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    inner_layout.addWidget(thumb_label)
            except Exception:
                pass

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        btn_local = QPushButton("📁 Local")
        btn_local.setObjectName("popup_btn_local")
        btn_local.setFixedHeight(26)
        btn_local.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_local.clicked.connect(lambda: (on_local(), self._safe_destroy()))
        btn_row.addWidget(btn_local)

        btn_cloud = QPushButton("☁ Cloud")
        btn_cloud.setObjectName("popup_btn_cloud")
        btn_cloud.setFixedHeight(26)
        btn_cloud.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_cloud.clicked.connect(lambda: (on_cloud(), self._safe_destroy()))
        btn_row.addWidget(btn_cloud)

        inner_layout.addLayout(btn_row)

        # Position and size
        self.setFixedSize(popup_w, popup_h)
        self.move(x - 5, y - 5)

        # Grace period before enabling auto-close
        QTimer.singleShot(500, self._enable_close)

        # Position check loop
        self._check_timer = QTimer(self)
        self._check_timer.setInterval(150)
        self._check_timer.timeout.connect(self._check_position_loop)

        self.show()

    def _safe_destroy(self):
        """Safely close popup."""
        if self._destroying:
            return
        self._destroying = True
        self._check_timer.stop()
        try:
            self.close()
            self.deleteLater()
        except Exception:
            pass

    def _enable_close(self):
        """Enable auto-close after grace period."""
        if self._destroying:
            return
        self._can_close = True
        # Use named method instead of lambda to avoid capturing stale state
        QTimer.singleShot(200, self._start_check_loop)

    def _start_check_loop(self):
        """Safely start the position monitoring loop."""
        if not self._destroying and hasattr(self, "_check_timer"):
            try:
                self._check_timer.start()
            except RuntimeError:
                pass  # C++ object likely gone

    def _check_position_loop(self):
        """Check if mouse is still near the popup."""
        if self._destroying or not self._can_close:
            return
        try:
            cursor_pos = QCursor.pos()
            geo = self.geometry()
            padding = 25
            expanded = geo.adjusted(-padding, -padding, padding, padding)
            if not expanded.contains(cursor_pos):
                self._safe_destroy()
        except Exception:
            self._safe_destroy()

    def leaveEvent(self, event):
        """On mouse leave, verify if we should close after a tiny buffer."""
        if self._can_close and not self._destroying:
            QTimer.singleShot(150, self._check_really_left)

    def _check_really_left(self):
        if self._destroying:
            return
        try:
            cursor_pos = QCursor.pos()
            geo = self.geometry()
            padding = 15
            expanded = geo.adjusted(-padding, -padding, padding, padding)
            if not expanded.contains(cursor_pos):
                self._safe_destroy()
        except Exception:
            pass
