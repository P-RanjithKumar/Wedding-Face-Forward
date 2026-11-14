"""Benchmark face detection+embedding setups (CPU vs DirectML) on this PC."""
import os, sys, time, threading, contextlib, io
import numpy as np, cv2
import onnxruntime as ort
from insightface.app import FaceAnalysis
from insightface.model_zoo import model_zoo as mz

SAMPLE = sys.argv[1]
ROOT = os.path.expanduser("~/.insightface")
WORKERS, N_IMAGES = 4, 24

base = cv2.imread(SAMPLE)
h, w = base.shape[:2]
s = 2048 / max(h, w)
big = cv2.resize(base, (int(w * s), int(h * s)), interpolation=cv2.INTER_CUBIC)
images = [big if i % 2 == 0 else cv2.flip(big, 1) for i in range(N_IMAGES)]

_sess_opts_factory = None
_orig_init = mz.PickableInferenceSession.__init__
def _patched(self, model_path, **kw):
    if _sess_opts_factory is not None and "sess_options" not in kw:
        kw["sess_options"] = _sess_opts_factory()
    _orig_init(self, model_path, **kw)
mz.PickableInferenceSession.__init__ = _patched


def make_analyzer(providers, modules, intra_threads=None, dml=False):
    global _sess_opts_factory
    def factory():
        so = ort.SessionOptions()
        if intra_threads:
            so.intra_op_num_threads = intra_threads
        if dml:
            so.enable_mem_pattern = False
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return so
    _sess_opts_factory = factory
    with contextlib.redirect_stdout(io.StringIO()):
        fa = FaceAnalysis(name="buffalo_l", root=ROOT, providers=providers, allowed_modules=modules)
        fa.prepare(ctx_id=0 if dml else -1, det_size=(640, 640))
    _sess_opts_factory = None
    return fa


def run(label, providers, modules, intra=None, dml=False, shared=False):
    t_load = time.time()
    if shared:
        one = make_analyzer(providers, modules, intra, dml)
        analyzers = [one] * WORKERS
    else:
        analyzers = [make_analyzer(providers, modules, intra, dml) for _ in range(WORKERS)]
    load = time.time() - t_load
    lock = threading.Lock() if (shared and dml) else contextlib.nullcontext()
    analyzers[0].get(images[0])  # warm-up
    results = [None] * N_IMAGES

    def work(k):
        for i in range(k, N_IMAGES, WORKERS):
            with lock:
                results[i] = analyzers[k].get(images[i])

    t0 = time.time()
    ts = [threading.Thread(target=work, args=(k,)) for k in range(WORKERS)]
    [t.start() for t in ts]; [t.join() for t in ts]
    dt = time.time() - t0
    faces = len(results[0])
    print(f"{label:<58} {dt / N_IMAGES * 1000:7.0f} ms/photo  ({N_IMAGES / dt:5.2f} photos/s)  load {load:4.1f}s  faces/photo={faces}", flush=True)
    return results


cores = os.cpu_count()
print(f"CPU threads: {cores}, workers: {WORKERS}, photo {big.shape[1]}x{big.shape[0]}, providers: {ort.get_available_providers()}\n")
CPU = ["CPUExecutionProvider"]
DML = ["DmlExecutionProvider", "CPUExecutionProvider"]
DR = ["detection", "recognition"]

r_now = run("1. TODAY: CPU, 5 models, per-thread, all cores each", CPU, None)
r2 = run("2. CPU, det+rec only, per-thread, all cores each", CPU, DR)
r3 = run(f"3. CPU, det+rec only, per-thread, {max(1, cores // WORKERS)} threads each", CPU, DR, intra=max(1, cores // WORKERS))
r4 = run("3b. CPU, det+rec only, ONE shared analyzer, all cores", CPU, DR, shared=True)
if "DmlExecutionProvider" in ort.get_available_providers():
    r5 = run("4. DirectML GPU, det+rec, ONE shared analyzer (locked)", DML, DR, dml=True, shared=True)
    r6 = run("5. DirectML GPU, det+rec, per-thread sessions", DML, DR, dml=True)

    def emb_sim(a, b):
        sims = []
        for fa, fb in zip(sorted(a, key=lambda f: tuple(f.bbox)), sorted(b, key=lambda f: tuple(f.bbox))):
            ea, eb = fa.embedding / np.linalg.norm(fa.embedding), fb.embedding / np.linalg.norm(fb.embedding)
            sims.append(float(ea @ eb))
        return min(sims) if sims else None
    print(f"\nGPU vs CPU: faces {len(r5[0])} vs {len(r_now[0])}, lowest embedding similarity {emb_sim(r5[0], r_now[0]):.5f}")
print(f"det+rec vs 5 models: lowest embedding similarity {min(float((a.embedding/np.linalg.norm(a.embedding)) @ (b.embedding/np.linalg.norm(b.embedding))) for a, b in zip(sorted(r2[0], key=lambda f: tuple(f.bbox)), sorted(r_now[0], key=lambda f: tuple(f.bbox)))):.5f}")
