"""Step 3b: guest page selfie flow in a phone-sized browser (Playwright Chromium)."""
import os, sys, shutil, threading, time, io
from pathlib import Path

PROJ = Path(sys.argv[1]).resolve()
SCRATCH = Path(sys.argv[2]).resolve()
work = SCRATCH / "t_3b"
shutil.rmtree(work, ignore_errors=True)
event = work / "EventRoot"
os.environ["EVENT_ROOT"] = str(event)
os.environ["DB_PATH"] = str(work / "data" / "test.db")
sys.path[:0] = [str(PROJ), str(PROJ / "backend"), str(PROJ / "frontend")]

from PIL import Image
import numpy as np
from app.config import get_config
get_config().ensure_directories()
from app.db import get_db
db = get_db()
a = db.create_person("Person_A", np.zeros(512, dtype=np.float32))
for rel in ["Solo/a1.jpg", "Solo/a2.jpg", "Group/a3.jpg"]:
    p = event / "People" / "Person_A" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (300, 200), (40, 120, 200)).save(p, "JPEG")

import server
from app.enrollment import EnrollmentResult
uploads = []
def fake_enroll(selfie_path, user_name, **kw):
    with Image.open(selfie_path) as im:
        uploads.append({"size": Path(selfie_path).stat().st_size, "dims": im.size, "name": user_name})
    return EnrollmentResult(success=True, person_id=a, person_name="Person_A", match_confidence=0.9, message="ok")
server.enroll_user = fake_enroll

import uvicorn
PORT = 8765
srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=PORT, log_level="warning"))
threading.Thread(target=srv.run, daemon=True).start()
while not srv.started: time.sleep(0.1)

big = work / "phone_photo.jpg"
Image.new("RGB", (4000, 3000), (180, 140, 120)).save(big, "JPEG", quality=95)
shots = SCRATCH / "shots_3b"; shots.mkdir(exist_ok=True)

from playwright.sync_api import sync_playwright
results = []
def check(name, cond):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

PHONE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)

with sync_playwright() as pw:
    # ── A. Phone over plain http (insecure origin: aura.test -> 127.0.0.1) ──
    browser = pw.chromium.launch(args=[f"--host-resolver-rules=MAP aura.test 127.0.0.1"])
    page = browser.new_context(**PHONE).new_page()
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://aura.test:{PORT}/")
    check("A: page is an insecure context (like a phone on venue Wi-Fi)", page.evaluate("!window.isSecureContext && !navigator.mediaDevices"))
    page.locator("#enroll").scroll_into_view_if_needed()
    check("A: 'camera unavailable' note shown", page.is_visible("#cameraUnavailable"))
    check("A: live camera + Capture button hidden", not page.is_visible("#videoWrapper") and not page.is_visible("#captureBtn"))
    check("A: photo button is primary, says 'Take a selfie'",
          page.inner_text("#uploadBtnText") == "Take a selfie" and "is-primary" in page.get_attribute("#uploadFallback", "class"))
    check("A: no 'Retry camera' button (camera is unsupported, not denied)", not page.is_visible("#retryCameraBtn"))
    check("A: file input opens the front camera", page.get_attribute("#selfieFileInput", "capture") == "user")
    page.screenshot(path=str(shots / "A1_no_camera.png"), full_page=False)

    page.set_input_files("#selfieFileInput", str(big))
    page.wait_for_selector("#previewContent:not(.hidden)", timeout=10000)
    check("A: preview shown, retake shown, photo button hidden",
          page.is_visible("#selfiePreview") and page.is_visible("#retakeBtn") and not page.is_visible("#uploadFallback"))
    page.screenshot(path=str(shots / "A2_preview.png"))

    page.click("#nextBtn")
    page.fill("#userName", "Test Guest")
    page.fill("#userPhone", "9876543210")
    page.click("#submitBtn")
    page.wait_for_selector("#resultsModal:not(.hidden)", timeout=15000)
    check("A: enrollment succeeded", page.is_visible("#resultSuccess"))
    up = uploads[-1] if uploads else {}
    check(f"A: photo shrunk before upload (4000x3000 -> {up.get('dims')}, {up.get('size', 0)//1024} KB)",
          up and max(up["dims"]) <= 1600 and up["size"] < 1_000_000)
    page.wait_for_function("document.querySelectorAll('#galleryPreview img').length >= 2 && [...document.querySelectorAll('#galleryPreview img')].every(i => i.complete && i.naturalWidth > 0)", timeout=10000)
    check("A: gallery preview thumbnails load (with private key)", True)
    page.screenshot(path=str(shots / "A3_success.png"))

    page.click("#viewGalleryBtn")
    page.wait_for_function("document.querySelectorAll('#galleryGrid img').length === 2 && [...document.querySelectorAll('#galleryGrid img')].every(i => i.complete && i.naturalWidth > 0)", timeout=10000)
    check("A: full gallery loads own 2 solo photos", True)
    page.click(".photo-card")
    page.wait_for_function("document.getElementById('lightboxImage').complete && document.getElementById('lightboxImage').naturalWidth > 0", timeout=10000)
    check("A: full-size photo opens in lightbox", True)
    page.screenshot(path=str(shots / "A4_gallery.png"))
    check("A: no JavaScript errors", not errors)
    if errors: print("   ", errors)

    # Retake in no-camera mode reopens the picker (input gets clicked)
    page2 = browser.new_context(**PHONE).new_page()
    page2.goto(f"http://aura.test:{PORT}/")
    page2.set_input_files("#selfieFileInput", str(big))
    page2.wait_for_selector("#previewContent:not(.hidden)")
    with page2.expect_file_chooser(timeout=5000) as fc:
        page2.click("#retakeBtn")
    check("A: 'Retake' reopens the phone camera / picker", fc.value is not None)
    browser.close()

    # ── B. Secure page but camera permission denied ──
    browser = pw.chromium.launch()
    ctx = browser.new_context(**PHONE)   # no camera permission granted -> denied in headless
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{PORT}/")
    page.wait_for_selector("#cameraUnavailable:not(.hidden)", timeout=10000)
    check("B: denied camera -> friendly note + photo button", page.is_visible("#uploadFallback") and "couldn't open the camera" in page.inner_text("#cameraUnavailableText"))
    check("B: 'Try camera again' button visible", page.is_visible("#retryCameraBtn"))
    calls = page.evaluate("""() => { window.__gum = 0; const o = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
        navigator.mediaDevices.getUserMedia = (c) => { window.__gum++; return o(c); }; return true; }""")
    page.click("#retryCameraBtn")
    page.wait_for_timeout(500)
    check("B: 'Try camera again' actually retries the camera", page.evaluate("window.__gum") == 1)
    page.screenshot(path=str(shots / "B_denied.png"))
    browser.close()

    # ── C. Camera works (fake camera) -> original live capture still works ──
    browser = pw.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    ctx = browser.new_context(**PHONE, permissions=["camera"])
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{PORT}/")
    page.wait_for_function("document.getElementById('cameraStream').videoWidth > 0", timeout=10000)
    check("C: live camera shown, Capture visible, photo button secondary",
          page.is_visible("#captureBtn") and page.inner_text("#uploadBtnText").startswith("Or ") and not page.is_visible("#cameraUnavailable"))
    page.screenshot(path=str(shots / "C1_live.png"))
    page.click("#captureBtn")
    page.wait_for_selector("#previewContent:not(.hidden)", timeout=5000)
    check("C: capture -> preview", page.is_visible("#retakeBtn"))
    page.click("#retakeBtn")
    page.wait_for_function("document.getElementById('cameraStream').videoWidth > 0 && !document.getElementById('videoWrapper').classList.contains('hidden')", timeout=10000)
    check("C: retake returns to live camera", True)
    browser.close()

srv.should_exit = True
print("Screenshots:", shots)
print("ALL CHECKS PASSED" if all(results) else f"{results.count(False)} FAILED")
