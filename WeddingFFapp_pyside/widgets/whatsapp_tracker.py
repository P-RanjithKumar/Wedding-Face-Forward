"""
WhatsAppTrackerWidget — Professional WhatsApp delivery status card.

Matches the unified card layout:
  TITLE
  Big metric (total messages)
  Status rows (Sent / Retry / Failed / Invalid)
"""

import json
from pathlib import Path

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt

from ..theme import c


class WhatsAppTrackerWidget(QFrame):
    """Professional WhatsApp delivery tracker — matches sibling cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("wa_tracker_widget")
        self._mode = "light"

        # Path to the WhatsApp state file
        try:
            import dist_utils
            self._state_file = dist_utils.get_user_data_dir() / "whatsapp_data" / "message_state_db.json"
        except ImportError:
            base_dir = Path(__file__).parent.parent.parent.resolve()
            self._state_file = base_dir / "whatsapp_tool" / "whatsapp_data" / "message_state_db.json"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(6)

        # Title
        title = QLabel("WHATSAPP")
        title.setObjectName("card_title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        layout.addStretch()

        # Big metric — total
        self.total_label = QLabel("0")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {c('text_secondary', self._mode)};"
        )
        layout.addWidget(self.total_label)

        layout.addSpacing(4)

        # Breakdown rows
        self.badge_sent = self._make_row(layout, "Sent", c("success", self._mode))
        self.badge_retry = self._make_row(layout, "Retry", c("warning", self._mode))
        self.badge_failed = self._make_row(layout, "Failed", c("error", self._mode))
        self.badge_invalid = self._make_row(layout, "Invalid", "#86868b")

        layout.addStretch()

    def _make_row(self, parent_layout, label_text: str, color: str) -> QLabel:
        """Create a status row: label + count."""
        row = QHBoxLayout()
        row.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold;")
        row.addWidget(lbl)

        row.addStretch()

        count = QLabel("0")
        count.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {color};")
        row.addWidget(count)

        parent_layout.addLayout(row)
        return count

    # ------------------------------------------------------------------
    # Public API — called from the main refresh loop
    # ------------------------------------------------------------------
    def refresh(self):
        """Reload the WhatsApp state file and update all UI elements."""
        state = self._load_state()

        sent = 0
        failed = 0
        invalid = 0
        retry = 0

        for _key, entry in state.items():
            status = entry.get("status", "")
            if status == "sent":
                sent += 1
            elif status == "failed":
                failed += 1
            elif status == "invalid":
                invalid += 1
            elif status == "retry":
                retry += 1

        total = sent + failed + invalid + retry

        # Update labels
        self.total_label.setText(str(total))

        if total == 0:
            clr = c("text_secondary", self._mode)
        elif failed > 0:
            clr = c("warning", self._mode)
        else:
            clr = c("text_primary", self._mode)
        self.total_label.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {clr};")

        self.badge_sent.setText(str(sent))
        self.badge_retry.setText(str(retry))
        self.badge_failed.setText(str(failed))
        self.badge_invalid.setText(str(invalid))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _load_state(self) -> dict:
        """Read message_state_db.json — returns empty dict on any error."""
        if not self._state_file.exists():
            return {}
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def set_mode(self, mode: str):
        self._mode = mode.lower()
