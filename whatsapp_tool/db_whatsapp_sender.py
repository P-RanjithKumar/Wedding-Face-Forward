import asyncio
import json
import os
import sys
import sqlite3
import urllib.parse
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# --- Setup Paths ---
# Add backend to sys.path to import app modules
current_dir = Path(__file__).parent.resolve()
backend_path = current_dir.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.cloud import get_cloud, CloudManager

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, 'message_state_db.json')
USER_DATA_DIR = os.path.join(SCRIPT_DIR, 'whatsapp_user_data')
DEFAULT_MESSAGE_TEMPLATE = "Hello {name}! Here are your photos from the event: {link}\n\nEnjoy!"

# --- Helper Functions ---

def load_state():
    """Loads the state of sent messages."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def ensure_state_file():
    """Creates the state file if it doesn't exist."""
    if not os.path.exists(STATE_FILE):
        try:
            save_state({})
            print(f"Created new state file at: {STATE_FILE}")
            # Log for UI
            print(f"Activity: WA Sender Initialized. State file ready.", flush=True)
        except Exception as e:
            print(f"Error creating state file: {e}")

def save_state(state):
    """Saves the state of sent messages."""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4)

def fetch_enrolled_users(db_path):
    """Fetches enrolled users with phone numbers from the database."""
    print(f"Connecting to database at: {db_path}")
    if not db_path.exists():
        print("Error: Database file not found.")
        return []

    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Set busy timeout to wait for locks (in milliseconds)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.execute("""
            SELECT
                e.id as enrollment_id,
                e.user_name,
                e.phone,
                p.name as folder_name
            FROM enrollments e
            JOIN persons p ON e.person_id = p.id
            WHERE e.phone IS NOT NULL AND e.phone != ''
        """)
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    except Exception as e:
        print(f"Database error: {e}")
        return []

def setup_drive_folder(cloud: CloudManager, folder_name: str):
    """
    Finds the person's folder, sets public permission, and returns the link.
    """
    if not cloud.is_enabled:
        print("Cloud is disabled.")
        return None

    # We assume structure is People/{folder_name}
    # First find 'People' folder
    people_folder_id = cloud.ensure_folder_path(["People"])
    if not people_folder_id:
        print("Could not find 'People' folder in Drive.")
        return None

    # Find specific person folder
    person_folder_id = cloud._find_folder(folder_name, parent_id=people_folder_id)
    if not person_folder_id:
        print(f"Folder not found for: {folder_name}")
        return None

    # Set Permission
    print(f"Setting public permission for folder: {folder_name} ({person_folder_id})")
    success = cloud.share_folder_publicly(person_folder_id)
    if not success:
        print(f"Failed to share folder: {folder_name}")
        return None

    # Get Link
    return cloud.get_folder_link(person_folder_id)

async def check_login(page):
    """Checks if the user is logged in by looking for the chat list pane."""
    print("Waiting for WhatsApp to load...")
    try:
        try:
            await page.wait_for_selector('div[id="side"]', timeout=60000)
            print("WhatsApp Login Detected!")
            print("Activity: WhatsApp Login successful.", flush=True)
            return True
        except:
             await page.wait_for_selector('div[role="button"][title="New chat"]', timeout=30000)
             print("WhatsApp Login Detected (via New Chat button)!")
             print("Activity: WhatsApp Login successful.", flush=True)
             return True

    except Exception as e:
        print(f"Timeout waiting for WhatsApp login. Please scan QR code if needed: {e}")
        # Give a bit more time if it's the first run
        await asyncio.sleep(5)
        return False

async def send_whatsapp_message(page, phone, message, enrollment_id, state):
    """Sends a WhatsApp message to a specific phone number."""
    
    user_key = str(enrollment_id) # Use enrollment ID as unique key
    
    # Check if already sent
    # Check if already processed (sent or invalid)
    if user_key in state:
        status = state[user_key].get('status')
        if status == 'sent':
            # print(f"[{phone}] Already sent to enrollment {enrollment_id}. Skipping.")
            return
        elif status == 'invalid':
            # print(f"[{phone}] Marked as invalid number for enrollment {enrollment_id}. Skipping.")
            return

    print(f"[{phone}] Navigating...")
    
    encoded_message = urllib.parse.quote(message)
    url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}"
    
    try:
        await page.goto(url)
        
        # Validation checks (same as original script)
        is_valid = False
        # Try multiple selectors for the chat input box
        input_box = None
        selectors = [
            'div[contenteditable="true"][data-tab="10"]',
            'div[aria-placeholder="Type a message"]',
            '#main footer div[contenteditable="true"]',
            'div[title="Type a message"]'
        ]

        for _ in range(30):
            for selector in selectors:
                try:
                    if await page.locator(selector).count() > 0 and await page.locator(selector).is_visible():
                        input_box = page.locator(selector)
                        break
                except:
                    pass
            
            if input_box:
                break
            
            # Check for invalid number popup - Try multiple text variations
            invalid_texts = [
                "Phone number shared via url is invalid",
                "The phone number shared via url is invalid",
                "isn't on WhatsApp",
                "is not on WhatsApp"
            ]
            
            found_invalid = False
            for text in invalid_texts:
                try:
                    # Look for any element containing this text
                    element = page.locator(f"text={text}")
                    if await element.count() > 0 and await element.is_visible():
                        found_invalid = True
                        break
                except:
                    pass
            
            if found_invalid:
                print(f"[{phone}] Error: Invalid number detected.")
                print(f"Activity: Invalid number for {phone}. Skipping.", flush=True)
                state[user_key] = {'status': 'invalid', 'phone': phone, 'timestamp': datetime.now().isoformat()}
                save_state(state)
                # Close the popup to avoid blocking
                try:
                    await page.click('div[role="button"]:has-text("OK")')
                except:
                    pass
                return

            await asyncio.sleep(1)
        
        if not input_box:
            print(f"[{phone}] Error: Timeout waiting for chat input. Is WhatsApp Web loaded?")
            return

        print(f"[{phone}] Ready to send. Pressing Enter...")
        
        await input_box.click()
        await asyncio.sleep(1)
        await page.keyboard.press('Enter')
        await asyncio.sleep(3) 

        print(f"[{phone}] Sent!")
        print(f"Activity: WhatsApp message sent to {phone}", flush=True)
        state[user_key] = {'status': 'sent', 'phone': phone, 'timestamp': datetime.now().isoformat()}
        save_state(state)

    except Exception as e:
        print(f"[{phone}] Navigation/Send Error: {e}")
        print(f"Activity: Failed to send to {phone}. Error: {str(e)[:50]}...", flush=True)

async def main():
    print("-" * 50)
    print("WHATSAPP AUTOMATION V2 (DATABASE + GOOGLE DRIVE)")
    print("-" * 50)

    # 1. Initialize Config & Cloud
    # Parse CLI args
    import argparse
    parser = argparse.ArgumentParser(description="WhatsApp Sender with DB & Drive Integration")
    parser.add_argument("--dry-run", action="store_true", help="Run without sending messages or changing permissions")
    args = parser.parse_args()

    config = get_config()
    
    # Override config dry_run if CLI flag is set
    if args.dry_run:
        config.dry_run = True
        
    cloud = get_cloud()
    
    if not cloud.is_enabled:
        print("WARNING: Cloud upload is NOT enabled. Links cannot be generated.")
        # Proceeding strictly for testing might be desired, but essential functionality is missing.
        # reply = input("Continue without cloud? (y/n): ")
        # if reply.lower() != 'y': return
    
    if config.dry_run:
        print("DRY RUN MODE ENABLED. No messages will be sent, no permissions changed.")

    # 2. Fetch Users
    users = fetch_enrolled_users(config.db_path)
    print(f"Found {len(users)} enrolled users with phone numbers.")
    # if not users:
    #    return  <-- REMOVED: Do not exit, continue to loop

    state = load_state()
    ensure_state_file()


    # 3. Launch Browser
    async with async_playwright() as p:
        user_data_path = os.path.abspath(USER_DATA_DIR)
        print(f"Launching browser persistence: {user_data_path}")
        
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_path,
                headless=False,
                accept_downloads=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                print("Browsers not found. Installing...")
                import subprocess
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_path,
                    headless=False,
                    accept_downloads=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
            else:
                raise e
        
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto("https://web.whatsapp.com")
        
        if not await check_login(page):
            await browser.close()
            return

        # Continuous Loop
        print("Starting continuous monitoring for new enrollments...")
        
        while True:
            try:
                # Reload users to pick up new enrollments
                users = fetch_enrolled_users(config.db_path)
                state = load_state() # Reload state to avoid race conditions/staleness
                
                # 4. Process Users
                new_messages_sent = 0
                for i, user in enumerate(users):
                    name = user['user_name']
                    phone = user['phone']
                    folder_name = user['folder_name']
                    enrollment_id = user['enrollment_id']
                    
                    # Helper to clean phone
                    clean_phone = "".join(filter(str.isdigit, phone))
                    
                    # Check state first to skip redundant checks
                    user_key = str(enrollment_id)
                    if user_key in state:
                        status = state[user_key].get('status')
                        if status == 'sent' or status == 'invalid':
                             continue

                    print(f"\nFound new enrollment: {name} ({clean_phone})")

                    # Drive Operations
                    drive_link = None
                    if cloud.is_enabled:
                        print(f"-> Resolving Drive folder for '{folder_name}'...")
                        drive_link = setup_drive_folder(cloud, folder_name)
                    
                    if not drive_link:
                        if config.dry_run:
                             drive_link = "https://drive.google.com/drive/folders/DRY_RUN_LINK"
                        else:
                            print(f"-> WARNING: Could not generate Drive link for {name}. Skipping message.")
                            continue
                        
                    print(f"-> Link: {drive_link}")

                    # Construct Message
                    message = DEFAULT_MESSAGE_TEMPLATE.format(name=name, link=drive_link)
                    
                    if config.dry_run:
                        print(f"[DRY RUN] Would send to {clean_phone}:")
                        print(f"--- {message} ---")
                        # Mark as sent in dry run so we don't spam logs
                        state[user_key] = {'status': 'sent', 'phone': phone, 'timestamp': datetime.now().isoformat(), 'dry_run': True}
                        save_state(state)
                        continue

                    # Send
                    await send_whatsapp_message(page, clean_phone, message, enrollment_id, state)
                    new_messages_sent += 1
                    
                    # Delay between messages in a batch
                    await asyncio.sleep(5) 

                if new_messages_sent == 0:
                    # No new messages, wait a bit before next DB check
                    # print(".", end="", flush=True)
                    pass
                
                # Wait before next database poll
                await asyncio.sleep(10)

            except KeyboardInterrupt:
                print("\nStopping WhatsApp Sender...")
                break
            except Exception as e:
                print(f"\nError in monitoring loop: {e}")
                await asyncio.sleep(10) # Wait a bit before retrying on error

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
