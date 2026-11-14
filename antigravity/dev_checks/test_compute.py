"""Tests for backend/app/compute.py + processor.py (run with the DirectML venv)."""
import os, sys, time, threading, json, shutil, warnings
warnings.filterwarnings("ignore")
from pathlib import Path

PROJ = Path(sys.argv[1]).resolve()
SAMPLE = Path(sys.argv[2])
WORK = Path(sys.argv[3]) / "t_compute"
shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir(parents=True)
sys.path[:0] = [str(PROJ), str(PROJ / "backend")]
os.chdir(PROJ)

import cv2
big = cv2.imread(str(SAMPLE)); h, w = big.shape[:2]; s = 2048 / max(h, w)
big = cv2.resize(big, (int(w * s), int(h * s)))
img_path = WORK / "group.jpg"; cv2.imwrite(str(img_path), big)

import dist_utils
from app import compute, processor

results = []
def check(name, cond, extra=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)

def reset_processor():
    processor._plan = None
    processor._shared_analyzer = None
    processor._thread_local = threading.local()

check("DirectML engine available in test env", compute.dml_available(), compute.ort_version())
check("graphics adapters detected", compute.gpu_names(), ", ".join(compute.gpu_names()))

# Settings
os.environ["COMPUTE_DEVICE"] = "cpu"
p = compute.get_plan()
check("COMPUTE_DEVICE=cpu -> CPU plan", p.device == "cpu" and p.providers == ["CPUExecutionProvider"], f"{p.intra_op_threads} threads/worker")
os.environ["COMPUTE_DEVICE"] = "gpu"
p = compute.get_plan()
check("COMPUTE_DEVICE=gpu -> DirectML plan, shared analyzer", p.device == "gpu" and p.providers[0] == "DmlExecutionProvider" and p.shared_analyzer)
os.environ["COMPUTE_DEVICE"] = "nonsense"
check("unknown setting falls back to auto", compute.requested_device() == "auto")

# Speed test in a separate process
os.environ["COMPUTE_DEVICE"] = "auto"
choice_file = dist_utils.get_user_data_dir() / "compute_choice.json"
backup = choice_file.read_text() if choice_file.exists() else None
choice_file.unlink(missing_ok=True)
check("describe_current before test: not tested, no test run", compute.describe_current()["tested"] is False)
t0 = time.time()
ch = compute.benchmark_in_subprocess()
check("speed test ran in a subprocess and saved a current result",
      compute.choice_is_current(compute.load_choice()) and ch.cpu_ms and ch.gpu_ms,
      f"gpu {ch.gpu_ms} ms, cpu {ch.cpu_ms} ms/photo -> {ch.device}, {time.time() - t0:.0f}s {ch.note}")
plan = compute.get_plan()
check("auto uses the speed test result", plan.device == ch.device, plan.reason)

# Real detection with each plan
for dev in ("cpu", "gpu"):
    os.environ["COMPUTE_DEVICE"] = dev
    reset_processor()
    t0 = time.time()
    faces = processor.detect_faces(img_path)
    check(f"detect_faces on {dev}: 6 faces", len(faces) == 6, f"{time.time() - t0:.1f}s incl. load")

# 4 threads at once on GPU (per-thread DirectML sessions segfault; shared+lock must not)
os.environ["COMPUTE_DEVICE"] = "gpu"
reset_processor()
counts, errs = [], []
def work():
    try:
        for _ in range(4):
            counts.append(len(processor.detect_faces(img_path)))
    except Exception as e:
        errs.append(repr(e))
ts = [threading.Thread(target=work) for _ in range(4)]
t0 = time.time(); [t.start() for t in ts]; [t.join() for t in ts]
check("4 threads share the GPU safely (16 photos)", not errs and counts == [6] * 16, f"{(time.time() - t0) / 16 * 1000:.0f} ms/photo")

# GPU failure mid-run -> CPU fallback, same result
reset_processor()
processor.detect_faces(img_path)
class Broken:
    def get(self, img): raise RuntimeError("simulated GPU driver error")
processor._shared_analyzer = Broken()
faces = processor.detect_faces(img_path)
check("GPU error -> switches to CPU and still finds 6 faces",
      len(faces) == 6 and processor.get_compute_plan().device == "cpu", processor.get_compute_plan().reason)

# Restore the real cached choice for the dev setup
if backup is not None:
    choice_file.write_text(backup)
print("ALL CHECKS PASSED" if all(results) else f"{results.count(False)} FAILED")
