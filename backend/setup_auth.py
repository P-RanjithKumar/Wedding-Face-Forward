import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']

def setup_auth():
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_path = Path("token.json")
    
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_path = Path("credentials.json")
            if not creds_path.exists():
                print("ERROR: credentials.json not found!")
                print("1. Go to Google Cloud Console > APIs & Services > Credentials")
                print("2. Create Credentials > OAuth client ID > Desktop app")
                print("3. Download JSON and save as 'credentials.json' in this folder")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            print(f"Successfully saved token.json to {token_path.absolute()}")

if __name__ == '__main__':
    setup_auth()
