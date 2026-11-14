# How to test AURA on your laptop (no Google Drive, no internet needed)

Everything below runs on this laptop only: face detection, grouping people, and the guest selfie page.
Google Drive and WhatsApp stay off; messages about them being "not connected" are expected.

---

## Part 1: Install

1. Close AURA if it is open.
2. Open the folder `C:\Users\ranji\Desktop\MYwork\Wedding Face Forward\antigravity\Output`
3. Double-click **`AURA_Setup_2.0.0.exe`**.
4. Windows shows **"Windows protected your PC"** (the installer is not signed yet).
   Click **More info**, then **Run anyway**.
5. If asked "Install for me only" or "for all users": choose **for me only** (no admin needed).
6. Click **Next**, **Next**, **Install**. Tick **Launch AURA** and click **Finish**.

## Part 2: First start (setup guide)

1. The intro video plays, then the **Set up AURA** window opens.
2. **Step 2, photos folder:** keep the suggested `C:\Users\ranji\Pictures\AURA` and click **Next**.
3. **Step 3, speed check:** wait about 40 seconds. On this laptop it should say your
   **Intel Arc graphics card** will do the face matching. Click **Next**.
4. **Step 4, Google Drive:** do **not** connect. Just click **Next**.
5. **Step 5, guests' link:** note the link (like `http://192.168.1.9:8000`). Click **Next**, then **Finish**.
   The link and QR code **only work after you press START** (Part 3). Scanning it now shows nothing; that is expected.

## Part 3: Process photos

1. On the dashboard, click **START**. The top bar shows **⚡ GPU**.
2. Open File Explorer at `C:\Users\ranji\Pictures\AURA\Incoming`.
3. Copy in **20 to 50 real event photos** (from your camera card, phone, or any folder).
   Tip: photos where the same people appear several times show the grouping best.
4. Watch the dashboard: the photo, face and people counts go up within seconds.
5. Open `C:\Users\ranji\Pictures\AURA\People`. There is one folder per person
   (`Person_001`, `Person_002`, ...), each with **Solo** (only that person) and **Group** photos.

What to check:
- Is the same person always in the same folder?
- Did two different people end up in one folder, or one person split into two folders?
  (Fix a split with **Merge** in the menu; tell Claude how often it happened.)

## Part 4: Guest selfie (on the laptop)

1. Processing must be running (Part 3).
2. On the laptop, open your browser at **http://localhost:8000**
   (if the dashboard log says another port, use that one).
3. Click **Get My Photos**, allow the camera, click **Capture Selfie** (or "take / choose a photo"),
   then **Next**, type a name and any phone number, keep the consent box ticked and click **Find My Photos**.
   Use the face of someone who appears in the photos (you can also hold up a printed photo or a phone
   showing their face).
4. You should see **Photos Found!** and their photos. Click **View All My Photos**.
5. Back in `Pictures\AURA\People`, that person's folder is now named after the guest.

## Part 5: Guest selfie on a phone (optional)

1. Phone on the **same Wi-Fi** as the laptop.
2. Open the guest link from Part 2 (or scan the QR code: menu **Setup**, then go to step 5).
3. The first time, Windows on the laptop may ask whether AURA may use the network:
   tick **Private networks** and click **Allow**.
4. Tap **Take a selfie**, then continue as in Part 4.

## Part 6: Other things worth a click

- **Share Links** (menu): each registered guest with **Open WhatsApp**, **Copy message** and **QR**.
  Without Google Drive the link points to their gallery on this Wi-Fi.
- **Settings > Processing Speed:** shows Graphics card vs Processor and lets you re-run the speed test.
- **Export Logs** (menu): saves a ZIP to your Desktop. Send it to Claude if anything goes wrong.

## Stop, and uninstall later

- Click **STOP** on the dashboard, then close the window.
- To uninstall: Windows **Settings > Apps > Installed apps > AURA > Uninstall**.
  When asked "Also delete your AURA data?", **No** (the default) keeps everything.
  Your photos in `Pictures\AURA` are never touched by the uninstaller.

---

## If something goes wrong

| What you see | What to do |
| :-- | :-- |
| "Windows protected your PC" | More info, then Run anyway (expected until the installer is signed) |
| "Google Drive is not connected" / "Uploads are OFF" | Expected in this local test, ignore |
| No people appear | Check the photos are in `Pictures\AURA\Incoming` and START was pressed; wait 1 minute (first run does the speed test) |
| Guest page does not open on the phone | 1) Is processing running (STOP button visible)? The link only works then. 2) Same Wi-Fi, mobile data off? 3) Test `http://<laptop IP>:8000/api/health` on the phone: "healthy" = network OK. 4) Allowed AURA in the Windows Firewall prompt? |
| Anything else | Menu **Export Logs**, send the ZIP from your Desktop |

## Testing from the source code instead (developer way)

`cd antigravity` then `python run_pyside.py`. This uses your developer settings in
`C:\Users\ranji\AURA-secrets\.env`, i.e. your **real event folder** `antigravity\EventRoot` and its database,
so test with the installed app first if you want a clean start.
