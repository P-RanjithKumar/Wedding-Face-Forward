"""Offline batch check of the BUILT app: no Google Drive, N photos, timed.

Usage (from antigravity/):
    python dev_checks/offline_batch.py <scratch folder> <group photo> [N=40]

Runs dist/AURA/AURA.exe --run-worker with LOCALAPPDATA redirected to the
scratch folder (a fresh install, Drive not connected), drops N variations of
the group photo into Incoming and waits until all are processed.
"""
import os, sys, time, shutil, sqlite3, subprocess
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps

PROJ = Path(__file__).resolve().parents[1]
WORK = Path(sys.argv[1]).resolve() / "t_offline"
SAMPLE = Path(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 40
EXE = PROJ / "dist" / "AURA" / "AURA.exe"

shutil.rmtree(WORK, ignore_errors=True)
appdata = WORK / "appdata"; appdata.mkdir(parents=True)
AURA = appdata / "AURA"
env = dict(os.environ, LOCALAPPDATA=str(appdata))
env.pop("AURA_SECRETS_DIR", None)

# Start the worker once so first launch creates the folders, then add photos
wrk = subprocess.Popen([str(EXE), "--run-worker"], env=env)
incoming = AURA / "EventRoot" / "Incoming"
t_wait = time.time()
while not incoming.exists() and time.time() - t_wait < 60:
    time.sleep(0.5)

base = Image.open(SAMPLE).convert("RGB")
for i in range(N):
    im = base
    if i % 2: im = ImageOps.mirror(im)
    im = ImageEnhance.Brightness(im).enhance(0.8 + (i % 5) * 0.1)
    w, h = im.size
    scale = 1.5 + (i % 4) * 0.5           # 1.5x - 3x, like camera photos
    im = im.resize((int(w * scale), int(h * scale)))
    # Unique per photo (identical files are skipped by AURA as duplicates):
    # crop a different strip off the edge for every i
    im = im.crop((i * 3, 0, im.size[0], im.size[1]))
    im.save(incoming / f"IMG_{i:04d}.jpg", quality=92)
t0 = time.time()

db = AURA / "data" / "wedding.db"
done = 0
while time.time() - t0 < 1200:
    time.sleep(3)
    if wrk.poll() is not None:
        print(f"worker exited early: {wrk.returncode}"); break
    try:
        c = sqlite3.connect(db)
        done = c.execute("SELECT COUNT(*) FROM photos WHERE status IN ('completed','no_faces','error')").fetchone()[0]
        c.close()
    except sqlite3.Error:
        continue
    print(f"  {time.time() - t0:5.0f}s  processed {done}/{N}", flush=True)
    if done >= N:
        break
elapsed = time.time() - t0
c = sqlite3.connect(db)
status = dict(c.execute("SELECT status, COUNT(*) FROM photos GROUP BY status").fetchall())
persons = c.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
faces = c.execute("SELECT COUNT(*) FROM faces WHERE person_id IS NOT NULL").fetchone()[0]
uploads = dict(c.execute("SELECT status, COUNT(*) FROM upload_queue GROUP BY status").fetchall())
c.close()
subprocess.run(["taskkill", "/PID", str(wrk.pid), "/T", "/F"], capture_output=True)

choice = (AURA / "compute_choice.json").read_text() if (AURA / "compute_choice.json").exists() else "{}"
people_dirs = sorted(p.name for p in (AURA / "EventRoot" / "People").iterdir())
solo_group = sum(1 for _ in (AURA / "EventRoot" / "People").rglob("*.jpg"))
print(f"photos: {status} of {N} in {elapsed:.0f}s ({elapsed / max(done, 1):.2f} s/photo incl. one-time speed test)")
print(f"faces linked: {faces}, people: {persons} ({people_dirs[:8]})")
print(f"photo copies in People folders: {solo_group}")
print(f"upload queue (Drive not connected, expect empty): {uploads or 'empty'}")
print(f"compute choice: {choice.strip()[:200]}")
ok = status.get("completed", 0) == N and persons == 6 and not uploads
print("OFFLINE BATCH OK" if ok else "OFFLINE BATCH: CHECK RESULTS")
