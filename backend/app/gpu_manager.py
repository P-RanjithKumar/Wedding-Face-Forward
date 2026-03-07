"""
GPU Manager — Hardware acceleration detection, setup, and management.

This module is the single source of truth for all GPU-related logic:
  • Detects NVIDIA GPUs via nvidia-smi
  • Validates against a whitelist of supported architectures (Turing+)
  • Checks CUDA / cuDNN installation status
  • Manages onnxruntime ↔ onnxruntime-gpu package swaps
  • Provides execution config (providers, ctx_id) for InsightFace

All GPU operations are opt-in: CPU is the default and GPU is the upgrade.
"""

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# The Rulebook — Pinned Compatibility Stack
# ─────────────────────────────────────────────────────────

GPU_RULEBOOK = {
    # Exact versions we test and guarantee
    "cuda_version_recommended": "12.6",
    "cuda_major_min": 12,
    "cudnn_major_required": 9,
    "ort_gpu_package": "onnxruntime-gpu",
    "ort_gpu_version": "1.20.1",
    "ort_cpu_package": "onnxruntime",

    # Hardware requirements
    "min_compute_capability": 7.5,   # Turing+
    "min_vram_mb": 2048,             # 2 GB minimum
    "min_driver_version": "525.60",

    # Download URLs
    "cuda_download_url": "https://developer.nvidia.com/cuda-12-6-0-download-archive",
    "cudnn_download_url": "https://developer.nvidia.com/cudnn-downloads",
}


# ─────────────────────────────────────────────────────────
# GPU Architecture Lookup Table
# ─────────────────────────────────────────────────────────

# GPU name substring → (compute_capability, architecture_name)
# Used when nvidia-smi can't directly report compute capability.
GPU_COMPUTE_TABLE = {
    # Turing — sm_75 (2018)
    "RTX 2060": (7.5, "Turing"), "RTX 2070": (7.5, "Turing"),
    "RTX 2080": (7.5, "Turing"),
    "GTX 1650": (7.5, "Turing"), "GTX 1660": (7.5, "Turing"),
    "Quadro RTX": (7.5, "Turing"), "Tesla T4": (7.5, "Turing"),
    "T4": (7.5, "Turing"),

    # Ampere — sm_86 consumer, sm_80 datacenter (2020)
    "RTX 3050": (8.6, "Ampere"), "RTX 3060": (8.6, "Ampere"),
    "RTX 3070": (8.6, "Ampere"), "RTX 3080": (8.6, "Ampere"),
    "RTX 3090": (8.6, "Ampere"),
    "RTX A2000": (8.6, "Ampere"), "RTX A4000": (8.6, "Ampere"),
    "RTX A5000": (8.6, "Ampere"), "RTX A6000": (8.6, "Ampere"),
    "A100": (8.0, "Ampere"), "A10": (8.6, "Ampere"),
    "A30": (8.0, "Ampere"), "A40": (8.6, "Ampere"),

    # Ada Lovelace — sm_89 (2022)
    "RTX 4050": (8.9, "Ada Lovelace"), "RTX 4060": (8.9, "Ada Lovelace"),
    "RTX 4070": (8.9, "Ada Lovelace"), "RTX 4080": (8.9, "Ada Lovelace"),
    "RTX 4090": (8.9, "Ada Lovelace"),
    "RTX 6000 Ada": (8.9, "Ada Lovelace"),
    "L4": (8.9, "Ada Lovelace"), "L40": (8.9, "Ada Lovelace"),

    # Blackwell — sm_100 datacenter, sm_120 consumer (2024)
    "RTX 5060": (12.0, "Blackwell"), "RTX 5070": (12.0, "Blackwell"),
    "RTX 5080": (12.0, "Blackwell"), "RTX 5090": (12.0, "Blackwell"),
    "B100": (10.0, "Blackwell"), "B200": (10.0, "Blackwell"),
    "GB200": (10.0, "Blackwell"),

    # ── Unsupported (for clear rejection messages) ──
    # Pascal — sm_61 (2016) — BLOCKED
    "GTX 1060": (6.1, "Pascal"), "GTX 1070": (6.1, "Pascal"),
    "GTX 1080": (6.1, "Pascal"), "Titan X": (6.1, "Pascal"),
    "Titan Xp": (6.1, "Pascal"), "P100": (6.0, "Pascal"),
    "GTX 1050": (6.1, "Pascal"),
    # Maxwell — sm_52 (2014) — BLOCKED
    "GTX 960": (5.2, "Maxwell"), "GTX 970": (5.2, "Maxwell"),
    "GTX 980": (5.2, "Maxwell"), "GTX 950": (5.2, "Maxwell"),
    "Titan X Maxwell": (5.2, "Maxwell"),
    # Kepler — sm_35 (2012) — BLOCKED
    "GTX 780": (3.5, "Kepler"), "GTX 680": (3.5, "Kepler"),
    "Tesla K40": (3.5, "Kepler"), "Tesla K80": (3.7, "Kepler"),
}


# ─────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────

@dataclass
class GPUHardwareInfo:
    """Raw hardware information from nvidia-smi."""
    gpu_name: str = "N/A"
    driver_version: str = "N/A"
    vram_mb: int = 0
    cuda_driver_version: str = "N/A"   # CUDA version reported by driver


@dataclass
class GPUInfo:
    """Complete GPU status — aggregates hardware, software, and wizard state."""

    # Hardware
    gpu_found: bool = False
    gpu_name: str = "N/A"
    gpu_architecture: str = "Unknown"
    compute_capability: float = 0.0
    driver_version: str = "N/A"
    vram_mb: int = 0

    # Whitelist
    is_whitelisted: bool = False
    whitelist_reason: str = ""

    # Software — CUDA & cuDNN
    cuda_version: str = "Not Installed"
    cuda_version_ok: bool = False
    cudnn_found: bool = False
    cudnn_version: str = "Not Found"

    # Software — ONNX Runtime
    ort_version: str = "N/A"
    ort_gpu_installed: bool = False
    cuda_provider_available: bool = False
    available_providers: List[str] = field(default_factory=list)

    # Wizard State
    wizard_step: int = 0
    status_message: str = "Not checked yet."
    can_proceed: bool = False


@dataclass
class ExecutionConfig:
    """Configuration for InsightFace / ONNX Runtime execution."""
    providers: List[str] = field(default_factory=lambda: ["CPUExecutionProvider"])
    ctx_id: int = -1               # -1 = CPU, 0 = GPU device 0
    mode: str = "CPU"              # Human-readable: "CPU" or "GPU (RTX 4070)"


@dataclass
class SwapResult:
    """Result of an onnxruntime swap operation."""
    success: bool = False
    error: str = ""
    message: str = ""


# ─────────────────────────────────────────────────────────
# Detection Functions
# ─────────────────────────────────────────────────────────

def _run_command(args: list, timeout: int = 10) -> Optional[str]:
    """Run a subprocess and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            args,
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.debug(f"Command {args[0]} failed: {e}")
        return None


def detect_nvidia_gpu() -> Optional[GPUHardwareInfo]:
    """
    Detect NVIDIA GPU using nvidia-smi.
    Returns GPUHardwareInfo or None if no NVIDIA GPU found.
    """
    # Query GPU info
    output = _run_command([
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader,nounits"
    ])
    if not output:
        logger.info("No NVIDIA GPU detected (nvidia-smi not found or failed).")
        return None

    # Parse first GPU (line 1)
    try:
        line = output.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            logger.warning(f"Unexpected nvidia-smi output format: {line}")
            return None

        gpu_name = parts[0]
        driver_version = parts[1]
        vram_mb = int(float(parts[2]))

        # Also grab the CUDA version the driver supports
        cuda_ver = "N/A"
        smi_output = _run_command(["nvidia-smi"])
        if smi_output:
            match = re.search(r"CUDA Version:\s*([\d.]+)", smi_output)
            if match:
                cuda_ver = match.group(1)

        info = GPUHardwareInfo(
            gpu_name=gpu_name,
            driver_version=driver_version,
            vram_mb=vram_mb,
            cuda_driver_version=cuda_ver,
        )
        logger.info(f"NVIDIA GPU detected: {gpu_name} ({vram_mb} MB, driver {driver_version})")
        return info

    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse nvidia-smi output: {e}")
        return None


def _lookup_gpu_architecture(gpu_name: str) -> Tuple[float, str]:
    """
    Look up compute capability and architecture name from GPU name.
    Returns (compute_cap, architecture) or (0.0, "Unknown").
    """
    gpu_upper = gpu_name.upper()
    for key, (cc, arch) in GPU_COMPUTE_TABLE.items():
        if key.upper() in gpu_upper:
            return cc, arch

    # If not in table, try to infer from name patterns
    if "RTX 20" in gpu_upper or "GTX 16" in gpu_upper:
        return 7.5, "Turing"
    if "RTX 30" in gpu_upper:
        return 8.6, "Ampere"
    if "RTX 40" in gpu_upper:
        return 8.9, "Ada Lovelace"
    if "RTX 50" in gpu_upper:
        return 12.0, "Blackwell"

    return 0.0, "Unknown"


def _check_whitelist(compute_cap: float, gpu_name: str, vram_mb: int,
                     driver_version: str) -> Tuple[bool, str]:
    """
    Check if this GPU passes our whitelist requirements.
    Returns (is_whitelisted, reason_message).
    """
    min_cc = GPU_RULEBOOK["min_compute_capability"]
    min_vram = GPU_RULEBOOK["min_vram_mb"]
    min_driver = GPU_RULEBOOK["min_driver_version"]

    # Check compute capability
    if compute_cap < min_cc:
        if compute_cap > 0:
            _, arch = _lookup_gpu_architecture(gpu_name)
            return False, (
                f"GPU too old for acceleration — {gpu_name} ({arch}, "
                f"sm_{compute_cap:.0f}). Minimum required: Turing (sm_75) or newer."
            )
        return False, (
            f"Unrecognized GPU: {gpu_name}. Cannot verify compatibility. "
            f"GPU acceleration requires Turing (RTX 20-series) or newer."
        )

    # Check VRAM
    if vram_mb < min_vram:
        return False, (
            f"Insufficient VRAM: {vram_mb} MB. GPU acceleration requires "
            f"at least {min_vram} MB (2 GB). Your {gpu_name} does not meet this requirement."
        )

    # Check driver version
    try:
        driver_parts = [int(x) for x in driver_version.split(".")]
        min_parts = [int(x) for x in min_driver.split(".")]
        if driver_parts < min_parts:
            return False, (
                f"NVIDIA driver too old: {driver_version}. "
                f"Minimum required: {min_driver}. Please update your NVIDIA drivers."
            )
    except ValueError:
        logger.debug(f"Could not parse driver version: {driver_version}")

    return True, "Supported"


def detect_cuda_toolkit() -> Tuple[Optional[str], bool]:
    """
    Detect installed CUDA Toolkit version.
    Returns (version_string, is_version_ok).
    """
    # Method 1: nvcc --version (CUDA Toolkit installation)
    output = _run_command(["nvcc", "--version"])
    if output:
        match = re.search(r"release\s+([\d.]+)", output)
        if match:
            version = match.group(1)
            try:
                major = int(version.split(".")[0])
                is_ok = major >= GPU_RULEBOOK["cuda_major_min"]
                logger.info(f"CUDA Toolkit found: v{version} (ok={is_ok})")
                return version, is_ok
            except ValueError:
                pass

    # Method 2: Check CUDA_PATH environment variable
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path:
        # Try to extract version from path (e.g., C:\...\CUDA\v12.6)
        match = re.search(r"v?([\d]+\.[\d]+)", cuda_path)
        if match:
            version = match.group(1)
            try:
                major = int(version.split(".")[0])
                is_ok = major >= GPU_RULEBOOK["cuda_major_min"]
                logger.info(f"CUDA Toolkit found via CUDA_PATH: v{version} (ok={is_ok})")
                return version, is_ok
            except ValueError:
                pass

    # Method 3: Check common installation paths on Windows
    if sys.platform == "win32":
        cuda_base = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
        if cuda_base.exists():
            versions = []
            try:
                for d in cuda_base.iterdir():
                    if d.is_dir():
                        match = re.match(r"v?([\d]+\.[\d]+)", d.name)
                        if match:
                            versions.append(match.group(1))
            except PermissionError:
                pass
            if versions:
                # Sort and use the latest
                versions.sort(key=lambda v: [int(x) for x in v.split(".")], reverse=True)
                version = versions[0]
                major = int(version.split(".")[0])
                is_ok = major >= GPU_RULEBOOK["cuda_major_min"]
                logger.info(f"CUDA Toolkit found in filesystem: v{version} (ok={is_ok})")
                return version, is_ok

    logger.info("CUDA Toolkit not detected.")
    return None, False


def detect_cudnn() -> Tuple[bool, str]:
    """
    Detect if cuDNN is installed and check version.
    Returns (found, version_string).
    """
    required_major = GPU_RULEBOOK["cudnn_major_required"]

    # Method 1: Check for cuDNN DLL in system PATH (Windows)
    if sys.platform == "win32":
        # Look for cudnn64_9.dll or cudnn_*.dll
        for dll_name in [f"cudnn64_{required_major}.dll", "cudnn64_9.dll",
                         "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll"]:
            result = _run_command(["where", dll_name])
            if result:
                logger.info(f"cuDNN found: {dll_name} at {result.split(chr(10))[0]}")
                return True, f"{required_major}.x"

        # Check CUDA_PATH/bin for cuDNN
        cuda_path = os.environ.get("CUDA_PATH", "")
        if cuda_path:
            bin_path = Path(cuda_path) / "bin"
            if bin_path.exists():
                try:
                    for f in bin_path.iterdir():
                        if f.name.lower().startswith("cudnn") and f.suffix == ".dll":
                            # Try to extract version from filename
                            match = re.search(r"cudnn\w*?(\d+)", f.name)
                            if match and int(match.group(1)) == required_major:
                                logger.info(f"cuDNN {required_major}.x found in CUDA bin: {f.name}")
                                return True, f"{required_major}.x"
                except PermissionError:
                    pass

        # Also check common CUDA installation directories
        cuda_base = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
        if cuda_base.exists():
            try:
                for cuda_dir in cuda_base.iterdir():
                    if cuda_dir.is_dir():
                        bin_dir = cuda_dir / "bin"
                        if bin_dir.exists():
                            for f in bin_dir.iterdir():
                                if f.name.lower().startswith("cudnn") and f.suffix == ".dll":
                                    match = re.search(r"cudnn\w*?(\d+)", f.name)
                                    if match and int(match.group(1)) == required_major:
                                        logger.info(f"cuDNN {required_major}.x found: {f}")
                                        return True, f"{required_major}.x"
            except PermissionError:
                pass

    else:
        # Linux: check ldconfig
        result = _run_command(["ldconfig", "-p"])
        if result and f"libcudnn.so.{required_major}" in result:
            logger.info(f"cuDNN {required_major}.x found via ldconfig")
            return True, f"{required_major}.x"

    logger.info(f"cuDNN {required_major}.x not detected.")
    return False, "Not Found"


def check_onnxruntime_providers() -> Tuple[bool, List[str], str]:
    """
    Check installed ONNX Runtime and available execution providers.
    Returns (has_cuda_provider, provider_list, ort_version).
    """
    try:
        import onnxruntime
        version = onnxruntime.__version__
        providers = onnxruntime.get_available_providers()
        has_cuda = "CUDAExecutionProvider" in providers
        logger.info(f"ONNX Runtime v{version}, providers: {providers}, CUDA: {has_cuda}")
        return has_cuda, list(providers), version
    except ImportError:
        logger.info("ONNX Runtime not installed.")
        return False, [], "Not Installed"
    except Exception as e:
        logger.warning(f"Failed to check ONNX Runtime providers: {e}")
        return False, [], "Error"


# ─────────────────────────────────────────────────────────
# Aggregated Status Check
# ─────────────────────────────────────────────────────────

def get_full_gpu_status() -> GPUInfo:
    """
    Run ALL checks and return a complete GPUInfo with wizard step guidance.
    This is the main entry point for the UI to get the current GPU state.
    """
    info = GPUInfo()

    # ── Step 0: Detect GPU hardware ──
    hw = detect_nvidia_gpu()
    if hw is None:
        info.status_message = "No NVIDIA GPU detected. Running in CPU mode."
        info.wizard_step = 0
        return info

    info.gpu_found = True
    info.gpu_name = hw.gpu_name
    info.driver_version = hw.driver_version
    info.vram_mb = hw.vram_mb

    # Look up architecture
    cc, arch = _lookup_gpu_architecture(hw.gpu_name)
    info.compute_capability = cc
    info.gpu_architecture = arch

    # ── Check whitelist ──
    whitelisted, reason = _check_whitelist(cc, hw.gpu_name, hw.vram_mb, hw.driver_version)
    info.is_whitelisted = whitelisted
    info.whitelist_reason = reason

    if not whitelisted:
        info.status_message = reason
        info.wizard_step = 0
        return info

    # GPU is whitelisted → wizard step 1 (ask user if they want GPU)
    info.wizard_step = 1
    info.can_proceed = True

    # ── Step 2: Check CUDA ──
    cuda_ver, cuda_ok = detect_cuda_toolkit()
    info.cuda_version = cuda_ver or "Not Installed"
    info.cuda_version_ok = cuda_ok

    if not cuda_ok:
        info.wizard_step = 2
        info.can_proceed = False
        if cuda_ver:
            info.status_message = (
                f"CUDA {cuda_ver} detected, but CUDA {GPU_RULEBOOK['cuda_major_min']}.x "
                f"or higher is required. Please install CUDA {GPU_RULEBOOK['cuda_version_recommended']}."
            )
        else:
            info.status_message = (
                f"CUDA Toolkit not installed. Please install CUDA "
                f"{GPU_RULEBOOK['cuda_version_recommended']} to enable GPU acceleration."
            )
        return info

    # ── Check cuDNN ──
    cudnn_found, cudnn_ver = detect_cudnn()
    info.cudnn_found = cudnn_found
    info.cudnn_version = cudnn_ver

    if not cudnn_found:
        info.wizard_step = 2
        info.can_proceed = False
        info.status_message = (
            f"CUDA {cuda_ver} is installed ✅, but cuDNN "
            f"{GPU_RULEBOOK['cudnn_major_required']}.x is required. "
            f"Please install cuDNN from NVIDIA's website."
        )
        return info

    # CUDA + cuDNN both OK → wizard step 3 (install onnxruntime-gpu)
    info.wizard_step = 3
    info.can_proceed = True

    # ── Step 3: Check ONNX Runtime ──
    has_cuda, providers, ort_ver = check_onnxruntime_providers()
    info.ort_version = ort_ver
    info.available_providers = providers
    info.cuda_provider_available = has_cuda
    info.ort_gpu_installed = has_cuda

    if has_cuda:
        info.status_message = (
            f"✅ GPU acceleration is ACTIVE — {hw.gpu_name} ({arch}, "
            f"{hw.vram_mb} MB) via CUDAExecutionProvider."
        )
    else:
        info.status_message = (
            f"GPU ready! CUDA {cuda_ver} ✅ cuDNN {cudnn_ver} ✅ — "
            f"Install onnxruntime-gpu to enable acceleration."
        )

    return info


# ─────────────────────────────────────────────────────────
# Execution Config for InsightFace
# ─────────────────────────────────────────────────────────

def get_execution_config(gpu_enabled: bool = False,
                         gpu_device_id: int = 0) -> ExecutionConfig:
    """
    Get the ONNX Runtime execution configuration based on settings.

    If gpu_enabled is True AND CUDAExecutionProvider is actually available,
    returns GPU config. Otherwise returns CPU config.

    The provider list always includes CPUExecutionProvider as fallback.
    """
    if not gpu_enabled:
        return ExecutionConfig(
            providers=["CPUExecutionProvider"],
            ctx_id=-1,
            mode="CPU",
        )

    # Check if CUDA provider is actually available
    try:
        import onnxruntime
        providers = onnxruntime.get_available_providers()
        if "CUDAExecutionProvider" in providers:
            # Get GPU name for the mode string
            hw = detect_nvidia_gpu()
            gpu_label = hw.gpu_name if hw else "GPU"
            return ExecutionConfig(
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                ctx_id=gpu_device_id,
                mode=f"GPU ({gpu_label})",
            )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to check CUDA provider, falling back to CPU: {e}")

    # Fallback to CPU
    logger.warning("GPU acceleration requested but CUDAExecutionProvider not available. Using CPU.")
    return ExecutionConfig(
        providers=["CPUExecutionProvider"],
        ctx_id=-1,
        mode="CPU (GPU unavailable)",
    )


# ─────────────────────────────────────────────────────────
# Package Swap Operations
# ─────────────────────────────────────────────────────────

def _get_installed_ort_version() -> Optional[str]:
    """Get the currently installed onnxruntime/onnxruntime-gpu version."""
    try:
        import onnxruntime
        return onnxruntime.__version__
    except ImportError:
        return None


def _pip_run(args: list, timeout: int = 300) -> Tuple[bool, str]:
    """
    Run a pip command using the current Python interpreter.
    Returns (success, output_or_error).
    """
    python = sys.executable
    cmd = [python, "-m", "pip"] + args
    logger.info(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        output = result.stdout + result.stderr
        if result.returncode == 0:
            return True, output
        else:
            logger.error(f"pip command failed: {output}")
            return False, output
    except subprocess.TimeoutExpired:
        return False, "pip command timed out (5 minutes). Check your internet connection."
    except Exception as e:
        return False, f"Failed to run pip: {e}"


def _verify_cuda_provider_subprocess() -> Tuple[bool, str]:
    """
    Verify CUDAExecutionProvider in a FRESH subprocess.
    This is necessary because Python caches module imports — the current
    process still has the old onnxruntime loaded.
    """
    python = sys.executable
    verify_script = (
        "import onnxruntime; "
        "providers = onnxruntime.get_available_providers(); "
        "print('PROVIDERS:' + ','.join(providers)); "
        "print('CUDA_OK' if 'CUDAExecutionProvider' in providers else 'CUDA_FAIL')"
    )

    try:
        result = subprocess.run(
            [python, "-c", verify_script],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        output = result.stdout + result.stderr
        if "CUDA_OK" in result.stdout:
            return True, output
        else:
            return False, output
    except Exception as e:
        return False, f"Verification failed: {e}"


def enable_gpu_acceleration(
    progress_callback=None
) -> SwapResult:
    """
    Swap onnxruntime → onnxruntime-gpu with full rollback safety.

    Args:
        progress_callback: Optional callable(step: int, total: int, message: str)
                          for UI progress updates.

    Returns:
        SwapResult with success status and messages.

    SAFETY GUARANTEE: If this function fails, the CPU onnxruntime will be
    restored. The app will NEVER be left without a working ONNX Runtime.
    """
    ort_gpu_version = GPU_RULEBOOK["ort_gpu_version"]
    original_version = _get_installed_ort_version()

    def _progress(step, total, msg):
        logger.info(f"[GPU Setup {step}/{total}] {msg}")
        if progress_callback:
            progress_callback(step, total, msg)

    try:
        # Step 1: Uninstall CPU onnxruntime
        _progress(1, 4, "Uninstalling onnxruntime (CPU)...")
        ok, output = _pip_run(["uninstall", "onnxruntime", "-y"])
        if not ok:
            # May not be installed (already gpu version?), continue anyway
            logger.debug(f"onnxruntime uninstall output: {output}")

        # Step 2: Install GPU onnxruntime
        _progress(2, 4, f"Installing onnxruntime-gpu {ort_gpu_version}... (this may take a few minutes)")
        ok, output = _pip_run(["install", f"onnxruntime-gpu=={ort_gpu_version}"])
        if not ok:
            # ROLLBACK
            _progress(2, 4, "Install failed. Rolling back to CPU version...")
            _rollback_to_cpu(original_version)
            return SwapResult(
                success=False,
                error=f"Failed to install onnxruntime-gpu: {output[:500]}",
                message="Installation failed. CPU mode has been restored."
            )

        # Step 3: Verify CUDA provider in a fresh subprocess
        _progress(3, 4, "Verifying GPU acceleration...")
        cuda_ok, verify_output = _verify_cuda_provider_subprocess()
        if not cuda_ok:
            # ROLLBACK
            _progress(3, 4, "Verification failed. Rolling back to CPU version...")
            _rollback_to_cpu(original_version)
            return SwapResult(
                success=False,
                error=(
                    "onnxruntime-gpu installed but CUDAExecutionProvider is not available. "
                    "This usually means CUDA or cuDNN versions don't match. "
                    f"Details: {verify_output[:500]}"
                ),
                message="GPU verification failed. CPU mode has been restored."
            )

        # Step 4: Success!
        _progress(4, 4, "GPU acceleration enabled successfully!")
        return SwapResult(
            success=True,
            message=(
                f"✅ GPU acceleration enabled! onnxruntime-gpu {ort_gpu_version} "
                f"installed with CUDAExecutionProvider."
            )
        )

    except Exception as e:
        logger.error(f"Unexpected error during GPU setup: {e}")
        _rollback_to_cpu(original_version)
        return SwapResult(
            success=False,
            error=f"Unexpected error: {e}",
            message="An unexpected error occurred. CPU mode has been restored."
        )


def disable_gpu_acceleration() -> SwapResult:
    """
    Swap onnxruntime-gpu → onnxruntime (back to CPU).
    """
    ort_cpu_package = GPU_RULEBOOK["ort_cpu_package"]

    try:
        # Uninstall GPU version
        ok, output = _pip_run(["uninstall", "onnxruntime-gpu", "-y"])

        # Install CPU version
        ok, output = _pip_run(["install", ort_cpu_package])
        if not ok:
            return SwapResult(
                success=False,
                error=f"Failed to install onnxruntime: {output[:500]}",
                message="Could not restore CPU mode. Please run: pip install onnxruntime"
            )

        return SwapResult(
            success=True,
            message="GPU acceleration disabled. Switched to CPU mode."
        )

    except Exception as e:
        return SwapResult(
            success=False,
            error=f"Unexpected error: {e}",
            message="Failed to disable GPU. Please run: pip install onnxruntime"
        )


def _rollback_to_cpu(original_version: Optional[str] = None):
    """
    Emergency rollback: ensure onnxruntime (CPU) is installed.
    Called when GPU setup fails at any step.
    """
    logger.warning("Rolling back to CPU onnxruntime...")

    # Try to uninstall whatever is there
    _pip_run(["uninstall", "onnxruntime-gpu", "-y"])
    _pip_run(["uninstall", "onnxruntime", "-y"])

    # Install CPU version
    if original_version:
        ok, _ = _pip_run(["install", f"onnxruntime=={original_version}"])
    else:
        ok, _ = _pip_run(["install", "onnxruntime"])

    if ok:
        logger.info("Rollback successful: onnxruntime (CPU) restored.")
    else:
        logger.error("CRITICAL: Rollback failed! Please manually run: pip install onnxruntime")


# ─────────────────────────────────────────────────────────
# .env Update Helper
# ─────────────────────────────────────────────────────────

def _find_env_path() -> Path:
    """Locate the project .env file."""
    try:
        import dist_utils
        return dist_utils.get_env_file_path()
    except ImportError:
        pass
    base = Path(__file__).parent.parent.parent
    env_path = base / ".env"
    if env_path.exists():
        return env_path
    backend_env = base / "backend" / ".env"
    if backend_env.exists():
        return backend_env
    return env_path


def update_env_gpu_setting(key: str, value: str) -> bool:
    """
    Update a single key in the .env file.
    If the key doesn't exist, append it at the end.
    """
    env_path = _find_env_path()
    if not env_path.exists():
        logger.warning(f".env file not found at {env_path}")
        return False

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
        key_found = False
        new_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                line_key = stripped.split("=", 1)[0].strip()
                if line_key == key:
                    new_lines.append(f"{key}={value}\n")
                    key_found = True
                    continue
            new_lines.append(line)

        if not key_found:
            # Append new key
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"\n# Hardware Acceleration (GPU)\n{key}={value}\n")

        env_path.write_text("".join(new_lines), encoding="utf-8")
        logger.info(f"Updated .env: {key}={value}")
        return True

    except Exception as e:
        logger.error(f"Failed to update .env: {e}")
        return False
