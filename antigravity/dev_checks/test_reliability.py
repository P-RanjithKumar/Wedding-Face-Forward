"""Reliability checks: free guest port, process supervisor, selfie cleanup."""
import os, sys, io, time, socket, shutil
from pathlib import Path

PROJ = Path(sys.argv[1]).resolve()
WORK = Path(sys.argv[2]).resolve() / "t_reliab"
shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir(parents=True)
os.environ["EVENT_ROOT"] = str(WORK / "EventRoot")
os.environ["DB_PATH"] = str(WORK / "data" / "t.db")
sys.path[:0] = [str(PROJ), str(PROJ / "backend"), str(PROJ / "frontend")]
os.chdir(PROJ)

import dist_utils
results = []
def check(name, cond, extra=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)

# ── 1. Guest port ────────────────────────────────────────────────
dist_utils.get_user_data_dir = lambda: WORK          # keep runtime files in the scratch folder
blocker = socket.socket(); blocker.bind(("0.0.0.0", 8000)); blocker.listen()
port = dist_utils.pick_guest_port()
check("port 8000 busy -> picks the next free port", port == 8001, str(port))
check("chosen port recorded for server/dashboard/wizard",
      (WORK / "guest_port.txt").read_text() == "8001" and dist_utils.get_guest_port() == 8001)
blocker.close()
os.environ.pop("AURA_GUEST_PORT")
check("other processes read the recorded port", dist_utils.get_guest_port() == 8001)
check("port 8000 free again -> 8000", dist_utils.pick_guest_port() == 8000)

from aura_app.widgets import first_run_wizard as frw
check("wizard QR link uses the recorded port", frw.guest_url().endswith(":8000"), frw.guest_url())

# ── 2. Supervisor ────────────────────────────────────────────────
from aura_app import process_manager as pm_mod
pm_mod.CHECK_INTERVAL_S = 0.3
msgs = []
pm = pm_mod.ProcessManager(on_output=lambda m, l: msgs.append((l, m)))
py = sys.executable
cmds = {
    "Worker": [py, "-c", "import time,sys; print('worker up', flush=True); time.sleep(0.5); print('boom: simulated crash', flush=True); sys.exit(3)"],
    "Server": [py, "-c", "import time; print('server up', flush=True); time.sleep(60)"],
    "WhatsApp": [py, "-c", "import time; time.sleep(0.2)"],
}
pm._command = lambda name: cmds[name]
pm.start()
time.sleep(9)
crash = [m for l, m in msgs if "stopped unexpectedly" in m and m.startswith("Worker")]
restarts = [m for l, m in msgs if m.startswith("Restarting Worker")]
gave_up = [m for l, m in msgs if "not restarting photo processing" in m]
check("crashed worker is reported with its last output", crash and "simulated crash" in crash[0], crash[0][:120] if crash else "")
check("worker restarted 3 times, then gives up with a clear message",
      len(restarts) == 3 and len(gave_up) == 1, f"{len(restarts)} restarts, gave up: {bool(gave_up)}")
check("healthy server left alone", pm.server_proc.poll() is None and not any(m.startswith("Restarting Server") for _, m in msgs))
check("WhatsApp exit reported once, not restarted",
      sum("WhatsApp sender stopped" in m for _, m in msgs) == 1)
pm.stop()
n = len(msgs); time.sleep(1.5)
check("Stop is not treated as a crash", not any("unexpectedly" in m for _, m in msgs[n:]))

# ── 3. Selfie cleanup after enrollment ───────────────────────────
from app.config import get_config
cfg = get_config(); cfg.ensure_directories()
import server
from app.enrollment import EnrollmentResult
from fastapi.testclient import TestClient
from PIL import Image
c = TestClient(server.app)
uploads = cfg.event_root / "Admin" / "Uploads"
mode = {}
def fake(selfie_path, user_name, **kw):
    if mode["kind"] == "fail":
        return EnrollmentResult(success=False, person_id=None, person_name=None, match_confidence=0.1, message="no match")
    folder = cfg.people_dir / "Guest"; folder.mkdir(parents=True, exist_ok=True)
    if mode["kind"] == "ok":
        (folder / "00_REFERENCE_SELFIE.jpg").write_bytes(b"x")
    else:
        (folder / "00_REFERENCE_SELFIE.jpg").unlink(missing_ok=True)
    return EnrollmentResult(success=True, person_id=1, person_name="Guest", match_confidence=0.9, message="ok")
server.enroll_user = fake
server.make_gallery_token = lambda pid: "t"
def post():
    buf = io.BytesIO(); Image.new("RGB", (8, 8)).save(buf, "JPEG")
    return c.post("/api/enroll", data={"name": "G"}, files={"selfie": ("s.jpg", buf.getvalue(), "image/jpeg")})
for kind, expect_left, label in [("fail", 0, "failed match -> uploaded selfie deleted"),
                                 ("ok", 0, "success with reference copy -> uploaded selfie deleted"),
                                 ("noref", 1, "success but reference copy missing -> upload kept (DB points at it)")]:
    for f in uploads.glob("*"): f.unlink()
    mode["kind"] = kind
    r = post()
    left = len(list(uploads.glob("selfie_*")))
    check(label, r.status_code == 200 and left == expect_left, f"{left} file(s) left")

print("ALL CHECKS PASSED" if all(results) else f"{results.count(False)} FAILED")
