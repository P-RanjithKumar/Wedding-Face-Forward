"""
StuckPhotosCard — Professional stuck photos status card.

Matches the unified card layout:
  TITLE
  Big metric (total stuck count)
  Status rows (Analysis / Cloud breakdown)
"""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt

from ..theme import c


class StuckPhotosCard(QFrame):
    """Professional stuck photos indicator — matches sibling cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stuck_card")
        self._mode = "light"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(6)

        # Title
        title = QLabel("STUCK PHOTOS")
        title.setObjectName("card_title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        layout.addStretch()

        # Big metric — total
        self.total_stuck_label = QLabel("0")
        self.total_stuck_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_stuck_label.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {c('success', self._mode)};"
        )
        layout.addWidget(self.total_stuck_label)

        layout.addSpacing(4)

        # Breakdown rows
        self.proc_stuck_label = self._make_row(layout, "Analysis")
        self.cloud_stuck_label = self._make_row(layout, "Cloud")

        layout.addStretch()

    def _make_row(self, parent_layout, label_text: str) -> QLabel:
        """Create a breakdown row: label + count."""
        row = QHBoxLayout()
        row.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setObjectName("card_detail")
        row.addWidget(lbl)

        row.addStretch()

        count = QLabel("0")
        count.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {c('success', self._mode)};"
        )
        row.addWidget(count)

        parent_layout.addLayout(row)
        return count

    def update_stuck(self, proc_stuck: int, cloud_stuck: int):
        """Update stuck photo counts."""
        total = proc_stuck + cloud_stuck

        warn = c("warning", self._mode)
        succ = c("success", self._mode)
        err = c("error", self._mode)

        self.proc_stuck_label.setText(str(proc_stuck))
        self.proc_stuck_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {warn if proc_stuck > 0 else succ};"
        )

        self.cloud_stuck_label.setText(str(cloud_stuck))
        self.cloud_stuck_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {warn if cloud_stuck > 0 else succ};"
        )

        if total > 0:
            clr = err
        else:
            clr = succ
        self.total_stuck_label.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {clr};"
        )
        self.total_stuck_label.setText(str(total))

    def set_mode(self, mode: str):
        self._mode = mode.lower()
