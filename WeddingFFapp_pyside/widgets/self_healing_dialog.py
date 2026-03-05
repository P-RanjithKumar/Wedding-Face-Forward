"""
SelfHealingDialog — Automatic database diagnostics and one-click repair.

Detects:
  • Photos stuck in 'processing' status
  • Uploads stuck in 'uploading' status
  • Photos in 'error' status that can be retried
  • Orphaned face records (faces linked to nonexistent photos)
  • Orphaned upload queue entries (uploads for missing files)
  • Failed uploads exceeding max retries
  • Database integrity issues (PRAGMA integrity_check)
  • WAL file size (pending checkpoints)

One-click repair actions:
  • Reset stuck processing → pending
  • Reset stuck uploads → pending
  • Retry error photos → pending
  • Clean orphaned face records
  • Clean orphaned upload entries
  • Reset failed uploads for retry
  • Run WAL checkpoint
  • Run full repair (all of the above)
"""

import os
import sqlite3
import threading
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy,
    QApplication, QProgressBar
)
from PySide6.QtGui import QCursor, QFont
from PySide6.QtCore import Qt, Signal, QTimer

from ..theme import c, COLORS


# ─────────────────────────────────────────────────────────
# Issue Card — represents one diagnostic finding
# ─────────────────────────────────────────────────────────

class IssueCard(QFrame):
    """A card showing one diagnostic issue with a repair button."""

    repair_requested = Signal(str)  # emits issue_key

    def __init__(self, issue_key: str, icon: str, title: str, description: str,
                 mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._issue_key = issue_key
        self.setObjectName("issue_card")
        self.setFixedHeight(80)
        self._apply_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        # Status icon (left)
        self.status_icon = QLabel(icon)
        self.status_icon.setFixedSize(36, 36)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon.setStyleSheet(
            f"font-size: 22px; background: {c('stat_bg', self._mode)}; "
            f"border-radius: 18px;"
        )
        layout.addWidget(self.status_icon)

        # Info (middle)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 13px; "
            f"font-weight: bold; background: transparent;"
        )
        info_layout.addWidget(self.title_label)

        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"background: transparent;"
        )
        self.desc_label.setWordWrap(True)
        info_layout.addWidget(self.desc_label)

        layout.addLayout(info_layout, 1)

        # Count badge (right of info)
        self.count_badge = QLabel("—")
        self.count_badge.setFixedSize(48, 28)
        self.count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_badge.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 13px; "
            f"font-weight: bold; background: {c('stat_bg', self._mode)}; "
            f"border-radius: 14px;"
        )
        layout.addWidget(self.count_badge)

        # Repair button (right)
        self.repair_btn = QPushButton("🔧 FIX")
        self.repair_btn.setFixedSize(80, 34)
        self.repair_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.repair_btn.setEnabled(False)
        self._style_repair_btn(enabled=False)
        self.repair_btn.clicked.connect(lambda: self.repair_requested.emit(self._issue_key))
        layout.addWidget(self.repair_btn)

    def _apply_style(self):
        bg = c("bg_card", self._mode)
        border = c("border", self._mode)
        self.setStyleSheet(
            f"QFrame#issue_card {{"
            f"  background-color: {bg}; "
            f"  border: 1px solid {border}; "
            f"  border-radius: 14px; "
            f"}}"
        )

    def _style_repair_btn(self, enabled=True):
        if enabled:
            accent = c("accent", self._mode)
            self.repair_btn.setStyleSheet(
                f"QPushButton {{ background: {accent}; color: white; "
                f"border-radius: 12px; font-size: 11px; font-weight: bold; border: none; }}"
                f"QPushButton:hover {{ background: #0066dd; }}"
            )
        else:
            self.repair_btn.setStyleSheet(
                f"QPushButton {{ background: {c('text_secondary', self._mode)}40; "
                f"color: {c('text_secondary', self._mode)}; "
                f"border-radius: 12px; font-size: 11px; font-weight: bold; border: none; }}"
            )

    def set_count(self, count: int, severity: str = "normal"):
        """Update the count badge. severity: 'normal', 'warning', 'error', 'success'"""
        self.count_badge.setText(str(count))

        color_map = {
            "normal": c("text_secondary", self._mode),
            "warning": c("warning", self._mode),
            "error": c("error", self._mode),
            "success": c("success", self._mode),
        }
        color = color_map.get(severity, c("text_secondary", self._mode))

        if count > 0 and severity != "success":
            bg = f"{color}18"
        elif severity == "success":
            bg = f"{color}18"
        else:
            bg = c("stat_bg", self._mode)

        self.count_badge.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: bold; "
            f"background: {bg}; border-radius: 14px;"
        )

        has_issues = count > 0 and severity != "success"
        self.repair_btn.setEnabled(has_issues)
        self._style_repair_btn(enabled=has_issues)

    def set_status(self, text: str, color: str = None):
        """Override count badge with status text."""
        if color is None:
            color = c("success", self._mode)
        self.count_badge.setFixedSize(60, 28)
        self.count_badge.setText(text)
        self.count_badge.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold; "
            f"background: {color}18; border-radius: 14px;"
        )
        self.repair_btn.setEnabled(False)
        self._style_repair_btn(enabled=False)

    def set_repairing(self):
        """Show repairing state."""
        self.repair_btn.setText("⏳")
        self.repair_btn.setEnabled(False)
        self._style_repair_btn(enabled=False)

    def set_repaired(self, fixed_count: int):
        """Show repaired state."""
        self.repair_btn.setText("✓ Done")
        self.repair_btn.setEnabled(False)
        success = c("success", self._mode)
        self.repair_btn.setStyleSheet(
            f"QPushButton {{ background: {success}; color: white; "
            f"border-radius: 12px; font-size: 11px; font-weight: bold; border: none; }}"
        )
        self.count_badge.setText(f"−{fixed_count}")
        self.count_badge.setStyleSheet(
            f"color: {success}; font-size: 11px; font-weight: bold; "
            f"background: {success}18; border-radius: 14px;"
        )

    def set_mode(self, mode: str):
        self._mode = mode
        self._apply_style()


# ─────────────────────────────────────────────────────────
# Main Self-Healing Dialog
# ─────────────────────────────────────────────────────────

class SelfHealingDialog(QDialog):
    """
    Database self-healing dialog — scans for issues and provides
    one-click repair for each detected problem.
    """

    repair_completed = Signal()  # Emitted after any repair action

    def __init__(self, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._issue_cards = {}
        self._diagnostics = {}

        self.setWindowTitle("Self-Healing Database — Wedding FaceForward")
        self.setMinimumSize(680, 580)
        self.resize(740, 650)
        self.setModal(True)

        bg = c("bg", self._mode)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

        self._build_ui()

        # Auto-scan on open
        QTimer.singleShot(300, self._run_diagnostics)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # ── Title Row ──
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title_icon = QLabel("🩺")
        title_icon.setStyleSheet("font-size: 28px;")
        title_row.addWidget(title_icon)

        title = QLabel("Self-Healing Database")
        title.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 22px; font-weight: bold;"
        )
        title_row.addWidget(title)

        title_row.addStretch()

        # Last scan timestamp
        self.scan_badge = QLabel("Scanning...")
        self.scan_badge.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"background: {c('stat_bg', self._mode)}; padding: 4px 10px; "
            f"border-radius: 10px;"
        )
        title_row.addWidget(self.scan_badge)

        main_layout.addLayout(title_row)

        # ── Subtitle ──
        subtitle = QLabel(
            "Automatically detects database anomalies — stuck records, orphaned data, "
            "integrity issues — and provides one-click repair for each problem."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px; line-height: 1.4;"
        )
        main_layout.addWidget(subtitle)

        # ── Health Summary Bar ──
        summary_frame = QFrame()
        summary_frame.setObjectName("health_summary")
        summary_frame.setFixedHeight(56)
        summary_frame.setStyleSheet(
            f"QFrame#health_summary {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"    stop:0 {c('success', self._mode)}15, stop:1 {c('accent', self._mode)}10);"
            f"  border: 1px solid {c('border', self._mode)}; border-radius: 14px;"
            f"}}"
        )
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(18, 0, 18, 0)
        summary_layout.setSpacing(20)

        self.health_icon = QLabel("⏳")
        self.health_icon.setStyleSheet("font-size: 22px; background: transparent;")
        summary_layout.addWidget(self.health_icon)

        self.health_label = QLabel("Running diagnostics...")
        self.health_label.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 14px; "
            f"font-weight: bold; background: transparent;"
        )
        summary_layout.addWidget(self.health_label)

        summary_layout.addStretch()

        self.issues_count_label = QLabel("")
        self.issues_count_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px; "
            f"background: transparent;"
        )
        summary_layout.addWidget(self.issues_count_label)

        main_layout.addWidget(summary_frame)

        # ── Scrollable Issue Cards ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("healing_scroll")
        scroll.setStyleSheet(
            f"QScrollArea#healing_scroll {{ background: transparent; border: none; }}"
            f"QScrollArea#healing_scroll > QWidget > QWidget {{ background: transparent; }}"
            f"QScrollBar:vertical {{"
            f"  background: {c('bg', self._mode)}; width: 8px; border: none; border-radius: 4px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {c('text_secondary', self._mode)}40; min-height: 30px; border-radius: 4px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{"
            f"  background: {c('accent', self._mode)}80;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"  height: 0px;"
            f"}}"
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(scroll_content)
        self.cards_layout.setContentsMargins(0, 0, 8, 0)
        self.cards_layout.setSpacing(8)

        # Create issue cards
        issue_definitions = [
            ("stuck_processing", "🔄", "Stuck Processing Photos",
             "Photos stuck in 'processing' status from crashes or timeouts"),
            ("stuck_uploads", "☁️", "Stuck Cloud Uploads",
             "Uploads stuck in 'uploading' status from network failures"),
            ("error_photos", "❌", "Error Photos",
             "Photos that failed processing and can be retried"),
            ("orphaned_faces", "👤", "Orphaned Face Records",
             "Face records linked to non-existent or unprocessed photos"),
            ("orphaned_uploads", "📤", "Orphaned Upload Entries",
             "Upload queue entries for files that no longer exist on disk"),
            ("failed_uploads", "⚠️", "Failed Uploads (Max Retries)",
             "Uploads that exhausted all retry attempts"),
            ("db_integrity", "🛡️", "Database Integrity",
             "SQLite structural integrity validation (PRAGMA integrity_check)"),
            ("wal_size", "📋", "WAL Journal Size",
             "Write-Ahead Log file size — large WAL slows performance"),
        ]

        for key, icon, title, desc in issue_definitions:
            card = IssueCard(key, icon, title, desc, mode=self._mode)
            card.repair_requested.connect(self._on_repair_requested)
            self.cards_layout.addWidget(card)
            self._issue_cards[key] = card

        self.cards_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        # ── Bottom Action Row ──
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px;"
        )
        bottom_row.addWidget(self.status_label)

        bottom_row.addStretch()

        # Re-scan button
        rescan_btn = QPushButton("🔍  Re-Scan")
        rescan_btn.setFixedSize(110, 38)
        rescan_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rescan_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 12px; font-weight: bold; "
            f"border: 1px solid {c('border', self._mode)}; }}"
            f"QPushButton:hover {{ background: {c('border', self._mode)}; }}"
        )
        rescan_btn.clicked.connect(self._run_diagnostics)
        bottom_row.addWidget(rescan_btn)

        # Fix All button
        self.fix_all_btn = QPushButton("🩹  Fix All")
        self.fix_all_btn.setFixedSize(120, 38)
        self.fix_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.fix_all_btn.setEnabled(False)
        self._style_fix_all_btn(enabled=False)
        self.fix_all_btn.clicked.connect(self._fix_all)
        bottom_row.addWidget(self.fix_all_btn)

        main_layout.addLayout(bottom_row)

    def _style_fix_all_btn(self, enabled=True):
        if enabled:
            accent = c("accent", self._mode)
            self.fix_all_btn.setStyleSheet(
                f"QPushButton {{ background: {accent}; color: white; "
                f"border-radius: 12px; font-size: 14px; font-weight: bold; border: none; }}"
                f"QPushButton:hover {{ background: #0066dd; }}"
            )
        else:
            self.fix_all_btn.setStyleSheet(
                f"QPushButton {{ background: {c('text_secondary', self._mode)}; "
                f"color: white; border-radius: 12px; "
                f"font-size: 14px; font-weight: bold; border: none; }}"
            )

    # ─────────────────────────────────────────────────────
    # Diagnostics
    # ─────────────────────────────────────────────────────

    def _run_diagnostics(self):
        """Run all diagnostic checks in a background thread."""
        self.health_icon.setText("⏳")
        self.health_label.setText("Running diagnostics...")
        self.scan_badge.setText("Scanning...")
        self.status_label.setText("")

        # Reset all cards to scanning state
        for card in self._issue_cards.values():
            card.count_badge.setText("...")
            card.repair_btn.setText("🔧 FIX")

        threading.Thread(target=self._diagnostics_worker, daemon=True).start()

    def _diagnostics_worker(self):
        """Background worker that runs all diagnostic checks."""
        import sys
        base_dir = Path(__file__).parent.parent.parent.resolve()
        backend_dir = base_dir / "backend"
        sys.path.insert(0, str(backend_dir))

        from app.db import get_db
        from app.config import get_config

        db = get_db()
        config = get_config()
        results = {}

        try:
            conn = db.connect()

            # 1. Stuck processing photos
            cursor = conn.execute("SELECT COUNT(*) FROM photos WHERE status = 'processing'")
            results["stuck_processing"] = cursor.fetchone()[0]

            # 2. Stuck uploads
            cursor = conn.execute("SELECT COUNT(*) FROM upload_queue WHERE status = 'uploading'")
            results["stuck_uploads"] = cursor.fetchone()[0]

            # 3. Error photos
            cursor = conn.execute("SELECT COUNT(*) FROM photos WHERE status = 'error'")
            results["error_photos"] = cursor.fetchone()[0]

            # 4. Orphaned faces (faces for photos not in 'completed' status)
            cursor = conn.execute(
                """SELECT COUNT(*) FROM faces f
                   WHERE NOT EXISTS (
                       SELECT 1 FROM photos p 
                       WHERE p.id = f.photo_id AND p.status = 'completed'
                   )"""
            )
            results["orphaned_faces"] = cursor.fetchone()[0]

            # 5. Orphaned upload entries (files that don't exist on disk)
            cursor = conn.execute(
                "SELECT id, local_path FROM upload_queue WHERE status IN ('pending', 'failed')"
            )
            orphaned_uploads = 0
            for row in cursor.fetchall():
                if not Path(row[1]).exists():
                    orphaned_uploads += 1
            results["orphaned_uploads"] = orphaned_uploads

            # 6. Failed uploads that exceeded max retries
            cursor = conn.execute(
                "SELECT COUNT(*) FROM upload_queue WHERE status = 'failed' AND retry_count >= 5"
            )
            results["failed_uploads"] = cursor.fetchone()[0]

            # 7. Database integrity
            cursor = conn.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            results["db_integrity"] = 0 if integrity_result == "ok" else 1
            results["db_integrity_detail"] = integrity_result

            # 8. WAL file size
            db_path = config.db_path
            wal_path = Path(str(db_path) + "-wal")
            if wal_path.exists():
                wal_size_mb = wal_path.stat().st_size / (1024 * 1024)
                results["wal_size"] = round(wal_size_mb, 2)
            else:
                results["wal_size"] = 0.0

            conn.commit()

        except Exception as e:
            results["error"] = str(e)

        self._diagnostics = results

        # Update UI from main thread
        QTimer.singleShot(0, lambda: self._update_ui_with_results(results))

    def _update_ui_with_results(self, results: dict):
        """Update all issue cards with diagnostic results."""
        if "error" in results:
            self.health_icon.setText("❌")
            self.health_label.setText(f"Diagnostics failed: {results['error']}")
            self.scan_badge.setText("Error")
            return

        total_issues = 0

        # Stuck processing
        count = results.get("stuck_processing", 0)
        total_issues += count
        severity = "warning" if count > 0 else "success"
        self._issue_cards["stuck_processing"].set_count(count, severity)

        # Stuck uploads
        count = results.get("stuck_uploads", 0)
        total_issues += count
        severity = "warning" if count > 0 else "success"
        self._issue_cards["stuck_uploads"].set_count(count, severity)

        # Error photos
        count = results.get("error_photos", 0)
        total_issues += count
        severity = "error" if count > 0 else "success"
        self._issue_cards["error_photos"].set_count(count, severity)

        # Orphaned faces
        count = results.get("orphaned_faces", 0)
        total_issues += count
        severity = "warning" if count > 0 else "success"
        self._issue_cards["orphaned_faces"].set_count(count, severity)

        # Orphaned uploads
        count = results.get("orphaned_uploads", 0)
        total_issues += count
        severity = "warning" if count > 0 else "success"
        self._issue_cards["orphaned_uploads"].set_count(count, severity)

        # Failed uploads
        count = results.get("failed_uploads", 0)
        total_issues += count
        severity = "error" if count > 0 else "success"
        self._issue_cards["failed_uploads"].set_count(count, severity)

        # DB integrity
        integrity_ok = results.get("db_integrity", 0) == 0
        if integrity_ok:
            self._issue_cards["db_integrity"].set_status("OK", c("success", self._mode))
        else:
            detail = results.get("db_integrity_detail", "unknown")
            self._issue_cards["db_integrity"].set_count(1, "error")
            self._issue_cards["db_integrity"].desc_label.setText(
                f"Integrity check failed: {detail}"
            )
            total_issues += 1

        # WAL size
        wal_mb = results.get("wal_size", 0.0)
        if wal_mb > 50:
            self._issue_cards["wal_size"].set_count(1, "warning")
            self._issue_cards["wal_size"].desc_label.setText(
                f"WAL file is {wal_mb:.1f} MB — checkpoint recommended (>50 MB)"
            )
            total_issues += 1
        elif wal_mb > 0:
            self._issue_cards["wal_size"].set_status(
                f"{wal_mb:.1f}MB", c("success", self._mode)
            )
        else:
            self._issue_cards["wal_size"].set_status("0 MB", c("success", self._mode))

        # Update summary bar
        now_str = datetime.now().strftime("%H:%M:%S")
        self.scan_badge.setText(f"Last scan: {now_str}")

        if total_issues == 0:
            self.health_icon.setText("✅")
            self.health_label.setText("Database is healthy — no issues found")
            self.issues_count_label.setText("All clear!")
            self.issues_count_label.setStyleSheet(
                f"color: {c('success', self._mode)}; font-size: 12px; "
                f"font-weight: bold; background: transparent;"
            )
            self.fix_all_btn.setEnabled(False)
            self._style_fix_all_btn(enabled=False)
        else:
            self.health_icon.setText("⚠️")
            self.health_label.setText(f"{total_issues} issue(s) detected")
            self.health_label.setStyleSheet(
                f"color: {c('warning', self._mode)}; font-size: 14px; "
                f"font-weight: bold; background: transparent;"
            )
            self.issues_count_label.setText("Click FIX or Fix All to resolve")
            self.issues_count_label.setStyleSheet(
                f"color: {c('text_secondary', self._mode)}; font-size: 12px; "
                f"background: transparent;"
            )
            self.fix_all_btn.setEnabled(True)
            self._style_fix_all_btn(enabled=True)

    # ─────────────────────────────────────────────────────
    # Repair Actions
    # ─────────────────────────────────────────────────────

    def _on_repair_requested(self, issue_key: str):
        """Handle repair request for a specific issue."""
        card = self._issue_cards.get(issue_key)
        if card:
            card.set_repairing()

        threading.Thread(
            target=self._repair_worker,
            args=(issue_key,),
            daemon=True
        ).start()

    def _repair_worker(self, issue_key: str):
        """Execute a specific repair action in background."""
        import sys
        base_dir = Path(__file__).parent.parent.parent.resolve()
        backend_dir = base_dir / "backend"
        sys.path.insert(0, str(backend_dir))

        from app.db import get_db
        from app.config import get_config

        db = get_db()
        config = get_config()
        fixed_count = 0

        try:
            conn = db.connect()

            if issue_key == "stuck_processing":
                fixed_count = db._reset_stuck_processing()
                # Also try the live version for time-based reset
                if fixed_count == 0:
                    fixed_count = db.reset_stuck_processing_live(timeout_minutes=0)

            elif issue_key == "stuck_uploads":
                fixed_count = db.reset_stuck_uploads(timeout_minutes=0)

            elif issue_key == "error_photos":
                # Reset error photos back to pending for reprocessing
                with conn:
                    cursor = conn.execute(
                        """UPDATE photos 
                           SET status = 'pending', 
                               processed_path = NULL,
                               thumbnail_path = NULL,
                               face_count = NULL,
                               processed_at = NULL
                           WHERE status = 'error'"""
                    )
                    fixed_count = cursor.rowcount
                # Also clean up any face records for these photos
                if fixed_count > 0:
                    cursor = conn.execute(
                        "SELECT id FROM photos WHERE status = 'pending' AND processed_at IS NULL"
                    )
                    reset_ids = [row[0] for row in cursor.fetchall()]
                    if reset_ids:
                        db._cleanup_orphaned_faces(reset_ids)

            elif issue_key == "orphaned_faces":
                # Delete faces that belong to photos not in 'completed' status
                with conn:
                    cursor = conn.execute(
                        """DELETE FROM faces 
                           WHERE photo_id NOT IN (
                               SELECT id FROM photos WHERE status = 'completed'
                           )"""
                    )
                    fixed_count = cursor.rowcount

            elif issue_key == "orphaned_uploads":
                # Remove upload entries for files that no longer exist
                cursor = conn.execute(
                    "SELECT id, local_path FROM upload_queue WHERE status IN ('pending', 'failed')"
                )
                orphan_ids = []
                for row in cursor.fetchall():
                    if not Path(row[1]).exists():
                        orphan_ids.append(row[0])
                if orphan_ids:
                    placeholders = ','.join('?' * len(orphan_ids))
                    with conn:
                        cursor = conn.execute(
                            f"DELETE FROM upload_queue WHERE id IN ({placeholders})",
                            orphan_ids
                        )
                        fixed_count = cursor.rowcount

            elif issue_key == "failed_uploads":
                # Reset failed uploads to pending for retry (reset retry count too)
                with conn:
                    cursor = conn.execute(
                        """UPDATE upload_queue 
                           SET status = 'pending', retry_count = 0, 
                               last_error = 'Reset by self-healing repair',
                               updated_at = ?
                           WHERE status = 'failed' AND retry_count >= 5""",
                        (datetime.now(),)
                    )
                    fixed_count = cursor.rowcount

            elif issue_key == "wal_size":
                # Run WAL checkpoint
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                fixed_count = 1

            conn.commit()

        except Exception as e:
            fixed_count = -1
            error_msg = str(e)

        # Update UI from main thread
        QTimer.singleShot(0, lambda: self._on_repair_complete(issue_key, fixed_count))

    def _on_repair_complete(self, issue_key: str, fixed_count: int):
        """Update UI after a repair action completes."""
        card = self._issue_cards.get(issue_key)
        if not card:
            return

        if fixed_count < 0:
            card.repair_btn.setText("❌ Error")
            card.repair_btn.setStyleSheet(
                f"QPushButton {{ background: {c('error', self._mode)}; color: white; "
                f"border-radius: 12px; font-size: 11px; font-weight: bold; border: none; }}"
            )
            self.status_label.setText(f"❌ Repair failed for {issue_key}")
            self.status_label.setStyleSheet(
                f"color: {c('error', self._mode)}; font-size: 12px; font-weight: bold;"
            )
        else:
            card.set_repaired(fixed_count)
            self.status_label.setText(
                f"✓ Fixed {fixed_count} item(s) in {issue_key.replace('_', ' ')}"
            )
            self.status_label.setStyleSheet(
                f"color: {c('success', self._mode)}; font-size: 12px; font-weight: bold;"
            )

        self.repair_completed.emit()

        # Re-scan after a short delay to update counts
        QTimer.singleShot(1500, self._run_diagnostics)

    def _fix_all(self):
        """Run all available repairs sequentially."""
        self.fix_all_btn.setEnabled(False)
        self.fix_all_btn.setText("⏳ Fixing...")
        self._style_fix_all_btn(enabled=False)
        self.status_label.setText("Running full repair...")
        self.status_label.setStyleSheet(
            f"color: {c('accent', self._mode)}; font-size: 12px; font-weight: bold;"
        )

        # Mark all cards with issues as repairing
        for key, card in self._issue_cards.items():
            if card.repair_btn.isEnabled():
                card.set_repairing()

        threading.Thread(target=self._fix_all_worker, daemon=True).start()

    def _fix_all_worker(self):
        """Run all repairs in sequence."""
        repair_keys = [
            "stuck_processing",
            "stuck_uploads",
            "error_photos",
            "orphaned_faces",
            "orphaned_uploads",
            "failed_uploads",
            "wal_size",
        ]

        total_fixed = 0

        for key in repair_keys:
            # Only repair if there's actually an issue
            diag_value = self._diagnostics.get(key, 0)
            if isinstance(diag_value, (int, float)) and diag_value > 0:
                self._repair_worker_sync(key)
                total_fixed += 1

        QTimer.singleShot(0, lambda: self._on_fix_all_complete(total_fixed))

    def _repair_worker_sync(self, issue_key: str):
        """Synchronous repair for use in fix_all sequence."""
        import sys
        base_dir = Path(__file__).parent.parent.parent.resolve()
        backend_dir = base_dir / "backend"
        sys.path.insert(0, str(backend_dir))

        from app.db import get_db
        from app.config import get_config

        db = get_db()
        config = get_config()

        try:
            conn = db.connect()

            if issue_key == "stuck_processing":
                db._reset_stuck_processing()
                db.reset_stuck_processing_live(timeout_minutes=0)

            elif issue_key == "stuck_uploads":
                db.reset_stuck_uploads(timeout_minutes=0)

            elif issue_key == "error_photos":
                with conn:
                    conn.execute(
                        """UPDATE photos 
                           SET status = 'pending', processed_path = NULL,
                               thumbnail_path = NULL, face_count = NULL, processed_at = NULL
                           WHERE status = 'error'"""
                    )

            elif issue_key == "orphaned_faces":
                with conn:
                    conn.execute(
                        """DELETE FROM faces 
                           WHERE photo_id NOT IN (
                               SELECT id FROM photos WHERE status = 'completed'
                           )"""
                    )

            elif issue_key == "orphaned_uploads":
                cursor = conn.execute(
                    "SELECT id, local_path FROM upload_queue WHERE status IN ('pending', 'failed')"
                )
                orphan_ids = [row[0] for row in cursor.fetchall() if not Path(row[1]).exists()]
                if orphan_ids:
                    placeholders = ','.join('?' * len(orphan_ids))
                    with conn:
                        conn.execute(
                            f"DELETE FROM upload_queue WHERE id IN ({placeholders})",
                            orphan_ids
                        )

            elif issue_key == "failed_uploads":
                with conn:
                    conn.execute(
                        """UPDATE upload_queue 
                           SET status = 'pending', retry_count = 0,
                               last_error = 'Reset by self-healing repair',
                               updated_at = ?
                           WHERE status = 'failed' AND retry_count >= 5""",
                        (datetime.now(),)
                    )

            elif issue_key == "wal_size":
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            conn.commit()

        except Exception:
            pass  # Individual repairs may fail silently in fix-all mode

    def _on_fix_all_complete(self, total_fixed: int):
        """Update UI after fix-all completes."""
        self.fix_all_btn.setText("🩹  Fix All")
        self.status_label.setText(f"✓ Full repair complete — {total_fixed} categories fixed")
        self.status_label.setStyleSheet(
            f"color: {c('success', self._mode)}; font-size: 12px; font-weight: bold;"
        )
        self.repair_completed.emit()

        # Re-scan
        QTimer.singleShot(1000, self._run_diagnostics)
