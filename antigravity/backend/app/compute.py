"""
Compute device selection for face detection/recognition (added 2026-11-14).

Replaces the old CUDA setup wizard (gpu_manager.py / gpu_wizard.py, now in
_archive_cuda_gpu/). Users install nothing extra:

  * AURA ships onnxruntime-directml. DirectML is part of Windows and runs on
    NVIDIA (RTX/GTX), AMD and Intel graphics. It also contains the normal
    CPU engine.
  * COMPUTE_DEVICE in .env: "auto" (default), "gpu" or "cpu".
  * auto: a short speed test compares the graphics card with the processor
    on this PC and keeps the faster one. The result is cached in
    <user data>/compute_choice.json and redone when the graphics hardware
    or the engine version changes. The test runs in a separate process
    (run_pyside.py --benchmark-compute), so a broken graphics driver can
    only crash the test, never AURA; a failed test means CPU.
  * If the GPU fails during processing, processor.py switches to CPU.

Measured on an Intel Core Ultra 5 125H (Intel Arc graphics), 2048 px event
photos with 6 faces, 4 worker threads:
    old setup (CPU, 5 models, every thread on all cores)   17.4 s per photo
    CPU, 2 models, cores split between threads               1.9 s per photo
    DirectML on the built-in Intel Arc                       0.23 s per photo
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DML = "DmlExecutionProvider"
CPU = "CPUExecutionProvider"

# Only these InsightFace models are used (face box, score, embedding).
# buffalo_l also ships age/gender and two landmark models that ran for every
# face and were never used; skipping them roughly halves CPU time.
FACE_MODULES = ["detection", "recognition"]

# Ask DirectML for the high-performance adapter so laptops with a gaming GPU
# use it instead of the built-in graphics.
DML_PROVIDER_OPTIONS = {"device_id": "0", "performance_preference": "high_performance"}

_CHOICE_FILE = "compute_choice.json"
_BENCH_TIMEOUT_S = 180


@dataclass
class ComputePlan:
    """How this process should run the face models."""
    device: str                      # "gpu" or "cpu"
    providers: list
    provider_options: Optional[list]
    ctx_id: int                      # InsightFace: >=0 keeps GPU, -1 forces CPU
    intra_op_threads: Optional[int]  # CPU threads per model session
    shared_analyzer: bool            # one analyzer for all threads (GPU)
    label: str                       # shown to the user
    reason: str = ""

    def session_options(self):
        import onnxruntime as ort
        so = ort.SessionOptions()
        if self.intra_op_threads:
            so.intra_op_num_threads = self.intra_op_threads
        if self.device == "gpu":
            # Required by the DirectML engine
            so.enable_mem_pattern = False
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return so


@dataclass
class ComputeChoice:
    """Cached result of the speed test."""
    device: str                     # "gpu" or "cpu"
    gpu_name: str
    gpus: list
    ort_version: str
    gpu_ms: Optional[float] = None
    cpu_ms: Optional[float] = None
    note: str = ""
    tested_at: str = ""
    extra: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────
# Hardware facts
# ─────────────────────────────────────────────────────────

def dml_available() -> bool:
    try:
        import onnxruntime as ort
        return DML in ort.get_available_providers()
    except Exception:
        return False


def ort_version() -> str:
    try:
        import onnxruntime as ort
        return ort.__version__
    except Exception:
        return "none"


_gpu_names_cache: Optional[list] = None


def gpu_names() -> list:
    """Names of the graphics adapters Windows reports (cached per process)."""
    global _gpu_names_cache
    if _gpu_names_cache is not None:
        return _gpu_names_cache
    names = []
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController).Name"],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).stdout
            names = [n.strip() for n in out.splitlines()
                     if n.strip() and "basic display" not in n.lower()
                     and "remote" not in n.lower()]
        except Exception as e:
            logger.debug(f"GPU name lookup failed: {e}")
    _gpu_names_cache = names
    return names


def preferred_gpu_name(names: Optional[list] = None) -> str:
    """The adapter DirectML's high-performance choice will most likely use."""
    names = gpu_names() if names is None else names
    if not names:
        return ""
    def score(n: str) -> int:
        n = n.lower()
        if any(k in n for k in ("nvidia", "geforce", "rtx", "quadro")):
            return 3
        if "radeon" in n and "graphics" not in n:   # discrete AMD (e.g. "Radeon RX 7600")
            return 2
        if "arc(tm) a" in n or "arc a" in n:       # discrete Intel Arc A-series
            return 2
        return 1
    return max(names, key=score)


def cpu_threads() -> int:
    return os.cpu_count() or 4


# ─────────────────────────────────────────────────────────
# Settings and cached choice
# ─────────────────────────────────────────────────────────

def requested_device() -> str:
    value = os.getenv("COMPUTE_DEVICE", "auto").strip().lower()
    return value if value in ("auto", "gpu", "cpu") else "auto"


def _choice_path() -> Path:
    import dist_utils
    return dist_utils.get_user_data_dir() / _CHOICE_FILE


def load_choice() -> Optional[ComputeChoice]:
    try:
        data = json.loads(_choice_path().read_text(encoding="utf-8"))
        return ComputeChoice(**data)
    except Exception:
        return None


def save_choice(choice: ComputeChoice) -> None:
    path = _choice_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(choice), indent=2), encoding="utf-8")


def choice_is_current(choice: Optional[ComputeChoice]) -> bool:
    """A cached test result is reused only for the same hardware and engine."""
    return (choice is not None
            and choice.ort_version == ort_version()
            and sorted(choice.gpus) == sorted(gpu_names()))


# ─────────────────────────────────────────────────────────
# Speed test
# ─────────────────────────────────────────────────────────

def _bench_image():
    """A 2048 px test image with real faces if available, else plain noise."""
    import numpy as np
    import cv2
    candidates = []
    try:
        import insightface
        candidates.append(Path(insightface.__file__).parent / "data" / "images" / "t1.jpg")
    except Exception:
        pass
    for p in candidates:
        img = cv2.imread(str(p))
        if img is not None:
            h, w = img.shape[:2]
            s = 2048 / max(h, w)
            return cv2.resize(img, (int(w * s), int(h * s)))
    rng = np.random.default_rng(0)
    return rng.integers(0, 255, size=(1417, 2048, 3), dtype=np.uint8)


def _time_plan(plan: ComputePlan, img, runs: int = 4) -> float:
    """Milliseconds per image for one analyzer built from `plan`."""
    from .processor import build_face_analyzer
    analyzer = build_face_analyzer(plan)
    analyzer.get(img)  # warm-up (first GPU run compiles shaders)
    t0 = time.perf_counter()
    for _ in range(runs):
        analyzer.get(img)
    return (time.perf_counter() - t0) / runs * 1000


def run_speed_test() -> ComputeChoice:
    """Measure GPU vs CPU in THIS process. Prefer benchmark_in_subprocess()."""
    import datetime
    names = gpu_names()
    choice = ComputeChoice(device="cpu", gpu_name=preferred_gpu_name(names), gpus=names,
                           ort_version=ort_version(),
                           tested_at=datetime.datetime.now().isoformat(timespec="seconds"))
    img = _bench_image()
    workers = _worker_count()

    cpu_plan = cpu_plan_for(workers)
    # A CPU worker runs `workers` analyzers side by side; compare per-photo
    # throughput, i.e. single-analyzer time divided by the worker count.
    choice.cpu_ms = round(_time_plan(cpu_plan, img) / workers, 1)

    if not dml_available():
        choice.note = "No DirectML engine in this build"
        return choice
    try:
        choice.gpu_ms = round(_time_plan(gpu_plan(), img), 1)
    except Exception as e:
        choice.note = f"Graphics card test failed: {e}"
        return choice

    # Keep the GPU only if it is clearly faster (10% margin)
    if choice.gpu_ms < choice.cpu_ms * 0.9:
        choice.device = "gpu"
    return choice


def benchmark_in_subprocess(on_done: Optional[Callable[[ComputeChoice], None]] = None) -> ComputeChoice:
    """Run the speed test in a separate process, save and return the result.

    A crash or hang in the graphics driver only affects the child process;
    the result is then "cpu".
    """
    import datetime
    import dist_utils
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--benchmark-compute"]
    else:
        cmd = [sys.executable, str(dist_utils.get_project_root() / "run_pyside.py"), "--benchmark-compute"]

    names = gpu_names()
    fallback = ComputeChoice(device="cpu", gpu_name=preferred_gpu_name(names), gpus=names,
                             ort_version=ort_version(),
                             tested_at=datetime.datetime.now().isoformat(timespec="seconds"))
    try:
        proc = subprocess.run(
            cmd, cwd=str(dist_utils.get_project_root()), timeout=_BENCH_TIMEOUT_S,
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        choice = load_choice()
        if proc.returncode != 0 or not choice_is_current(choice):
            fallback.note = f"Speed test did not finish (exit code {proc.returncode}); using the processor"
            choice = fallback
            save_choice(choice)
    except subprocess.TimeoutExpired:
        fallback.note = "Speed test timed out; using the processor"
        choice = fallback
        save_choice(choice)
    except Exception as e:
        fallback.note = f"Speed test could not run ({e}); using the processor"
        choice = fallback
        save_choice(choice)

    logger.info(f"Compute speed test: device={choice.device} gpu={choice.gpu_name!r} "
                f"gpu_ms={choice.gpu_ms} cpu_ms={choice.cpu_ms} {choice.note}")
    if on_done:
        on_done(choice)
    return choice


def benchmark_cli() -> int:
    """Entry point for `run_pyside.py --benchmark-compute` (child process)."""
    choice = run_speed_test()
    save_choice(choice)
    return 0


# ─────────────────────────────────────────────────────────
# Plans
# ─────────────────────────────────────────────────────────

def _worker_count() -> int:
    try:
        from .config import get_config
        return max(1, get_config().worker_count)
    except Exception:
        return 4


def cpu_plan_for(workers: Optional[int] = None, reason: str = "") -> ComputePlan:
    workers = workers or _worker_count()
    threads = max(1, cpu_threads() // workers)
    return ComputePlan(
        device="cpu", providers=[CPU], provider_options=None, ctx_id=-1,
        intra_op_threads=threads, shared_analyzer=False,
        label=f"Processor (CPU, {cpu_threads()} threads)", reason=reason,
    )


def gpu_plan(gpu_name: str = "", reason: str = "") -> ComputePlan:
    return ComputePlan(
        device="gpu", providers=[DML, CPU],
        provider_options=[dict(DML_PROVIDER_OPTIONS), {}], ctx_id=0,
        intra_op_threads=None, shared_analyzer=True,
        label=f"Graphics card ({gpu_name or preferred_gpu_name() or 'DirectML'})", reason=reason,
    )


def get_plan(run_test_if_needed: bool = True) -> ComputePlan:
    """Decide CPU or GPU for this process (call once, then reuse)."""
    wanted = requested_device()
    if wanted == "cpu":
        return cpu_plan_for(reason="Set to processor in Settings")
    if not dml_available():
        return cpu_plan_for(reason="Graphics card engine not available")
    if wanted == "gpu":
        return gpu_plan(reason="Set to graphics card in Settings")

    choice = load_choice()
    if not choice_is_current(choice):
        if not run_test_if_needed:
            return cpu_plan_for(reason="Speed test not run yet")
        logger.info("Running the one-time GPU vs CPU speed test...")
        choice = benchmark_in_subprocess()
    if choice.device == "gpu":
        return gpu_plan(choice.gpu_name,
                        reason=f"Speed test: graphics {choice.gpu_ms} ms vs processor {choice.cpu_ms} ms per photo")
    return cpu_plan_for(reason=choice.note or
                        f"Speed test: processor {choice.cpu_ms} ms vs graphics {choice.gpu_ms} ms per photo")


def describe_current() -> dict:
    """Snapshot for the UI: what is (or will be) used, without running tests."""
    plan = get_plan(run_test_if_needed=False)
    choice = load_choice()
    return {
        "setting": requested_device(),
        "device": plan.device,
        "label": plan.label,
        "reason": plan.reason,
        "gpus": gpu_names(),
        "gpu_name": preferred_gpu_name(),
        "dml_available": dml_available(),
        "tested": choice_is_current(choice),
        "gpu_ms": choice.gpu_ms if choice else None,
        "cpu_ms": choice.cpu_ms if choice else None,
    }
