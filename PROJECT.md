# Project: Glide Ultra Local Studio — Final Polishing & Technical Hardening

## Architecture
- **Web Layer**: FastAPI / Starlette application in `app.py` serving `/` and `/api/*` endpoints. Launcher in `web_app.py` running on port 8787.
- **Frontend Layer**: Vanilla HTML5, CSS3, and JavaScript in `frontend/` (`index.html`, `style.css`, `app.js`, `modules/runtime-config.js`). High performance 60 FPS micro-animations, theme support, responsive grid.
- **Desktop Packaging Layer**: PyInstaller bundle (`GlideUltra.spec`) embedding Python runtime, Web/API backend, and frontend assets, displayed via `pywebview` in `desktop_app.py` with EdgeChromium/WinForms engine.
- **Multimedia Engine**: Single-pass fused video rendering with NVENC acceleration (`render_single_chunk_fused`), monotonic DP speech-to-text alignment (`glide_align.py`), EBU R128 mastering (`glide_audio_master.py`), ASS subtitle burning, and SFX mixing (`glide_core/audio/sfx_mixer.py`).
- **Thermal Governance**: `HardwareThermalGovernor` in `glide_core/hardware/thermal_governor.py` with GPU telemetry, dynamic breathers, mobile worker calibration, and NVENC concurrency gating (`_NvencGate`).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | 1440p / Ultrawide Viewport Alignment | Constrain `.render-dock` width to flush-align with `.app` max-width (1920px) | M1 | Survey (explorer_frontend) |
| F2 | Responsive Grid Adaptation (1051px-1250px) | Prevent card squeezing and horizontal overflow in `.grid.two` down to 1080x680 min size | M1 | Survey (explorer_frontend) |
| F3 | Production Level Description Multi-Line Wrapping | Remove `nowrap + ellipsis` in `.level-desc` to eliminate truncated text | M1 | Survey (explorer_frontend) |
| F4 | Duplicate Select Options & Contrast Fix | Remove duplicate `smart_auto` in `<select>` elements and replace hardcoded inline colors with CSS variables | M1 | Survey (explorer_frontend) |
| F5 | SFX Attack Micro-Fade | Add 4ms attack micro-fade (`afade=t=in:st=0:d=0.004`) after silence truncation in `make_sfx_clip` | M2 | Survey (explorer_multimedia) |
| F6 | SFX Buffer Step Discontinuity Ramp | Apply 192-sample (4ms) entry/exit ramp envelope in `sfx_mixer.py` during in-memory WAV assembly | M2 | Survey (explorer_multimedia) |
| F7 | Expanded Audio Bit Depth Support | Add 24-bit PCM (`sampwidth == 3`) and 32-bit float (`sampwidth == 4`) parsing in `_load_and_normalize_clip` | M2 | Survey (explorer_multimedia) |
| F8 | Universal Laptop Thermal Fallback Pacing | Inject 0.25s chunk breather when `is_laptop` is detected and GPU temperature is unavailable | M2 | Survey (explorer_multimedia) |
| F9 | Global Import Fixes in app.py | Add module-level `import logging` / logger definition and `import numpy as np` to restore dHash and YuNet face detector | M2 | Survey (explorer_desktop) |
| F10 | Desktop Executable Compilation & Local Install Sync | Recompile `Glide Studio.exe` via PyInstaller, update root, `dist/`, and `%LOCALAPPDATA%\Programs\Glide Studio\`, verify SHA-256 equivalence | M3 | Survey (explorer_desktop) |
| F11 | Full Automated Test & Smoke Test Gate Verification | Verify 97/97 tests pass, 114/114 full suite, native `--smoke-test` code 0 with 14/14 HTTP 200 | M4 | Survey (all explorers) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Frontend UI/UX Aesthetic Refinement | `frontend/index.html`, `frontend/style.css`, `frontend/app.js` | none | DONE |
| M2 | Backend Multimedia Precision & Stability | `app.py`, `glide_core/audio/sfx_mixer.py`, `glide_core/hardware/thermal_governor.py` | none | DONE |
| M3 | Desktop Packaging & Dual Sync | `GlideUltra.spec`, `installer.py`, `Glide Studio.exe` synchronization | M1, M2 | DONE |
| M4 | Final E2E Test Suite & Adversarial Hardening | Full test suite, smoke test, API checks, coverage audit | M3 | DONE |

## Interface Contracts
### Frontend ↔ Backend API
- Health check: `GET /api/health` -> `{"status": "ok", ...}` HTTP 200
- Config: `GET /api/config` -> `{"version": "1.40.0", ...}` HTTP 200
- CTA Assets: `GET /api/cta-assets` -> JSON list HTTP 200
- Static assets: `GET /static/style.css`, `GET /static/app.js`, `GET /static/modules/runtime-config.js` HTTP 200

### Audio Engine ↔ SFX Mixer
- `sfx_mixer.mix_sfx_tracks(bed_arr, total_frames, channels, sfx_clips)`:
  - Input: `bed_arr` (int32 numpy array), `sfx_clips` list of `(clip_arr, start_frame, volume)`
  - Output: normalized mixed array with boundary zero-crossing envelope ramps applied.

### Packaging ↔ Installation Paths
- Root Executable: `Glide Studio.exe`
- Dist Executable: `dist\Glide Studio.exe`
- User Install Path: `%LOCALAPPDATA%\Programs\Glide Studio\Glide Studio.exe`
- All 3 match identical SHA-256 hash: `BA383ED0F2D1A41F8B1F0D1A81530CAAD4D054B425E4F419D84304B52081B162`.

## Code Layout
- `frontend/`: Static web UI assets (`index.html`, `style.css`, `app.js`, `modules/runtime-config.js`)
- `glide_core/`: Core internal modules
  - `glide_core/audio/`: Audio mixing and mastering (`sfx_mixer.py`, etc.)
  - `glide_core/hardware/`: Hardware and thermal management (`thermal_governor.py`, etc.)
- `app.py`: Main application backend, API routes, and rendering pipeline
- `desktop_app.py`: Desktop wrapper and native CLI commands (`--smoke-test`)
- `web_app.py`: Web edition entry point
- `tests/`: Automated unit and regression test suite
  - `tests/test_stability.py`: Stability and resource tests
  - `tests/test_auto_mode.py`: Auto mode state and resilience tests
  - `tests/test_regressions.py`: Regression and concurrency tests
- `GlideUltra.spec`: PyInstaller specification for desktop packaging
