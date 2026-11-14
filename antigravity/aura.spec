# -*- mode: python ; coding: utf-8 -*-
"""
AURA — PyInstaller Spec File (v2.0.0)
=====================================

Build command:
    pyinstaller aura.spec

This produces a FOLDER-mode distribution (--onedir) in:
    dist/AURA/

Why --onedir and NOT --onefile:
  • Startup is 5-10x faster (no temp extraction of 500+ MB)
  • Native DLLs (CUDA, OpenCV, ONNX) load reliably
  • Easier to debug missing-file issues
  • The Inno Setup installer hides the folder structure from users anyway
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ─────────────────────────────────────────────────────────
# Project paths
# ─────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.abspath('.')
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')
WHATSAPP_DIR = os.path.join(PROJECT_ROOT, 'whatsapp_tool')
PYSIDE_DIR = os.path.join(PROJECT_ROOT, 'aura_app')
ASSETS_DIR = os.path.join(PYSIDE_DIR, 'assets')

# InsightFace models — bundled for offline use
MODELS_SRC = os.path.join(os.path.expanduser('~'), '.insightface', 'models', 'buffalo_l')


# ─────────────────────────────────────────────────────────
# Analysis: Entry point + hidden imports + data files
# ─────────────────────────────────────────────────────────

# Collect ALL submodules for libraries that use lazy/dynamic imports
# PyInstaller's static analysis misses these without explicit listing

hidden_imports = [
    # ── Our own project modules ──────────────────────────
    'dist_utils',

    # backend.app.*
    'app',
    'app.config',
    'app.db',
    'app.worker',
    'app.watcher',
    'app.processor',
    'app.cluster',
    'app.cloud',
    'app.router',
    'app.enrollment',
    'app.phase',
    'app.upload_queue',
    'app.compute',          # GPU (DirectML) vs CPU choice; replaced app.gpu_manager
    'app.gallery_access',   # per-guest gallery keys (server + Share Links window)

    # frontend
    'server',

    # aura_app
    'aura_app',
    'aura_app.main',
    'aura_app.app_window',
    'aura_app.theme',
    'aura_app.process_manager',
    'aura_app.worker_bridge',

    # aura_app.widgets
    'aura_app.widgets',
    'aura_app.widgets.settings_dialog',
    'aura_app.widgets.health_monitor',
    'aura_app.widgets.self_healing_dialog',
    'aura_app.widgets.auth_dialog',
    # 'aura_app.widgets.gpu_wizard',  # retired 2026-11-14 (CUDA wizard), see _archive_cuda_gpu/
    'aura_app.widgets.whatsapp_tracker',
    'aura_app.widgets.first_run_wizard',
    'aura_app.widgets.share_links_dialog',
    'segno',
    'aura_app.splash_screen',

    # whatsapp_tool
    'whatsapp_tool.db_whatsapp_sender',

    # ── Playwright (WhatsApp browser automation) ──────────
    'playwright',
    'playwright.async_api',
    'playwright._impl',
    'playwright._impl._api_types',
    'playwright._impl._connection',
    'playwright._impl._driver',
    'playwright._impl._transport',

    # ── InsightFace (notorious for missing submodules) ────
    'insightface',
    'insightface.app',
    'insightface.app.face_analysis',
    'insightface.data',
    'insightface.model_zoo',
    'insightface.model_zoo.model_zoo',
    'insightface.model_zoo.arcface_onnx',
    'insightface.model_zoo.retinaface',
    'insightface.model_zoo.scrfd',
    'insightface.model_zoo.landmark',
    'insightface.model_zoo.attribute',
    'insightface.model_zoo.inswapper',
    'insightface.utils',
    'insightface.utils.face_align',
    'insightface.utils.transform',
    'insightface.utils.download',
    'insightface.utils.storage',

    # ── ONNX Runtime ─────────────────────────────────────
    'onnxruntime',
    'onnxruntime.capi',
    'onnxruntime.capi._pybind_state',
    'onnxruntime.capi.onnxruntime_pybind11_state',

    # ── OpenCV ────────────────────────────────────────────
    'cv2',

    # ── NumPy / SciPy / scikit-learn ─────────────────────
    'numpy',
    'numpy.core',
    'numpy.core._methods',
    'numpy.lib',
    'numpy.lib.format',
    'sklearn',
    'sklearn.cluster',
    'sklearn.cluster._dbscan',
    'sklearn.utils',
    'sklearn.utils._cython_blas',
    'sklearn.neighbors',
    'sklearn.neighbors._ball_tree',
    'sklearn.neighbors._kd_tree',
    'sklearn.metrics',
    'sklearn.metrics.pairwise',

    # ── PIL / Pillow + format plugins ────────────────────
    'PIL',
    'PIL.Image',
    'PIL.JpegImagePlugin',
    'PIL.PngImagePlugin',
    'PIL.WebPImagePlugin',
    'PIL.TiffImagePlugin',
    'PIL.BmpImagePlugin',
    'PIL.GifImagePlugin',
    'pillow_heif',
    'pillow_avif',

    # ── rawpy (RAW image support) ────────────────────────
    'rawpy',
    'rawpy._rawpy',

    # ── Google APIs ──────────────────────────────────────
    'google.auth',
    'google.auth.transport',
    'google.auth.transport.requests',
    'google.oauth2',
    'google.oauth2.credentials',
    'google.oauth2.service_account',
    'google_auth_oauthlib',
    'google_auth_oauthlib.flow',
    'google_auth_httplib2',
    'googleapiclient',
    'googleapiclient.discovery',
    'googleapiclient.http',
    'googleapiclient.errors',
    'httplib2',

    # ── FastAPI + Uvicorn (frontend web server) ──────────
    'fastapi',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'fastapi.staticfiles',
    'fastapi.responses',
    'starlette',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.staticfiles',
    'starlette.responses',
    'uvicorn',
    'uvicorn.config',
    'uvicorn.main',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'h11',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'pydantic',
    'pydantic.fields',
    'python_multipart',

    # ── PySide6 — usually auto-detected, but just in case
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtWidgets',
    'PySide6.QtGui',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',

    # ── Monitoring (optional but installed) ──────────────
    'psutil',
    'GPUtil',

    # ── Standard library that PyInstaller sometimes misses
    'multiprocessing',
    'sqlite3',
    'json',
    'email.mime.text',
    'encodings',
    'encodings.utf_8',
    'encodings.cp1252',
    'encodings.ascii',
    'encodings.latin_1',
]

# Also auto-collect any submodules we might have missed
hidden_imports += collect_submodules('insightface')
hidden_imports += collect_submodules('onnxruntime')
hidden_imports += collect_submodules('uvicorn')
hidden_imports += collect_submodules('sklearn')
hidden_imports += collect_submodules('google.auth')
hidden_imports += collect_submodules('googleapiclient')
hidden_imports += collect_submodules('playwright')

# Deduplicate
hidden_imports = list(set(hidden_imports))


# ─────────────────────────────────────────────────────────
# Data files to bundle (src_path, dest_in_bundle)
# ─────────────────────────────────────────────────────────

# Google sign-in client (credentials.json): kept outside the project in
# %USERPROFILE%\AURA-secrets (or AURA_SECRETS_DIR) since 2026-11-14.
def _find_oauth_client():
    for folder in (os.environ.get('AURA_SECRETS_DIR'),
                   os.path.join(os.path.expanduser('~'), 'AURA-secrets'),
                   PROJECT_ROOT):
        if folder and os.path.isfile(os.path.join(folder, 'credentials.json')):
            return os.path.join(folder, 'credentials.json')
    raise SystemExit("BUILD STOPPED: credentials.json (Google sign-in client) not found in "
                     "AURA_SECRETS_DIR, %USERPROFILE%\AURA-secrets or the project folder")

OAUTH_CLIENT_FILE = _find_oauth_client()


def _source_tree(src_dir, dest_dir):
    """Copy a source folder file by file, skipping __pycache__/.pyc. Copying
    whole folders shipped stale caches of deleted modules (2026-11-14)."""
    out = []
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        rel = os.path.relpath(root, src_dir)
        for f in files:
            if not f.endswith(('.pyc', '.pyo')):
                out.append((os.path.join(root, f), os.path.normpath(os.path.join(dest_dir, rel))))
    return out


datas = [
    # dist_utils (our path resolver)
    (os.path.join(PROJECT_ROOT, 'dist_utils.py'), '.'),

    # Frontend (HTML + CSS + JS for the web portal)
    (os.path.join(FRONTEND_DIR, 'index.html'), 'frontend'),
    (os.path.join(FRONTEND_DIR, 'css'), os.path.join('frontend', 'css')),
    (os.path.join(FRONTEND_DIR, 'js'), os.path.join('frontend', 'js')),
    (os.path.join(FRONTEND_DIR, 'server.py'), 'frontend'),

    # WhatsApp tool
    (os.path.join(WHATSAPP_DIR, 'db_whatsapp_sender.py'), 'whatsapp_tool'),


    # Assets (app icon)
    (os.path.join(ASSETS_DIR, 'logo.png'), os.path.join('aura_app', 'assets')),

    # Intro video (splash screen animation)
    (os.path.join(PROJECT_ROOT, 'logo'), 'logo'),

    # Clean default settings (copied to %LOCALAPPDATA%\AURA\.env on first launch).
    # NEVER bundle the developer's own .env.
    (os.path.join(PROJECT_ROOT, '.env.template'), '.'),

    # Google sign-in client ("Desktop app" OAuth client ID). Not a user secret:
    # it only opens the Google sign-in page; each user signs in with their own
    # account and their token.json is written to AppData at runtime.
    (OAUTH_CLIENT_FILE, '.'),

    # Backend Python source and PySide6 app package are added below with
    # _source_tree() (no __pycache__).

    # NOT bundled on purpose: .env, token.json, service_account.json.
    # Those belong to the developer and would give every user access to the
    # developer's Google Drive. See the safety check below.
]

datas += _source_tree(os.path.join(BACKEND_DIR, 'app'), os.path.join('backend', 'app'))
datas += _source_tree(PYSIDE_DIR, 'aura_app')   # PySide6 app package (needed for imports to work)

# InsightFace ONNX models (~325 MB)
# Bundle them so the app works offline immediately after install
if os.path.isdir(MODELS_SRC):
    datas.append((MODELS_SRC, os.path.join('models', 'buffalo_l')))
else:
    print(f"WARNING: InsightFace models not found at {MODELS_SRC}")
    print("         The user will need to download models on first launch.")

# Auto-collect data files for libraries with non-Python assets
datas += collect_data_files('insightface')
datas += collect_data_files('onnxruntime')
datas += collect_data_files('cv2')
datas += collect_data_files('sklearn')
datas += collect_data_files('certifi')
datas += collect_data_files('google_auth_oauthlib')
datas += collect_data_files('pydantic')

# Playwright driver (node.js executable + protocol files)
try:
    datas += collect_data_files('playwright')
except Exception:
    print("WARNING: Could not collect playwright data files")


# ─────────────────────────────────────────────────────────
# Safety check: never ship the developer's secrets
# ─────────────────────────────────────────────────────────
# Fails the build if a private file would end up in the installer,
# whether listed directly or sitting inside a bundled folder.

import json as _json

_FORBIDDEN_NAMES = {'.env', 'token.json', 'service_account.json',
                    'my_credentials_backup.txt', 'gallery_secret.key'}

def _iter_bundled_files(src):
    if os.path.isdir(src):
        for _root, _dirs, _files in os.walk(src):
            for _f in _files:
                yield os.path.join(_root, _f)
    else:
        yield src

_leaks = [p for _src, _dst in datas for p in _iter_bundled_files(_src)
          if os.path.basename(p).lower() in _FORBIDDEN_NAMES]
if _leaks:
    raise SystemExit("BUILD STOPPED: private files would be bundled:\n  " + "\n  ".join(_leaks))

# credentials.json must be a Desktop-app OAuth client, never a service-account key
with open(OAUTH_CLIENT_FILE, encoding='utf-8') as _fh:
    _client = _json.load(_fh)
if 'installed' not in _client or 'private_key' in _client:
    raise SystemExit("BUILD STOPPED: credentials.json is not a Desktop-app OAuth client "
                     "(it must contain an 'installed' section and no private key)")


# ─────────────────────────────────────────────────────────
# Binaries — native DLLs that PyInstaller might miss
# ─────────────────────────────────────────────────────────

binaries = []

# rawpy has a native extension that sometimes gets missed
try:
    import rawpy
    rawpy_dir = os.path.dirname(rawpy.__file__)
    for f in os.listdir(rawpy_dir):
        if f.endswith(('.pyd', '.dll', '.so')):
            binaries.append((os.path.join(rawpy_dir, f), 'rawpy'))
except ImportError:
    pass

# pillow_heif native extension
try:
    import pillow_heif
    heif_dir = os.path.dirname(pillow_heif.__file__)
    for f in os.listdir(heif_dir):
        if f.endswith(('.pyd', '.dll', '.so')):
            binaries.append((os.path.join(heif_dir, f), 'pillow_heif'))
except ImportError:
    pass


# ─────────────────────────────────────────────────────────
# Exclusions — reduce bundle size by removing unused packages
# ─────────────────────────────────────────────────────────

excludes = [
    # Heavy packages we definitely don't use
    # 'matplotlib',  # insightface/thirdparty/face3d needs it
    # 'scipy',  # WARNING: DO NOT EXCLUDE SCIPY. InsightFace requires it at runtime!
    'torch',         # In case someone has PyTorch installed
    'tensorflow',
    'keras',
    'jupyter',
    'notebook',
    'IPython',
    'pandas',

    # Test frameworks
    'pytest',
    'pytest_cov',
    # 'unittest',  # numpy.testing imports unittest, insightface depends on it

    # Development tools
    'pylint',
    'black',
    'mypy',
    'flake8',
    'autopep8',

    # PySide6 modules we don't use (saves ~100 MB)
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DRender',
    'PySide6.QtBluetooth',
    'PySide6.QtCharts',
    'PySide6.QtDataVisualization',
    'PySide6.QtDesigner',
    # 'PySide6.QtMultimedia',        # NEEDED for intro video splash screen
    # 'PySide6.QtMultimediaWidgets',  # NEEDED for intro video splash screen
    'PySide6.QtNetworkAuth',
    'PySide6.QtNfc',
    'PySide6.QtPositioning',
    'PySide6.QtQuick',
    'PySide6.QtQuick3D',
    'PySide6.QtQuickControls2',
    'PySide6.QtQuickWidgets',
    'PySide6.QtRemoteObjects',
    'PySide6.QtScxml',
    'PySide6.QtSensors',
    'PySide6.QtSerialBus',
    'PySide6.QtSerialPort',
    'PySide6.QtSpatialAudio',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtTest',
    'PySide6.QtTextToSpeech',
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    'PySide6.QtXml',

    # Tkinter (not used — we use PySide6)
    'tkinter',
    '_tkinter',
    'customtkinter',
]


# ─────────────────────────────────────────────────────────
# Path list — where PyInstaller should look for imports
# ─────────────────────────────────────────────────────────

pathex = [
    PROJECT_ROOT,
    BACKEND_DIR,
    FRONTEND_DIR,
    WHATSAPP_DIR,
]


# ═══════════════════════════════════════════════════════════
# SPEC DEFINITION
# ═══════════════════════════════════════════════════════════

a = Analysis(
    ['run_pyside.py'],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    exclude_binaries=True,
    name='AURA',
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],                      # Empty = --onedir mode (not --onefile)
    exclude_binaries=True,   # Binaries go in the folder, not the exe
    name='AURA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX compression can break native DLLs
    console=False,           # GUI app — no console window
    disable_windowed_traceback=False,
    icon=os.path.join(ASSETS_DIR, 'logo.ico'),
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AURA',
)
