"""Step 3 checks: guest-only server, per-guest gallery tokens, upload hardening."""
import os, sys, shutil, io
from pathlib import Path

PROJ = Path(sys.argv[1]).resolve()
work = Path(sys.argv[2]).resolve() / "t_server"
shutil.rmtree(work, ignore_errors=True)
event = work / "EventRoot"; data = work / "data"
os.environ["EVENT_ROOT"] = str(event)          # absolute -> used as-is; overrides .env
os.environ["DB_PATH"] = str(data / "test.db")
sys.path[:0] = [str(PROJ), str(PROJ / "backend"), str(PROJ / "frontend")]

from PIL import Image
import numpy as np

def jpg(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), (200, 50, 50)).save(path, "JPEG")

from app.config import get_config
cfg = get_config(); cfg.ensure_directories()
assert str(cfg.event_root) == str(event)
from app.db import get_db
db = get_db()
if hasattr(db, "initialize"): db.initialize()
a = db.create_person("Person_A", np.zeros(512, dtype=np.float32))
b = db.create_person("Person_B", np.zeros(512, dtype=np.float32))
jpg(event / "People" / "Person_A" / "Solo" / "a1.jpg")
jpg(event / "People" / "Person_A" / "Group" / "a2.jpg")
jpg(event / "People" / "Person_B" / "Solo" / "b1.jpg")

import server
from app.enrollment import EnrollmentResult
def fake_enroll(selfie_path, user_name, **kw):
    fake_enroll.saved = Path(selfie_path)
    return EnrollmentResult(success=True, person_id=a, person_name="Person_A",
                            match_confidence=0.9, message="ok")
server.enroll_user = fake_enroll

from fastapi.testclient import TestClient
c = TestClient(server.app)
results = []
def check(name, cond):
    results.append(cond); print(("PASS " if cond else "FAIL ") + name)

# Admin and listing endpoints are gone
for url in ["/api/admin/settings", "/api/admin/worker/status", "/api/persons",
            "/api/photos/Person_B", f"/api/photo?path={event}/People/Person_B/Solo/b1.jpg"]:
    check(f"gone: {url[:45]}", c.get(url).status_code == 404)
check("no API explorer (/docs is just the guest page)", "swagger" not in c.get("/docs").text.lower())
check("no CORS header", "access-control-allow-origin" not in c.get("/api/health", headers={"Origin": "http://evil.example"}).headers)

# Enroll: hostile filename, token returned
buf = io.BytesIO(); Image.new("RGB", (10, 10)).save(buf, "JPEG")
r = c.post("/api/enroll", data={"name": "Guest"},
           files={"selfie": ("../../../evil.jpg", buf.getvalue(), "image/jpeg")})
j = r.json(); tok = j.get("gallery_token")
check("enroll ok + token", r.status_code == 200 and bool(tok))
check("selfie saved inside Uploads with server name",
      fake_enroll.saved.parent == event / "Admin" / "Uploads" and "evil" not in fake_enroll.saved.name)
check("nothing written outside event root", not (work / "evil.jpg").exists() and not (event.parent.parent / "evil.jpg").exists())

big = b"\xff\xd8" + b"0" * (15 * 1024 * 1024 + 10)
check("oversized selfie rejected (413)",
      c.post("/api/enroll", data={"name": "x"}, files={"selfie": ("x.jpg", big, "image/jpeg")}).status_code == 413)

# Own gallery works
r = c.get(f"/api/gallery/{a}/photos", params={"token": tok, "category": "solo"})
check("own gallery lists photos", r.status_code == 200 and [p["path"] for p in r.json()] == ["Solo/a1.jpg"])
check("paths are relative (no local disk paths leaked)", str(event) not in r.text)
check("own group photos", [p["path"] for p in c.get(f"/api/gallery/{a}/photos", params={"token": tok, "category": "group"}).json()] == ["Group/a2.jpg"])
check("own photo download", c.get(f"/api/gallery/{a}/photo", params={"token": tok, "path": "Solo/a1.jpg"}).status_code == 200)
r = c.get(f"/api/gallery/{a}/thumbnail", params={"token": tok, "path": "Solo/a1.jpg"})
check("own thumbnail", r.status_code == 200 and r.headers["content-type"] == "image/jpeg")

# Other guests are off limits
check("no token -> 404", c.get(f"/api/gallery/{a}/photos").status_code == 404)
check("wrong token -> 404", c.get(f"/api/gallery/{a}/photos", params={"token": "x" * 43}).status_code == 404)
check("A's token on B -> 404", c.get(f"/api/gallery/{b}/photos", params={"token": tok}).status_code == 404)
for p in ["../Person_B/Solo/b1.jpg", "Solo/../../Person_B/Solo/b1.jpg",
          str(event / "People" / "Person_B" / "Solo" / "b1.jpg"), "../../../data/test.db"]:
    check(f"traversal blocked: {p[-30:]}", c.get(f"/api/gallery/{a}/photo", params={"token": tok, "path": p}).status_code == 404)

# Static files
check("css served", c.get("/css/main.css").status_code == 200)
check("css traversal blocked", c.get("/css/..%2Fserver.py").status_code in (404,) or "import" not in c.get("/css/..%2Fserver.py").text)
check("guest page loads", c.get("/").status_code == 200 and "main.js?v=" in c.get("/").text)

# Secret stored next to the DB, token stable
check("secret file next to DB", (data / "gallery_secret.key").exists())
check("token stable", server.make_gallery_token(a) == tok and server.make_gallery_token(b) != tok)

print("ALL CHECKS PASSED" if all(results) else f"{results.count(False)} FAILED")
