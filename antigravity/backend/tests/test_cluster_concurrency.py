"""
Regression tests for the clustering race and atomic merge (fixed 2026-11-14).

Before the fix, worker threads clustering at the same time created duplicate
people for one guest, reused Person_NNN names and lost face_count updates
(8 threads x 40 faces of 6 people gave 10 people and 167/320 faces).
Merging a person with a guest enrollment half-failed on the foreign key.
"""

import sys
import threading
from pathlib import Path

import numpy as np
import pytest

# assign_person reads the app config, which imports dist_utils from the
# project root (one level above backend/).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app.db as app_db
from app.cluster import assign_person, merge_persons
from app.config import reset_config
from app.db import Database

K, THREADS, PER_THREAD, DIM = 6, 8, 40, 512


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Fresh database used by cluster.get_db() for this test."""
    reset_config()
    database = Database(tmp_path / "test.db")
    database.initialize()
    monkeypatch.setattr(app_db, "_db", database)
    yield database


def _identities(seed=0):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(K, DIM))
    return base / np.linalg.norm(base, axis=1, keepdims=True)


def _noisy(base, rng):
    noise = rng.normal(size=DIM)
    v = base + noise * (0.3 / np.linalg.norm(noise))
    return (v / np.linalg.norm(v)).astype(np.float32)


def test_parallel_clustering_creates_one_person_per_identity(db):
    base = _identities()
    barrier = threading.Barrier(THREADS)
    errors = []

    def work(t):
        rng = np.random.default_rng(100 + t)
        jobs = [_noisy(base[(t + i) % K], rng) for i in range(PER_THREAD)]
        barrier.wait()  # start all threads at the same moment
        try:
            for emb in jobs:
                assign_person(emb, 0.6)
        except Exception as ex:  # pragma: no cover - reported below
            errors.append(repr(ex))

    threads = [threading.Thread(target=work, args=(t,)) for t in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = db.connect().execute("SELECT name, face_count FROM persons").fetchall()
    names = [r["name"] for r in rows]
    assert not errors
    assert len(rows) == K                                   # no duplicate people
    assert len(set(names)) == len(names)                    # no duplicate names
    assert sum(r["face_count"] for r in rows) == THREADS * PER_THREAD  # no lost updates


def test_assign_person_links_face_in_same_step(db):
    photo = db.create_photo("hash1", "a.jpg")
    emb = _noisy(_identities()[0], np.random.default_rng(1))
    face = db.create_face(photo, (0, 0, 10, 10), emb, 0.99)
    person = assign_person(emb, 0.6, face_id=face)
    linked = db.connect().execute("SELECT person_id FROM faces WHERE id = ?", (face,)).fetchone()[0]
    assert linked == person


def test_write_transaction_rolls_back_on_error(db):
    db.create_person("Person_001", np.ones(DIM, dtype=np.float32))
    with pytest.raises(RuntimeError):
        with db.write_transaction() as conn:
            conn.execute("UPDATE persons SET face_count = 999")
            raise RuntimeError("simulated crash")
    assert db.connect().execute("SELECT face_count FROM persons").fetchone()[0] == 1


def test_merge_moves_faces_and_enrollments_atomically(db):
    base, rng = _identities(), np.random.default_rng(3)
    photo = db.create_photo("hash2", "b.jpg")
    face_a = db.create_face(photo, (0, 0, 1, 1), _noisy(base[0], rng), 0.9)
    face_b = db.create_face(photo, (0, 0, 1, 1), _noisy(base[1], rng), 0.9)
    a = assign_person(_noisy(base[0], rng), 0.6, face_id=face_a)
    b = assign_person(_noisy(base[1], rng), 0.6, face_id=face_b)
    db.create_enrollment(b, "Guest B", "selfie.jpg", 0.9, phone="1")

    assert merge_persons(a, b) is True

    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM persons WHERE id = ?", (b,)).fetchone()[0] == 0
    assert conn.execute("SELECT person_id FROM faces WHERE id = ?", (face_b,)).fetchone()[0] == a
    assert conn.execute("SELECT person_id FROM enrollments").fetchone()[0] == a
    assert conn.execute("SELECT face_count FROM persons WHERE id = ?", (a,)).fetchone()[0] == 2


def test_merge_rejects_unknown_or_same_person(db):
    a = assign_person(_noisy(_identities()[0], np.random.default_rng(4)), 0.6)
    assert merge_persons(a, 999) is False
    assert merge_persons(a, a) is False
    assert db.connect().execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 1
