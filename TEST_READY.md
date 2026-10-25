# E2E Test Suite Ready

## Test Runner
- Automated Regression Suite: `.\.venv-build311\Scripts\python.exe -m unittest tests.test_stability tests.test_auto_mode tests.test_regressions`
- Full Discovery Suite: `.\.venv-build311\Scripts\python.exe -m unittest discover -s tests`
- Native Executable Smoke Test: `.\'Glide Studio.exe' --smoke-test`
- Installed Executable Smoke Test: `& "$env:LOCALAPPDATA\Programs\Glide Studio\Glide Studio.exe" --smoke-test`
- Expected: All tests pass with exit code 0, 14/14 HTTP 200 routes in `desktop_smoke_ok.json`.

## Coverage Summary
| Tier | Count | Description |
|------|------:|-------------|
| 1. Feature Coverage | 55 | >=5 cases per feature (F1-F11) |
| 2. Boundary & Corner | 55 | Min window 1080x680, 1440p, short SFX, high-res audio, thermal limits |
| 3. Cross-Feature | 11 | End-to-end integration across UI, A/V, Thermal, Packaging |
| 4. Real-World Application | 4 | Complete batch render, window resize, thermal pacing, web/desktop parity |
| **Total** | **125** | Full verification coverage |

## Feature Checklist
| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Status |
|---------|:------:|:------:|:------:|:------:|:------:|
| F1 (1440p Viewport Alignment) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F2 (Responsive Grid 1051-1250px) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F3 (Level Description Wrapping) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F4 (Select Options & Contrast) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F5 (SFX Attack Micro-Fade) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F6 (SFX Buffer Envelope Ramp) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F7 (24/32-bit Audio Support) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F8 (Laptop Thermal Fallback) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F9 (Global Imports in app.py) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F10 (Desktop Compilation & Sync) | 5 | 5 | ✓ | ✓ | VERIFIED |
| F11 (Full Automated Tests & Smoke) | 5 | 5 | ✓ | ✓ | VERIFIED |
