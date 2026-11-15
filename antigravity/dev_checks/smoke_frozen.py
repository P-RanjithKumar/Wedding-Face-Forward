"""Smoke test of the BUILT app (dist/AURA/AURA.exe) as a fresh install.

LOCALAPPDATA is redirected to a scratch folder so the owner's real
%LOCALAPPDATA%\\AURA is never touched.
"""
import os, sys, time, shutil, sqlite3, subprocess, json, io, urllib.request, urllib.error
from pathlib import Path

PROJ = Path(sys.argv[1]).resolve()
WORK = Path(sys.argv[2]).resolve() / "t_frozen"
EXE = PROJ / "dist" / "AURA" / "AURA.exe"
shutil.rmtree(WORK, ignore_errors=True)
appdata = WORK / "appdata"; appdata.mkdir(parents=True)
AURA = appdata / "AURA"
# Own port so the check also works while the installed AURA is open (it uses 8000)
PORT = int(os.environ.get("SMOKE_PORT", "8790"))
env = dict(os.environ, LOCALAPPDATA=str(appdata), AURA_GUEST_PORT=str(PORT))
SAMPLE = Path(sys.argv[3])  # insightface t1.jpg (group photo)

results = []
def check(name, cond, extra=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)

def kill(p):
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)

def http(path, data=None, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

# ── 0. Bundle scan ───────────────────────────────────────────────
bad = {".env", "token.json", "service_account.json", "my_credentials_backup.txt", "gallery_secret.key"}
leaks = [str(p) for p in (PROJ / "dist" / "AURA").rglob("*") if p.name.lower() in bad]
check("bundle contains no private files", not leaks, ", ".join(leaks[:5]))
internal = PROJ / "dist" / "AURA" / "_internal"
for rel in [".env.template", "credentials.json", "frontend/index.html", "frontend/js/main.js",
            "frontend/server.py", "models/buffalo_l", "logo"]:
    check(f"bundle has {rel}", (internal / rel).exists())
check("old admin router not bundled", not list((PROJ / "dist" / "AURA").rglob("admin_router.py")))
dml = list((PROJ / "dist" / "AURA").rglob("DirectML.dll"))
check("DirectML engine bundled (GPU without CUDA)", bool(dml), str(dml[:1]))
check("old CUDA wizard not bundled", not list((PROJ / "dist" / "AURA").rglob("gpu_wizard*")))

# ── 1+2. Server mode (also runs first-launch bootstrap) ──────────
srv = subprocess.Popen([str(EXE), "--run-server"], env=env)
ok = False
for _ in range(120):
    time.sleep(1)
    try:
        if http("/api/health")[0] == 200: ok = True; break
    except Exception:
        pass
    if srv.poll() is not None: break
check("server starts from the built exe", ok, f"exit={srv.poll()}")
check("first launch created .env from the template",
      (AURA / ".env").exists() and (AURA / ".env").read_text() == (PROJ / ".env.template").read_text())
check("first launch copied no credentials",
      not any((AURA / f).exists() for f in ("token.json", "service_account.json", "credentials.json")))
if ok:
    code, body = http("/")
    check("guest page served", code == 200 and b"main.js?v=" in body)
    for path in ["/api/admin/settings", "/api/persons", "/api/photos/Person_001", "/openapi.json"]:
        code, body = http(path)
        check(f"removed route not available: {path}", code == 404 or b"<html" in body[:200].lower())
    check("stats endpoint works", http("/api/stats")[0] == 200)

# ── 3. Worker with the real face models ──────────────────────────
incoming = AURA / "EventRoot" / "Incoming"
incoming.mkdir(parents=True, exist_ok=True)
shutil.copy2(SAMPLE, incoming / "group_photo.jpg")
wrk = subprocess.Popen([str(EXE), "--run-worker"], env=env)
db_path = AURA / "data" / "wedding.db"
status, persons, faces = None, 0, 0
t0 = time.time()
while time.time() - t0 < 300:
    time.sleep(3)
    if wrk.poll() is not None: break
    try:
        c = sqlite3.connect(db_path)
        row = c.execute("SELECT status FROM photos LIMIT 1").fetchone()
        status = row[0] if row else None
        persons = c.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        faces = c.execute("SELECT COUNT(*) FROM faces WHERE person_id IS NOT NULL").fetchone()[0]
        c.close()
        if status in ("completed", "error", "no_faces"): break
    except sqlite3.Error:
        pass
elapsed = time.time() - t0
check("worker processed the photo with the bundled AI models", status == "completed",
      f"status={status}, {faces} faces, {persons} people, {elapsed:.0f}s, worker exit={wrk.poll()}")
choice_file = AURA / "compute_choice.json"
choice = json.loads(choice_file.read_text()) if choice_file.exists() else {}
check("speed test ran inside the built app and was saved", bool(choice),
      f"device={choice.get('device')}, gpu={choice.get('gpu_name')}, gpu_ms={choice.get('gpu_ms')}, cpu_ms={choice.get('cpu_ms')} {choice.get('note', '')}")
check("this PC (Intel Arc) uses the graphics card", choice.get("device") == "gpu")
wlog = "\n".join(p.read_text(errors="replace") for p in (AURA / "logs").glob("*.log"))
check("worker logs which device it uses", "Face processing on:" in wlog,
      next((l.strip()[-110:] for l in wlog.splitlines() if "Face processing on:" in l), ""))
people_dirs = sorted(p.name for p in (AURA / "EventRoot" / "People").iterdir()) if (AURA / "EventRoot" / "People").exists() else []
check("photo sorted into People folders", len(people_dirs) >= 2, f"{people_dirs[:6]}")
kill(wrk)

# ── 4. Real enrollment: a face cropped from the group photo ─────
if ok and status == "completed":
    from PIL import Image
    c = sqlite3.connect(db_path)
    pid, x, y, w, h = c.execute(
        "SELECT person_id, bbox_x, bbox_y, bbox_w, bbox_h FROM faces ORDER BY bbox_w*bbox_h DESC LIMIT 1").fetchone()
    c.close()
    im = Image.open(SAMPLE).convert("RGB")
    pad = int(max(w, h) * 0.8)
    crop = im.crop((max(0, x - pad), max(0, y - pad), x + w + pad, y + h + pad))
    buf = io.BytesIO(); crop.save(buf, "JPEG"); img = buf.getvalue()
    boundary = "----aura"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\nSmoke Guest\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"phone\"\r\n\r\n+911234567890\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"selfie\"; filename=\"selfie.jpg\"\r\n"
            f"Content-Type: image/jpeg\r\n\r\n").encode() + img + f"\r\n--{boundary}--\r\n".encode()
    code, resp = http("/api/enroll", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    j = json.loads(resp) if code == 200 else {}
    check("real selfie enrollment matches the right person", code == 200 and j.get("success") and j.get("person_id") == pid,
          f"code={code}, matched={j.get('person_id')}, expected={pid}, conf={j.get('match_confidence')}, msg={j.get('message')}")
    if j.get("gallery_token"):
        code, lst = http(f"/api/gallery/{j['person_id']}/photos?token={j['gallery_token']}&category=group")
        photos = json.loads(lst) if code == 200 else []
        check("guest's own gallery lists the group photo", code == 200 and len(photos) >= 1, f"{photos[:1]}")
        if photos:
            code, _ = http(f"/api/gallery/{j['person_id']}/thumbnail?token={j['gallery_token']}&path={urllib.request.quote(photos[0]['path'])}")
            check("thumbnail loads", code == 200)
        code, _ = http(f"/api/gallery/{j['person_id']}/photos?token=wrong")
        check("wrong key refused", code == 404)
kill(srv)

# ── 5. Desktop window app starts and stays up ────────────────────
gui = subprocess.Popen([str(EXE)], env=env)
time.sleep(30)
alive = gui.poll() is None
check("desktop app starts and is still running after 30 s", alive, f"exit={gui.poll()}")
kill(gui)

# Errors in the app's own logs
logtxt = "\n".join(p.read_text(errors="replace") for p in (AURA / "logs").rglob("*") if p.is_file())
tb = logtxt.count("Traceback")
check("no tracebacks in the app logs", tb == 0, f"{tb} tracebacks")
if tb:
    i = logtxt.index("Traceback"); print(logtxt[i:i + 1500])

# ── 6. WhatsApp browser download goes where the launch looks ─────
# (~150 MB download; skipped when SMOKE_SKIP_CHROMIUM=1)
if os.environ.get("SMOKE_SKIP_CHROMIUM") == "1":
    print("SKIP Chromium download check (SMOKE_SKIP_CHROMIUM=1)")
    print("ALL CHECKS PASSED" if all(results) else f"{results.count(False)} FAILED")
    sys.exit(0 if all(results) else 1)
t0 = time.time()
pw = subprocess.run([str(EXE), "--playwright-install"], env=env, timeout=900)
browsers = appdata / "ms-playwright"
installed = sorted(p.name for p in browsers.glob("chromium*")) if browsers.exists() else []
check("built app downloads Chromium into %LOCALAPPDATA%\\ms-playwright (where WhatsApp launch looks)",
      pw.returncode == 0 and any(n.startswith("chromium-") for n in installed),
      f"exit={pw.returncode}, {installed}, {time.time() - t0:.0f}s")

print("ALL CHECKS PASSED" if all(results) else f"{results.count(False)} FAILED")
sys.exit(0 if all(results) else 1)
