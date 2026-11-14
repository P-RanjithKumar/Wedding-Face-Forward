from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import dist_utils
import logging
import sys
import os

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = dist_utils.DRIVE_SCOPES  # drive.file, see dist_utils

def setup_auth(force: bool = False):
    """Trigger Google Drive OAuth flow."""
    logger.info(f"Starting Google Drive authentication setup (force={force})...")
    creds = None
    user_data_dir = dist_utils.get_user_data_dir()
    token_path = dist_utils.get_token_path()   # secrets folder
    
    if token_path.exists() and not force:
        try:
            logger.info(f"Checking existing token at {token_path}")
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load existing token: {e}")
        
    if force or not creds or not creds.valid:
        if not force and creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired token...")
                creds.refresh(Request())
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}. Falling back to full reauth.")
                creds = None
        
        if force or not creds or not creds.valid:
            # Try user data dir, then bundled root
            creds_path = dist_utils.get_oauth_client_path()
            
            if creds_path is None:
                err_msg = f"credentials.json NOT FOUND! Checked user data and bundled root."
                logger.error(err_msg)
                print(f"ERROR: {err_msg}")
                return

            logger.info(f"Found credentials at {creds_path}. Opening browser flow...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                # This should open the browser automatically
                creds = flow.run_local_server(port=0, open_browser=True)
                logger.info("Browser flow completed successfully.")
            except Exception as e:
                logger.error(f"Failed to run browser flow: {e}")
                print(f"ERROR: {e}")
                return
            
        # Save the credentials for the next run
        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, 'w', encoding='utf-8') as token:
                token.write(creds.to_json())
            logger.info(f"Successfully saved new token.json to {token_path}")
            print(f"Successfully saved token.json to {token_path}")
        except Exception as e:
            logger.error(f"Failed to save token.json: {e}")
            print(f"ERROR saving token: {e}")
    else:
        logger.info("Token is already valid and force=False. Skipping browser flow.")

if __name__ == '__main__':
    # Default to force=True when run as a script for setup
    setup_auth(force=True)
