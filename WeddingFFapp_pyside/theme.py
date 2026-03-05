"""
Color Theme & QSS Stylesheets for the Wedding Face Forward Dashboard.
Ported from the CustomTkinter COLORS dict — light/dark mode support.
"""


# =============================================================================
# Color Palette — (light, dark) tuples
# =============================================================================
COLORS = {
    "bg":              ("#f5f5f7", "#1c1c1e"),
    "bg_card":         ("#ffffff", "#2c2c2e"),
    "border":          ("#e8e8ed", "#38383a"),
    "accent":          ("#007aff", "#0a84ff"),
    "success":         ("#34c759", "#30d158"),
    "warning":         ("#ff9500", "#ff9f0a"),
    "error":           ("#ff3b30", "#ff453a"),
    "text_primary":    ("#1d1d1f", "#f5f5f7"),
    "text_secondary":  ("#86868b", "#98989d"),
    "stat_bg":         ("#f0f0f5", "#2c2c2e"),
    "stat_highlight":  ("#e8eaf6", "#33335a"),
    "thick_border":    ("#e0e0e5", "#444446"),
    "log_outer":       ("#1e1e2e", "#1a1a2e"),
    "log_inner":       ("#141422", "#111120"),
}


def c(key, mode="light"):
    """Get a color value by key and mode. mode='light' or 'dark'."""
    idx = 0 if mode == "light" else 1
    return COLORS[key][idx]


# =============================================================================
# Light Mode QSS
# =============================================================================
LIGHT_QSS = """
/* ── Global ── */
QMainWindow {
    background-color: #f5f5f7;
}

QWidget {
    font-family: 'Segoe UI', sans-serif;
}

/* ── Stat Cards ── */
QFrame#stat_card {
    background-color: #f0f0f5;
    border: 1px solid #e8e8ed;
    border-radius: 14px;
}

QFrame#stat_card_highlight {
    background-color: #e8eaf6;
    border: 1px solid #e8e8ed;
    border-radius: 14px;
}

QLabel#stat_value {
    color: #1d1d1f;
    font-size: 26px;
    font-weight: bold;
}

QLabel#stat_title {
    color: #1d1d1f;
    font-size: 10px;
}

/* ── Status Cards ── */
QFrame#status_card {
    background-color: #ffffff;
    border: 1px solid #e8e8ed;
    border-radius: 14px;
}

QLabel#card_title {
    color: #1d1d1f;
    font-size: 12px;
    font-weight: bold;
}

QLabel#card_value {
    color: #86868b;
    font-size: 22px;
    font-weight: bold;
}

QLabel#card_detail {
    color: #86868b;
    font-size: 10px;
}

/* ── System Health Indicator ── */
QFrame#health_indicator {
    background-color: #ffffff;
    border: 1px solid #e8e8ed;
    border-radius: 20px;
}

/* ── Buttons ── */
QPushButton#start_btn {
    background-color: #34c759;
    color: white;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 20px;
    border: none;
}
QPushButton#start_btn:hover {
    background-color: #2aa64a;
}
QPushButton#start_btn:disabled {
    background-color: #86868b;
}

QPushButton#stop_btn {
    background-color: #ff3b30;
    color: white;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 20px;
    border: none;
}
QPushButton#stop_btn:hover {
    background-color: #cc2222;
}

QPushButton#theme_btn {
    background-color: #ffffff;
    color: #cc8800;
    border: 1px solid #e8e8ed;
    border-radius: 18px;
    font-size: 16px;
    padding: 4px;
}
QPushButton#theme_btn:hover {
    background-color: #ededf0;
}

QPushButton#folder_btn {
    background-color: #ebebf0;
    color: #1d1d1f;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: none;
}
QPushButton#folder_btn:hover {
    background-color: #dddde2;
}

QPushButton#merge_btn {
    background-color: #e8eaf6;
    color: #007aff;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: 1px solid #007aff;
}
QPushButton#merge_btn:hover {
    background-color: #007aff;
    color: white;
}

QPushButton#health_btn {
    background-color: #ecfdf5;
    color: #059669;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: 1px solid #059669;
}
QPushButton#health_btn:hover {
    background-color: #059669;
    color: white;
}

QPushButton#settings_btn {
    background-color: #f3e8ff;
    color: #7c3aed;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: 1px solid #7c3aed;
}
QPushButton#settings_btn:hover {
    background-color: #7c3aed;
    color: white;
}

QPushButton#repair_btn {
    background-color: #fee2e2;
    color: #dc2626;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: 1px solid #dc2626;
}
QPushButton#repair_btn:hover {
    background-color: #dc2626;
    color: white;
}

/* ── Activity Log ── */
QFrame#log_outer {
    background-color: #1e1e2e;
    border-radius: 14px;
    border: none;
}

QLabel#log_title {
    color: #a0a0b0;
    font-size: 12px;
    font-weight: bold;
}

QTextEdit#log_terminal {
    background-color: #141422;
    color: #c0c0d0;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    border-radius: 10px;
    border: none;
    padding: 8px;
}

/* ── Sidebar ── */
QFrame#sidebar {
    background-color: #ffffff;
    border: 1px solid #e8e8ed;
    border-radius: 14px;
}

QLabel#sidebar_title {
    color: #86868b;
    font-size: 13px;
    font-weight: bold;
}

/* ── People List ── */
QScrollArea#people_scroll {
    background: transparent;
    border: none;
}

QFrame#person_row {
    background-color: #f5f5f7;
    border: 1px solid #e8e8ed;
    border-radius: 22px;
}

QFrame#person_row:hover {
    background-color: #e8eaf6;
    border-color: #007aff;
}

QLabel#person_name {
    color: #1d1d1f;
    font-size: 13px;
    font-weight: bold;
}

QLabel#person_photos {
    color: #86868b;
    font-size: 11px;
}

QLabel#person_badge_enrolled {
    color: #34c759;
    font-size: 10px;
    font-weight: bold;
}

QLabel#person_badge_detected {
    color: #007aff;
    font-size: 10px;
    font-weight: bold;
}

/* ── VIP (Pinned) Person Row ── */
QFrame#person_row_vip {
    background-color: #fff8e8;
    border: 1.5px solid #c8950a;
    border-radius: 22px;
}

QFrame#person_row_vip:hover {
    background-color: #fff0cc;
    border-color: #a07000;
}

/* ── Header ── */
QLabel#app_title {
    color: #1d1d1f;
    font-size: 26px;
    font-weight: bold;
}

/* ── Stuck Photos ── */
QFrame#stuck_card {
    background-color: #ffffff;
    border: 1px solid #e8e8ed;
    border-radius: 14px;
}

QLabel#stuck_label {
    color: #86868b;
    font-size: 11px;
}

QLabel#stuck_value {
    color: #1d1d1f;
    font-size: 14px;
    font-weight: bold;
}

/* ── Processing / Cloud Widgets ── */
QFrame#processing_widget, QFrame#cloud_widget {
    background-color: #ffffff;
    border: 1px solid #e8e8ed;
    border-radius: 14px;
}

/* ── WhatsApp Tracker Widget ── */
QFrame#wa_tracker_widget {
    background-color: #ffffff;
    border: 1px solid #e8e8ed;
    border-radius: 14px;
}

/* ── Popup ── */
QFrame#popup_outer {
    background-color: #e8e8ed;
    border-radius: 16px;
}

QFrame#popup_inner {
    background-color: #ffffff;
    border-radius: 14px;
}

QPushButton#popup_btn_local {
    background-color: #ebebf0;
    color: #1d1d1f;
    border-radius: 14px;
    font-size: 11px;
    font-weight: bold;
    padding: 6px 12px;
    border: none;
}
QPushButton#popup_btn_local:hover {
    background-color: #dddde2;
}

QPushButton#popup_btn_cloud {
    background-color: #007aff;
    color: white;
    border-radius: 14px;
    font-size: 11px;
    font-weight: bold;
    padding: 6px 12px;
    border: none;
}
QPushButton#popup_btn_cloud:hover {
    background-color: #0066dd;
}

/* ── Status Indicator ── */
QLabel#status_dot {
    font-size: 12px;
}

QLabel#status_label {
    font-size: 13px;
}

/* ── Menu Bar ── */
QMenuBar {
    background-color: #f5f5f7;
    color: #1d1d1f;
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
    border-bottom: 1px solid #e0e0e5;
    padding: 2px 0px;
    spacing: 2px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 12px;
    border-radius: 6px;
    margin: 1px 2px;
}

QMenuBar::item:selected,
QMenuBar::item:pressed {
    background-color: #e0e0e8;
    color: #1d1d1f;
}

QMenu {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d0d0d8;
    border-radius: 8px;
    padding: 4px 0px;
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
}

QMenu::item {
    padding: 7px 24px 7px 16px;
    border-radius: 4px;
    margin: 1px 4px;
}

QMenu::item:selected {
    background-color: #007aff;
    color: white;
}

QMenu::separator {
    height: 1px;
    background: #e8e8ed;
    margin: 4px 8px;
}

QMenu::indicator {
    width: 14px;
    height: 14px;
    margin-left: 4px;
}
"""


# =============================================================================
# Dark Mode QSS
# =============================================================================
DARK_QSS = """
/* ── Global ── */
QMainWindow {
    background-color: #1c1c1e;
}

QWidget {
    font-family: 'Segoe UI', sans-serif;
}

/* ── Stat Cards ── */
QFrame#stat_card {
    background-color: #2c2c2e;
    border: 1px solid #38383a;
    border-radius: 14px;
}

QFrame#stat_card_highlight {
    background-color: #33335a;
    border: 1px solid #38383a;
    border-radius: 14px;
}

QLabel#stat_value {
    color: #f5f5f7;
    font-size: 26px;
    font-weight: bold;
}

QLabel#stat_title {
    color: #f5f5f7;
    font-size: 10px;
}

/* ── Status Cards ── */
QFrame#status_card {
    background-color: #2c2c2e;
    border: 1px solid #38383a;
    border-radius: 14px;
}

QLabel#card_title {
    color: #f5f5f7;
    font-size: 12px;
    font-weight: bold;
}

QLabel#card_value {
    color: #98989d;
    font-size: 22px;
    font-weight: bold;
}

QLabel#card_detail {
    color: #98989d;
    font-size: 10px;
}

/* ── System Health Indicator ── */
QFrame#health_indicator {
    background-color: #2c2c2e;
    border: 1px solid #38383a;
    border-radius: 20px;
}

/* ── Buttons ── */
QPushButton#start_btn {
    background-color: #30d158;
    color: white;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 20px;
    border: none;
}
QPushButton#start_btn:hover {
    background-color: #248a3d;
}
QPushButton#start_btn:disabled {
    background-color: #98989d;
}

QPushButton#stop_btn {
    background-color: #ff453a;
    color: white;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 20px;
    border: none;
}
QPushButton#stop_btn:hover {
    background-color: #d63a3a;
}

QPushButton#theme_btn {
    background-color: #2c2c2e;
    color: #ffcc00;
    border: 1px solid #38383a;
    border-radius: 18px;
    font-size: 16px;
    padding: 4px;
}
QPushButton#theme_btn:hover {
    background-color: #3a3a3c;
}

QPushButton#folder_btn {
    background-color: #3a3a3c;
    color: #f5f5f7;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: none;
}
QPushButton#folder_btn:hover {
    background-color: #48484a;
}

QPushButton#merge_btn {
    background-color: #33335a;
    color: #0a84ff;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: 1px solid #0a84ff;
}
QPushButton#merge_btn:hover {
    background-color: #0a84ff;
    color: white;
}

QPushButton#health_btn {
    background-color: #0d3d30;
    color: #34d399;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: 1px solid #34d399;
}
QPushButton#health_btn:hover {
    background-color: #34d399;
    color: #1c1c1e;
}

QPushButton#settings_btn {
    background-color: #2d1b4e;
    color: #a78bfa;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: 1px solid #a78bfa;
}
QPushButton#settings_btn:hover {
    background-color: #a78bfa;
    color: white;
}

QPushButton#repair_btn {
    background-color: #3d1b1b;
    color: #f87171;
    border-radius: 18px;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 16px;
    border: 1px solid #f87171;
}
QPushButton#repair_btn:hover {
    background-color: #f87171;
    color: #1c1c1e;
}

/* ── Activity Log ── */
QFrame#log_outer {
    background-color: #1a1a2e;
    border-radius: 14px;
    border: none;
}

QLabel#log_title {
    color: #a0a0b0;
    font-size: 12px;
    font-weight: bold;
}

QTextEdit#log_terminal {
    background-color: #111120;
    color: #b0b0c0;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    border-radius: 10px;
    border: none;
    padding: 8px;
}

/* ── Sidebar ── */
QFrame#sidebar {
    background-color: #2c2c2e;
    border: 1px solid #38383a;
    border-radius: 14px;
}

QLabel#sidebar_title {
    color: #98989d;
    font-size: 13px;
    font-weight: bold;
}

/* ── People List ── */
QScrollArea#people_scroll {
    background: transparent;
    border: none;
}

QFrame#person_row {
    background-color: #2c2c2e;
    border: 1px solid #38383a;
    border-radius: 22px;
}

QFrame#person_row:hover {
    background-color: #33335a;
    border-color: #0a84ff;
}

QLabel#person_name {
    color: #f5f5f7;
    font-size: 13px;
    font-weight: bold;
}

QLabel#person_photos {
    color: #98989d;
    font-size: 11px;
}

QLabel#person_badge_enrolled {
    color: #30d158;
    font-size: 10px;
    font-weight: bold;
}

QLabel#person_badge_detected {
    color: #0a84ff;
    font-size: 10px;
    font-weight: bold;
}

/* ── VIP (Pinned) Person Row ── */
QFrame#person_row_vip {
    background-color: #2d2700;
    border: 1.5px solid #c8950a;
    border-radius: 22px;
}

QFrame#person_row_vip:hover {
    background-color: #3d3200;
    border-color: #e0aa20;
}

/* ── Header ── */
QLabel#app_title {
    color: #f5f5f7;
    font-size: 26px;
    font-weight: bold;
}

/* ── Stuck Photos ── */
QFrame#stuck_card {
    background-color: #2c2c2e;
    border: 1px solid #38383a;
    border-radius: 14px;
}

QLabel#stuck_label {
    color: #98989d;
    font-size: 11px;
}

QLabel#stuck_value {
    color: #f5f5f7;
    font-size: 14px;
    font-weight: bold;
}

/* ── Processing / Cloud Widgets ── */
QFrame#processing_widget, QFrame#cloud_widget {
    background-color: #2c2c2e;
    border: 1px solid #38383a;
    border-radius: 14px;
}

/* ── WhatsApp Tracker Widget ── */
QFrame#wa_tracker_widget {
    background-color: #2c2c2e;
    border: 1px solid #38383a;
    border-radius: 14px;
}

/* ── Popup ── */
QFrame#popup_outer {
    background-color: #38383a;
    border-radius: 16px;
}

QFrame#popup_inner {
    background-color: #2c2c2e;
    border-radius: 14px;
}

QPushButton#popup_btn_local {
    background-color: #3a3a3c;
    color: #f5f5f7;
    border-radius: 14px;
    font-size: 11px;
    font-weight: bold;
    padding: 6px 12px;
    border: none;
}
QPushButton#popup_btn_local:hover {
    background-color: #48484a;
}

QPushButton#popup_btn_cloud {
    background-color: #0a84ff;
    color: white;
    border-radius: 14px;
    font-size: 11px;
    font-weight: bold;
    padding: 6px 12px;
    border: none;
}
QPushButton#popup_btn_cloud:hover {
    background-color: #0066dd;
}

/* ── Status Indicator ── */
QLabel#status_dot {
    font-size: 12px;
}

QLabel#status_label {
    font-size: 13px;
}

/* ── Menu Bar ── */
QMenuBar {
    background-color: #1c1c1e;
    color: #f5f5f7;
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
    border-bottom: 1px solid #38383a;
    padding: 2px 0px;
    spacing: 2px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 12px;
    border-radius: 6px;
    margin: 1px 2px;
}

QMenuBar::item:selected,
QMenuBar::item:pressed {
    background-color: #3a3a3c;
    color: #f5f5f7;
}

QMenu {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #48484a;
    border-radius: 8px;
    padding: 4px 0px;
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
}

QMenu::item {
    padding: 7px 24px 7px 16px;
    border-radius: 4px;
    margin: 1px 4px;
}

QMenu::item:selected {
    background-color: #0a84ff;
    color: white;
}

QMenu::separator {
    height: 1px;
    background: #38383a;
    margin: 4px 8px;
}

QMenu::indicator {
    width: 14px;
    height: 14px;
    margin-left: 4px;
}
"""
