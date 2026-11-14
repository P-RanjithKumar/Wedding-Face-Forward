"""
WhatsAppTrackerWidget — Premium 3D animated WhatsApp delivery tracker.

Production-level animations:
  • 3D gradient WhatsApp icon with specular highlights, shadows & rim light
  • Pulsating light-green glow with expanding signal rings during sending
  • Explosive particle burst + shockwave on message delivery
  • Energetic comet trail (envelope → target badge) with sparkle particles
  • Badge highlight flash on comet arrival
  • Ambient floating particle system
"""

import json
import math
import random
from pathlib import Path

from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QWidget, QSizePolicy
)
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath
)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF

from ..theme import c

# ── WhatsApp brand palette ──────────────────────────────────────────────────
WA_LIGHT = "#a8e6a3"
WA_GREEN = "#25D366"
WA_DARK  = "#128C7E"
WA_TEAL  = "#075E54"

# ── Animation states ────────────────────────────────────────────────────────
S_IDLE    = "idle"
S_SEND    = "sending"
S_FLASH   = "flash"
S_COMET   = "comet"

TICK_MS = 33  # ~30 FPS


# ─── Particle ──────────────────────────────────────────────────────────────
class _P:
    __slots__ = ("x", "y", "vx", "vy", "cr", "cg", "cb", "ca",
                 "sz", "life", "maxl", "decay", "alive")

    def __init__(self, x, y, vx, vy, col: QColor, sz, life, decay=.97):
        self.x = x; self.y = y; self.vx = vx; self.vy = vy
        self.cr = col.red(); self.cg = col.green(); self.cb = col.blue()
        self.ca = col.alphaF(); self.sz = sz
        self.life = life; self.maxl = life; self.decay = decay; self.alive = True

    def tick(self):
        self.x += self.vx; self.y += self.vy
        self.vx *= self.decay; self.vy *= self.decay
        self.life -= 1
        if self.life <= 0:
            self.alive = False

    @property
    def alpha(self):
        return max(0.0, self.life / self.maxl) * self.ca


# ─── Signal Ring ───────────────────────────────────────────────────────────
class _Ring:
    __slots__ = ("x", "y", "rad", "mx", "spd", "alive")

    def __init__(self, x, y, mx, spd=1.2):
        self.x = x; self.y = y; self.rad = 0
        self.mx = mx; self.spd = spd; self.alive = True

    def tick(self):
        self.rad += self.spd
        if self.rad >= self.mx:
            self.alive = False

    @property
    def alpha(self):
        return max(0, 1 - self.rad / self.mx)


# ─── Animation Canvas ─────────────────────────────────────────────────────
class _Canvas(QWidget):
    """All animation rendering via QPainter — 3D icon, particles, comet."""

    def __init__(self, on_arrived=None, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._mode = "light"
        self._on_arrived = on_arrived

        # State
        self._st = S_IDLE
        self._frame = 0
        self._active = False

        # Idle breathing
        self._breath = 0.0

        # Sending
        self._pulse = 0.0
        self._rings: list[_Ring] = []
        self._ring_cd = 0
        self._orbits: list[_P] = []

        # Success flash
        self._flash_a = 0.0
        self._flash_sc = 1.0
        self._bursts: list[_P] = []
        self._shock_r = 0.0
        self._shock_a = 0.0

        # Comet
        self._comet_t = 0.0
        self._comet_tgt = "sent"
        self._comet_clr = QColor(WA_GREEN)
        self._trail: list = []
        self._sparks: list[_P] = []

        # Ambient
        self._ambient: list[_P] = []

        # Timer
        self._tmr = QTimer(self)
        self._tmr.setInterval(TICK_MS)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start()

    def set_mode(self, mode):
        self._mode = mode

    # ── State transitions ────────────────────────────────────────────────
    def go(self, st, tgt=None):
        self._st = st
        if st == S_SEND:
            self._pulse = 0; self._rings.clear(); self._ring_cd = 0
            self._orbits.clear()
        elif st == S_FLASH:
            self._flash_a = 1.0; self._flash_sc = 1.0
            self._shock_r = 0; self._shock_a = 1.0
            self._bursts.clear()
            cx, cy = self.width() / 2, self.height() / 2
            for i in range(28):
                a = (i / 28) * math.tau
                sp = random.uniform(2.5, 6.0)
                col = QColor(WA_GREEN)
                col.setAlphaF(random.uniform(.5, 1))
                self._bursts.append(_P(cx, cy, math.cos(a) * sp, math.sin(a) * sp,
                                       col, random.uniform(2, 5), random.randint(18, 38)))
            if tgt:
                self._comet_tgt = tgt
            self._comet_clr = self._tgt_color(self._comet_tgt)
            QTimer.singleShot(420, self._launch_comet)
        elif st == S_COMET:
            self._comet_t = 0; self._trail.clear(); self._sparks.clear()
            if tgt:
                self._comet_tgt = tgt
            self._comet_clr = self._tgt_color(self._comet_tgt)

    def _launch_comet(self):
        if self._st == S_FLASH:
            self._st = S_COMET
            self._comet_t = 0; self._trail.clear(); self._sparks.clear()

    def _tgt_color(self, t):
        return {"sent": QColor("#34c759"), "failed": QColor("#ff3b30"),
                "retry": QColor("#ff9500"), "invalid": QColor("#86868b")
                }.get(t, QColor(WA_GREEN))

    # ── Main tick ────────────────────────────────────────────────────────
    def _tick(self):
        self._frame += 1
        self._breath += .04

        # Ambient particles
        if random.random() < .05 and len(self._ambient) < 12:
            self._ambient.append(_P(
                random.uniform(0, self.width()), self.height() + 2,
                random.uniform(-.3, .3), random.uniform(-.7, -.15),
                QColor(WA_GREEN), random.uniform(1, 2.5),
                random.randint(50, 90), .99))
        for p in self._ambient:
            p.tick()
        self._ambient = [p for p in self._ambient if p.alive]

        if self._st == S_SEND:
            self._tick_send()
        elif self._st == S_FLASH:
            self._tick_flash()
        elif self._st == S_COMET:
            self._tick_comet()

        self.update()

    def _tick_send(self):
        self._pulse += .06
        self._ring_cd += 1
        if self._ring_cd >= 28:
            self._ring_cd = 0
            cx, cy = self.width() / 2, self.height() / 2
            self._rings.append(_Ring(cx, cy, max(self.width(), self.height()) * .42, 1.3))
        for r in self._rings:
            r.tick()
        self._rings = [r for r in self._rings if r.alive]

        if random.random() < .12 and len(self._orbits) < 10:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, math.tau)
            d = random.uniform(18, 34)
            self._orbits.append(_P(
                cx + math.cos(ang) * d, cy + math.sin(ang) * d,
                random.uniform(-.4, .4), random.uniform(-.4, .4),
                QColor(WA_LIGHT), random.uniform(1.5, 3), random.randint(20, 45), .97))
        for p in self._orbits:
            p.tick()
        self._orbits = [p for p in self._orbits if p.alive]

    def _tick_flash(self):
        self._flash_a *= .91
        self._flash_sc = 1.0 + self._flash_a * .18
        self._shock_r += 3.5
        self._shock_a *= .89
        for p in self._bursts:
            p.tick()
        self._bursts = [p for p in self._bursts if p.alive]

    def _tick_comet(self):
        self._comet_t += .035
        if self._comet_t >= 1.0:
            self._comet_t = 1.0
            if self._on_arrived:
                self._on_arrived(self._comet_tgt)
            self._st = S_SEND if self._active else S_IDLE
            return

        t = self._comet_t
        et = t * t * (3 - 2 * t)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        sx, sy = cx, cy - 4
        tgt_map = {"sent": .2, "retry": .4, "failed": .6, "invalid": .8}
        tx = w * tgt_map.get(self._comet_tgt, .5)
        ex, ey = tx, h + 4

        cpx = (sx + ex) / 2 + (ex - sx) * .25
        cpy = (sy + ey) / 2 - 15

        bx = (1 - et) ** 2 * sx + 2 * (1 - et) * et * cpx + et ** 2 * ex
        by = (1 - et) ** 2 * sy + 2 * (1 - et) * et * cpy + et ** 2 * ey

        self._trail.append((bx, by, 1.0))
        self._trail = [(x, y, a * .90) for x, y, a in self._trail if a > .04]

        if random.random() < .5:
            self._sparks.append(_P(
                bx + random.uniform(-3, 3), by + random.uniform(-3, 3),
                random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2),
                self._comet_clr, random.uniform(1, 3), random.randint(7, 14), .94))
        for p in self._sparks:
            p.tick()
        self._sparks = [p for p in self._sparks if p.alive]

    # ── Paint ────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        ptr = QPainter(self)
        ptr.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # Background glow
        if self._st in (S_SEND, S_FLASH):
            ga = .07 if self._st == S_SEND else self._flash_a * .15
            gr = QRadialGradient(cx, cy, w * .5)
            gc = QColor(WA_GREEN); gc.setAlphaF(ga)
            gr.setColorAt(0, gc); gr.setColorAt(1, QColor(0, 0, 0, 0))
            ptr.fillRect(self.rect(), QBrush(gr))

        # Ambient particles
        for p in self._ambient:
            self._paint_particle(ptr, p)

        # Signal rings
        if self._st == S_SEND:
            for ring in self._rings:
                rc = QColor(WA_LIGHT); rc.setAlphaF(ring.alpha * .35)
                ptr.setPen(QPen(rc, 1.5)); ptr.setBrush(Qt.BrushStyle.NoBrush)
                ptr.drawEllipse(QPointF(ring.x, ring.y), ring.rad, ring.rad)
            for p in self._orbits:
                self._paint_particle(ptr, p)

        # Shockwave
        if self._st == S_FLASH and self._shock_a > .01:
            sc = QColor(WA_GREEN); sc.setAlphaF(self._shock_a * .45)
            ptr.setPen(QPen(sc, 2.5)); ptr.setBrush(Qt.BrushStyle.NoBrush)
            ptr.drawEllipse(QPointF(cx, cy), self._shock_r, self._shock_r)
            for p in self._bursts:
                self._paint_particle(ptr, p)

        # 3D Icon
        self._paint_icon(ptr, cx, cy)

        # Comet
        if self._st == S_COMET:
            self._paint_comet(ptr)

        ptr.end()

    def _paint_icon(self, p, cx, cy):
        sz = 34
        hs = sz / 2

        # Determine look
        if self._st == S_SEND:
            t = (math.sin(self._pulse) + 1) / 2
            base = QColor(WA_LIGHT); hi = QColor(WA_GREEN)
            ic = QColor(
                int(base.red() + (hi.red() - base.red()) * t),
                int(base.green() + (hi.green() - base.green()) * t),
                int(base.blue() + (hi.blue() - base.blue()) * t))
            sc = 1.0 + t * .07
        elif self._st == S_FLASH:
            ic = QColor(WA_GREEN); sc = self._flash_sc
        else:
            b = (math.sin(self._breath) + 1) / 2
            ic = QColor(WA_GREEN); ic.setAlphaF(.75 + b * .25)
            sc = 1.0 + b * .025

        p.save()
        p.translate(cx, cy)
        p.scale(sc, sc)

        # Drop shadow
        sr = QRectF(-hs - 1, -hs + 2, sz + 2, sz + 2)
        sg = QRadialGradient(0, 3, hs + 4)
        sg.setColorAt(0, QColor(0, 0, 0, 55)); sg.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(sg)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(sr, 10, 10)

        # Body gradient
        br = QRectF(-hs, -hs, sz, sz)
        bg = QLinearGradient(-hs, -hs, hs, hs)
        bg.setColorAt(0, self._lighten(ic, 35))
        bg.setColorAt(.45, ic)
        bg.setColorAt(1, self._darken(ic, 45))
        p.setBrush(QBrush(bg)); p.drawRoundedRect(br, 10, 10)

        # Specular highlight
        hr = QRectF(-hs + 3, -hs + 3, sz * .48, sz * .32)
        hg = QLinearGradient(hr.topLeft(), hr.bottomRight())
        hg.setColorAt(0, QColor(255, 255, 255, 105))
        hg.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hg)); p.drawRoundedRect(hr, 7, 7)

        # Rim light
        rr = QRectF(-hs + 3, hs - sz * .18, sz - 6, sz * .12)
        rg = QLinearGradient(rr.topLeft(), rr.bottomLeft())
        rg.setColorAt(0, QColor(255, 255, 255, 0))
        rg.setColorAt(1, QColor(255, 255, 255, 35))
        p.setBrush(QBrush(rg)); p.drawRoundedRect(rr, 3, 3)

        # Speech bubble (white circle + tail)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 225))
        bub_r = sz * .30
        p.drawEllipse(QPointF(0, -1), bub_r, bub_r)

        tail = QPainterPath()
        tail.moveTo(-bub_r * .25, bub_r * .55)
        tail.lineTo(-bub_r * .75, bub_r * 1.1)
        tail.lineTo(bub_r * .1, bub_r * .4)
        p.drawPath(tail)

        # Phone handset
        h_color = ic if ic.alphaF() > .9 else QColor(WA_GREEN)
        p.setPen(QPen(h_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        ph = QPainterPath()
        ph.moveTo(-3.5, -5)
        ph.cubicTo(-5.5, -2, 5.5, 1, 3.5, 4)
        p.drawPath(ph)
        p.setBrush(h_color); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(-3.5, -5), 1.6, 1.2)
        p.drawEllipse(QPointF(3.5, 4), 1.6, 1.2)

        # Outer glow when sending
        if self._st == S_SEND:
            gs = hs + 6 + (math.sin(self._pulse * 2) + 1) * 3
            gg = QRadialGradient(0, 0, gs)
            gc = QColor(WA_GREEN)
            gc.setAlphaF(.12 + (math.sin(self._pulse) + 1) * .04)
            gg.setColorAt(.6, gc); gg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(gg)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(0, 0), gs, gs)

        p.restore()

    def _paint_comet(self, p):
        # Trail glow
        for tx, ty, ta in self._trail:
            sz = 2 + ta * 4
            tc = QColor(self._comet_clr); tc.setAlphaF(ta * .55)
            g = QRadialGradient(tx, ty, sz)
            g.setColorAt(0, tc); tc2 = QColor(tc); tc2.setAlphaF(0)
            g.setColorAt(1, tc2)
            p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(tx, ty), sz, sz)

        for sp in self._sparks:
            self._paint_particle(p, sp)

        # Envelope head
        if self._trail:
            hx, hy, _ = self._trail[-1]
            p.save(); p.translate(hx, hy)
            # Head glow
            g = QRadialGradient(0, 0, 12)
            gc = QColor(self._comet_clr); gc.setAlphaF(.35)
            g.setColorAt(0, gc); g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(0, 0), 12, 12)
            # Envelope
            es = 7
            p.setBrush(QColor(255, 255, 255, 235))
            p.setPen(QPen(self._comet_clr, .8))
            er = QRectF(-es / 2, -es / 3, es, es * .66)
            p.drawRoundedRect(er, 1.5, 1.5)
            flap = QPainterPath()
            flap.moveTo(-es / 2, -es / 3)
            flap.lineTo(0, es * .08)
            flap.lineTo(es / 2, -es / 3)
            p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(flap)
            p.restore()

    def _paint_particle(self, p, pt):
        if not pt.alive:
            return
        a = pt.alpha
        if a < .01:
            return
        col = QColor(pt.cr, pt.cg, pt.cb)
        col.setAlphaF(a)
        g = QRadialGradient(pt.x, pt.y, pt.sz)
        g.setColorAt(0, col)
        col2 = QColor(col); col2.setAlphaF(0)
        g.setColorAt(1, col2)
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(pt.x, pt.y), pt.sz, pt.sz)

    @staticmethod
    def _lighten(c, amt):
        return QColor(min(255, c.red() + amt), min(255, c.green() + amt),
                       min(255, c.blue() + amt), c.alpha())

    @staticmethod
    def _darken(c, amt):
        return QColor(max(0, c.red() - amt), max(0, c.green() - amt),
                       max(0, c.blue() - amt), c.alpha())


# ─── Main Widget ───────────────────────────────────────────────────────────
class WhatsAppTrackerWidget(QFrame):
    """Premium WhatsApp delivery tracker with 3D animated icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("wa_tracker_widget")
        self._mode = "light"
        self._system_active = False
        self._first_refresh = True

        # Previous counts for change detection
        self._prev = {"sent": 0, "failed": 0, "invalid": 0, "retry": 0}

        # Path to WhatsApp state file
        try:
            import dist_utils
            self._state_file = dist_utils.get_user_data_dir() / "whatsapp_data" / "message_state_db.json"
        except ImportError:
            base_dir = Path(__file__).parent.parent.parent.resolve()
            self._state_file = base_dir / "whatsapp_tool" / "whatsapp_data" / "message_state_db.json"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 8)
        layout.setSpacing(3)

        # Title
        title = QLabel("WHATSAPP")
        title.setObjectName("card_title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        # Animation canvas
        self.canvas = _Canvas(on_arrived=self._on_comet_arrived)
        layout.addWidget(self.canvas, 1)

        # Total
        self.total_label = QLabel("0")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {c('text_secondary', self._mode)};"
        )
        layout.addWidget(self.total_label)

        layout.addSpacing(2)

        # Badge rows
        self._badges = {}
        self._badges["sent"] = self._make_row(layout, "Sent", c("success", self._mode))
        self._badges["retry"] = self._make_row(layout, "Retry", c("warning", self._mode))
        self._badges["failed"] = self._make_row(layout, "Failed", c("error", self._mode))
        self._badges["invalid"] = self._make_row(layout, "Invalid", "#86868b")

        # Convenience aliases for backward compat
        self.badge_sent = self._badges["sent"]
        self.badge_retry = self._badges["retry"]
        self.badge_failed = self._badges["failed"]
        self.badge_invalid = self._badges["invalid"]

    def _make_row(self, parent_layout, label_text: str, color: str) -> QLabel:
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

    # ── Public API ───────────────────────────────────────────────────────
    def set_system_active(self, active: bool):
        """Called from app_window when system starts/stops."""
        self._system_active = active
        # We don't force self.canvas.go(S_SEND) here anymore.
        # The refresh() call will determine the correct state.

    def refresh(self, total_enrollments: int = 0):
        """Reload the WhatsApp state file and update all UI elements."""
        state = self._load_state()

        counts = {"sent": 0, "failed": 0, "invalid": 0, "retry": 0}
        for _key, entry in state.items():
            st = entry.get("status", "")
            if st in counts:
                counts[st] += 1

        total = sum(counts.values())
        
        # Determine if we have work to do
        # We consider work "done" if it's sent, permanently failed, or invalid.
        # Retries are still considered "active" work.
        done_count = counts["sent"] + counts["failed"] + counts["invalid"]
        has_active_work = (total_enrollments > done_count) or (counts["retry"] > 0)
        
        is_actively_sending = self._system_active and has_active_work

        # Update the canvas behavior flag so it knows what to do after a comet arrives
        self.canvas._active = is_actively_sending

        # On first refresh, just record baseline — don't animate
        if self._first_refresh:
            self._prev = dict(counts)
            self._first_refresh = False
            # set initial state based on current workload
            if is_actively_sending:
                self.canvas.go(S_SEND)
        else:
            # 1. Detect changes — trigger animation for the highest-priority change
            # Success/Failure flashes take precedence over the background pulse
            for key in ("sent", "failed", "invalid", "retry"):
                if counts[key] > self._prev[key]:
                    self.canvas.go(S_FLASH, key)
                    break
            
            # 2. If no special animation is running, ensure we are in the correct basic state
            if self.canvas._st in (S_IDLE, S_SEND):
                if is_actively_sending:
                    if self.canvas._st == S_IDLE:
                        self.canvas.go(S_SEND)
                else:
                    if self.canvas._st == S_SEND:
                        self.canvas.go(S_IDLE)
            
            self._prev = dict(counts)

        # Update labels
        self.total_label.setText(str(total))
        if total == 0:
            clr = c("text_secondary", self._mode)
        elif counts["failed"] > 0:
            clr = c("warning", self._mode)
        else:
            clr = c("text_primary", self._mode)
        self.total_label.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {clr};"
        )

        self.badge_sent.setText(str(counts["sent"]))
        self.badge_retry.setText(str(counts["retry"]))
        self.badge_failed.setText(str(counts["failed"]))
        self.badge_invalid.setText(str(counts["invalid"]))

    def _on_comet_arrived(self, target: str):
        """Flash the target badge when the comet arrives."""
        badge = self._badges.get(target)
        if not badge:
            return
        orig = badge.styleSheet()
        color_map = {
            "sent": "#34c759", "failed": "#ff3b30",
            "retry": "#ff9500", "invalid": "#86868b"
        }
        clr = color_map.get(target, "#34c759")
        badge.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: white; "
            f"background: {clr}; border-radius: 4px; padding: 1px 4px;"
        )
        QTimer.singleShot(600, lambda: badge.setStyleSheet(orig))

    # ── Internal ─────────────────────────────────────────────────────────
    def _load_state(self) -> dict:
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
        self.canvas.set_mode(self._mode)
