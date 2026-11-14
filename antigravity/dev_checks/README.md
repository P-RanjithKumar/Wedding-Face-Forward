# dev_checks

Manual check scripts written on 2026-11-14 while fixing AURA (see `todo/future_improvements.md`).
They use throwaway folders, never the real event data or `%LOCALAPPDATA%\AURA`.

Run from `antigravity/`, with a scratch folder as the second argument:

| Script | What it checks | Example |
| :-- | :-- | :-- |
| `smoke_frozen.py` | The BUILT app (`dist\AURA\AURA.exe`) as a fresh install: no secrets bundled, server, worker with real models + GPU speed test, real selfie match, gallery keys, desktop app starts, Chromium download | `python dev_checks/smoke_frozen.py . C:\temp\aura_checks <path to a group photo>` |
| `test_step2.py` | First launch copies no credentials; spec secret-leak guard | `python dev_checks/test_step2.py . C:\temp\aura_checks` |
| `test_step3.py` | Guest-only server, per-guest gallery keys, upload hardening | same pattern |
| `test_step3b.py` | Guest page selfie flow in a phone-sized browser (Playwright) | same pattern |
| `test_step4.py` | Clustering race (old vs new), atomic merge, folder merge | same pattern |
| `test_reliability.py` | Free guest port, process supervisor, selfie cleanup | `set QT_QPA_PLATFORM=offscreen` first |
| `test_share.py` | Share Links window, direct gallery links | `set PYTHONIOENCODING=utf-8` first |
| `test_compute.py` | GPU (DirectML) vs CPU choice with real models | `python dev_checks/test_compute.py . <group photo> C:\temp\aura_checks` |
| `bench_compute.py` | Speed comparison of CPU/GPU setups | `python dev_checks/bench_compute.py <group photo>` |

A group photo for testing ships with InsightFace: `<site-packages>/insightface/data/images/t1.jpg`.
The permanent unit tests are in `backend/tests/` (`cd backend; python -m pytest -q tests`).
