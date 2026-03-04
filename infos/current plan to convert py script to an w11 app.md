<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# this is my current project, mostly just a prototype..

now i wanna create a windows app, which does the same things..
but no need to install things like python, onxx etc etc and setup the path in windows etc etc.

what i wanna do is make a windows app, user should just download and install like anyother apps, and then magic the app should work all perfectly and a satisfied user..

now how can i do this ??

Now I have a solid picture of your project. Here's a complete roadmap to turn **Wedding Face Forward** into a professional Windows installer.

## The Strategy: PyInstaller + Inno Setup

The gold standard approach for your stack is a two-step pipeline:[^1][^2]

1. **PyInstaller** bundles your Python code, all libraries (ONNX Runtime, InsightFace, CustomTkinter, FastAPI, Playwright, rawpy, etc.) + the Python interpreter itself into a `dist/` folder.
2. **Inno Setup** wraps that `dist/` folder into a single `setup.exe` that users download and install like any normal Windows app.

The end user never sees Python, never touches pip, never configures PATH — it just works.[^3]

***

## Step 1: Prepare PyInstaller

Install it in your project's venv:

```bash
pip install pyinstaller
```

Your entry point is `WeddingFFapp.py` (the CustomTkinter dashboard that also launches the backend workers and FastAPI server via `run.py`). Start with:

```bash
pyinstaller --name "WeddingFF" --windowed --onedir WeddingFFapp.py
```

- `--windowed` suppresses the black console terminal from popping up[^4]
- `--onedir` (recommended over `--onefile` for AI apps) keeps DLLs in a folder — this is critical because ONNX Runtime has many native DLLs that don't play well inside a single compressed `.exe`[^5]

***

## Step 2: Handle the Tricky Dependencies

This is the most important part for your project. PyInstaller won't auto-detect everything.

**ONNX Runtime** — Add a custom hook file `hook-onnxruntime.py` in your project root:[^5]

```python
# hook-onnxruntime.py
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs
datas, binaries, hiddenimports = collect_all('onnxruntime')
binaries += collect_dynamic_libs('onnxruntime')
```

**InsightFace / Buffalo_L model** — The `.onnx` model files need to be explicitly included as data files in your `.spec` file:

```python
# In your .spec file, add to datas:
datas = [
    ('backend/app', 'backend/app'),
    ('.insightface', '.insightface'),  # buffalo_L model cache folder
    ('frontend', 'frontend'),
    ('credentials.json', '.'),
    ('.env', '.'),
]
```

**Playwright/Chromium** — This one is complex. Playwright's bundled Chromium browser (~150MB) must be included. The cleanest way is to include the Playwright browser directory:

```python
# Add to binaries in .spec:
('path/to/playwright/driver', 'playwright/driver'),
```

Alternatively, during first launch, your app can auto-run `playwright install chromium` silently if Chromium is not found — this is the more practical approach.

**CustomTkinter themes** — Must be explicitly added as `datas` since PyInstaller misses them:

```python
import customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)
# Add (ctk_path, 'customtkinter') to datas
```


***

## Step 3: Build and Test

Run PyInstaller with your `.spec` file:

```bash
pyinstaller WeddingFF.spec
```

Test the output `dist/WeddingFF/WeddingFF.exe` on a **clean Windows machine** (ideally a VM with no Python installed) to catch any missing DLLs or files.[^6]

***

## Step 4: Create the Installer with Inno Setup

Once `dist/WeddingFF/` works perfectly, wrap it into a proper installer:[^2]

1. Download and install **Inno Setup** (free, from jrsoftware.org)
2. Use the Wizard to point it at your `dist/WeddingFF/` folder
3. Key things to configure in the `.iss` script:
```ini
[Setup]
AppName=Wedding Face Forward
AppVersion=1.0
DefaultDirName={autopf}\WeddingFF
DefaultGroupName=Wedding Face Forward
OutputBaseFilename=WeddingFF_Setup

[Files]
Source: "dist\WeddingFF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Wedding Face Forward"; Filename: "{app}\WeddingFF.exe"
Name: "{commondesktop}\Wedding Face Forward"; Filename: "{app}\WeddingFF.exe"

[Run]
; Optionally run a first-time setup script after install
Filename: "{app}\WeddingFF.exe"; Description: "Launch WeddingFF"; Flags: postinstall
```

This produces a single `WeddingFF_Setup.exe` that users can download.[^7]

***

## Handling the `.env` \& `credentials.json`

Since these contain sensitive/user-specific config, you have two good options:

- **Bundle empty templates** (`.env.example`) and on first launch, show a **setup wizard** inside the app asking for Google Drive credentials and folder paths.
- Or let the installer prompt for these values via Inno Setup's `[Code]` section and write them to the install directory.

***

## Quick Summary of Tools

| Tool | Purpose |
| :-- | :-- |
| **PyInstaller** | Bundles Python + all libs + ONNX/InsightFace into `dist/` folder |
| **Inno Setup** | Wraps `dist/` into a `setup.exe` with Start Menu + Desktop shortcuts |
| **Hook file** | Fixes ONNX Runtime DLL discovery for PyInstaller [^5] |
| **Clean VM test** | Validates the build on a Python-free Windows machine |

The biggest challenge you'll face is the Playwright/Chromium bundling — would you like to go deeper on how to handle that specifically, or on the first-launch setup wizard approach for credentials?
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://realpython.com/pyinstaller-python/

[^2]: https://cyrille.rossant.net/create-a-standalone-windows-installer-for-your-python-application/

[^3]: https://www.pyinstaller.org

[^4]: https://pyinstaller.org/en/latest/usage.html

[^5]: https://github.com/microsoft/onnxruntime/issues/25193

[^6]: https://stackoverflow.com/questions/79841828/pyinstaller-exe-crashes-silently-when-loading-ai-model

[^7]: https://www.youtube.com/watch?v=87apPk8NuS0

[^8]: project_structure.md

[^9]: system_architecture.md

[^10]: README.md

[^11]: https://github.com/microsoft/onnxruntime/issues/24044

[^12]: https://onnxruntime.ai/docs/install/

[^13]: https://dev.to/arhamrumi/build-a-one-file-exe-with-pyinstaller-including-binaries-resources-3o00

[^14]: https://python101.pythonlibrary.org/chapter44_creating_an_installer.html

[^15]: https://www.youtube.com/watch?v=jPnl5-bQGHI

[^16]: https://www.youtube.com/watch?v=nJQh1L9Y70U

[^17]: https://stackoverflow.com/questions/17543262/creating-a-windows-installer-for-python-using-inno-setup

[^18]: https://www.reddit.com/r/learnprogramming/comments/1hfj8qs/using_inno_setup_how_to_create_an_installer_for_a/

