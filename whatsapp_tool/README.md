# WhatsApp Automation Tool

This tool automatically sends WhatsApp messages with a Google Drive link to a list of phone numbers using your personal WhatsApp account via Playwright.

## 🚀 Features
- **Personal Account**: Uses your existing WhatsApp via `web.whatsapp.com`.
- **Safe**: Scans QR code once, saves session. Adds human-like delays.
- **Smart**: Skips duplicates (tracks state in `message_state.json`) and handles invalid numbers.
- **No Contact Saving**: Sends directly via URL.

## 📦 Installation

1.  **Install Python** (if not already installed).
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Install Playwright Browsers**:
    ```bash
    playwright install chromium
    ```

## ⚙️ Configuration

1.  **Edit `contacts.csv`**:
    - Add numbers in the `phone` column.
    - Format: International format preferred (e.g., `+1234567890`).

2.  **Edit `whatsapp_sender.py`** (Optional):
    - Change `DEFAULT_DRIVE_LINK` to your Google Drive folder link.
    - Change `DEFAULT_MESSAGE_TEMPLATE` to customize the message.

## ▶️ Usage

1.  **Run the script**:
    ```bash
    python whatsapp_sender.py
    ```

2.  **First Run**:
    - A browser window will open.
    - **Scan the QR code** with your phone (WhatsApp > Linked Devices > Link a Device).
    - The script will wait until you are logged in.

3.  **Subsequent Runs**:
    - The script will reuse the session (no QR scan needed).
    - It will pick up where it left off, skipping already sent numbers.

## ⚠️ Important Notes
- **Do not minimize** the browser window fully (it might pause execution). Keep it open or in the background.
- **Rate Limit**: The script adds a 5-10 second delay between messages to be safe. Do not reduce this too much or you risk a ban.
- **Invalid Numbers**: Are logged in `message_state.json` and skipped in future runs.

## 📁 Files
- `whatsapp_sender.py`: Main script.
- `contacts.csv`: Input list.
- `message_state.json`: Tracks sent/failed numbers (auto-created).
- `whatsapp_user_data/`: Stores browser session (auto-created).
