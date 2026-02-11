# Comprehensive Project Development Log & Issue Tracker
**Project**: Wedding Face Forward
**Document Version**: 2.0 (Comprehensive)
**Last Updated**: 2026-02-11

This document serves as a complete historical record of the development lifecycle, specifically focusing on the critical issues faced, errors encountered, and the specific technical resolutions applied.

---

## 1. 🛑 Startup & Environment Critical Failures

### 1.1 The "Port 8000" Blockade
*   **The Issue**: The application refused to start, providing the error `OSError: [Errno 98] Address already in use`.
*   **Symptoms**:
    *   Web server failed to bind to `localhost:8000`.
    *   Web browser would not auto-launch.
    *   "Zombie" Python processes from previous runs were holding the port.
*   **The Fix**:
    *   Developed a startup routine to identifying processes listening on Port 8000.
    *   Implemented a hard-kill logic to terminate those specific PIDs before the new server instance attempts to bind.

### 1.2 Tooling Crashes (Pyrefly)
*   **The Issue**: Persistent crashes of the Pyre language server (`pyreflycrash.txt`).
*   **Context**: `Thread panicked... assertion failed`.
*   **Resolution**: This was identified as an IDE tooling environment issue rather than runtime application code failure, but it caused development friction.

---

## 2. 🗄️ Database Concurrency & Pipeline Stalls

### 2.1 The "Database is Locked" Crisis
*   **The Issue**: `sqlite3.OperationalError: database is locked`.
*   **Context**: This was the single biggest stability blocker. The application uses multiple concurrent threads:
    1.  **Face Processing**: Writing new faces/clusters to DB.
    2.  **Cloud Upload**: Reading paths from DB.
    3.  **WhatsApp Sender**: Reading/Writing user status.
    4.  **Enrollment Web Request**: Writing new users.
*   **The Struggle**: SQLite default timeouts (5s) were insufficient for this high-concurrency load, causing threads to crash and the pipeline to halt.
*   **The Solutions**:
    *   **Timeout Tuning**: Increased connection timeout to `30.0` seconds: `sqlite3.connect(..., timeout=30)`.
    *   **Retry Logic**: Implemented a `db_retry` decorator that catches `OperationalError` and retries with exponential backoff.
    *   **Transaction Scope**: Refactored database access patterns to keep transaction windows (open cursor time) as short as possible.

---

## 3. 📱 WhatsApp Automation (The "Spam Risk" & Logic Wars)

### 3.1 The Infinite Loop / Ban Risk
*   **The Issue**: The initial sender script had no "give up" logic. If a number was invalid or network failed, it retried infinitely in a tight loop.
*   **Risk**: High probability of WhatsApp account bans due to "bot-like behavior".
*   **The Fix**:
    *   **Retry Limiting**: Introduced a strict `max_retries=3` limit.
    *   **Permanent Failure**: Created a logic state `permanently_failed` to blacklist numbers after 3 attempts.

### 3.2 Duplicate Messaging
*   **The Issue**: Users were receiving the same "Welcome" message multiple times if the server restarted.
*   **The Fix**:
    *   **State Persistence**: Implemented `message_state_db.json` (a flat-file database) to track exactly which phone numbers had already successfully received a message.
    *   **Check-First Logic**: The sender now queries this state file *before* attempting any action.

### 3.3 The "Access Denied" Drive Links
*   **The Issue**: Messages were delivering successfully, but guests complained they couldn't open the Google Drive links.
*   **The Cause**: The automation was sending links to folders that were still "Private" by default.
*   **The Fix**:
    *   **Permission Automation**: Updated `cloud.py` / sender logic to programmatically call the Google Drive API (`permissions.create`) and grant `role='reader', type='anyone'` *before* generating the shareable link.

### 3.4 Phone Number Validation
*   **The Issue**: Messages failed immediately because numbers were stored without Country Codes (e.g., `9876543210` instead of `+919876543210`).
*   **The Fix**:
    *   **Frontend**: Modified the Enrollment HTML form to enforce strict input patterns.
    *   **Backend**: Added logic to inspect the number format and reject/warn on invalid headers before adding to the queue.

---

## 4. ☁️ Cloud Upload Instability

### 4.1 SSL & Network Fragility
*   **The Issue**: `SSLError: [SSL: WRONG_VERSION_NUMBER]`.
*   **Context**: Long-running upload queues would fail intermittently due to ISP fluctuations or API hiccups.
*   **The Fix**:
    *   **RobustSession**: Replaced standard `requests.get` with a custom Session object using `HTTPAdapter`.
    *   **Retry Strategy**: Configured `urllib3` to retry on specific HTTP status codes (500, 502, 503) and connection errors.

### 4.2 The "Non-Dictionary" Crash
*   **The Issue**: `AttributeError: 'str' object has no attribute 'get'`.
*   **Context**: The FaceForward API occasionally returned a raw HTML string (error page) instead of JSON when the server was overloaded. Validating `response.json()` blindness caused the crash.
*   **The Fix**:
    *   **Defensive Coding**: Added `if isinstance(response, dict):` checks around all API response parsers.

### 4.3 Warnings & Cache
*   **The Issue**: `file_cache is only supported with oauth2client<4.0.0`.
*   **Context**: A warning from the Google Client Library cluttering the logs.
*   **Status**: Identified as a library deprecation warning; harmless but noted for future upgrades.

---

## 5. 🎨 UI/UX Polish & Project Structure

### 5.1 Documentation & Sidebar
*   **The Issue**: The documentation sidebar was clunky, with massive fonts and poor spacing.
*   **The Fix**:
    *   **CSS Refactor**: Manually tweaked font sizes (`1.1rem` -> `0.9rem`), margins, and container widths to create a professional "Docs" look.

### 5.2 Dark/Light Mode
*   **The Issue**: The app was blindingly white at night.
*   **The Fix**:
    *   **CSS Variables**: Implemented a generic toggler that swaps CSS root variables for background/text colors without complex JS frameworks.

### 5.3 Activity Log Readability
*   **The Issue**: Logs were a wall of text.
*   **The Fix**:
    *   **Scoped Coloring**: Applied CSS classes to specific log prefixes (e.g., `[UPLOAD]` is Blue, `[WA]` is Green, `ERROR` is Red) while keeping the message body neutral.

---

## 6. 📂 Repository & Setup
*   **The Issue**: Initial codebase had no version control hygiene.
*   **The Fixes**:
    *   **Git Init**: Created new repository structure.
    *   **.gitignore**: Added specific exclusions for `__pycache__`, `venv`, `*.log`, `token.json`, and `credentials.json` to prevent security leaks.
    *   **README**: Expanded from a stub to a full technical manual.
