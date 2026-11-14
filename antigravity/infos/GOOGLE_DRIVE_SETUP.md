# Google Drive sign-in: how it works and what the owner must set up

Written 2026-11-14, after step 2 of `todo/future_improvements.md`. For the AURA owner and for future Claude sessions.

## Short version

- **Users never touch Google Cloud.** After installing AURA they click **Auth > Connect Google Drive**, choose their Google account in the browser and click **Allow**. Done. Photos go to *their own* Drive.
- **The owner sets up one Google Cloud project, once.** Its sign-in ID (`credentials.json`) ships inside the installer, the same way every desktop app that offers "Sign in with Google" ships one.
- Before giving AURA to people outside your own test list, the owner must **publish the app** in Google Cloud Console (and, depending on the Drive permission chosen, get it verified). Until then, other users either cannot sign in or get signed out every 7 days.

## Who has which file

| File | What it is | Who owns it | Shipped in installer? |
| :-- | :-- | :-- | :-- |
| `credentials.json` | AURA's sign-in ID ("Desktop app" OAuth client). Only opens Google's sign-in page; gives no access to anyone's Drive. Google treats it as non-secret for desktop apps. | Owner's Google Cloud project | **Yes** |
| `token.json` | One person's sign-in to their own Drive. Created when they click "Connect Google Drive". | Each user (stored in `%LOCALAPPDATA%\AURA\`) | **No, never** |
| `service_account.json` | A robot account with a private key, owned by the owner. Old setup; not needed for users. | Owner only | **No, never** |
| `.env` | Settings. Installer ships a clean `.env.template` instead. | Each user | Template only |

The build (`aura.spec`) stops with an error if `token.json`, `service_account.json`, `.env` or `MY_CREDENTIALS_BACKUP.txt` would be bundled.

**On the developer PC** (since 2026-11-14) these private files are kept outside the project in `%USERPROFILE%\AURA-secrets` (`.env`, `credentials.json`, `token.json`, `service_account.json`, `MY_CREDENTIALS_BACKUP.txt`), so git or a zip of the project can't pick them up. `dist_utils.get_secrets_dir()` finds them (override with `AURA_SECRETS_DIR`); the build takes `credentials.json` from there. The installed app keeps using `%LOCALAPPDATA%\AURA`.

## What the user sees

1. Install AURA, open it.
2. Auth menu > **Connect Google Drive**. The browser opens Google's sign-in page.
3. Pick an account, click **Allow**. The browser says the sign-in is complete; return to AURA.
4. If processing was already running, stop and start it once. Uploads go to an **AURA** folder in their Drive (created automatically).

What can go wrong for them, depending on the owner's setup (next section):
- App in **Testing** and they are not a listed test user: Google shows "Access blocked". They cannot sign in.
- App in **Testing** and they are listed: works, but they are signed out after **7 days**.
- App **published but not verified**: Google shows "Google hasn't verified this app". They can continue via *Advanced > Go to AURA (unsafe)*. Scary for non-technical users, and limited to 100 users in total.
- App **published and verified**: normal "AURA wants to access your Google Drive" screen. This is the goal.

## Owner: one-time setup in Google Cloud Console

Do this in the same Google Cloud project that `credentials.json` came from (its `project_id` field).

1. **APIs & Services > Enabled APIs**: make sure **Google Drive API** is on.
2. **OAuth consent screen** (called *Google Auth Platform > Branding / Audience* in the newer console):
   - App name **AURA**, support email, logo.
   - A **home page** and a **privacy policy** page on a domain you own (a simple one-page site is enough). Google requires these for verification.
3. **Data access / Scopes**: add `https://www.googleapis.com/auth/drive.file` (the only Drive scope AURA uses).
4. **Audience**: change publishing status from **Testing** to **In production**.
5. If Google asks for verification, submit it. Expect a few days to a few weeks.
6. **Credentials**: the OAuth client must be type **Desktop app**. Download it as `credentials.json` into `antigravity/` (the build checks the type).

Your own sign-in from March 2026 is already dead (`invalid_grant`, probably the 7-day Testing limit or a revoked token). Reconnect from the Auth menu after step 4.

## Drive permission: `drive.file` (decided 2026-11-14)

AURA asks for **`drive.file`**: access only to files and folders AURA itself created (per Google Cloud project, i.e. per `credentials.json`). It used to ask for full Drive access (`drive`), which Google classes as *restricted* and only approves after a paid yearly third-party security assessment. `drive.file` needs only the normal app review (name, logo, home page, privacy policy).

What this means:
- New sign-ins show "AURA wants to see, edit, create and delete only the specific Google Drive files you use with this app".
- Sign-ins that already granted full access keep working (full access includes `drive.file`); nobody has to reconnect.
- Folders AURA already created with this `credentials.json` stay visible. Folders made **by hand** in Drive, by other tools, or by the old service account are invisible to AURA. So leave `DRIVE_ROOT_FOLDER_ID` empty (AURA then uses its own "AURA" folder), or only set it to a folder AURA created.
- Sharing photos by link still works (AURA created those files).
- Code: `dist_utils.DRIVE_SCOPES`, used by `backend/app/cloud.py`, `backend/setup_auth.py` and `aura_app/widgets/auth_dialog.py`.

**Owner action in Google Cloud Console:** under *Data access / Scopes*, list `.../auth/drive.file` (remove `.../auth/drive` if it is listed), then publish and submit for verification as described above.

(Scope categories and review rules are from Google's published OAuth policies as of 2026; check the console when doing it, since Google changes them.)

## Troubleshooting

| Symptom | Cause | Fix |
| :-- | :-- | :-- |
| Log: `invalid_grant` | Sign-in expired or revoked (Testing mode 7-day limit, password change, unused for 6 months, or access removed at myaccount.google.com) | Auth > Connect Google Drive |
| Log: "Google Drive is not connected yet" | User has not signed in | Auth > Connect Google Drive |
| "Access blocked" in browser | App still in Testing and user not a test user | Publish the app (owner) |
| "Google hasn't verified this app" | Published but not verified | Finish verification (owner) |
| Sign-in works but nothing uploads | Processing was running before sign-in | Stop and start processing once |

## Where this lives in the code

- `dist_utils.py`: `get_token_path()`, `get_oauth_client_path()`, `bootstrap_user_data()`
- `backend/app/cloud.py`: `CloudManager.initialize()`, `_find_or_create_default_root()`, `get_auth_status()`
- `aura_app/widgets/auth_dialog.py`: the Connect Google Drive window
- `backend/setup_auth.py`: the same sign-in from the command line (developer use)
- `aura.spec`: what goes in the installer, plus the secret-leak check
- `.env.template`: default settings for new installs (`DRIVE_USE_APP_FOLDER=true`)
