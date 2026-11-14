"""
HealthMonitorDialog — Real-time Process Health Monitoring Dashboard.

Shows live-updating graphs for:
  • CPU, Memory & GPU all on ONE multi-line chart (3 colored lines)
  • Processing speed (Photos/Hour rolling average)
  • Queue depth & wait times

Uses QPainter-based custom chart widgets for a premium look,
consistent with the existing dashboard aesthetic.
"""

import time
from collections import deque
from pathlib import Path
import sys

from PySide6.QtWidgets import (
    QDialog, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy,
)
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont,
    QLinearGradient, QPainterPath, QCursor
)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal

from ..theme import c, COLORS

# ── Optional system-metric libraries ──────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

# ── Backend DB ────────────────────────────────────────────
try:
    import dist_utils
    BACKEND_DIR = dist_utils.get_backend_dir()
except ImportError:
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    BACKEND_DIR = BASE_DIR / "backend"
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.db import get_db
    HAS_DB = True
except ImportError:
    HAS_DB = False


HISTORY_SIZE = 60   # rolling 60-second window


# ══════════════════════════════════════════════════════════
#  MultiLineChart  — N colored lines on one canvas
# ══════════════════════════════════════════════════════════

class MultiLineChart(QWidget):
    """
    A QPainter chart that draws N smooth, gradient-filled series.

    Each series is a dict:
        {
          "name":   str,          # display label
          "color":  str,          # hex color
          "data":   deque[float], # rolling history
          "value":  float,        # latest value (set at add time)
        }

    The current value for every series is drawn as a stacked legend
    in the TOP-RIGHT corner, each in its own matching color — no overlap.
    """

    def __init__(
        self,
        series_defs: list,      # list of {"name", "color"} dicts
        max_val: float = 100.0,
        suffix: str = "%",
        show_grid: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.setMinimumSize(220, 140)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._mode = "light"
        self._max_val = max_val
        self._suffix = suffix
        self._show_grid = show_grid

        # Build internal series list
        self._series = []
        for sd in series_defs:
            self._series.append({
                "name":  sd["name"],
                "color": sd["color"],
                "data":  deque([0.0] * HISTORY_SIZE, maxlen=HISTORY_SIZE),
                "value": 0.0,
            })

    # ── Public API ────────────────────────────────────────

    def add_values(self, *values: float):
        """Push one value per series (positional order matches series_defs)."""
        for i, v in enumerate(values):
            if i < len(self._series):
                clamped = min(float(v), self._max_val)
                self._series[i]["data"].append(clamped)
                self._series[i]["value"] = float(v)
        self.update()

    def set_max(self, max_val: float):
        self._max_val = max(max_val, 1.0)

    def set_mode(self, mode: str):
        self._mode = mode
        self.update()

    # ── paintEvent ────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        PAD_L, PAD_R, PAD_T, PAD_B = 6, 8, 8, 6
        chart_w = w - PAD_L - PAD_R
        chart_h = h - PAD_T - PAD_B

        if chart_w <= 0 or chart_h <= 0:
            painter.end()
            return

        # ── background ────────────────────────────────────
        bg = QColor(c("bg_card", self._mode))
        bg.setAlpha(0)                  # transparent — card bg shows through
        painter.fillRect(self.rect(), bg)

        # ── grid lines ────────────────────────────────────
        if self._show_grid:
            gc = QColor(c("border", self._mode))
            gc.setAlpha(55)
            gpen = QPen(gc, 1, Qt.PenStyle.DotLine)
            painter.setPen(gpen)
            for i in range(1, 5):        # 4 horizontal grid lines
                y = PAD_T + chart_h * (1 - i / 4.0)
                # Y-axis label (tiny)
                pct = int(self._max_val * i / 4)
                painter.setFont(QFont("Segoe UI", 7))
                painter.setPen(gc)
                painter.drawText(
                    QRectF(0, y - 7, PAD_L + 2, 14),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    str(pct),
                )
                painter.setPen(gpen)
                painter.drawLine(
                    QPointF(PAD_L, y), QPointF(w - PAD_R, y)
                )

        # ── draw each series (back→front) ─────────────────
        for idx, s in enumerate(self._series):
            self._draw_series(
                painter, s["data"], s["color"],
                chart_w, chart_h, PAD_L, PAD_T, w, h,
                fill_alpha=55 + idx * 10   # slight variation for readability
            )

        # ── inline legend (top-right stacked) ─────────────
        legend_x = w - PAD_R - 140
        legend_y_start = PAD_T + 2
        row_h = 16

        for i, s in enumerate(self._series):
            y_top = legend_y_start + i * row_h
            text = f"{s['name']}: {s['value']:.1f}{self._suffix}"
            color = QColor(s["color"])

            # Semi-transparent pill background
            pill = QColor(s["color"])
            pill.setAlpha(28)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(pill))
            painter.drawRoundedRect(
                QRectF(legend_x - 4, y_top, 142, row_h - 1), 5, 5
            )

            # Color dot
            dot_color = QColor(s["color"])
            painter.setBrush(QBrush(dot_color))
            painter.drawEllipse(QPointF(legend_x + 5, y_top + row_h / 2 - 0.5), 3.5, 3.5)

            # Text
            painter.setPen(color)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(legend_x + 13, y_top, 122, row_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

        painter.end()

    # ── helpers ───────────────────────────────────────────

    def _draw_series(
        self, painter, data, color_hex,
        chart_w, chart_h, pad_l, pad_t, w, h, fill_alpha=70
    ):
        n = len(data)
        if n < 2:
            return

        max_v = max(self._max_val, 1.0)

        # Convert data → screen points
        points = []
        for i, val in enumerate(data):
            x = pad_l + (i / (n - 1)) * chart_w
            y = pad_t + chart_h * (1.0 - val / max_v)
            points.append(QPointF(x, y))

        # Catmull-Rom → cubic Bezier spline
        path = QPainterPath()
        path.moveTo(points[0])
        for i in range(1, len(points)):
            p0 = points[max(i - 2, 0)]
            p1 = points[i - 1]
            p2 = points[i]
            p3 = points[min(i + 1, len(points) - 1)]

            cp1x = p1.x() + (p2.x() - p0.x()) / 6.0
            cp1y = p1.y() + (p2.y() - p0.y()) / 6.0
            cp2x = p2.x() - (p3.x() - p1.x()) / 6.0
            cp2y = p2.y() - (p3.y() - p1.y()) / 6.0
            path.cubicTo(
                QPointF(cp1x, cp1y), QPointF(cp2x, cp2y), p2
            )

        # Stroke
        lc = QColor(color_hex)
        lpen = QPen(lc, 1.8)
        lpen.setCapStyle(Qt.PenCapStyle.RoundCap)
        lpen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(lpen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Fill gradient
        fill = QPainterPath(path)
        bottom_y = pad_t + chart_h
        fill.lineTo(QPointF(points[-1].x(), bottom_y))
        fill.lineTo(QPointF(points[0].x(), bottom_y))
        fill.closeSubpath()

        grad = QLinearGradient(0, pad_t, 0, h)
        tc = QColor(color_hex); tc.setAlpha(fill_alpha)
        bc = QColor(color_hex); bc.setAlpha(4)
        grad.setColorAt(0, tc)
        grad.setColorAt(1, bc)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(fill)

        # Glowing trail dot
        lp = points[-1]
        gc = QColor(color_hex); gc.setAlpha(70)
        painter.setBrush(QBrush(gc))
        painter.drawEllipse(lp, 5.5, 5.5)
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.drawEllipse(lp, 2.8, 2.8)


# ══════════════════════════════════════════════════════════
#  MetricCard  — wraps a MultiLineChart with header & summary
# ══════════════════════════════════════════════════════════

class MetricCard(QFrame):
    """Card that holds a MultiLineChart plus title and min/avg/peak summary."""

    def __init__(
        self,
        title: str,
        icon: str,
        series_defs: list,      # [{"name", "color"}, ...]
        max_val: float = 100.0,
        suffix: str = "%",
        mode: str = "light",
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._series_defs = series_defs
        self._primary_color = series_defs[0]["color"] if series_defs else "#007aff"
        self.setObjectName("health_metric_card")
        self._apply_card_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(6)

        # ── Header ────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 16px; background: transparent;")
        hdr.addWidget(icon_lbl)

        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 11px; "
            f"font-weight: bold; letter-spacing: 1px; background: transparent;"
        )
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        # ── Chart ─────────────────────────────────────────
        self.chart = MultiLineChart(
            series_defs=series_defs,
            max_val=max_val,
            suffix=suffix,
        )
        self.chart.set_mode(mode)
        layout.addWidget(self.chart, 1)

        # ── Summary (min/avg/peak for primary series) ──────
        self._summary = QLabel("")
        self._summary.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 9px; "
            f"background: transparent;"
        )
        self._summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._summary)

        # History for primary series only (for summary stats)
        self._primary_history = deque(maxlen=HISTORY_SIZE)

    # ── Public API ────────────────────────────────────────

    def add_values(self, *values: float):
        """Forward values to the chart; update summary from primary series."""
        self.chart.add_values(*values)

        if values:
            self._primary_history.append(values[0])

        if len(self._primary_history) > 2:
            mn  = min(self._primary_history)
            mx  = max(self._primary_history)
            avg = sum(self._primary_history) / len(self._primary_history)
            sfx = self.chart._suffix
            self._summary.setText(
                f"Min: {mn:.1f}{sfx}   •   Avg: {avg:.1f}{sfx}   •   Peak: {mx:.1f}{sfx}"
            )

    def set_max(self, max_val: float):
        self.chart.set_max(max_val)

    def set_mode(self, mode: str):
        self._mode = mode
        self._apply_card_style()
        self.chart.set_mode(mode)
        self._title_lbl.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 11px; "
            f"font-weight: bold; letter-spacing: 1px; background: transparent;"
        )
        self._summary.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 9px; "
            f"background: transparent;"
        )

    def _apply_card_style(self):
        bg     = c("bg_card", self._mode)
        border = c("border",  self._mode)
        self.setStyleSheet(
            f"QFrame#health_metric_card {{"
            f"  background-color: {bg}; "
            f"  border: 1px solid {border}; "
            f"  border-radius: 14px; "
            f"}}"
        )


# ══════════════════════════════════════════════════════════
#  StatPill  — compact summary badge above the charts
# ══════════════════════════════════════════════════════════

class StatPill(QFrame):
    """Small pill-shaped stat indicator for the header summary row."""

    def __init__(
        self, icon: str, label: str, value: str,
        color: str, mode: str = "light", parent=None
    ):
        super().__init__(parent)
        self._mode = mode
        self._color = color
        self.setObjectName("health_stat_pill")
        self._apply_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(icon_lbl)

        info = QVBoxLayout()
        info.setSpacing(0)

        self._label_w = QLabel(label)
        self._label_w.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 9px; "
            f"background: transparent;"
        )
        info.addWidget(self._label_w)

        self._value_w = QLabel(value)
        self._value_w.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: bold; "
            f"background: transparent;"
        )
        info.addWidget(self._value_w)

        layout.addLayout(info)

    def update_value(self, value: str):
        self._value_w.setText(value)

    def _apply_style(self):
        self.setStyleSheet(
            f"QFrame#health_stat_pill {{"
            f"  background: {c('stat_bg', self._mode)}; "
            f"  border: 1px solid {c('border', self._mode)}; "
            f"  border-radius: 12px; "
            f"}}"
        )

    def set_mode(self, mode: str):
        self._mode = mode
        self._apply_style()


# ══════════════════════════════════════════════════════════
#  HealthMonitorDialog  — the main dialog
# ══════════════════════════════════════════════════════════

class HealthMonitorDialog(QDialog):
    """
    Real-time process health monitoring dashboard.

    Layout:
        Row 0 — Title + live indicator
        Row 1 — Summary pills (CPU, MEM, GPU, Speed, Queue)
        Row 2 — Charts:
            [System Resources (CPU+MEM+GPU)] | [Processing Speed]
            [Queue & Wait                  ] |
        Row 3 — Footer / uptime
    """

    def __init__(self, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode

        self.setWindowTitle("Process Health — AURA")
        self.setMinimumSize(820, 550)
        self.resize(920, 620)
        self.setModal(False)   # non-modal — keep working in main app

        self._apply_bg()

        # Speed-calculation state
        self._last_completed    = None
        self._last_time         = None
        self._pph_history       = deque(maxlen=HISTORY_SIZE)
        self._session_start     = time.time()

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._collect)
        self._timer.start()

        QTimer.singleShot(120, self._collect)

    # ── UI construction ───────────────────────────────────

    def _build_ui(self):
        ml = QVBoxLayout(self)
        ml.setContentsMargins(24, 20, 24, 16)
        ml.setSpacing(14)

        # ── Title row ─────────────────────────────────────
        tr = QHBoxLayout()
        tr.setSpacing(10)

        lbl_icon = QLabel("📊")
        lbl_icon.setStyleSheet("font-size: 26px;")
        tr.addWidget(lbl_icon)

        self._title_lbl = QLabel("Process Health Monitor")
        self._title_lbl.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; "
            f"font-size: 21px; font-weight: bold;"
        )
        tr.addWidget(self._title_lbl)
        tr.addStretch()

        # Live dot
        self._live_dot = QLabel("●")
        self._live_dot.setStyleSheet(
            f"color: {c('success', self._mode)}; font-size: 10px;"
        )
        tr.addWidget(self._live_dot)

        lbl_live = QLabel("LIVE")
        lbl_live.setStyleSheet(
            f"color: {c('success', self._mode)}; font-size: 11px; font-weight: bold;"
        )
        tr.addWidget(lbl_live)

        ml.addLayout(tr)

        # ── Summary pills ─────────────────────────────────
        pr = QHBoxLayout()
        pr.setSpacing(8)

        C_CPU  = "#3b82f6"   # blue
        C_MEM  = "#a855f7"   # purple
        C_GPU  = "#10b981"   # emerald
        C_SPD  = c("warning", self._mode)
        C_QUE  = c("error",   self._mode)

        self.pill_cpu = StatPill("🖥", "CPU",    "--", C_CPU, self._mode)
        self.pill_mem = StatPill("🧠", "Memory", "--", C_MEM, self._mode)
        self.pill_gpu = StatPill("⚡", "GPU",    "--", C_GPU, self._mode)
        self.pill_spd = StatPill("📸", "Speed",  "--", C_SPD, self._mode)
        self.pill_que = StatPill("📋", "Queue",  "--", C_QUE, self._mode)

        for p in (self.pill_cpu, self.pill_mem, self.pill_gpu,
                  self.pill_spd, self.pill_que):
            pr.addWidget(p)

        ml.addLayout(pr)

        # ── Charts grid ───────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 6)
        grid.setColumnStretch(1, 4)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        # Chart 1: CPU + Memory + GPU  (top-left, spans rows)
        self.sys_card = MetricCard(
            title="System Resources",
            icon="🖥",
            series_defs=[
                {"name": "CPU",    "color": C_CPU},
                {"name": "Mem",    "color": C_MEM},
                {"name": "GPU",    "color": C_GPU},
            ],
            max_val=100.0,
            suffix="%",
            mode=self._mode,
        )
        grid.addWidget(self.sys_card, 0, 0, 2, 1)  # spans 2 rows

        # Chart 2: Processing speed  (top-right)
        self.spd_card = MetricCard(
            title="Processing Speed",
            icon="📸",
            series_defs=[
                {"name": "Rate", "color": c("warning", self._mode)},
            ],
            max_val=500.0,
            suffix=" p/h",
            mode=self._mode,
        )
        grid.addWidget(self.spd_card, 0, 1)

        # Chart 3: Queue  (bottom-right)
        self.que_card = MetricCard(
            title="Queue & Wait",
            icon="📋",
            series_defs=[
                {"name": "Pending",    "color": c("error",   self._mode)},
                {"name": "Processing", "color": "#fb923c"},
            ],
            max_val=50.0,
            suffix="",
            mode=self._mode,
        )
        grid.addWidget(self.que_card, 1, 1)

        ml.addLayout(grid, 1)

        # ── Footer ────────────────────────────────────────
        fr = QHBoxLayout()
        fr.setSpacing(8)

        self._uptime_lbl = QLabel("Monitor uptime: 0s")
        self._uptime_lbl.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px;"
        )
        fr.addWidget(self._uptime_lbl)
        fr.addStretch()

        for ok, label in [
            (HAS_PSUTIL, "psutil"),
            (HAS_GPUTIL, "GPUtil"),
        ]:
            badge = QLabel(
                f"{'✓' if ok else '✗'} {label}"
                + ("" if ok else " — install for live GPU data" if label == "GPUtil" else " — install for system metrics")
            )
            badge.setStyleSheet(
                f"color: {c('success' if ok else 'text_secondary', self._mode)}; "
                f"font-size: 10px; background: {c('stat_bg', self._mode)}; "
                f"padding: 3px 8px; border-radius: 8px;"
            )
            fr.addWidget(badge)

        ml.addLayout(fr)

        # Pulsing live dot
        self._pulse_on = True
        self._pulse_tmr = QTimer(self)
        self._pulse_tmr.setInterval(700)
        self._pulse_tmr.timeout.connect(self._pulse_live)
        self._pulse_tmr.start()

    # ── Metric collection ─────────────────────────────────

    def _collect(self):
        # ── System (CPU + MEM + GPU) ──────────────────────
        cpu, mem, gpu_load = 0.0, 0.0, 0.0

        if HAS_PSUTIL:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
            except Exception:
                pass

        if HAS_GPUTIL:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_load = gpus[0].load * 100
            except Exception:
                pass

        self.sys_card.add_values(cpu, mem, gpu_load)
        self.pill_cpu.update_value(f"{cpu:.0f}%")
        self.pill_mem.update_value(f"{mem:.0f}%")
        self.pill_gpu.update_value(f"{gpu_load:.0f}%")

        # ── DB / processing metrics ───────────────────────
        pph         = 0.0
        queue_depth = 0
        processing  = 0

        if HAS_DB:
            try:
                db    = get_db()
                stats = db.get_stats()
                pbs   = stats.get("photos_by_status", {})

                completed  = (
                    pbs.get("completed", 0) + pbs.get("no_faces", 0)
                )
                processing = pbs.get("processing", 0)
                pending    = pbs.get("pending",    0)
                queue_depth = pending + processing

                now = time.time()
                if self._last_completed is not None:
                    dp = completed - self._last_completed
                    dt = now - self._last_time
                    if dt > 0 and dp >= 0:
                        self._pph_history.append((dp / dt) * 3600)
                if self._pph_history:
                    pph = sum(self._pph_history) / len(self._pph_history)

                self._last_completed = completed
                self._last_time      = now

                # auto-scale
                if pph > 0:
                    self.spd_card.set_max(max(500.0, pph * 1.5))
                if queue_depth > 0:
                    self.que_card.set_max(max(50.0, queue_depth * 1.5))

            except Exception:
                pass

        self.spd_card.add_values(pph)
        self.que_card.add_values(float(queue_depth - processing),
                                  float(processing))

        self.pill_spd.update_value(f"{pph:.0f}/h")
        self.pill_que.update_value(str(queue_depth))

        # ── Uptime ────────────────────────────────────────
        el = time.time() - self._session_start
        if el < 60:
            s = f"{el:.0f}s"
        elif el < 3600:
            s = f"{el/60:.1f}m"
        else:
            s = f"{el/3600:.1f}h"
        self._uptime_lbl.setText(f"Monitor uptime: {s}")

    # ── Misc ──────────────────────────────────────────────

    def _pulse_live(self):
        self._pulse_on = not self._pulse_on
        col = c("success", self._mode) if self._pulse_on else "transparent"
        self._live_dot.setStyleSheet(f"color: {col}; font-size: 10px;")

    def _apply_bg(self):
        self.setStyleSheet(f"QDialog {{ background: {c('bg', self._mode)}; }}")

    def set_mode(self, mode: str):
        self._mode = mode
        self._apply_bg()
        for card in (self.sys_card, self.spd_card, self.que_card):
            card.set_mode(mode)
        for pill in (
            self.pill_cpu, self.pill_mem, self.pill_gpu,
            self.pill_spd, self.pill_que
        ):
            pill.set_mode(mode)

    def closeEvent(self, event):
        self._timer.stop()
        self._pulse_tmr.stop()
        event.accept()
