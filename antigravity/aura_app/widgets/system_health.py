"""
SystemHealthIndicator — Pill-shaped badge showing overall system health.
Green pulsating = all idle, Red/Orange = workers busy, Grey = offline.
Ported from CustomTkinter SystemHealthIndicator class.
"""

from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QWidget
from PySide6.QtCore import QTimer

from ..theme import c


class SystemHealthIndicator(QFrame):
    """Shows overall system health with a pulsing colored dot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("health_indicator")
        self._mode = "light"

        # Inner container for padding
        inner = QWidget(self)
        inner_layout = QHBoxLayout(inner)
        inner_layout.setContentsMargins(12, 6, 12, 6)
        inner_layout.setSpacing(8)

        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {c('text_secondary', self._mode)}; font-size: 14px;")
        inner_layout.addWidget(self.dot)

        self.label = QLabel("System Idle")
        self.label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; font-weight: bold;"
        )
        inner_layout.addWidget(self.label)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(inner)

        self._state = "offline"
        self._pulsing = False
        self._pulse_step = 0

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(500)
        self._pulse_timer.timeout.connect(self._pulse)

    def set_idle(self):
        """All workers are idle — show green pulsating dot."""
        if self._state == "idle":
            return
        self._state = "idle"
        self._pulsing = True
        color = c("success", self._mode)
        self.setStyleSheet(self._border_style(color))
        self.label.setText("System Idle")
        self.label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
        self._pulse_timer.start()

    def set_busy(self):
        """At least one worker is busy — show red/orange pulsating dot."""
        if self._state == "busy":
            return
        self._state = "busy"
        self._pulsing = True
        color = c("warning", self._mode)
        self.setStyleSheet(self._border_style(color))
        self.label.setText("Workers Active")
        self.label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
        self._pulse_timer.start()

    def set_offline(self):
        """System is stopped — show grey static dot."""
        if self._state == "offline":
            return
        self._state = "offline"
        self._pulsing = False
        self._pulse_timer.stop()
        border_c = c("border", self._mode)
        sec = c("text_secondary", self._mode)
        self.setStyleSheet(self._border_style(border_c))
        self.dot.setStyleSheet(f"color: {sec}; font-size: 14px;")
        self.label.setText("System Offline")
        self.label.setStyleSheet(f"color: {sec}; font-size: 11px; font-weight: bold;")

    def _pulse(self):
        if not self._pulsing:
            self._pulse_timer.stop()
            return

        if self._state == "busy":
            colors = [
                c("error", self._mode), "#ff6b60",
                c("warning", self._mode), "#ffaa33"
            ]
        else:
            colors = [
                c("success", self._mode), "#5fd47a",
                c("success", self._mode), "#2aa64a"
            ]

        color = colors[self._pulse_step % len(colors)]
        self.dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self._pulse_step += 1

    def _border_style(self, color):
        bg = c("bg_card", self._mode)
        return (
            f"QFrame#health_indicator {{ "
            f"background-color: {bg}; "
            f"border: 1px solid {color}; "
            f"border-radius: 20px; }}"
        )

    def set_mode(self, mode: str):
        self._mode = mode.lower()
