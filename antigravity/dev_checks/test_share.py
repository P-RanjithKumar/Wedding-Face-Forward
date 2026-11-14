"""Share Links fallback + direct gallery links (server, guest page, desktop window)."""
import os, sys, json, shutil, threading, time, urllib.parse
from pathlib import Path

PROJ = Path(sys.argv[1]).resolve()
SCR = Path(sys.argv[2]).resolve()
WORK = SCR / "t_share"
shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir(parents=True)
os.environ["EVENT_ROOT"] = str(WORK / "EventRoot")
os.environ["DB_PATH"] = str(WORK / "data" / "t.db")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"
sys.path[:0] = [str(PROJ), str(PROJ / "backend"), str(PROJ / "frontend")]
os.chdir(PROJ)

import dist_utils
dist_utils.get_user_data_dir = lambda: WORK
os.environ["AURA_GUEST_PORT"] = "8767"

results = []
def check(name, cond, extra=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)

import numpy as np
from PIL import Image
from app.config import get_config
cfg = get_config(); cfg.ensure_directories()
from app.db import get_db
db = get_db()
a = db.create_person("Asha", np.zeros(512, dtype=np.float32))
b = db.create_person("Ben", np.zeros(512, dtype=np.float32))
for name, rel in [("Asha", "Solo/a1.jpg"), ("Asha", "Group/g.jpg"), ("Ben", "Solo/b1.jpg")]:
    p = cfg.people_dir / name / rel; p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 150), (90, 160, 90)).save(p, "JPEG")
e1 = db.create_enrollment(a, "Asha", "x.jpg", 0.9, phone="+91 98765 43210")
e2 = db.create_enrollment(b, "Ben", "y.jpg", 0.9, phone="+44 7700 900123")
db.create_enrollment(b, "No Phone", "z.jpg", 0.9, phone="")
(WORK / "whatsapp_data").mkdir()
(WORK / "whatsapp_data" / "message_state_db.json").write_text(json.dumps({str(e1): {"status": "sent"}, str(e2): {"status": "failed"}}))

from app.gallery_access import make_gallery_token, gallery_link, token_is_valid
import server, uvicorn
srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=8767, log_level="warning"))
threading.Thread(target=srv.run, daemon=True).start()
while not srv.started: time.sleep(0.1)

# ── server info endpoint ─────────────────────────────────────────
from fastapi.testclient import TestClient
cl = TestClient(server.app)
r = cl.get(f"/api/gallery/{a}/info", params={"token": make_gallery_token(a)})
check("info endpoint returns the guest's name with the right key", r.status_code == 200 and r.json()["person_name"] == "Asha")
check("info endpoint refuses another guest's key", cl.get(f"/api/gallery/{b}/info", params={"token": make_gallery_token(a)}).status_code == 404)
link = gallery_link("http://aura.test:8767", a)
check("direct link format", "/?g=" in link and "&k=" in link and token_is_valid(a, urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["k"][0]), link)

# ── guest page opened from a direct link (phone, plain http) ─────
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--host-resolver-rules=MAP aura.test 127.0.0.1"])
    ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    gum = []
    page.add_init_script("window.__gum=0; if (navigator.mediaDevices) { const o = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices); navigator.mediaDevices.getUserMedia = c => { window.__gum++; return o(c); }; }")
    errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(link)
    page.wait_for_selector("#gallerySection:not(.hidden)", timeout=10000)
    page.wait_for_function("document.querySelectorAll('#galleryGrid img').length === 1 && document.querySelector('#galleryGrid img').naturalWidth > 0", timeout=10000)
    check("direct link opens the guest's gallery with their name", page.inner_text("#galleryUserName") == "Asha")
    page.click(".tab-btn[data-tab='group']")
    page.wait_for_function("document.querySelectorAll('#galleryGrid img').length === 1", timeout=5000)
    check("group tab works from a direct link", True)
    check("no camera request when opening a gallery link", page.evaluate("window.__gum") == 0)
    page.screenshot(path=str(SCR / "share_direct_link.png"))
    check("no JavaScript errors", not errs, "; ".join(errs))

    bad = ctx.new_page()
    bad.goto(f"http://aura.test:8767/?g={a}&k=wrongkey")
    bad.wait_for_timeout(1500)
    check("broken link: gallery stays closed, selfie flow shown",
          not bad.is_visible("#gallerySection") and bad.is_visible("#uploadFallback"))
    br.close()
srv.should_exit = True

# ── desktop Share Links window ───────────────────────────────────
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QDesktopServices, QGuiApplication
app = QApplication([])
opened = []
QDesktopServices.openUrl = staticmethod(lambda url: opened.append(url.toString()) or True)
from aura_app.widgets import share_links_dialog as sld
sld.ShareLinksDialog._drive_connected = lambda self: False      # no Drive in the test
dlg = sld.ShareLinksDialog(mode="dark")
dlg.resize(860, 420); dlg.show(); app.processEvents()
rows = {dlg._table.item(r, 0).text(): dlg._table.item(r, 2).text() for r in range(dlg._table.rowCount())}
check("lists only guests with a phone, with WhatsApp status",
      rows == {"Asha": "Sent ✓", "Ben": "Failed"}, str(rows))
row_ben = [r for r in range(dlg._table.rowCount()) if dlg._table.item(r, 0).text() == "Ben"][0]
dlg._act(row_ben, "whatsapp"); app.processEvents()
url = opened[-1] if opened else ""
qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
check("Open WhatsApp -> wa.me with number digits and the message",
      url.startswith("https://wa.me/447700900123?") and "Hello Ben!" in qs.get("text", [""])[0], url[:80])
msg_link = qs.get("text", [""])[0].split("event: ")[1].split("\n")[0] if "event: " in qs.get("text", [""])[0] else ""
check("message contains Ben's own working gallery link (this Wi-Fi)",
      f"g={b}&" in msg_link and token_is_valid(b, urllib.parse.parse_qs(urllib.parse.urlparse(msg_link).query)["k"][0]), msg_link)
dlg._act(row_ben, "copy"); app.processEvents()
check("Copy message puts it on the clipboard", QGuiApplication.clipboard().text().startswith("Hello Ben!"))
check("wa.me helper", sld.wa_me_url("+91 98765-43210", "hi there") == "https://wa.me/919876543210?text=hi%20there")
dlg.grab().save(str(SCR / "share_links_dialog.png"))

print("ALL CHECKS PASSED" if all(results) else f"{results.count(False)} FAILED")
