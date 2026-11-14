<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# okayy seee..

mainly focus on windows app..
my app has to run on GPU..
it is as facial recognnition and classificaiton model :  InsightFace(buffalo_l)..
others have to just donwload it and click instal install install and able to run it in their system((if they have gpu, the app should use it, like how blender app uses it)..

and which ai agent to use for this ?

Now this is very specific and clear. Here's the full honest picture:

***

## The Core Architecture Decision

InsightFace `buffalo_l` is **already ONNX-based** — it's literally 5 ONNX model files under the hood (detection, landmarks, recognition, etc.). This is great news: you **don't need to convert anything**. You just need to wire it up correctly with the right execution provider.[^1]

The challenge isn't the ML — it's **packaging it cleanly for end users** who just click "Install".

***

## GPU Strategy: Exactly Like Blender

Blender detects your GPU at launch and uses it. You want the same. Here's how it works for InsightFace:

```python
# This is your GPU detection logic — priority waterfall
providers = []

# NVIDIA GPU (CUDA)
providers.append("CUDAExecutionProvider")

# AMD / Intel GPU (DirectML — works on ANY Windows GPU via DirectX 12)
providers.append("DmlExecutionProvider")

# CPU fallback — always last
providers.append("CPUExecutionProvider")

app = FaceAnalysis(name="buffalo_l", providers=providers)
app.prepare(ctx_id=0, det_size=(640, 640))
```

ONNX Runtime automatically **falls down the list** — if CUDA isn't available, it tries DirectML, then CPU. DirectML is the key — it works on **NVIDIA, AMD, and Intel GPUs** on Windows via DirectX 12 with no extra driver install from the user.[^2][^3][^4]

***

## The Real Problem: Packaging for "Click Install"

InsightFace on Windows is notoriously painful to install manually. Your users can't run `pip install` — they need a double-click installer. Here's the production-grade solution:[^5][^6]

### Recommended Stack

| Layer | Tool | Why |
| :-- | :-- | :-- |
| **App framework** | **PyQt6 or PySide6** | Native Windows UI, GPU-aware, ships as `.exe` |
| **ML backend** | **InsightFace + ONNX Runtime** | Already ONNX, GPU via CUDA/DirectML |
| **Packaging** | **PyInstaller + Inno Setup** | Creates a proper `.exe` installer like Blender |
| **GPU detection** | **ONNX Runtime EP waterfall** | Auto CUDA → DirectML → CPU |
| **Model bundling** | Bundle `buffalo_l` model files inside installer | No internet needed at runtime |

### Why PySide6/PyQt6 over Flutter/Electron?

- Your ML code is **Python** — keeping everything in Python avoids FFI bridges[^7]
- PySide6 is what tools like **DaVinci Resolve, Shotcut, and many AI desktop apps** use
- Ships as a proper Windows `.exe` — users never see Python or pip
- GPU rendering for the UI itself via OpenGL/Vulkan

***

## The Installer Flow (What Users Experience)

```
user downloads:  FaceApp_Setup_v1.0.exe  (made with Inno Setup)
        ↓
 clicks install → install → install → finish
        ↓
 app launches → auto-detects GPU
        ↓
 "Using NVIDIA RTX 4070 (CUDA)" ← shows in status bar
 "Using AMD RX 7600 (DirectML)"
 "No GPU found, using CPU"
```

Behind the scenes, your PyInstaller bundle contains:

- Your Python app + PySide6
- `onnxruntime-gpu` DLLs (CUDA) + `onnxruntime-directml` DLLs
- `buffalo_l` model files (pre-downloaded, ~500MB)
- MSVC redistributables (silent install)

***

## AI Agent: Claude Code is the Right Call

For this project specifically, Claude Code is the right choice  because:[^8]

- It will write **PyInstaller `.spec` files** correctly — this is notoriously tricky with GPU DLLs and hidden imports
- It handles the **Inno Setup script** for the installer wizard
- It writes the **ONNX Runtime execution provider waterfall** correctly with proper error handling
- It manages **multi-threaded inference** (running buffalo_l in a background thread so the UI doesn't freeze)
- It knows about the **CUDA DLL bundling problem** on Windows (a common packaging trap)[^2]

Use this `CLAUDE.md` prompt structure:

```
App: Windows desktop facial recognition app
ML: InsightFace buffalo_l via ONNX Runtime
GPU: Auto-detect CUDA → DirectML → CPU fallback
UI: PySide6, modern dark theme
Packaging: PyInstaller + Inno Setup (.exe installer)
Models: Bundle buffalo_l inside installer (offline runtime)
Goal: End user clicks install 3 times, app runs, GPU auto-detected
```


***

## Watch Out For

- **CUDA DLL hell** — PyInstaller doesn't auto-bundle CUDA DLLs; you need to manually add `cudart64_12.dll`, `cublas64_12.dll` etc. to your `.spec` file — Claude Code knows this[^2]
- **buffalo_l auto-download** — by default InsightFace downloads models at first run; you should pre-bundle them so offline installs work[^1]
- **numpy version** — InsightFace requires `numpy<2` currently[^5]
- **Installer size** — expect ~800MB–1.5GB installer with models + CUDA DLLs bundled; that's normal (Blender is 250MB, DaVinci Resolve is 3GB)
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^9]</span>

<div align="center">⁂</div>

[^1]: https://forums.developer.nvidia.com/t/inisightface-custom-model-pipelining-in-deepstream-for-face-recognition/357747

[^2]: https://discuss.huggingface.co/t/run-onnxruntime-for-insightface-model/74338

[^3]: https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html

[^4]: https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/supported-execution-providers

[^5]: https://github.com/cobanov/insightface_windows

[^6]: https://stackoverflow.com/questions/77747968/cant-pip-install-insightface-0-7-3

[^7]: https://www.buildmvpfast.com/blog/best-mobile-app-frameworks-ai-2026

[^8]: https://www.nxcode.io/resources/news/claude-code-vs-cursor-which-is-better-2026

[^9]: https://www.reddit.com/r/comfyui/comments/18ou0ly/installing_insightface/

[^10]: https://pyshine.com/Deep-Live-Cam-Real-Time-Face-Swap/

[^11]: https://www.youtube.com/watch?v=WKKIPUOkYqs

[^12]: https://github.com/deepinsight/insightface/issues/1824

[^13]: https://www.youtube.com/watch?v=vCCVxGtCyho

[^14]: https://pypi.org/project/insightface/

[^15]: https://www.piwheels.org/project/insightface/

[^16]: https://github.com/deepinsight/insightface/issues/2751

[^17]: https://piptrends.com/package/insightface

