"""
CloudWidget — Compact cloud upload status card.

Layout:
  CLOUD SYNC                           (title)
  ████████████████████░░░░░░░░░░░░     (full-width progress bar, tight padding)
  Uploading...  |  45%  |  45 / 200   (values row below bar)
"""

from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QWidget, QSizePolicy
)
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QLinearGradient
from PySide6.QtCore import Qt, QTimer, QRectF

from ..theme import c


class CloudProgressBar(QWidget):
    """Full-width gradient progress bar for cloud uploads."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._mode = "light"
        self._progress = 0.0
        self._bar_color_start = "#5856d6"
        self._bar_color_end = "#34c759"

    def set_colors(self, start: str, end: str):
        self._bar_color_start = start
        self._bar_color_end = end

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#3a3a3c" if self._mode == "dark" else "#e4e4e8"))
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        fw = max(w * self._progress, 0)
        if fw > 1:
            grad = QLinearGradient(0, 0, fw, 0)
            grad.setColorAt(0, QColor(self._bar_color_start))
            grad.setColorAt(1, QColor(self._bar_color_end))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(0, 0, fw, h), r, r)
            glow = QColor(self._bar_color_end)
            glow.setAlphaF(0.25)
            p.setPen(QPen(glow, 1))
            if fw > r * 2:
                p.drawLine(int(r), 1, int(fw - r), 1)
        p.end()


class CloudWidget(QFrame):
    """Compact cloud card — progress bar full width, stats below."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cloud_widget")
        self._mode = "light"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(5)

        # Title
        self.title_label = QLabel("CLOUD SYNC")
        self.title_label.setObjectName("card_title")
        layout.addWidget(self.title_label)

        # Progress bar — full width
        self.bar = CloudProgressBar()
        self.bar.set_colors("#5856d6", c("success", self._mode))
        layout.addWidget(self.bar)

        # Values row below bar: Status | Percentage | Count
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(0)

        self.status_label = QLabel("Synced")
        self.status_label.setObjectName("card_detail")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        meta_row.addWidget(self.status_label, 1)

        sep1 = QLabel("|")
        sep1.setObjectName("card_detail")
        sep1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep1.setFixedWidth(16)
        meta_row.addWidget(sep1)

        self.pct_label = QLabel("--")
        self.pct_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pct_label.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {c('text_secondary', self._mode)};"
        )
        self.pct_label.setFixedWidth(40)
        meta_row.addWidget(self.pct_label)

        sep2 = QLabel("|")
        sep2.setObjectName("card_detail")
        sep2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep2.setFixedWidth(16)
        meta_row.addWidget(sep2)

        self.progress_label = QLabel("—")
        self.progress_label.setObjectName("card_detail")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        meta_row.addWidget(self.progress_label, 1)

        layout.addLayout(meta_row)

        # State
        self._uploading = False
        self._upload_total = 0
        self._upload_done = 0
        self._target_progress = 0.0
        self._current_progress = 0.0

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._animate)

    def start_uploading(self):
        if not self._uploading:
            self._uploading = True
            color = c("accent", self._mode)
            self.status_label.setText("Uploading...")
            self.status_label.setStyleSheet(f"color: {color};")
            self._anim_timer.start()

    def update_progress(self, uploaded: int, total: int):
        self._upload_done = uploaded
        self._upload_total = total

        if total > 0:
            self._target_progress = min(uploaded / total, 1.0)
            self.bar._progress = self._target_progress
            pct = int((uploaded / total) * 100)
            self.progress_label.setText(f"{uploaded} / {total}")
            if uploaded >= total:
                self.pct_label.setText("100%")
                self.pct_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c('success', self._mode)};")
            else:
                self.pct_label.setText(f"{pct}%")
                self.pct_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c('text_primary', self._mode)};")
        else:
            self._target_progress = 0.0
            self.bar._progress = 0.0
            self.pct_label.setText("--")
            self.pct_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c('text_secondary', self._mode)};")
            self.progress_label.setText("—")

    def stop_uploading(self):
        if self._uploading:
            self._uploading = False
            self._anim_timer.stop()
            color = c("success", self._mode)
            self.status_label.setText("Synced")
            self.status_label.setStyleSheet(f"color: {color};")
            self.bar.update()

    def draw_static_cloud(self):
        self.bar.update()

    def _animate(self):
        if not self._uploading:
            self._anim_timer.stop()
            return
        diff = self._target_progress - self._current_progress
        if abs(diff) > 0.002:
            self._current_progress += diff * 0.10
        else:
            self._current_progress = self._target_progress
        self.bar._progress = self._current_progress
        self.bar.update()

    def set_appearance_mode(self, mode):
        self._mode = mode.lower()
        self.bar._mode = self._mode
        self.bar.set_colors("#5856d6", c("success", self._mode))
        self.bar.update()
        self.progress_label.setStyleSheet("")

    def set_mode(self, mode: str):
        self.set_appearance_mode(mode)
