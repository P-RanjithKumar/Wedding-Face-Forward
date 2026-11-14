"""Step 2 checks: simulated frozen first launch, spec safety check, cloud 'not connected'."""
import os, sys, shutil, types, tempfile, logging
from pathlib import Path

PROJ = Path(sys.argv[1]).resolve()
SCRATCH = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(PROJ))
logging.basicConfig(level=logging.INFO, format="   log %(levelname)s %(message)s")

# ── 1. Simulated installed-app first launch ─────────────────────────
work = SCRATCH / "t_bootstrap"
shutil.rmtree(work, ignore_errors=True)
bundle = work / "bundle"; appdata = work / "appdata"
bundle.mkdir(parents=True); appdata.mkdir()
shutil.copy2(PROJ / ".env.template", bundle / ".env.template")
shutil.copy2(Path.home() / "AURA-secrets" / "credentials.json", bundle / "credentials.json")
os.environ["LOCALAPPDATA"] = str(appdata)
sys.frozen = True; sys._MEIPASS = str(bundle)
import dist_utils
dist_utils.bootstrap_user_data()
aura = appdata / "AURA"
files = sorted(p.name for p in aura.iterdir())
print("1. AppData after first launch:", files)
assert (aura / ".env").read_text() == (PROJ / ".env.template").read_text()
for bad in ("token.json", "service_account.json", "credentials.json"):
    assert not (aura / bad).exists(), bad
assert dist_utils.get_oauth_client_path() == bundle / "credentials.json"
assert dist_utils.get_token_path() == aura / "token.json"
print("   PASS: clean .env, no credentials copied, sign-in client found in bundle")

# ── 4. Cloud with no sign-in (still 'frozen' into the temp AppData) ──
sys.path.insert(0, str(PROJ / "backend"))
from app import config as cfgmod
cfgmod.reset_config()
os.environ.pop("DRIVE_ROOT_FOLDER_ID", None)
os.environ["GOOGLE_CREDENTIALS_FILE"] = "service_account.json"
cfg = cfgmod.Config.from_env()
# event_root parent is also searched for token.json; keep it inside temp AppData
assert str(cfg.event_root).startswith(str(aura)), cfg.event_root
from app.cloud import CloudManager, get_auth_status
cm = CloudManager(cfg)
print("4. Cloud enabled with no sign-in:", cm.is_enabled, "| auth status:", get_auth_status()["token_exists"])
assert cm.is_enabled is False
print("   PASS: no crash, cloud reports not connected")
del sys.frozen; del sys._MEIPASS

# ── 3. Spec safety check, run with PyInstaller stubbed out ───────────
def run_spec(extra_datas_line=None):
    spec = (PROJ / "aura.spec").read_text(encoding="utf-8")
    if extra_datas_line:
        spec = spec.replace("# Playwright driver", extra_datas_line + "\n# Playwright driver", 1)
    hooks = types.ModuleType("PyInstaller.utils.hooks")
    hooks.collect_data_files = lambda *a, **k: []
    hooks.collect_submodules = lambda *a, **k: []
    for name in ("PyInstaller", "PyInstaller.utils"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["PyInstaller.utils.hooks"] = hooks
    captured = {}
    stub = lambda *a, **k: types.SimpleNamespace(pure=[], zipped_data=[], scripts=[], binaries=[], datas=k.get("datas", []))
    def analysis(*a, **k):
        captured["datas"] = k.get("datas"); return stub(*a, **k)
    g = {"__name__": "__main__", "Analysis": analysis, "PYZ": stub, "EXE": stub, "COLLECT": stub}
    cwd = os.getcwd(); os.chdir(PROJ)
    try:
        exec(compile(spec, "aura.spec", "exec"), g)
    finally:
        os.chdir(cwd)
    return captured["datas"]

datas = run_spec()
names = sorted({os.path.basename(s) for s, d in datas if os.path.isfile(s)})
print("3. Spec ran. Top-level bundled files:", names)
assert ".env" not in names and "token.json" not in names and "service_account.json" not in names
assert ".env.template" in names and "credentials.json" in names
try:
    run_spec("datas.append((os.path.join(PROJECT_ROOT, 'token.json'), '.'))")
    print("   FAIL: leak not blocked"); sys.exit(1)
except SystemExit as e:
    print("   PASS: leaked token.json blocked ->", str(e).splitlines()[0])
print("ALL CHECKS PASSED")
