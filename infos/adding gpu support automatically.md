# 🚀 Adding GPU Support Automatically — Full Plan (v2)

> **Status:** Planning Phase  
> **Author:** Ranjith + Antigravity  
> **Date:** 2026-03-06  
> **Priority:** High (major performance boost for the entire pipeline)  
> **Revised:** v2 — Added Guided Wizard Flow, GPU Whitelist Rulebook, Step-by-Step CUDA Install Guidance

---

## 📑 Table of Contents

1. [Why GPU Support?](#1-why-gpu-support)
2. [The Problem — Why We Can't "Just Switch"](#2-the-problem--why-we-cant-just-switch)
3. [Our Strategy — The "Guided Wizard" Approach (v2)](#3-our-strategy--the-guided-wizard-approach-v2)
4. [The GPU Whitelist Rulebook](#4-the-gpu-whitelist-rulebook)
5. [The Compatibility Rulebook — Pinned Versions](#5-the-compatibility-rulebook--pinned-versions)
6. [GPU Detection Module Design](#6-gpu-detection-module-design)
7. [The 3-Step Wizard Flow (UI)](#7-the-3-step-wizard-flow-ui)
8. [Package Installation Strategy](#8-package-installation-strategy)
9. [Backend Integration — processor.py Changes](#9-backend-integration--processorpy-changes)
10. [Configuration — .env Changes](#10-configuration--env-changes)
11. [Settings Dialog — Hardware Acceleration Section](#11-settings-dialog--hardware-acceleration-section)
12. [Risk Analysis & Edge Cases](#12-risk-analysis--edge-cases)
13. [Implementation Order](#13-implementation-order)
14. [Files That Will Be Created or Modified](#14-files-that-will-be-created-or-modified)

---

## 1. Why GPU Support?

Currently the entire AI pipeline (face detection + embedding extraction) runs on CPU via:

```python
providers=["CPUExecutionProvider"]
```

### Performance Comparison (Estimated)

| Metric                    | CPU (Current)        | GPU (CUDA)          |
|:--------------------------|:---------------------|:--------------------|
| Face detection per photo  | ~100-200ms           | ~10-30ms            |
| Embedding extraction      | ~50-100ms            | ~5-15ms             |
| 1000 photos total         | ~15-30 minutes       | ~2-5 minutes        |
| CPU load during AI work   | 80-100%              | 10-20% (offloaded)  |

**Bottom line:** GPU acceleration could make the pipeline **5x–10x faster**, and frees the CPU for RAW conversion, cloud upload, and the web server.

---

## 2. The Problem — Why We Can't "Just Switch"

### 2.1 Not Everyone Has NVIDIA

- AMD and Intel GPUs do **NOT** support CUDA
- Only NVIDIA GPUs work with `onnxruntime-gpu`
- We must gracefully handle non-NVIDIA systems

### 2.2 Version Hell

The most dangerous part. There are FOUR things that must all be compatible:

```
NVIDIA Driver  →  CUDA Toolkit  →  cuDNN  →  onnxruntime-gpu
```

If ANY link in that chain is wrong, the AI model either:

- Falls back to CPU silently (best case)
- Crashes with cryptic DLL errors (worst case)

### 2.3 Package Conflict

**Critical:** You CANNOT have both `onnxruntime` AND `onnxruntime-gpu` installed at the same time. Having both causes the system to silently use the CPU version. One must be uninstalled before installing the other.

### 2.4 cuDNN Is NOT Included with CUDA

**Important:** Installing the CUDA Toolkit does NOT automatically install cuDNN. cuDNN is a separate NVIDIA SDK and must be installed independently. Our wizard must handle this.

### 2.5 The "Others Downloading This" Problem

If someone clones this repo on a machine without NVIDIA hardware:

- They should never even see GPU options
- The app must work perfectly on CPU out of the box
- No extra installation steps should be required

### 2.6 Old GPUs = Headaches

Older NVIDIA GPUs (Maxwell, Kepler, etc.) have limited CUDA support, different compute capabilities, and frequently cause version conflicts. We explicitly exclude them to keep the system predictable and supportable.

---

## 3. Our Strategy — The "Guided Wizard" Approach (v2)

### ❌ Previous Strategy (v1): "Detect & Suggest" — One-Click Button

We originally planned a single "Enable GPU" button that does everything at once.
**Problem:** Too many hidden failure points. User doesn't know what's happening behind the scenes.

### ✅ New Strategy (v2): "Guided 3-Step Wizard"

The app walks the user through GPU setup **one step at a time**, asking for consent at each stage. Each step only appears AFTER the previous one is confirmed complete.

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   STEP 1: GPU Detection                                     │
│   ├── Detect GPU → Confirm it's in our Whitelist             │
│   ├── If YES → Ask: "We found your RTX 4070. Would you      │
│   │            like to set up GPU acceleration?"             │
│   └── If NO  → "Your GPU is not supported / not found."     │
│                Show CPU mode. Done.                          │
│                                                              │
│   STEP 2: CUDA Installation Check                            │
│   ├── Check if CUDA 12.x is installed                        │
│   ├── If NOT → Show: "To use GPU, you need CUDA 12.6.       │
│   │            Click here to download it from NVIDIA."       │
│   │            [Download CUDA 12.6] ← Opens browser          │
│   │            After install → User clicks "I've installed   │
│   │            CUDA, check again"                            │
│   ├── Check if cuDNN 9.x is installed                        │
│   ├── If NOT → Show: "cuDNN 9.x is also required.           │
│   │            Click here to download." [Download cuDNN 9]   │
│   └── If BOTH installed → Move to Step 3                     │
│                                                              │
│   STEP 3: Enable GPU Mode                                    │
│   ├── Ask: "CUDA 12.6 ✅ cuDNN 9 ✅ — Ready to go!          │
│   │        Install onnxruntime-gpu and enable acceleration?" │
│   ├── If YES → Swap onnxruntime → onnxruntime-gpu            │
│   │         → Verify CUDAExecutionProvider is available       │
│   │         → Enable GPU mode in .env                        │
│   │         → "✅ GPU Acceleration is now ACTIVE!"            │
│   └── If NO  → Stay on CPU. Done.                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Why This Is Better

1. **Transparency** — The user sees exactly what's happening at each step.
2. **No Surprises** — We never install anything without explicit consent.
3. **Easy Debugging** — If something fails, the user (and we) know EXACTLY which step broke.
4. **CUDA Install is Manual** — We guide them to the download page, but they install it themselves. This avoids admin privilege issues and respects their system.
5. **Reversible** — At any point, the user can go back to CPU mode.

---

## 4. The GPU Whitelist Rulebook

### Philosophy: Only Support "Easy" GPUs

We're NOT trying to support every NVIDIA card ever made. We support the ones that are:

- Modern enough to work with CUDA 12.x without issues
- Common enough that users will actually have them
- Documented enough that troubleshooting is straightforward

### ✅ Supported GPU Architectures

| Architecture    | Compute Capability | Example GPUs                           | Min. Driver | Status         |
|:----------------|:-------------------|:---------------------------------------|:------------|:---------------|
| **Turing**      | sm_75              | RTX 2060, 2070, 2080, GTX 1650/1660   | ≥ 525.60    | ✅ Supported   |
| **Ampere**      | sm_80 / sm_86      | RTX 3060, 3070, 3080, 3090, A100      | ≥ 525.60    | ✅ Supported   |
| **Ada Lovelace**| sm_89              | RTX 4060, 4070, 4080, 4090            | ≥ 525.60    | ✅ Supported   |
| **Blackwell**   | sm_100 / sm_120    | RTX 5070, 5080, 5090                  | ≥ 560.00    | ✅ Supported   |

### ❌ Unsupported (Blocked) GPU Architectures

| Architecture    | Compute Capability | Example GPUs                           | Why Blocked                                            |
|:----------------|:-------------------|:---------------------------------------|:-------------------------------------------------------|
| **Kepler**      | sm_30 / sm_35      | GTX 680, 780, Tesla K40               | Dropped from CUDA 12.x. No driver support.             |
| **Maxwell**     | sm_50 / sm_52      | GTX 960, 970, 980, Titan X (Maxwell)  | CUDA 12.x technically works but very fragile. Driver issues common. |
| **Pascal**      | sm_60 / sm_61      | GTX 1060, 1070, 1080, Titan Xp        | Borderline. CUDA 12 works but these cards are 8+ years old. cuDNN 9 compatibility is spotty. Driver update path is unclear. Too many support headaches. |

### How We Detect & Filter

```python
# Minimum compute capability we support
MIN_COMPUTE_CAPABILITY = 7.5  # Turing and above

# Minimum VRAM (buffalo_l needs ~500 MB, we want headroom)
MIN_VRAM_MB = 2048  # 2 GB minimum

# Minimum driver version for CUDA 12.x
MIN_DRIVER_VERSION = "525.60"
```

We get the compute capability from:

1. `nvidia-smi --query-gpu=compute_cap --format=csv` (if available in that nvidia-smi version)
2. OR by matching the GPU name against a lookup table

### The Lookup Table (Embedded in Code)

```python
# GPU name substring → compute capability
# Used as fallback when nvidia-smi can't report compute_cap directly
GPU_COMPUTE_TABLE = {
    # Turing (7.5)
    "RTX 2060": 7.5, "RTX 2070": 7.5, "RTX 2080": 7.5,
    "GTX 1650": 7.5, "GTX 1660": 7.5,
    "Quadro RTX": 7.5, "Tesla T4": 7.5,
    
    # Ampere (8.0 / 8.6)
    "RTX 3060": 8.6, "RTX 3070": 8.6, "RTX 3080": 8.6, "RTX 3090": 8.6,
    "RTX A": 8.6, "A100": 8.0, "A10": 8.6, "A30": 8.0,
    
    # Ada Lovelace (8.9)
    "RTX 4060": 8.9, "RTX 4070": 8.9, "RTX 4080": 8.9, "RTX 4090": 8.9,
    "RTX 6000 Ada": 8.9, "L40": 8.9,
    
    # Blackwell (10.0 / 12.0)
    "RTX 5070": 12.0, "RTX 5080": 12.0, "RTX 5090": 12.0,
    "B100": 10.0, "B200": 10.0, "GB200": 10.0,
}
```

### What The User Sees if GPU is NOT in Whitelist

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ⚠️  GPU Not Supported for Acceleration                     │
│                                                              │
│  We detected: NVIDIA GeForce GTX 1080 (Pascal, sm_61)       │
│                                                              │
│  Wedding Face Forward supports GPU acceleration for          │
│  Turing (RTX 20-series) and newer GPUs only.                 │
│                                                              │
│  Your GPU is too old to guarantee stable CUDA 12             │
│  compatibility. The app will continue to run perfectly        │
│  on CPU mode.                                                │
│                                                              │
│  ┌──────────────┐                                            │
│  │     OK       │                                            │
│  └──────────────┘                                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. The Compatibility Rulebook — Pinned Versions

### The ONE Combination We Test & Support

We don't try to support multiple CUDA versions. We pick ONE known-good combination and stick with it.

```
┌───────────────────────────────────────────────────────┐
│                                                       │
│   THE RULEBOOK — Pinned Compatibility Stack           │
│                                                       │
│   onnxruntime-gpu    ==  1.20.x (CUDA 12 build)      │
│   CUDA Toolkit       ==  12.6                         │
│   cuDNN              ==  9.x (9.1+ recommended)       │
│   NVIDIA Driver      >=  525.60                       │
│   Python             >=  3.10                         │
│   InsightFace        >=  0.7.3                        │
│                                                       │
│   Supported GPUs:    Turing+ (compute >= 7.5)         │
│   Min VRAM:          2 GB                             │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### Why These Specific Versions?

| Choice              | Reason                                                        |
|:--------------------|:--------------------------------------------------------------|
| **CUDA 12.6**       | Latest stable 12.x release. Well-tested. ONNX Runtime 1.20 is built against CUDA 12.x. Any CUDA 12.x version is forward/backward compatible within the 12.x family. But we recommend 12.6 specifically to reduce "which one do I pick?" confusion. |
| **cuDNN 9.x**       | ONNX Runtime 1.19+ is built against cuDNN 9. cuDNN 8.x will NOT work with ORT 1.19+. cuDNN 9.x will NOT work with ORT < 1.19. This is a hard requirement. |
| **onnxruntime-gpu 1.20.x** | Latest stable. PyPI default ships CUDA 12 variant. `pip install onnxruntime-gpu` just works. No special flags or custom wheels needed. |
| **Driver ≥ 525.60** | Minimum driver that supports CUDA 12.x runtime. Most users on Turing+ will already have 530+ installed. |

### What If User Has CUDA 11.x Installed?

We do NOT support CUDA 11.x. Here's why:

- ORT 1.19+ PyPI default = CUDA 12. Getting CUDA 11 builds requires manual wheel installs = too complex.
- cuDNN 8.x (required by CUDA 11 builds) conflicts with cuDNN 9.x = version hell.
- CUDA 11 is end-of-life from NVIDIA's perspective.
- If user has CUDA 11, we tell them: "Please upgrade to CUDA 12.6 to use GPU acceleration."

### The Rulebook as a Python Dict (For Code)

```python
GPU_RULEBOOK = {
    "cuda_version": "12.6",
    "cuda_major_min": 12,         # Any CUDA 12.x is acceptable
    "cudnn_major": 9,             # cuDNN 9.x required
    "ort_gpu_package": "onnxruntime-gpu",
    "ort_gpu_version": "1.20.1",  # Pinned exact version
    "min_driver": "525.60",
    "min_compute_cap": 7.5,       # Turing+
    "min_vram_mb": 2048,          # 2 GB
    "cuda_download_url": "https://developer.nvidia.com/cuda-12-6-0-download-archive",
    "cudnn_download_url": "https://developer.nvidia.com/cudnn-downloads",
}
```

---

## 6. GPU Detection Module Design

### New File: `backend/app/gpu_manager.py`

This module is the single source of truth for all GPU-related logic.

### 6.1 Detection Functions

```
detect_nvidia_gpu()
├── Run `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv`
├── Parse output to get:
│   ├── GPU Name (e.g., "NVIDIA GeForce RTX 4070")
│   ├── Driver Version (e.g., "560.81")
│   └── VRAM (e.g., "12288 MiB")
├── Look up compute capability from GPU_COMPUTE_TABLE
├── Check against MIN_COMPUTE_CAPABILITY whitelist
└── Return GPUInfo dataclass or None

detect_cuda_version()
├── Try: `nvidia-smi` output contains CUDA version (driver-level)
├── Try: `nvcc --version` for toolkit install version
├── Check: Is CUDA major version >= 12?
└── Return version string or None

detect_cudnn()
├── Check if cuDNN DLLs exist in CUDA path or system PATH
│   └── Look for: cudnn64_9.dll (Windows) or libcudnn.so.9 (Linux)
├── Try: `where cudnn64_9.dll` (Windows) or `ldconfig -p | grep cudnn` (Linux)
└── Return (found: bool, version: str or None)

check_onnxruntime_provider()
├── Try: `import onnxruntime`
├── Check: `onnxruntime.get_available_providers()`
├── Look for "CUDAExecutionProvider" in the list
└── Return (has_cuda: bool, providers: list, ort_version: str)
```

### 6.2 GPUInfo Data Class

```python
@dataclass
class GPUInfo:
    # Hardware
    gpu_found: bool                # Is any NVIDIA GPU found?
    gpu_name: str                  # "NVIDIA GeForce RTX 4070" or "N/A"
    gpu_architecture: str          # "Ada Lovelace" or "Unknown"
    compute_capability: float      # 8.9 or 0.0
    driver_version: str            # "560.81" or "N/A"
    vram_mb: int                   # 12288 or 0
    
    # Whitelist
    is_whitelisted: bool           # Matches our supported GPU list?
    whitelist_reason: str          # "Supported" or "GPU too old (Pascal sm_61)"
    
    # Software
    cuda_version: str              # "12.6" or "Not Installed"
    cuda_version_ok: bool          # Is CUDA >= 12.0?
    cudnn_found: bool              # Is cuDNN 9.x installed?
    ort_gpu_installed: bool        # Is onnxruntime-gpu installed?
    cuda_provider_available: bool  # Can ONNX actually use CUDA right now?
    
    # Wizard state
    wizard_step: int               # 1, 2, or 3 (which step user is on)
    status_message: str            # Human-readable status for the UI
    can_proceed: bool              # Can user move to the next wizard step?
```

### 6.3 Full Status Check Function

```python
def get_full_gpu_status() -> GPUInfo:
    """Run all checks and return complete GPU status."""
    
    # 1. Detect GPU hardware
    gpu = detect_nvidia_gpu()
    if not gpu.gpu_found:
        return GPUInfo(wizard_step=0, status_message="No NVIDIA GPU detected.")
    
    # 2. Check whitelist
    if not gpu.is_whitelisted:
        return GPUInfo(wizard_step=0, status_message=gpu.whitelist_reason)
    
    # 3. Check CUDA
    cuda = detect_cuda_version()
    if not cuda or cuda_major < 12:
        return GPUInfo(wizard_step=2, status_message="CUDA 12.x required.")
    
    # 4. Check cuDNN
    cudnn = detect_cudnn()
    if not cudnn.found:
        return GPUInfo(wizard_step=2, status_message="cuDNN 9.x required.")
    
    # 5. Check onnxruntime-gpu
    ort = check_onnxruntime_provider()
    if not ort.has_cuda:
        return GPUInfo(wizard_step=3, status_message="Ready to enable GPU!")
    
    # 6. Everything is good!
    return GPUInfo(wizard_step=3, status_message="GPU acceleration is ACTIVE!")
```

---

## 7. The 3-Step Wizard Flow (UI)

### Overview — What the User Experiences on First Launch

```
App starts → detect_nvidia_gpu() runs silently (takes < 1 second)

IF no GPU or unsupported GPU:
    → Nothing happens. App runs on CPU. User never sees GPU options.
    → Settings shows: "GPU Status: CPU Mode (No compatible GPU detected)"

IF supported GPU found:
    → First-time popup appears (STEP 1)
```

### STEP 1: GPU Discovery Prompt

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ⚡ High-Performance GPU Detected!                           │
│                                                              │
│  GPU:    NVIDIA GeForce RTX 4070 (Ada Lovelace)              │
│  VRAM:   12 GB                                               │
│  Driver: 560.81                                              │
│                                                              │
│  Your GPU can accelerate face detection and matching         │
│  by up to 10x. Would you like to set it up?                  │
│                                                              │
│  This requires installing CUDA 12.6 and a GPU-optimized      │
│  AI library (~200 MB total).                                 │
│                                                              │
│  ┌──────────────┐    ┌──────────────────────┐               │
│  │  Not Now      │    │  ⚡ Let's Set It Up  │               │
│  └──────────────┘    └──────────────────────┘               │
│                                                              │
│  □ Don't ask me again                                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**If "Not Now"** → Dismiss. Store `GPU_WIZARD_STEP=dismissed` in .env. User can re-trigger from Settings at any time.

**If "Let's Set It Up"** → Move to STEP 2.

### STEP 2: CUDA & cuDNN Installation Guide

This step has TWO sub-checks: CUDA Toolkit and cuDNN.

#### Sub-Step 2A: CUDA Check

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  📦 Step 2/3 — Install CUDA Toolkit                          │
│                                                              │
│  CUDA Status:  🔴  Not Installed                             │
│                                                              │
│  Wedding Face Forward requires CUDA Toolkit 12.6 for         │
│  GPU acceleration.                                           │
│                                                              │
│  1. Click the button below to open NVIDIA's download page    │
│  2. Select: Windows → x86_64 → 11/10 → exe (local)         │
│  3. Run the installer (use "Express" installation)           │
│  4. Restart your computer if prompted                        │
│  5. Come back here and click "Check Again"                   │
│                                                              │
│  ┌───────────────────────────┐                               │
│  │  🌐 Download CUDA 12.6   │  ← Opens browser              │
│  └───────────────────────────┘                               │
│                                                              │
│  ┌──────────────┐    ┌──────────────────────┐               │
│  │  Cancel       │    │  🔄 Check Again      │               │
│  └──────────────┘    └──────────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**On "Check Again"** → Re-run `detect_cuda_version()`.

- If CUDA 12.x found → ✅ Show green checkmark, auto-move to Sub-Step 2B.
- If still not found → Show "CUDA still not detected. Make sure to restart your terminal/app after installation."

#### Sub-Step 2B: cuDNN Check

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  📦 Step 2/3 — Install cuDNN                                 │
│                                                              │
│  CUDA Status:    ✅  CUDA 12.6 Installed                     │
│  cuDNN Status:   🔴  Not Found                               │
│                                                              │
│  cuDNN is NVIDIA's deep learning acceleration library.       │
│  It is separate from CUDA and must be installed manually.    │
│                                                              │
│  1. Click below to open the cuDNN download page              │
│  2. You may need to create a free NVIDIA developer account   │
│  3. Download cuDNN 9.x for CUDA 12.x                        │
│  4. Extract and copy the files into your CUDA folder         │
│     (typically C:\Program Files\NVIDIA GPU Computing         │
│      Toolkit\CUDA\v12.6\)                                    │
│  5. Come back here and click "Check Again"                   │
│                                                              │
│  ┌──────────────────────────┐                                │
│  │  🌐 Download cuDNN 9.x  │  ← Opens browser               │
│  └──────────────────────────┘                                │
│                                                              │
│  ┌──────────────┐    ┌──────────────────────┐               │
│  │  Cancel       │    │  🔄 Check Again      │               │
│  └──────────────┘    └──────────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**On "Check Again"** → Re-run `detect_cudnn()`.

- If cuDNN 9.x found → ✅ Move to STEP 3.
- If not found → Show helpful message.

### STEP 3: Enable GPU Acceleration

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ⚡ Step 3/3 — Enable GPU Acceleration                       │
│                                                              │
│  ✅ GPU:     NVIDIA GeForce RTX 4070 (12 GB)                 │
│  ✅ CUDA:    12.6 Installed                                   │
│  ✅ cuDNN:   9.1 Installed                                    │
│  ⬜ Engine:  onnxruntime (CPU only)                           │
│                                                              │
│  Everything is ready! To enable GPU acceleration, we need    │
│  to swap the AI engine to the GPU-optimized version.         │
│                                                              │
│  This will:                                                  │
│  • Uninstall onnxruntime (CPU version)                       │
│  • Install onnxruntime-gpu 1.20.x (~200 MB download)        │
│  • Verify GPU is working                                     │
│                                                              │
│  ⚠️  The app will need to restart after this change.         │
│                                                              │
│  ┌──────────────┐    ┌──────────────────────┐               │
│  │  Stay on CPU  │    │  ⚡ Install & Enable │               │
│  └──────────────┘    └──────────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**On "Install & Enable"** → Show progress dialog:

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ⏳ Setting up GPU Acceleration...                            │
│                                                              │
│  ▸ Uninstalling onnxruntime (CPU)...          ✅ Done        │
│  ▸ Installing onnxruntime-gpu 1.20.1...       ⏳ 45%         │
│  ▸ Verifying GPU provider...                  ⬜ Waiting      │
│  ▸ Updating configuration...                  ⬜ Waiting      │
│                                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━               45%     │
│                                                              │
│  Please wait, this may take a few minutes...                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**On Success:**

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ✅ GPU Acceleration is Now Active!                           │
│                                                              │
│  GPU:     NVIDIA GeForce RTX 4070 (12 GB)                    │
│  Engine:  onnxruntime-gpu 1.20.1 (CUDAExecutionProvider)     │
│  Speed:   Up to 10x faster face detection                    │
│                                                              │
│  The app needs to restart to apply GPU acceleration.         │
│                                                              │
│  ┌──────────────────────┐                                    │
│  │  🔄 Restart Now      │                                    │
│  └──────────────────────┘                                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**On Failure (Rollback):**

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ❌ GPU Setup Failed                                          │
│                                                              │
│  Error: CUDAExecutionProvider not available after install.    │
│  This usually means CUDA/cuDNN versions don't match.         │
│                                                              │
│  ✅ onnxruntime (CPU) has been restored automatically.        │
│  Your app will continue to work normally on CPU.             │
│                                                              │
│  Troubleshooting:                                            │
│  • Ensure CUDA 12.6 is installed (not 11.x)                  │
│  • Ensure cuDNN 9.x is in your CUDA directory                │
│  • Try restarting your computer                              │
│                                                              │
│  ┌──────────────┐    ┌──────────────────────┐               │
│  │  OK (Use CPU) │    │  🔄 Try Again        │               │
│  └──────────────┘    └──────────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. Package Installation Strategy

### The Swap Process (Detailed)

```python
def enable_gpu_acceleration() -> SwapResult:
    """
    Swap onnxruntime → onnxruntime-gpu with rollback safety.
    Must be called from a background thread (not UI thread).
    """
    python = sys.executable  # Always use the project's Python
    ort_gpu_version = GPU_RULEBOOK["ort_gpu_version"]
    
    # Step 1: Record current state for rollback
    current_ort_version = get_installed_ort_version()  # e.g., "1.20.1"
    
    # Step 2: Uninstall CPU onnxruntime
    run([python, "-m", "pip", "uninstall", "onnxruntime", "-y"])
    
    # Step 3: Install GPU onnxruntime
    result = run([python, "-m", "pip", "install", 
                  f"onnxruntime-gpu=={ort_gpu_version}"])
    
    if result.returncode != 0:
        # ROLLBACK: Reinstall CPU version
        run([python, "-m", "pip", "install", 
             f"onnxruntime=={current_ort_version}"])
        return SwapResult(success=False, error="pip install failed")
    
    # Step 4: Verify CUDA provider is available
    # We need to actually test it in a fresh subprocess because
    # Python caches imports — the current process still has old onnxruntime
    verify_result = run([python, "-c", 
        "import onnxruntime; "
        "providers = onnxruntime.get_available_providers(); "
        "print('CUDA_OK' if 'CUDAExecutionProvider' in providers else 'CUDA_FAIL')"
    ])
    
    if "CUDA_OK" not in verify_result.stdout:
        # ROLLBACK
        run([python, "-m", "pip", "uninstall", "onnxruntime-gpu", "-y"])
        run([python, "-m", "pip", "install", 
             f"onnxruntime=={current_ort_version}"])
        return SwapResult(success=False, 
                         error="CUDAExecutionProvider not available after install")
    
    # Step 5: Update .env
    update_env("GPU_ACCELERATION", "true")
    update_env("GPU_WIZARD_STEP", "complete")
    
    return SwapResult(success=True)
```

### Rollback Safety: The Golden Rule

> **NO MATTER WHAT HAPPENS, the app must be able to process photos after this function returns.**
>
> If GPU install fails → CPU onnxruntime MUST be restored.
> If anything throws an exception → wrap in try/finally to ensure rollback.

### Important: Virtual Environment Awareness

The pip commands must run inside the project's virtual environment, NOT the system Python. We detect this from `sys.executable` which always points to the correct Python.

---

## 9. Backend Integration — processor.py Changes

### 9.1 Current Code (Lines 43-47)

```python
analyzer = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)
analyzer.prepare(ctx_id=-1, det_size=(640, 640))
```

### 9.2 New Code (After Implementation)

```python
from .gpu_manager import get_execution_config

exec_config = get_execution_config()

analyzer = FaceAnalysis(
    name="buffalo_l",
    providers=exec_config.providers
    # GPU enabled: ["CUDAExecutionProvider", "CPUExecutionProvider"]
    # GPU disabled: ["CPUExecutionProvider"]
)
analyzer.prepare(
    ctx_id=exec_config.ctx_id,  # 0 for GPU, -1 for CPU
    det_size=(640, 640)
)

logger.info(f"InsightFace running on: {exec_config.mode}")  
# "GPU (RTX 4070)" or "CPU"
```

### 9.3 The Provider Chain (Fallback Order)

When GPU is enabled, we pass BOTH providers in priority order:

```python
providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
```

ONNX Runtime will:

1. **Try** CUDAExecutionProvider first
2. If CUDA fails at runtime → **automatically fall back** to CPUExecutionProvider
3. This is built-in ONNX Runtime behavior — no extra code needed!

### 9.4 ctx_id Meaning

| Value | Meaning |
|:------|:--------|
| `-1`  | Use CPU |
| `0`   | Use GPU device 0 (first/only GPU) |
| `1`   | Use GPU device 1 (multi-GPU, rare) |

---

## 10. Configuration — .env Changes

### New Environment Variables

```env
# ─────────────────────────────────────────────────────────
# Hardware Acceleration (GPU)
# ─────────────────────────────────────────────────────────

# Set to "true" to use GPU (NVIDIA CUDA) for face detection.
# Only works if onnxruntime-gpu is installed and CUDA 12.x + cuDNN 9.x are available.
# The app will auto-fallback to CPU if GPU is unavailable at runtime.
GPU_ACCELERATION=false

# Which GPU device to use (0 = first GPU, usually the only one)
GPU_DEVICE_ID=0

# Wizard progress tracking
# Values: not_started, dismissed, cuda_pending, cudnn_pending, ort_pending, complete
GPU_WIZARD_STEP=not_started

# Set to "true" if user dismissed the first-time GPU prompt
GPU_PROMPT_DISMISSED=false
```

### Config.py Additions

```python
# Hardware Acceleration
gpu_acceleration: bool
gpu_device_id: int
gpu_wizard_step: str
gpu_prompt_dismissed: bool
```

---

## 11. Settings Dialog — Hardware Acceleration Section

### Always Visible in Settings

Even after the wizard is complete (or skipped), the Settings dialog always shows the GPU status.

### Layout When GPU is Active

```
┌─────────────────────────────────────────────────────────────┐
│ ⚡ Hardware Acceleration                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  GPU:       ● NVIDIA GeForce RTX 4070 (Ada Lovelace, 12 GB)│
│  CUDA:      ● v12.6                                         │
│  cuDNN:     ● v9.1                                           │
│  Engine:    ● onnxruntime-gpu 1.20.1 (CUDA)                 │
│  Status:    ✅ GPU Acceleration ACTIVE                       │
│                                                             │
│  ┌────────────────────────────────────┐                     │
│  │  ⬜ Use GPU for face detection     │  ← Toggle switch    │
│  └────────────────────────────────────┘                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Layout When No GPU / Unsupported

```
┌─────────────────────────────────────────────────────────────┐
│ ⚡ Hardware Acceleration                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  GPU:       ● No compatible NVIDIA GPU detected             │
│  Engine:    ● onnxruntime 1.20.1 (CPU)                      │
│  Status:    ℹ️  Running in CPU mode                          │
│                                                             │
│  GPU acceleration requires an NVIDIA Turing or newer GPU    │
│  (RTX 2060+, GTX 1650+, RTX 3060+, RTX 4060+).             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Layout When GPU Found but Setup Pending

```
┌─────────────────────────────────────────────────────────────┐
│ ⚡ Hardware Acceleration                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  GPU:       ● NVIDIA GeForce RTX 4070 (12 GB)              │
│  CUDA:      🔴 Not Installed                                │
│  Engine:    ● onnxruntime 1.20.1 (CPU)                      │
│  Status:    🟡 GPU setup incomplete                          │
│                                                             │
│  ┌───────────────────────────────────┐                      │
│  │  ⚡ Resume GPU Setup Wizard       │                      │
│  └───────────────────────────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. Risk Analysis & Edge Cases

### 🔴 High Risk

| Risk | Impact | Mitigation |
|:-----|:-------|:-----------|
| `pip install onnxruntime-gpu` fails mid-install | App loses ONNX entirely → can't process photos | Always verify `import onnxruntime` works after swap. Rollback in try/finally. |
| User has CUDA 11.x but we install CUDA-12 ORT | Cryptic DLL load errors | We detect CUDA version BEFORE allowing install. Block if < 12. |
| Antivirus blocks pip subprocess | Install hangs or fails silently | Set timeout (300s) on subprocess. Show clear timeout error. |
| Multiple Python environments | Wrong pip gets called | Always use `sys.executable -m pip` — never bare `pip`. |
| cuDNN version mismatch (8.x vs 9.x) | ORT loads but CUDA provider silently fails | Specifically check cuDNN major version. Block if cuDNN 8.x detected. |

### 🟡 Medium Risk

| Risk | Impact | Mitigation |
|:-----|:-------|:-----------|
| GPU VRAM too low | ONNX Runtime crash or swap to system RAM | buffalo_l needs ~500MB. We require 2GB minimum. Check before enabling. |
| Laptop Optimus / hybrid GPU | CUDA initializes but runs on wrong GPU | Detect multiple GPUs. Warn about hybrid setups. |
| User updates NVIDIA drivers → breaks CUDA | GPU was working, suddenly stops | On each startup, verify GPU is still functional. Auto-fallback to CPU. |
| Network issues during pip install | Download hangs or partial install | Show progress. Timeout after 5 minutes. Rollback on any failure. |

### 🟢 Low Risk

| Risk | Impact | Mitigation |
|:-----|:-------|:-----------|
| AMD/Intel GPU user confused | Tries to find GPU option, can't | Section shows "No compatible NVIDIA GPU detected" — clear message. |
| User installs CUDA but forgets cuDNN | Wizard stuck at step 2B | Clear instructions with download link. "Check Again" button. |
| Speed difference confuses user | "Why fast sometimes?" | Status bar always shows current mode (CPU / GPU ⚡). |

---

## 13. Implementation Order

### Phase 1: GPU Detection Module + Rulebook (Backend)

**New File:** `backend/app/gpu_manager.py`

- [ ] Create `GPU_RULEBOOK` dict with pinned versions
- [ ] Create `GPU_COMPUTE_TABLE` lookup dict
- [ ] Create `GPUInfo` dataclass
- [ ] Implement `detect_nvidia_gpu()` — runs `nvidia-smi`, parses output, checks whitelist
- [ ] Implement `detect_cuda_version()` — checks CUDA toolkit version, validates ≥ 12.0
- [ ] Implement `detect_cudnn()` — checks for cuDNN 9.x DLLs
- [ ] Implement `check_onnxruntime_provider()` — checks installed ORT providers
- [ ] Implement `get_full_gpu_status()` — aggregates all checks into `GPUInfo`
- [ ] Implement `get_execution_config()` — returns providers list and ctx_id based on .env setting
- [ ] Write unit tests with mocked subprocess calls

### Phase 2: Package Swap Logic (Backend)

**File:** `backend/app/gpu_manager.py` (continued)

- [ ] Implement `enable_gpu_acceleration()` — pip swap with rollback
- [ ] Implement `disable_gpu_acceleration()` — reverse swap
- [ ] Implement verification subprocess (check CUDA provider in fresh process)
- [ ] Implement rollback safety net (try/finally)
- [ ] Test on a machine WITH GPU
- [ ] Test on a machine WITHOUT GPU

### Phase 3: Configuration Integration

**Files:** `backend/app/config.py` + `.env` + `.env.example`

- [ ] Add `GPU_ACCELERATION`, `GPU_DEVICE_ID`, `GPU_WIZARD_STEP`, `GPU_PROMPT_DISMISSED` to Config
- [ ] Add env vars to `.env` and `.env.example` with documentation
- [ ] Update `get_config()` to load GPU settings

### Phase 4: Processor Integration

**File:** `backend/app/processor.py`

- [ ] Modify `_get_face_analyzer()` to use `get_execution_config()`
- [ ] Add GPU status logging on startup (which provider is active)
- [ ] Verify fallback chain works (GPU → CPU automatic)
- [ ] Test that switching GPU on/off in .env takes effect after app restart

### Phase 5: UI — The 3-Step Wizard Dialog

**New File:** `WeddingFFapp_pyside/widgets/gpu_wizard.py`

- [ ] Create `GPUWizardDialog` (QDialog)
- [ ] Implement Step 1: GPU Detection + Whitelist Check
- [ ] Implement Step 2A: CUDA Installation Guide + "Download" button + "Check Again"
- [ ] Implement Step 2B: cuDNN Installation Guide + "Download" button + "Check Again"
- [ ] Implement Step 3: ORT GPU Install + Progress + Result
- [ ] Implement Failure/Rollback dialog
- [ ] Implement "Don't ask again" checkbox
- [ ] Wire wizard signals to main app

### Phase 6: UI — Settings Dialog "Hardware Acceleration" Section

**File:** `WeddingFFapp_pyside/widgets/settings_dialog.py`

- [ ] Add "⚡ Hardware Acceleration" section at top of settings
- [ ] Show GPU detection results (name, VRAM, CUDA, cuDNN, ORT version)
- [ ] Add GPU enable/disable toggle (when fully set up)
- [ ] Add "Resume GPU Setup Wizard" button (when setup is incomplete)
- [ ] Handle all visual states (no GPU, pending, active, error)

### Phase 7: First-Time Startup Trigger

**File:** Main app entry point (or `run_pyside.py`)

- [ ] On first launch, run `get_full_gpu_status()` in background
- [ ] If GPU found + whitelisted + not dismissed → show wizard Step 1
- [ ] Store wizard progress in .env

### Phase 8: Status Bar Integration

**File:** Main app window

- [ ] Show "CPU" or "GPU ⚡" indicator in the main status bar
- [ ] Real-time provider info visible at all times
- [ ] Tooltip shows full GPU info on hover

---

## 14. Files That Will Be Created or Modified

| File | Action | Description |
|:-----|:-------|:------------|
| `backend/app/gpu_manager.py` | **CREATE** | GPU detection, rulebook, whitelist, swap logic |
| `WeddingFFapp_pyside/widgets/gpu_wizard.py` | **CREATE** | 3-step GPU setup wizard dialog |
| `backend/tests/test_gpu_manager.py` | **CREATE** | Unit tests for GPU detection & swap |
| `backend/app/processor.py` | MODIFY | Use dynamic providers from gpu_manager |
| `backend/app/config.py` | MODIFY | Add GPU config fields |
| `.env` | MODIFY | Add GPU env vars |
| `.env.example` | MODIFY | Add GPU env vars with docs |
| `WeddingFFapp_pyside/widgets/settings_dialog.py` | MODIFY | Add Hardware Acceleration section |
| Main app entry | MODIFY | Trigger GPU wizard on first launch |

---

## 📋 Summary — The Golden Rules

> 1. **CPU is the default. GPU is the upgrade.** App must ALWAYS work on CPU.
> 2. **Only support Turing+ GPUs** (compute ≥ 7.5). Old GPUs = old problems.
> 3. **ONE pinned version stack.** CUDA 12.6 + cuDNN 9.x + ORT-GPU 1.20.x. No mix-and-match.
> 4. **Guide, don't auto-install.** We link to NVIDIA's downloads. User installs. We verify.
> 5. **Ask at every step.** Never install anything without explicit user consent.
> 6. **Rollback is non-negotiable.** If GPU setup fails, CPU mode is restored automatically.
> 7. **The user should NEVER see the app break because of GPU issues.**
