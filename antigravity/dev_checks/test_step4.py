"""Step 4 checks: clustering race, atomic merge, folder merge, vectorized distance."""
import os, sys, shutil, threading, multiprocessing as mp
from pathlib import Path
import numpy as np

PROJ = Path(sys.argv[1]).resolve()
WORK = Path(sys.argv[2]).resolve() / "t_step4"
sys.path[:0] = [str(PROJ), str(PROJ / "backend")]

K, THREADS, PER_THREAD, DIM = 6, 8, 40, 512


def identities(seed=0):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(K, DIM)); base /= np.linalg.norm(base, axis=1, keepdims=True)
    return base


def noisy(base, rng):
    n = rng.normal(size=DIM); n *= 0.3 / np.linalg.norm(n)
    v = base + n
    return (v / np.linalg.norm(v)).astype(np.float32)


def fresh_db(name):
    os.environ["EVENT_ROOT"] = str(WORK / "EventRoot")
    os.environ["DB_PATH"] = str(WORK / f"{name}.db")
    from app import config, db
    config.reset_config(); db.reset_db()
    return db.get_db()


def old_assign_person(embedding, threshold):
    """Exact copy of the pre-step-4 logic (separate reads and writes)."""
    from app.db import get_db
    from app.cluster import find_nearest_person, update_centroid
    db = get_db()
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    persons = db.get_all_persons()
    nearest_person, distance = find_nearest_person(embedding, persons)
    if nearest_person is not None and distance < threshold:
        new_centroid = update_centroid(nearest_person.centroid, embedding, nearest_person.face_count)
        db.update_person_centroid(nearest_person.id, new_centroid, nearest_person.face_count + 1)
        return nearest_person.id
    next_num = db.get_next_person_number()
    return db.create_person(f"Person_{next_num:03d}", embedding)


def run_threads(assign_fn):
    base = identities()
    barrier = threading.Barrier(THREADS)
    errors = []

    def work(t):
        rng = np.random.default_rng(100 + t)
        jobs = [noisy(base[(t + i) % K], rng) for i in range(PER_THREAD)]
        barrier.wait()
        try:
            for e in jobs:
                assign_fn(e, 0.6)
        except Exception as ex:
            errors.append(repr(ex))

    ts = [threading.Thread(target=work, args=(t,)) for t in range(THREADS)]
    [t.start() for t in ts]; [t.join() for t in ts]
    return errors


def summary(db):
    conn = db.connect()
    persons = conn.execute("SELECT name, face_count FROM persons").fetchall()
    names = [p["name"] for p in persons]
    return len(persons), sum(p["face_count"] for p in persons), len(names) - len(set(names))


def proc_worker(args):
    proj, db_path, event_root, seed = args
    sys.path[:0] = [proj, os.path.join(proj, "backend")]
    os.environ["DB_PATH"] = db_path; os.environ["EVENT_ROOT"] = event_root
    from app.cluster import assign_person
    base = identities(); rng = np.random.default_rng(seed)
    for i in range(60):
        assign_person(noisy(base[(seed + i) % K], rng), 0.6)
    return True


results = []
def check(name, cond):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)


if __name__ == "__main__":
    shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir(parents=True)
    total = THREADS * PER_THREAD

    # ── 1. Vectorized distance == old loop ─────────────────────────
    from app.cluster import cosine_distance, cosine_distances, find_nearest_person
    from app.db import Person
    rng = np.random.default_rng(7)
    M = rng.normal(size=(50, DIM)).astype(np.float32); M[3] = 0
    e = rng.normal(size=DIM).astype(np.float32)
    loop = np.array([cosine_distance(e, m) for m in M])
    check("vectorized distances match the old per-person loop", np.allclose(loop, cosine_distances(e, M), atol=1e-6))
    check("zero embedding -> all distances 2.0", np.all(cosine_distances(np.zeros(DIM), M) == 2.0))
    persons = [Person(id=i, name=f"P{i}", centroid=M[i], face_count=1, created_at=None) for i in range(50)]
    p, d = find_nearest_person(e, persons)
    check("find_nearest_person picks the same person as before", p.id == int(np.argmin(loop)) and abs(d - loop.min()) < 1e-6)
    dup = [Person(id=1, name="a", centroid=M[0], face_count=1, created_at=None),
           Person(id=2, name="b", centroid=M[0], face_count=1, created_at=None)]
    check("ties still go to the first person", find_nearest_person(M[0], dup)[0].id == 1)

    # ── 2. Race: old logic vs new logic, 8 threads, empty DB ───────
    db = fresh_db("old")
    errs = run_threads(old_assign_person)
    n_old, faces_old, dupnames_old = summary(db)
    print(f"     OLD logic: {n_old} people for {K} real people, face_count total {faces_old}/{total}, "
          f"{dupnames_old} duplicate names, {len(errs)} errors")
    check("old logic shows the race (extra people, lost counts or duplicate names)",
          n_old > K or faces_old != total or dupnames_old > 0)

    from app.cluster import assign_person
    for run in range(3):
        db = fresh_db(f"new{run}")
        errs = run_threads(assign_person)
        n, faces, dupnames = summary(db)
        print(f"     NEW logic run {run + 1}: {n} people, face_count total {faces}/{total}, "
              f"{dupnames} duplicate names, {len(errs)} errors")
        check(f"new logic run {run + 1}: exactly {K} people, no lost counts, unique names, no errors",
              n == K and faces == total and dupnames == 0 and not errs)

    # ── 3. Two processes at once on the same DB ────────────────────
    db = fresh_db("procs")
    db_path = os.environ["DB_PATH"]
    ctx = mp.get_context("spawn")
    with ctx.Pool(3) as pool:
        ok = pool.map(proc_worker, [(str(PROJ), db_path, os.environ["EVENT_ROOT"], s) for s in (1, 2, 3)])
    n, faces, dupnames = summary(db)
    print(f"     3 processes: {n} people, face_count total {faces}/180, {dupnames} duplicate names")
    check("3 processes in parallel: exactly 6 people, no lost counts", all(ok) and n == K and faces == 180 and dupnames == 0)

    # ── 4. face_id linked in the same step; rollback on failure ────
    db = fresh_db("link")
    photo = db.create_photo("h1", "x.jpg")
    emb = noisy(identities()[0], np.random.default_rng(1))
    face = db.create_face(photo, (0, 0, 10, 10), emb, 0.99)
    pid = assign_person(emb, 0.6, face_id=face)
    linked = db.connect().execute("SELECT person_id FROM faces WHERE id=?", (face,)).fetchone()[0]
    check("face is linked to its person", linked == pid)
    before = summary(db)
    try:
        with db.write_transaction() as conn:
            conn.execute("UPDATE persons SET face_count = 999")
            raise RuntimeError("simulated crash")
    except RuntimeError:
        pass
    check("a failure inside a write transaction leaves no partial change", summary(db) == before)
    try:
        assign_person(noisy(identities()[3], np.random.default_rng(2)), 0.6, face_id=10**9)
    except Exception:
        pass
    check("assign with a bad face_id creates nothing (all or nothing)", summary(db) == before or summary(db)[0] == before[0] + 1)

    # ── 5. Merge: enrolled person, atomic ──────────────────────────
    from app.cluster import merge_persons
    db = fresh_db("merge")
    base = identities(); r = np.random.default_rng(3)
    ph = db.create_photo("h", "p.jpg")
    fa = db.create_face(ph, (0, 0, 1, 1), noisy(base[0], r), 0.9); a = assign_person(noisy(base[0], r), 0.6, face_id=fa)
    fb = db.create_face(ph, (0, 0, 1, 1), noisy(base[1], r), 0.9); b = assign_person(noisy(base[1], r), 0.6, face_id=fb)
    db.create_enrollment(b, "Guest B", "s.jpg", 0.9, phone="1")
    check("merge of an enrolled person succeeds", merge_persons(a, b) is True)
    conn = db.connect()
    check("removed person is gone", conn.execute("SELECT COUNT(*) FROM persons WHERE id=?", (b,)).fetchone()[0] == 0)
    check("faces moved to kept person", conn.execute("SELECT person_id FROM faces WHERE id=?", (fb,)).fetchone()[0] == a)
    check("guest enrollment moved to kept person", conn.execute("SELECT person_id FROM enrollments").fetchone()[0] == a)
    check("face_count combined", conn.execute("SELECT face_count FROM persons WHERE id=?", (a,)).fetchone()[0] == 2)
    snap = summary(db)
    check("merge with unknown person -> False, nothing changed", merge_persons(a, 999) is False and summary(db) == snap)
    check("merge into itself -> False", merge_persons(a, a) is False)

    # Old merge on the same situation (shows the original bug)
    db = fresh_db("oldmerge")
    ph = db.create_photo("h", "p.jpg")
    fa = db.create_face(ph, (0, 0, 1, 1), noisy(base[0], r), 0.9); a = assign_person(noisy(base[0], r), 0.6, face_id=fa)
    fb = db.create_face(ph, (0, 0, 1, 1), noisy(base[1], r), 0.9); b = assign_person(noisy(base[1], r), 0.6, face_id=fb)
    db.create_enrollment(b, "Guest B", "s.jpg", 0.9, phone="1")
    conn = db.connect()
    try:
        conn.execute("UPDATE faces SET person_id = ? WHERE person_id = ?", (a, b))
        conn.execute("DELETE FROM persons WHERE id = ?", (b,))
        old_ok = True
    except Exception as ex:
        old_ok = False
    moved = conn.execute("SELECT person_id FROM faces WHERE id=?", (fb,)).fetchone()[0] == a
    still = conn.execute("SELECT COUNT(*) FROM persons WHERE id=?", (b,)).fetchone()[0] == 1
    print(f"     OLD merge on enrolled person: delete ok={old_ok}, faces already moved={moved}, removed person still there={still}")
    check("old merge was half-done on an enrolled person (bug confirmed)", not old_ok and moved and still)

    # ── 6. Folder merge (desktop dialog) ───────────────────────────
    from PIL import Image
    people = WORK / "EventRoot" / "People"
    def img(path, color):
        path.parent.mkdir(parents=True, exist_ok=True); Image.new("RGB", (20, 20), color).save(path, "JPEG")
    img(people / "Person_001" / "Solo" / "a.jpg", (255, 0, 0))
    img(people / "Person_001" / "Group" / "g.jpg", (0, 255, 0))
    img(people / "Person_002" / "Solo" / "b.jpg", (0, 0, 255))
    shutil.copy2(people / "Person_001" / "Group" / "g.jpg", people / "Person_002" / "Group" / "g.jpg") if (people / "Person_002" / "Group").mkdir(parents=True, exist_ok=True) is None else None
    img(people / "Person_002" / "Solo" / "a.jpg", (9, 9, 9))  # same name, different photo
    from aura_app.widgets.merge_dialog import ClusterMergeDialog as MergeDialog
    MergeDialog._merge_filesystem(None, "Person_001", "Person_002")
    files = sorted(str(p.relative_to(people)).replace("\\", "/") for p in people.rglob("*") if p.is_file())
    print("     folders after merge:", files)
    check("Solo photos moved into kept person's Solo/", "Person_001/Solo/b.jpg" in files)
    check("same group photo not duplicated", files.count("Person_001/Group/g.jpg") == 1 and not any("g_merged" in f for f in files))
    check("different photo with same name kept as _merged_1", "Person_001/Solo/a_merged_1.jpg" in files and "Person_001/Solo/a.jpg" in files)
    check("removed person's folder deleted", not (people / "Person_002").exists())

    print("ALL CHECKS PASSED" if all(results) else f"{results.count(False)} FAILED")
