# AURA: Future Improvements Plan

Living document for the owner and for Claude. Created 2026-11-14 from a first-pass review of the `antigravity` folder.
Not everything here was verified by running the code. Items marked (verify) need a check first.

## Project history (from the repo docs, so nobody guesses this again)

1. v1: customtkinter app (`infos/project_structure.md`).
2. v2.0.0: PySide6 + PyInstaller + Inno Setup. The README and the old "okayy seee" note still describe this stage.
3. Electron + Next.js was proposed (`todo/electron_nextjs_migration_plan.md`) and superseded.
4. v3.0.0 (current target): Next.js + Tauri 2 with the Python backend as a sidecar. See `todo/nextjs_migration_plan.md` ("Tauri confirmed", guest portal stays separate) and `infos/WINDOWS_DISTRIBUTION_PLAN.md` (`aura_app/`, `run_pyside.py` and `aura.iss` marked for deletion after migration).
   The migration is in progress: `aura_web/`, `backend_entry.py` and a built sidecar exist, but the plan checklists were never ticked.

Stale docs to update: `README.md` (still PySide-era) and `infos/project_structure.md` (customtkinter-era).

> **Update 2026-11-14:** at the owner's request the unfinished Tauri + Next.js work was moved to `_archive_tauri_v3/` (`aura_web/`, `sidecar/`, `backend_entry.py`, `nextjs_migration_plan.md`, `WINDOWS_DISTRIBUTION_PLAN.md`). The active app is the PySide6 v2.0.0. Sections below that mention Tauri, the sidecar or Next.js describe the archived rewrite and apply only if it is resumed. Backend items (P0 and P1) still apply.

## START HERE: current status and handoff (2026-11-14)

**What is left (updated 2026-11-14, end of day; details further down)**

*Owner (only you can do these):*
1. Test locally with `HOW_TO_TEST_LOCALLY.md` (installer, offline, face grouping, selfie on laptop and phone). Note how often people are split or mixed up.
2. Re-sign in to Google Drive (your March sign-in is dead), and in Google Cloud Console switch the scope to `drive.file` and publish the app (`infos/GOOGLE_DRIVE_SETUP.md`).
3. Clean-PC test (step 5 checklist), ideally also on a PC with an NVIDIA card. Then merge branch `aura-v2-fixes` into `main`.
4. Delete when no longer needed: `Output\WeddingFaceForward_Setup_1.0.x.exe` (contain old secrets) and `%LOCALAPPDATA%\AURA_old_2026-03` (March test data incl. old sign-in/key; renamed out of the way on 2026-11-14 so the new install starts fresh).
5. Optional: buy a code-signing certificate to remove the "Windows protected your PC" warning.

*Verified 2026-11-14 night:* the built app works fully offline. `dev_checks/offline_batch.py` (no Drive, fresh install): 40 photos in 33 s incl. the speed test, 240 faces -> exactly the right 6 people, upload queue empty. Identical files are skipped as duplicates (by design). Fixed since that build (in the next installer): the periodic folder scanner did not count photos in the progress counter (log showed "17/16"); display only.

*Owner feedback 2026-11-14:* local test of the installed app: photo recognition is "very fast compared to previous version". (Grouping accuracy on real photos: not reported yet.)
*Owner feedback 2026-11-14:* guest QR link "didn't work" on a Samsung (Android) phone. Diagnosed: network, firewall (Windows Firewall; the McAfee firewall entry is a stale registration, no McAfee installed) and server were fine (phone reached `/api/health`); the QR had been scanned during setup, before START, when the guest server does not run. Works after START. Fix: the setup guide's guest step now shows a live "Guest page is ON / OFF, press START" line (checked every 2 s); test guide updated. Idea for later: start the guest page together with the app instead of with processing.

*Next for Claude, best done with your real event photos (results from item 1):*
- Face quality filters (skip tiny/blurry background faces that create junk "people"); stricter selfie match threshold; reject selfies with several faces; show the top 2-3 candidates; suggest merges for near-duplicate people.
- Merging two people should also merge their Google Drive folders.

*Later / product:* guest page from anywhere (tunnel, HTTPS), WhatsApp Business API, several events with separate folders, ZIP export of a gallery, consent text + "delete my data", code cleanup (`checker_scripts/`, bare `except:`), CI that runs the tests and builds the installer.

**State of the project**
- Active app: PySide6 v2.0.0. Run with `python run_pyside.py` from `antigravity/`. It was launched this session and the owner confirmed it works (intro video plays, dashboard opens). It uses the real `.env` and `EventRoot` (1.1 GB of photos).
- The PySide6 app is also what GitHub HEAD contains (`0696daf`, 19 commits). The Tauri + Next.js rewrite was never pushed and is archived in `_archive_tauri_v3/` (moved, not deleted; the owner may delete it).
- Goal: a real Windows app for non-technical users (install in a few clicks, no commands) plus a separate guest web page to register and upload a selfie.

**Warnings**
- **Git (updated 2026-11-14):** the work is committed on branch **`aura-v2-fixes`** (pushed to GitHub), which records the move of the code into `antigravity/` plus all fixes. `main` is unchanged (still the old layout at the repo root). Merge `aura-v2-fixes` into `main` once the clean-PC test passes. Secrets, photos, databases, logs, builds and the WhatsApp profile are excluded by `antigravity/.gitignore`; the commit was checked for secret-looking content before pushing. The untracked `WORKFLOW_STATE_it_is_for_another_app_i_made_in_web.md` at the repo root was deliberately left out.
- ~~`aura.spec` was the v3 sidecar version.~~ Fixed 2026-11-14: `aura.spec` is the v2 version restored from git `0696daf` (builds `dist\AURA\` from `run_pyside.py`, matching `aura.iss`). The v3 spec is kept at `_archive_tauri_v3/aura_sidecar_v3.spec`. All paths it bundles exist and it parses; a full PyInstaller build has not been run yet.
- ~~Broken launchers.~~ Fixed 2026-11-14: `start_aura.py`, `start_aura.bat`, `launch_aura.ps1`, `launch_aura.bat` (all v3: `backend_entry.py` + Next.js on port 3000, and they force-killed every `node` process) moved to `_archive_tauri_v3/launchers/`. Use `python run_pyside.py`.
- `dist_utils.py` vs git: checked 2026-11-14. Differences are only extra logging, comments, and an unused `APP_VERSION = "3.0.0"`. Safe to build with. (`frontend/server.py` also labels its API docs `3.0.0`; cosmetic.)
- ~~The spec bundled the owner's `.env`, `token.json`, `service_account.json`.~~ Fixed 2026-11-14 (step 2, details below). The installer now ships only `.env.template` and `credentials.json` (the sign-in client, which Google treats as non-secret for desktop apps).
- **Owner's Google sign-in is dead (found 2026-11-14):** `token.json` (dated 2026-03-15) is rejected by Google with `invalid_grant`, so Drive upload on the owner's machine does not work right now. This is older than step 2. Fix: open the app > Auth > "Connect Google Drive" and sign in again. Also, `CloudManager.is_enabled` still reports True with a dead token; uploads then fail one by one. Make it report "not connected" instead (small follow-up).
- **Google Cloud Console (owner action, not code):** if the OAuth consent screen for the `credentials.json` project is still in "Testing", only listed test users can sign in and their sign-in expires after 7 days (a likely cause of the `invalid_grant` above). Before giving the app to other people, publish the consent screen. The app asks for the full `drive` scope, which Google classes as restricted: users see an "unverified app" warning and there is a 100-user cap until Google verifies the app. Option: switch to the `drive.file` scope (only files AURA creates), which avoids verification. It needs a re-sign-in and cannot see Drive folders made before the switch, so decide before the first real release.
- ~~`frontend/admin_router.py` loaded by `server.py`.~~ Decided 2026-11-14 (step 3): moved to `_archive_tauri_v3/frontend_admin_router.py`; `server.py` no longer loads any admin router. The PySide6 app never used it (it reads the database directly).
- ~~Guests could not take a selfie on their phones~~ (found and fixed 2026-11-14, step 3b). Phones only allow the live camera on HTTPS or `localhost`; guests open `http://<laptop-ip>:8000`. The page now offers "Take a selfie" (file input with `capture="user"`, which opens the phone's front camera over plain HTTP). **Still needs one test on a real Android phone and a real iPhone on the venue Wi-Fi.** Long term: HTTPS (tunnel) per "Guest reach" below, which would also bring back the live camera on phones.
- ~~Secrets sit in the project folder.~~ Moved to `C:\Users\ranji\AURA-secrets` on 2026-11-14 (step 8). Still to clean up by the owner: the copies in `%LOCALAPPDATA%\AURA` (March installer tests) and the old `Output\WeddingFaceForward_Setup_1.0.x.exe` files.

**First-run experience checklist (blockers for non-technical users)**
1. ~~`dist_utils.bootstrap_user_data()` copies the owner's credentials to every user.~~ Fixed 2026-11-14 (step 2): each user signs in with their own Google account. Still open: nothing prompts a new user to sign in; they must find Auth > "Connect Google Drive" themselves. The first-run wizard (item 4) should do this.
2. WhatsApp via Playwright: no place found where the Chromium browser is bundled or installed for end users; needs a QR scan and a logged-in profile (fragile).
3. ~~GPU: the wizard asked users to install CUDA and cuDNN.~~ Fixed 2026-11-14 (step 6 below): DirectML, automatic, nothing to install.
4. ~~No first-run wizard.~~ Added 2026-11-14 (step 6 below).
5. Port 8000 is hardcoded; a collision silently breaks the app.
6. Installer needs a clean Windows 11 VM test and code signing. Avoid forcing admin rights.
7. Guests' phones must be able to reach the guest page (venue Wi-Fi QR or tunnel).
8. No automatic recovery or clear error if the backend process dies.

**Suggested next steps (in order)**
1. ~~Restore the v2 `aura.spec` from git; fix or remove the broken launcher scripts.~~ Done 2026-11-14 (see Warnings).
2. ~~Fix the credentials bundling (checklist item 1).~~ Done 2026-11-14:
   - `aura.spec`: bundles `.env.template` + `credentials.json` only. A build-time check stops the build if `.env`, `token.json`, `service_account.json` or `MY_CREDENTIALS_BACKUP.txt` would be bundled (also inside bundled folders), or if `credentials.json` is not a Desktop-app OAuth client.
   - `.env.template` (new, project root): defaults from `config.py`, no folder ID, no credential paths, `DRIVE_USE_APP_FOLDER=true`.
   - `dist_utils.py`: `bootstrap_user_data()` only creates `.env` from the template (no credential copying, no "CRITICAL" log). New helpers `get_token_path()` and `get_oauth_client_path()` (user folder first, then bundle).
   - `backend/app/cloud.py`: no longer turns cloud off when `service_account.json` is missing (it used to, even with a valid sign-in). Order: user sign-in, then a service account only if one exists, else a plain "not connected, sign in" message. With `DRIVE_USE_APP_FOLDER=true` and no folder ID, it uploads into an "AURA" folder in the user's own Drive (found or created). The flag is only in the template, so the owner's existing setup still uploads to the Drive root and the current event is not split.
   - `aura_app/widgets/auth_dialog.py`: also finds the bundled `credentials.json`; button renamed "Connect Google Drive"; plain wording; after sign-in it says to stop and start processing once so uploads begin.
   - Verified with a script (in a temp folder, not the real AppData): simulated installed first launch creates a clean `.env` and copies no credentials; cloud with no sign-in reports "not connected" without crashing; the spec (PyInstaller stubbed) bundles only the template and the sign-in client, and blocks a planted `token.json`. The owner's dev setup still connects the same way.
   - Not verified yet: a real PyInstaller build, and a real "Connect Google Drive" sign-in with a second Google account (needs the consent-screen fix above).
3. ~~Bind the server to localhost for admin routes and add auth; keep only the guest endpoints public.~~ Done 2026-11-14, in a simpler form: the v2 desktop app never calls the server, so the server became **guest-only** and needs no admin login.
   - `frontend/server.py`: no admin router, no CORS middleware, no `/docs` or `/openapi.json`, version label 2.0.0, `reload=True` removed from `main()`. Still listens on 0.0.0.0 port 8000 on purpose (guests' phones). Remaining routes: `/`, `/css/*`, `/js/*`, `/api/health`, `/api/stats` (counts only), `/api/enroll`, `/api/gallery/{person_id}/photos|photo|thumbnail`.
   - Per-guest gallery keys (P0 item 5, local part): `/api/enroll` returns `gallery_token` = HMAC-SHA256 of the person ID with a random per-install secret in `<db folder>/gallery_secret.key` (deleting it invalidates all keys; it is in the spec's blocked list). Gallery endpoints need the key, return paths relative to the guest's folder (no local disk paths), and only serve photos inside that guest's own folder. Wrong key, another guest's ID and path tricks all get 404.
   - Removed: `/api/persons`, `/api/photos/{name}`, `/api/photo?path=`, `/api/thumbnail?path=` (anyone on the Wi-Fi could list every person and step through `Person_1`, `Person_2`, ...).
   - `/api/enroll`: server-generated selfie filename (the phone's filename could write outside the upload folder), 15 MB limit, error details go to the log instead of the phone.
   - `/css/*` and `/js/*` only serve plain files in their own folder.
   - `frontend/js/main.js` sends `person_id` + `gallery_token` on every gallery call; `index.html` loads `main.js?v=2026-11-14` so phones don't use a cached old copy.
   - Verified with a script against a throwaway event folder and database (enrollment patched out, so no AI models): 28 checks pass, covering everything above. The real server imports and lists only the guest routes. Not verified: a real enrollment on a real phone (blocked by the camera issue in Warnings).
   - Still open: hardcoded port 8000 (P0 item 7); no rate limit on `/api/enroll`; plain HTTP on the venue Wi-Fi; uploaded selfies are still never deleted (P1); anyone holding a photo of a guest can enroll with it and see that guest's gallery (inherent to selfie matching; consider phone-number confirmation later).
3b. ~~Selfie upload fallback for phones.~~ Done 2026-11-14:
   - `frontend/index.html`: "Take a selfie" / "Or take / choose a photo" button (hidden `<input type="file" accept="image/*" capture="user">`), a friendly "camera unavailable" note inside the camera frame, and a "Try camera again" button. CSS and JS links carry `?v=2026-11-14b` so phones don't keep the old cached page.
   - `frontend/js/main.js`: `setCameraMode('live'|'unavailable'|'preview')` drives the UI. No camera API (phones over http) shows the note and makes the photo button the main green action, with no error toast. Camera denied shows the note plus "Try camera again". Chosen photos are shrunk in the browser to max 1600 px JPEG before upload (falls back to the original if the browser can't decode it, e.g. HEIC; the 15 MB server limit still applies). "Retake" reopens the phone camera when there is no live camera.
   - Fixed an old bug on the way: on camera failure the page replaced the Capture button with an inline `onclick="startCamera()"` "Retry Camera" button that did nothing (the script is a module, so `startCamera` is not global) and destroyed the Capture button.
   - `frontend/css/main.css`: styles for the above; the selfie preview now fills the camera frame (an old `max-height: 280px` rule squashed it, also for live-camera captures).
   - Verified in Playwright Chromium at phone size (390x844) against a test server, 21 checks: (A) a genuinely insecure page (made-up hostname mapped to 127.0.0.1) shows the fallback, a 4000x3000 photo is uploaded as 1600x1200, enrollment, gallery preview, gallery and full-size photo all load with the private key, retake reopens the picker, no JS errors; (B) camera denied shows the note and "Try camera again" really retries; (C) with a working (fake) camera the original live capture and retake still work. Screenshots checked by eye. Step 3 server tests re-run: still pass.
   - Not verified: real phones (iOS Safari, Android Chrome), and a real AI match (enrollment was stubbed in tests).
4. ~~Fix the clustering race in `backend/app/cluster.py` (`assign_person`).~~ Done 2026-11-14, plus two merge bugs found on the way:
   - **Race (confirmed before fixing):** worker threads clustered at the same time with separate read and write steps. Replaying 8 threads x 40 faces of 6 people with the old logic gave **10 people, face_count 167/320, 4 duplicate `Person_NNN` names**. So past events probably contain split guests and wrong face counts; the existing Merge tool can join the split ones.
   - `backend/app/db.py`: new `Database.write_transaction()` (BEGIN IMMEDIATE ... COMMIT, rollback on any error). Inside it, use the yielded connection only, since other `Database` methods commit on their own.
   - `backend/app/cluster.py`: `assign_person(embedding, threshold, face_id=None)` does read all centroids, pick nearest, update or create, and link the face in ONE step under a thread lock plus `write_transaction` (covers threads and other processes). Distance search is now one matrix operation (`cosine_distances`); same results and tie-breaking as the old loop. `cluster_faces` uses `face_id`. Old version saved at `<scratchpad>/cluster.py.before_step4` for this session only.
   - `backend/app/worker.py`: passes `face_id` so the face link is part of the same step.
   - **Merge bug 1 (DB):** `merge_persons` ran as separate auto-committed statements and did not move guest enrollments. Merging a person a guest had enrolled as failed on the foreign key after the faces had already moved (confirmed by test). Now one atomic step that also moves enrollments; refuses unknown IDs and merging a person into itself.
   - **Merge bug 2 (folders):** `aura_app/widgets/merge_dialog.py` `_merge_filesystem` only moved files directly in the person folder, but photos live in `Solo/` and `Group/`, so merged photos never reached the kept person's gallery. Now moves the whole tree, drops identical duplicates (a group photo with both people is in both folders), keeps different same-name files as `name_merged_N`, removes the emptied folders, logs failures instead of hiding them.
   - Not chosen: an in-memory centroid cache in the worker. The desktop app can merge people at any time from another process, so a cache could point faces at deleted people. Reading centroids inside the transaction is safe and fast enough for event sizes (hundreds of people). Revisit only if clustering shows up as slow.
   - Verified: `backend/tests/test_cluster_concurrency.py` (new, 5 tests) plus the old 24 all pass (`cd backend; python -m pytest -q tests`). A larger scratch script also passed: old-vs-new race comparison, 3 runs of 8 threads (always exactly 6 people, 320/320), 3 separate processes (6 people, 180/180), vectorized distance equals the old loop, rollback leaves no partial change, old merge half-failure reproduced and new merge correct, folder merge with Solo/Group, duplicates and name clashes. All edited modules import cleanly.
   - Still open: merging does not merge the two people's **Google Drive** folders (the removed person's Drive folder stays); a real processing run on event photos has not been done after the change.
5. Build the installer and test it on a clean VM. **Installer built and smoke-tested 2026-11-14; waiting for the owner's clean-PC test (checklist below):**
   - `aura.iss`: per-user install by default (`PrivilegesRequired=lowest`, installs to `%LOCALAPPDATA%\Programs\AURA`, no admin prompt; "all users" still offered). Uninstall question now says plainly that it deletes the **event photos** (EventRoot lives in `%LOCALAPPDATA%\AURA`), and "No" is the default button. Build steps written at the top of the file.
   - First PyInstaller build (`python -m PyInstaller aura.spec --noconfirm --clean`, ~22 min): OK, `dist\AURA\` = 11,077 files, 1.8 GB. One build error line: hidden import `playwright._impl._api_types` not found (removed in newer Playwright; probably harmless, but test WhatsApp from the installed app).
   - Smoke test of the built `AURA.exe` (`<scratchpad>/smoke_frozen.py`, LOCALAPPDATA redirected to a scratch folder): no private files in the bundle; first launch creates `.env` from the template and copies no credentials; **worker with the bundled AI models processed a real group photo: 6 faces -> 6 people in 21 s**; desktop app starts and stays up; no tracebacks in logs.
   - **Bug found and fixed:** `AURA.exe --run-server` crashed ("Unable to configure formatter 'default'", `sys.stdout` is None in a console-less exe, uvicorn calls `isatty()`). It only worked inside the app because the desktop window happens to capture the server's output. `run_pyside.py` now gives the process real streams (stdout to devnull, stderr to `logs/<mode>-errors.log`). Rebuilt (no `--clean`, ~16 min).
   - **Smoke test of the rebuilt exe: 26/26 pass.** Server serves the guest page; admin/old photo routes gone; worker sorts the real group photo (6 faces -> 6 people, 27 s); **real AI enrollment** with a face cropped from that photo matched the right person (confidence 0.987); the guest's gallery, thumbnail and key check work (also after enrollment renamed the folder to the guest's name); desktop app starts and stays up; no tracebacks. The new `*-errors.log` files only contain harmless library deprecation warnings.
   - **Installer built: `Output\AURA_Setup_2.0.0.exe`, 630 MB** (`ISCC.exe aura.iss`, ~4 min). The first compile failed at the last step ("EndUpdateResource failed", antivirus scanning the new file); a plain retry worked, no antivirus change needed. If it happens again: retry, or exclude `Output\` from Defender.
   - Not done here on purpose: installing it on the owner's PC (it would register the app and the uninstaller asks about the owner's real `%LOCALAPPDATA%\AURA`). The installer is **not code-signed**, so Windows SmartScreen will show "Windows protected your PC" (users must click *More info > Run anyway*) until it is signed.
   - Found: `Output/` holds five old `WeddingFaceForward_Setup_1.0.x.exe` (March) built with the old spec, which bundled the owner's `.env`, `token.json`, `service_account.json`. Do not share them; if any were shared, treat those credentials as exposed. Not deleted (owner's decision). The owner's real `%LOCALAPPDATA%\AURA` (from March tests) also holds copies of `token.json` and `service_account.json`; part of the secrets cleanup (P0 item 2).
   - **Owner: clean-PC test checklist** (Windows 11 VM or a spare PC with no Python, no GPU drivers, normal non-admin user):
     1. Copy `AURA_Setup_2.0.0.exe` over, run it. Expect the SmartScreen warning (unsigned). Expect **no admin prompt**. Note how long install takes.
     2. Launch AURA from the Start menu. Intro video plays, dashboard opens.
     3. Auth > Connect Google Drive: sign in with a test Google account (needs the consent-screen fix in Warnings, or that account added as a test user).
     4. Start processing, copy 10-20 real event photos into the event folder's `Incoming`. Check people appear and photos upload into an "AURA" folder in that account's Drive.
     5. On a phone on the same Wi-Fi, open `http://<PC's IP>:8000` (Windows Firewall will ask to allow AURA on first server start; allow on Private networks). Take a selfie, check the gallery.
     6. Try WhatsApp sending (checklist item 2: Playwright browser download, QR login).
     7. Uninstall from Settings > Apps. The data question must default to **No**; answer No and check photos remain in `%LOCALAPPDATA%\AURA`.
     Write down anything confusing; that is the first-run wizard's to-do list.

6. **DirectML GPU default + faster CPU + first-run wizard. Done 2026-11-14, new installer built.**
   - **Rebuilt installer: `Output\AURA_Setup_2.0.0.exe`, 640 MB, 2026-11-14 22:08** (clean PyInstaller build ~24 min). Smoke test of the built exe: all checks pass. `DirectML.dll` is bundled; the speed test ran inside the built app (`AURA.exe --benchmark-compute`) and chose the graphics card on this laptop (221 ms vs CPU 507 ms per photo); the worker logs "Face processing on: Graphics card (Intel(R) Arc(TM) Graphics)"; real group photo -> 6 people; real selfie matched (0.987); gallery/key checks pass; app + wizard start cleanly; no tracebacks. On a fresh install the first processing run waits ~40 s for the one-time speed test (first photo done after ~90 s), later runs start straight away.
   - Fixed in the bundle: stale `gpu_wizard`/`gpu_manager` `.pyc` files (the spec copies whole `aura_app/` and `backend/app/` folders, `__pycache__` included). Deleted. Follow-up: make the spec skip `__pycache__` when copying folders.
   - **Installer compile tip:** Inno Setup failed twice with "EndUpdateResource failed ... antivirus" when writing into `Output\`. Compiling to another folder worked: `ISCC.exe /O"<some temp folder>" aura.iss`, then move the file into `Output\`. (Alternative: exclude `Output\` from Defender; owner's decision.) Owner's wish: "if they have an RTX GPU use it, otherwise CPU, and CPU should be fast too; no CUDA install".
   - **Measured on the owner's laptop** (Core Ultra 5 125H, Intel Arc graphics, 2048 px photo with 6 faces, 4 workers; scripts in the session scratchpad):
     | Setup | per photo |
     | :-- | :-- |
     | Old: CPU, 5 models per thread, every thread on all 18 cores | **17.4 s** |
     | CPU, only detection+recognition models | 8.3 s |
     | CPU, 2 models, cores split between threads (new CPU default) | **1.0-1.9 s** |
     | DirectML on the built-in Intel Arc (new GPU path) | **0.22-0.34 s** |
     Results are identical: same 6 faces, same boxes, embedding similarity 1.00000 vs the old setup (CPU and GPU). CPU timings vary a lot run to run on this laptop (power/thermal state); a sweep of thread splits was too noisy to tune further, so the simple rule `threads per worker = CPU threads / workers` stays.
   - **Important finding:** separate DirectML sessions in several threads at once **crashed Python (segfault)**. The GPU path therefore uses ONE shared analyzer with a lock, and the speed test runs in a separate process.
   - New `backend/app/compute.py`: `COMPUTE_DEVICE=auto|gpu|cpu` (default auto). Auto runs a one-time speed test in a subprocess (`run_pyside.py --benchmark-compute` / `AURA.exe --benchmark-compute`), keeps the GPU only if >10% faster, caches it in `<user data>/compute_choice.json`, and re-tests when the graphics hardware or engine version changes. DirectML is asked for the `high_performance` adapter (RTX on gaming laptops, not the Intel chip). A failed/crashed/timed-out test means CPU.
   - `backend/app/processor.py`: `build_face_analyzer(plan)` loads only detection+recognition (`allowed_modules`), applies session options (InsightFace doesn't pass them, so its session class is patched while loading), GPU = one shared analyzer + lock, CPU = one per thread with split cores. If the GPU errors during processing it switches to CPU for the rest of the run.
   - Retired the CUDA wizard: `backend/app/gpu_manager.py` and `aura_app/widgets/gpu_wizard.py` moved to `_archive_cuda_gpu/` (they could never work in the installed app anyway: they ran `pip install onnxruntime-gpu`, and AURA.exe has no pip). Startup no longer pops a CUDA prompt; it shows a short "Using graphics card / processor" note. Header badge shows GPU/CPU with the reason as tooltip. Settings has a new "Processing Speed" section: what is used and why, Automatic / Graphics card / Processor choice, "Run speed test now".
   - First-run wizard `aura_app/widgets/first_run_wizard.py` (opens after the intro video until finished or skipped, `FIRST_RUN_DONE=true`; reopen from the new **Setup** menu): Welcome, photos folder (new installs default to `Pictures\AURA`, not the hidden AppData folder; existing setups keep their folder), speed check with a plain result, Connect Google Drive (or skip), guest link + QR code (this PC's Wi-Fi address, port 8000, firewall hint), Done. Pages rendered and checked in light and dark.
   - `dist_utils.set_env_values()` (new): updates or ADDS keys in the user's .env (the settings dialog's writer only updated existing keys, so new keys were silently not saved).
   - Dependencies: `onnxruntime-directml==1.24.1` replaces `onnxruntime` (requirements.txt, pyproject.toml; the owner's main Python was switched; undo with `pip uninstall onnxruntime-directml && pip install onnxruntime==1.24.1`). New `segno==1.6.6` (QR code, pure Python). Microsoft has put DirectML in maintenance mode (1.24.4 is the last release); it works and is supported, but watch for a successor (Windows ML) later.
   - `.env.template`: GPU_* keys replaced by `COMPUTE_DEVICE=auto`.
   - Tests: new `backend/tests/test_compute.py` (7 tests, no models needed); fixed a flaky old test (`test_assign_to_existing_when_similar` used noise that put the distance right at the threshold, failing ~1 in 3 runs). Backend suite 36/36, 15 runs in a row clean. Scratch test with real models and DirectML: 12/12 (settings, subprocess speed test chose GPU 218 ms vs CPU 990 ms, 4 threads sharing the GPU, simulated GPU failure falls back to CPU and still finds 6 faces). Earlier step 3/3b/4 tests re-run: pass.
   - Not verified yet: an NVIDIA RTX or AMD machine (only Intel Arc here); installing the new installer on a clean PC (step 5 checklist, plus: the setup wizard appears after the intro video, and Settings > Processing Speed shows the right device).

7. **Reliability pack. Done 2026-11-14, installer rebuilt.**
   - **Current installer: `Output\AURA_Setup_2.0.0.exe`, 640 MB, 2026-11-14 22:46, SHA-256 starts `ad94f63661c5de6e`.** It contains steps 1-7. Smoke test of the built exe: 33/33 pass, including the new checks (no `__pycache__` in the bundle; `AURA.exe --playwright-install` downloaded Chromium into `%LOCALAPPDATA%\ms-playwright` in 40 s, where the WhatsApp launch looks). The speed test chose the graphics card again, but this run measured GPU 353 ms vs CPU 419 ms (earlier 221 vs 507): laptop timings vary with power/heat; the 10% margin rule still picked the GPU.
   - **Guest port** (checklist item 5): `dist_utils.pick_guest_port()` picks the first free port from 8000 when processing starts and records it (`<user data>/guest_port.txt`, `AURA_GUEST_PORT`); the server, the dashboard's "Guest page" log line (now shows the Wi-Fi address) and the wizard QR code all use it. A warning is logged if 8000 was busy.
   - **Crash recovery** (checklist item 8): `aura_app/process_manager.py` rewritten with a supervisor thread. Worker or server exiting unexpectedly -> error message with its last output lines + automatic restart; after 3 crashes in 10 minutes it stops and says so. WhatsApp exit is reported once, not restarted. Stop is not treated as a crash.
   - **Dead Google sign-in**: `cloud.py` treats `invalid_grant` on refresh as "not connected" with a plain message (before, it said connected and every upload failed). Confirmed on the owner's dev setup: now `is_enabled=False` with the message.
   - **Speed**: removed the 0.1 s per photo "visual stability" sleep in `worker.py`; the worker decides GPU/CPU (speed test) at startup, before the first photo.
   - **Logs**: `worker.log` and `aura.log` rotate at 5 MB x 3 (`dist_utils.rotating_log_handler`); only the newest 30 `session_*.txt` are kept. New **Export Logs** menu item zips logs + speed-test result to the Desktop (no settings, no sign-in files).
   - **Privacy**: the uploaded guest selfie is deleted after enrollment (failed match: always; success: when the resized `00_REFERENCE_SELFIE.jpg` exists in the guest's folder, which the DB points at).
   - **WhatsApp browser path**: `run_pyside.py` now always uses `%LOCALAPPDATA%\ms-playwright` for both the automatic Chromium download (`--playwright-install`) and the launch (`--run-whatsapp`); before, a fresh PC could download into one folder and look in another.
   - Build hygiene: spec copies `backend/app` and `aura_app` file by file without `__pycache__`; `numpy<2` pinned.
   - Tests: `<scratchpad>/test_reliability.py` 13/13 (busy port 8000 -> 8001 recorded and used by the wizard; simulated worker crash reported with last output, restarted 3x then gives up; healthy server untouched; Stop not a crash; selfie cleanup in all three cases). Backend 36/36 and the step 2/3/3b/4 suites re-run: pass.

8. **Owner decisions carried out (2026-11-14):** secrets moved, `drive.file`, WhatsApp fallback, git branch pushed.
   - **Secrets moved out of the project** to `C:\Users\ranji\AURA-secrets` (`.env`, `credentials.json`, `token.json`, `service_account.json`, `MY_CREDENTIALS_BACKUP.txt`; moved, nothing deleted). `dist_utils.get_secrets_dir()` is the single place code looks (dev: that folder if it exists, override `AURA_SECRETS_DIR`; installed app: `%LOCALAPPDATA%\AURA` as before). Used by config, cloud, the Connect Google Drive window, `setup_auth.py` and the build (`aura.spec` finds `credentials.json` there). Verified: dev setup loads the same photos folder and DB, finds the sign-in, and the build picks up the sign-in client from there. Not touched: old copies in `%LOCALAPPDATA%\AURA` from the March installer tests (contain `token.json` and `service_account.json`; delete when no longer needed) and the five old `Output\WeddingFaceForward_Setup_1.0.x.exe` (contain the old secrets; do not share).
   - **Drive permission is now `drive.file`** (`dist_utils.DRIVE_SCOPES`, used by cloud.py, setup_auth.py, auth_dialog.py). Existing full-access sign-ins keep working; new sign-ins ask only for files AURA creates. Folders AURA created with this `credentials.json` stay visible; folders made by hand do not. **Owner action:** in Google Cloud Console > Data access, list `.../auth/drive.file` (remove `.../auth/drive`), then publish. Details in `infos/GOOGLE_DRIVE_SETUP.md`.
   - **WhatsApp fallback: "Share Links" menu** (`aura_app/widgets/share_links_dialog.py`): every guest with a phone number, the automatic sender's status, and per guest **Open WhatsApp** (wa.me link with the message filled in; you press Send), **Copy message**, **QR** (scan on the spot). Link = the guest's Drive folder when Drive is connected (shared publicly, same as the sender), else a **direct gallery link** to the guest page. New: `backend/app/gallery_access.py` (gallery keys shared by server and desktop app), `/api/gallery/{id}/info`, guest page opens `/?g=<id>&k=<key>` straight into that guest's gallery without asking for the camera (bad link -> normal selfie flow). Tested (`dev_checks/test_share.py`, 13/13): endpoint keys, direct link in a phone browser over plain http, broken link fallback, the window's list/status, wa.me URL with digits and message, copy, link validity.
   - **Test scripts kept in the project:** `dev_checks/` (smoke test of the built app, step tests, reliability, share links, compute, benchmark) with a README; the `<scratchpad>` paths mentioned above refer to these.
   - All suites re-run after these changes: backend 36/36, step 2/3/3b/4, reliability, compute with real models + DirectML: pass.
   - **Git:** see "Warnings" (updated) for the branch. The commit was rewritten without the Claude co-author line at the owner's request (now `990e280`, same files) and force-pushed; future commits show only the owner.
   - **Final installer: `Output\AURA_Setup_2.0.0.exe`, 2026-11-14 23:30, SHA-256 starts `869ddf679dd0b8b0`**, includes steps 1-8. Smoke test of the built exe: all checks pass (speed test chose the graphics card, 382 ms vs CPU 801 ms per photo). This replaces the 22:46 build mentioned in step 7.

**Docs map**
- `infos/GOOGLE_DRIVE_SETUP.md`: how Drive sign-in works, what users see, the owner's one-time Google Cloud setup, the `drive` vs `drive.file` decision, troubleshooting. (Added 2026-11-14.)
- `README.md`, `infos/project_structure.md`, `infos/system_architecture.md`: corrected this session to describe the PySide6 v2 as active (system_architecture still shows the v3 diagram with a note).
- `infos/PROJECT_DEV_LOG.md`, `Z_AgentLogs.md`: history and bug logs.
- `infos/adding gpu support automatically.md`: old CUDA wizard plan, marked OBSOLETE (replaced by DirectML, step 6).
- `_archive_outdated_docs/`: the Electron plan and a Perplexity note, both obsolete.
- `_archive_tauri_v3/`: the Tauri/Next.js app, sidecar, and its two plan docs.

## Decision point: which UI ships first? (added 2026-11-14, from the owner)

- The owner confirms the **last PySide6 app (v2.0.0, GitHub HEAD 0696daf, 19 commits) worked well**. It is a real installable Windows app (PyInstaller + Inno Setup, `aura_app/`, `run_pyside.py`, `aura.iss`) and launches its own backend processes, so users run no commands.
- The v3.0.0 Tauri + Next.js app exists only in the untracked `antigravity` folder and has never been verified end to end.
- The migration was started for the UI look ("Liquid Glass") and because the Electron plan notes OS-level freezing caused by PySide6's frameless window styling (verify).
- The **backend is shared by both UIs**, so the P0 fixes below (secrets and credentials, API split and auth, clustering race, port handling, first-run flow) are needed either way. Do those first.
- Recommended: fix the shared backend, then ship whichever shell passes the clean-VM install test first. **Do not delete `aura_app/`, `run_pyside.py` or `aura.iss` until the Tauri app passes that test.** The earlier note calling them "legacy, planned for deletion" reflects the old migration plan, not a decision.

## Target product

- One Windows desktop app, installed with a few clicks (Next, Next, Install). Used by the photographer or event host.
- One web page for guests (phones) to register with name and phone number and upload a selfie.
- GPU is used automatically when present, with a clean CPU fallback.

## Recommended architecture

| Piece | Decision | Why |
| :-- | :-- | :-- |
| Main app | Tauri 2 + Next.js (`aura_web`), the stack already in use | Best-looking UI, small installer shell, auto-updater built in |
| Backend | Python FastAPI, shipped as a Tauri sidecar `.exe` | AI stack is Python; the sidecar already exists |
| Guest page | Small separate static page (plain HTML/JS or Next static export), served by the backend on its own port | Guests must never see the admin UI or admin API |
| Retire | PySide6 `aura_app/` and old admin parts of `frontend/` | Two admin UIs double the maintenance |
| GPU | Default to `onnxruntime-directml` (works on NVIDIA, AMD and Intel with no CUDA download); keep CUDA as an optional "turbo" for NVIDIA | Removes the multi-GB CUDA/cuDNN wizard from the first-run path |
| Installer | Tauri NSIS, `perUser` install mode, code-signed | No admin prompt, fewer SmartScreen warnings |
| Updates | Tauri updater, with the models split into a separate first-run download or a separate installer component | Keeps updates small |
| Guest reach | Option A: QR code on the venue Wi-Fi (LAN). Option B: Cloudflare Tunnel for a public URL | Guests' phones need to reach the laptop |

## P0: Before using at another event

1. **Put the project in git** (it is currently untracked). Commit source only. Do not commit `EventRoot`, `data`, `sidecar`, `target`, `node_modules`, `whatsapp_user_data`, or any secret.
2. **Secrets**: move `credentials.json`, `token.json`, `service_account.json`, `.env` and `infos/MY_CREDENTIALS_BACKUP.txt` out of the project folder (password manager and `%LOCALAPPDATA%\AURA`). Rotate any that were ever committed or shared.
> Items 3 to 5 below were written for the Tauri plan. For the active v2 app, step 3 (2026-11-14) solved them by making the server guest-only with per-guest gallery keys; see "Suggested next steps". Signed Drive links (item 5's cloud side) are still open.

3. **Split the API into two servers/routers.**
   - Admin API: bind to `127.0.0.1` only, random port, per-launch auth token passed to the UI by Tauri.
   - Guest API: its own port, only `enroll` and the guest's own gallery. Nothing else.
4. **Remove `allow_origins=["*"]` with credentials**, `host="0.0.0.0"` on the admin side, and `reload=True`.
5. **Guest gallery access via signed, unguessable per-guest links** (token in URL). Remove open `/api/persons`, `/api/photo` and `/api/photos/{name}` from the public side.
6. ~~**Fix the clustering race** in `cluster.py` `assign_person`.~~ Done 2026-11-14 (step 4). The in-memory cache was deliberately not added; see step 4 for why.
7. **Pick a free port at startup** and pass it to the UI, instead of the hardcoded 8000.

## P1: Quality of results

- Quality filters before clustering: minimum detection score, minimum face size, blur check.
- Use a stricter threshold for selfie matching than for clustering (verify the right values on real event photos).
- Enrollment: reject selfies with more than one face, show the top 2 or 3 candidate matches, allow the admin to confirm or correct a match.
- Suggest merges for near-duplicate people, and a periodic re-cluster pass.
- Vector index (numpy matrix or FAISS) for matching once an event has many people.
- Delete guest selfies after enrollment (the cleanup is currently commented out), and avoid double JPEG recompression at quality 95.

## P1: Installer and first-run experience

- First-run wizard: pick the event folder, sign in to Google Drive, detect the GPU, show a "Using ..." status.
- Bundle the buffalo_l models, or download them once with a progress bar (decide on installer size vs offline use).
- Pin `numpy<2` (InsightFace requirement), and pin the other dependencies exactly.
- Reduce the 720 MB sidecar: check for duplicated DLLs and unused packages (verify).
- Code-sign the installer and the sidecar. Test on a clean Windows 11 VM with no Python, no GPU and no admin rights.
- Crash reporting and a "Export logs" button.
- Clear error messages when Drive auth expires or the disk is full.

## P2: Cleanup

- Delete or archive: `checker_scripts/`, one-off fix scripts, `frontend/` admin code, `aura_app/`, `build/`, `Output/`, the empty `--version` file, and duplicate databases (`aura.db`, extra `wedding.db`). Work out which database is the real one first.
- One configuration source with validation, replacing the hand-rolled `.env` editor in `admin_router.py`.
- Move worker state from `worker_states.json` into memory or the database. Remove `time.sleep(0.1)` "for visual stability" and the bare `except:` blocks.
- Log rotation.
- Tests: worker, cloud, enrollment, API (including auth and path traversal), plus an end-to-end test with a few sample photos. Add CI that runs pytest and builds the installer.

## P2: Privacy and sharing

- Consent text on the guest page, a retention period, and a "delete my data" action (embeddings, selfie, phone number).
- Replace "anyone with the link" Drive sharing with per-guest links or expiring links.
- Do not store the logged-in WhatsApp profile inside the project folder.

## P3: Product features

- WhatsApp: replace browser automation with the WhatsApp Business Cloud API, or offer a share link and QR code as the fallback.
- Live event mode: photographer's camera folder or FTP/tether, with the guest gallery updating in real time.
- Multiple events, with a separate database and folder per event.
- Export a person's gallery as a ZIP, and slideshow or print selections.
- Dashboard polish from `memory.md`: multi-layer glass cards and micro-interactions, and a proper empty state when counts are 0.

## Suggested order

1. Git and secrets (P0 items 1 and 2).
2. API split, auth and port handling (P0 items 3 to 7).
3. Clustering fix and quality filters.
4. ~~DirectML default and the first-run wizard.~~ Done 2026-11-14 (step 6 in "Suggested next steps").
5. Installer: perUser, signed, tested on a clean VM.
6. Guest page polish, privacy and signed links.
7. Cleanup, tests and CI.
8. Product features.

## Open questions for the owner

- Will guests be on the venue Wi-Fi, or should the guest page work from anywhere (needs a tunnel or hosted relay)?
- Is the offline requirement strict (bundle models) or is a one-time download acceptable?
- Is Google Drive required, or is local-only plus a hosted gallery enough?
- Drive permission: keep full `drive` (needs Google's paid security assessment to verify) or switch to `drive.file` (lighter review; everyone re-signs in once; AURA can't see folders made by the old setup)? Recommended: `drive.file`, switched between events. See `infos/GOOGLE_DRIVE_SETUP.md`.
- Owner action: publish the OAuth consent screen (currently probably "Testing") before anyone else uses the app.
