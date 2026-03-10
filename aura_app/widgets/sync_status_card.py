"""
SyncStatusCard — Premium animated Cloud & Local sync status card.

States:
  IDLE    (—)       — gentle breathing glow, neutral colors
  SYNCING           — orbiting dots, pulsing ring, lively animation
  MATCHED (YES ✓)   — radiant green checkmark, success burst
  FAILED  (NO ✗)    — red pulsing alert, warning shake
  WARNING (NO)      — amber pulse, attention ring

Transitions between states are smooth — colors morph, elements fade/scale.
"""

import math

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont,
    QLinearGradient, QPainterPath
)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF

from ..theme import c, COLORS

# ── State constants ──────────────────────────────────────────────────────
STATE_IDLE     = "idle"
STATE_SYNCING  = "syncing"
STATE_MATCHED  = "matched"
STATE_FAILED   = "failed"
STATE_WARNING  = "warning"

# Colors per state (light, dark)
_STATE_COLORS = {
    STATE_IDLE:    (("#86868b", "#98989d"), ("#e8e8ed", "#38383a")),
    STATE_SYNCING: (("#ff9500", "#ff9f0a"), ("#fff3d6", "#3d3520")),
    STATE_MATCHED: (("#34c759", "#30d158"), ("#e6f9ed", "#1a3d24")),
    STATE_FAILED:  (("#ff3b30", "#ff453a"), ("#fde8e8", "#3d1b1b")),
    STATE_WARNING: (("#ff9500", "#ff9f0a"), ("#fff3d6", "#3d3520")),
}


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    """Linear interpolate between two QColors. t=0→a, t=1→b."""
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red()   + (b.red()   - a.red())   * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue()  + (b.blue()  - a.blue())  * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


# ── Animated canvas ─────────────────────────────────────────────────────
class SyncCanvas(QFrame):
    """Custom-painted animated sync status indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(90, 90)
        self._mode = "light"

        # Animation state
        self._phase = 0.0          # master phase counter (radians)
        self._state = STATE_IDLE
        self._prev_state = STATE_IDLE

        # Transition
        self._transition_t = 1.0   # 0→1 from prev_state to state
        self._TRANSITION_SPEED = 0.06

        # Current interpolated colors
        self._accent = QColor("#86868b")
        self._bg_tint = QColor("#e8e8ed")

    def set_state(self, state: str):
        if state == self._state:
            return
        self._prev_state = self._state
        self._state = state
        self._transition_t = 0.0  # start transition

    def _current_colors(self):
        """Get interpolated accent + bg colors for current transition."""
        mi = 0 if self._mode == "light" else 1

        prev_accent = QColor(_STATE_COLORS[self._prev_state][0][mi])
        next_accent = QColor(_STATE_COLORS[self._state][0][mi])
        prev_bg     = QColor(_STATE_COLORS[self._prev_state][1][mi])
        next_bg     = QColor(_STATE_COLORS[self._state][1][mi])

        t = self._transition_t
        return _lerp_color(prev_accent, next_accent, t), _lerp_color(prev_bg, next_bg, t)

    def tick(self):
        """Called every frame by the parent timer."""
        # Advance transition
        if self._transition_t < 1.0:
            self._transition_t = min(1.0, self._transition_t + self._TRANSITION_SPEED)

        # Advance phase
        if self._state == STATE_SYNCING:
            self._phase += 0.08   # faster for syncing
        else:
            self._phase += 0.03   # gentle for other states

        self._accent, self._bg_tint = self._current_colors()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        t = self._transition_t

        # ── Background glow circle ───────────────────────────────────
        glow_r = 38 + 3 * math.sin(self._phase * 1.5)
        bg = QColor(self._bg_tint)
        bg.setAlphaF(0.5 + 0.15 * math.sin(self._phase))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # ── Outer ring ───────────────────────────────────────────────
        ring_r = 34
        ring_w = 3.0

        ring_color = QColor(self._accent)
        ring_color.setAlphaF(0.3 + 0.15 * math.sin(self._phase * 0.8))
        pen = QPen(ring_color, ring_w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        # ── State-specific animations ────────────────────────────────
        state = self._state if t > 0.5 else self._prev_state

        if state == STATE_SYNCING:
            self._draw_syncing(p, cx, cy, ring_r)
        elif state == STATE_MATCHED:
            self._draw_matched(p, cx, cy)
        elif state == STATE_FAILED:
            self._draw_failed(p, cx, cy)
        elif state == STATE_WARNING:
            self._draw_warning(p, cx, cy)
        else:
            self._draw_idle(p, cx, cy)

        p.end()

    # ── SYNCING: orbiting dots + rotating arcs ───────────────────────
    def _draw_syncing(self, p: QPainter, cx, cy, ring_r):
        accent = QColor(self._accent)

        # 3 orbiting dots at different speeds/offsets
        for i in range(3):
            angle = self._phase * (1.8 + i * 0.4) + i * (2 * math.pi / 3)
            orbit_r = ring_r - 1
            dx = cx + orbit_r * math.cos(angle)
            dy = cy + orbit_r * math.sin(angle)
            dot_size = 4.0 - i * 0.6

            dot_color = QColor(accent)
            dot_color.setAlphaF(1.0 - i * 0.25)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(dot_color)
            p.drawEllipse(QPointF(dx, dy), dot_size, dot_size)

        # Rotating arc sweep
        arc_rect = QRectF(cx - 18, cy - 18, 36, 36)
        arc_color = QColor(accent)
        arc_color.setAlphaF(0.6)
        pen = QPen(arc_color, 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        start = int(-self._phase * 180 / math.pi) * 16
        p.drawArc(arc_rect, start, 120 * 16)

        # Counter-rotating inner arc
        arc_color2 = QColor(accent)
        arc_color2.setAlphaF(0.3)
        pen2 = QPen(arc_color2, 1.5)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen2)
        arc_rect2 = QRectF(cx - 12, cy - 12, 24, 24)
        p.drawArc(arc_rect2, -start, 90 * 16)

    # ── MATCHED: checkmark + radiant glow ────────────────────────────
    def _draw_matched(self, p: QPainter, cx, cy):
        accent = QColor(self._accent)

        # Pulsing inner glow
        glow_alpha = 0.15 + 0.1 * math.sin(self._phase * 1.2)
        glow = QColor(accent)
        glow.setAlphaF(glow_alpha)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        pulse_r = 22 + 2 * math.sin(self._phase * 1.5)
        p.drawEllipse(QPointF(cx, cy), pulse_r, pulse_r)

        # Checkmark — scaled by transition
        scale = min(self._transition_t * 1.2, 1.0)
        pen = QPen(accent, 3.5 * scale)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        # Checkmark path points (relative to center)
        p1 = QPointF(cx - 10 * scale, cy + 1 * scale)
        p2 = QPointF(cx - 3 * scale,  cy + 8 * scale)
        p3 = QPointF(cx + 10 * scale, cy - 7 * scale)
        p.drawLine(p1, p2)
        p.drawLine(p2, p3)

        # Radiating particles (subtle sparkle)
        for i in range(6):
            angle = self._phase * 0.5 + i * (math.pi / 3)
            pr = 26 + 3 * math.sin(self._phase + i)
            px = cx + pr * math.cos(angle)
            py = cy + pr * math.sin(angle)
            spark = QColor(accent)
            spark.setAlphaF(0.3 + 0.2 * math.sin(self._phase * 2 + i))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(spark)
            p.drawEllipse(QPointF(px, py), 1.5, 1.5)

    # ── FAILED: X mark + pulsing alert ───────────────────────────────
    def _draw_failed(self, p: QPainter, cx, cy):
        accent = QColor(self._accent)

        # Pulsing warning ring
        pulse = 0.4 + 0.3 * math.sin(self._phase * 2.5)
        ring_color = QColor(accent)
        ring_color.setAlphaF(pulse)
        pen = QPen(ring_color, 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        pr = 20 + 2 * math.sin(self._phase * 2)
        p.drawEllipse(QPointF(cx, cy), pr, pr)

        # X mark
        scale = min(self._transition_t * 1.3, 1.0)
        x_pen = QPen(accent, 3.5 * scale)
        x_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(x_pen)
        d = 8 * scale
        p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
        p.drawLine(QPointF(cx + d, cy - d), QPointF(cx - d, cy + d))

    # ── WARNING: exclamation + amber pulse ───────────────────────────
    def _draw_warning(self, p: QPainter, cx, cy):
        accent = QColor(self._accent)

        # Amber pulsing disc
        pulse_alpha = 0.15 + 0.12 * math.sin(self._phase * 1.8)
        disc = QColor(accent)
        disc.setAlphaF(pulse_alpha)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(disc)
        dr = 20 + 3 * math.sin(self._phase * 2)
        p.drawEllipse(QPointF(cx, cy), dr, dr)

        # Exclamation mark
        scale = min(self._transition_t * 1.2, 1.0)
        pen = QPen(accent, 3.5 * scale)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx, cy - 10 * scale), QPointF(cx, cy + 3 * scale))
        # Dot
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent)
        p.drawEllipse(QPointF(cx, cy + 9 * scale), 2.5 * scale, 2.5 * scale)

    # ── IDLE: soft breathing ─────────────────────────────────────────
    def _draw_idle(self, p: QPainter, cx, cy):
        accent = QColor(self._accent)
        # Gentle horizontal line (dash)
        accent.setAlphaF(0.4 + 0.2 * math.sin(self._phase))
        pen = QPen(accent, 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx - 10, cy), QPointF(cx + 10, cy))


# ── Main SyncStatusCard ─────────────────────────────────────────────────
class SyncStatusCard(QFrame):
    """Animated cloud-local sync status card.

    Drop-in replacement for StatCard("Cloud & Local\\nMatch?", ...).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stat_card_highlight")
        self._mode = "light"
        self._state = STATE_IDLE

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(2)

        # Animated canvas
        self.canvas = SyncCanvas()
        layout.addWidget(self.canvas, 0, Qt.AlignmentFlag.AlignCenter)

        # Value label (text below animation)
        self.value_label = QLabel("—")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {c('text_secondary', self._mode)};"
        )
        layout.addWidget(self.value_label)

        # Title
        self.title_label = QLabel("CLOUD & LOCAL")
        self.title_label.setObjectName("stat_title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self._last_value = "—"

        # Animation timer (30 fps)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start()

    def _tick(self):
        self.canvas.tick()

    def set_sync_state(self, state: str, label: str):
        """Set the sync state with animated transition.

        state: one of STATE_IDLE / STATE_SYNCING / STATE_MATCHED / STATE_FAILED / STATE_WARNING
        label: display text like 'YES ✓', 'SYNCING', 'NO ✗', etc.
        """
        mi = 0 if self._mode == "light" else 1
        accent = _STATE_COLORS[state][0][mi]

        self.canvas.set_state(state)
        self._state = state
        self.value_label.setText(label)
        self.value_label.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {accent};"
        )
        self._last_value = label

    # Legacy compat — so existing app_window code still works
    def update_value(self, value: str):
        """Legacy fallback — infer state from text value."""
        if value == "—":
            self.set_sync_state(STATE_IDLE, "—")
        elif "YES" in value:
            self.set_sync_state(STATE_MATCHED, value)
        elif "SYNCING" in value:
            self.set_sync_state(STATE_SYNCING, value)
        elif "NO" in value and "✗" in value:
            self.set_sync_state(STATE_FAILED, value)
        elif "NO" in value:
            self.set_sync_state(STATE_WARNING, value)
        else:
            self.set_sync_state(STATE_IDLE, value)

    def set_mode(self, mode: str):
        self._mode = mode.lower()
        self.canvas._mode = self._mode
        # Re-apply current state colors
        if self._state:
            self.set_sync_state(self._state, self._last_value)
