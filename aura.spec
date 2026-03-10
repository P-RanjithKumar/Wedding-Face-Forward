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
    'app.gpu_manager',

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
    'aura_app.widgets.gpu_wizard',
    'aura_app.widgets.whatsapp_tracker',
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

datas = [
    # dist_utils (our path resolver)
    (os.path.join(PROJECT_ROOT, 'dist_utils.py'), '.'),

    # Backend Python source
    (os.path.join(BACKEND_DIR, 'app'), os.path.join('backend', 'app')),

    # Frontend (HTML + CSS + JS for the web portal)
    (os.path.join(FRONTEND_DIR, 'index.html'), 'frontend'),
    (os.path.join(FRONTEND_DIR, 'css'), os.path.join('frontend', 'css')),
    (os.path.join(FRONTEND_DIR, 'js'), os.path.join('frontend', 'js')),
    (os.path.join(FRONTEND_DIR, 'server.py'), 'frontend'),

    # WhatsApp tool
    (os.path.join(WHATSAPP_DIR, 'db_whatsapp_sender.py'), 'whatsapp_tool'),

    # PySide6 app package (needed for imports to work)
    (PYSIDE_DIR, 'aura_app'),

    # Assets (app icon)
    (os.path.join(ASSETS_DIR, 'logo.png'), os.path.join('aura_app', 'assets')),

    # Intro video (splash screen animation)
    (os.path.join(PROJECT_ROOT, 'logo'), 'logo'),

    # .env template (will be copied to AppData on first launch)
    (os.path.join(PROJECT_ROOT, '.env'), '.'),

    # Credential placeholders (templates for first-launch wizard)
    (os.path.join(PROJECT_ROOT, 'credentials.json'), '.'),
    (os.path.join(BACKEND_DIR, 'service_account.json'), os.path.join('backend', '.')),
]

# Include token.json if it exists (carry over dev auth)
if os.path.exists(os.path.join(PROJECT_ROOT, 'token.json')):
    datas.append((os.path.join(PROJECT_ROOT, 'token.json'), '.'))

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
