# E2E Test Infra: Glide Ultra Local Studio

## Test Philosophy
- Opaque-box, requirement-driven verification covering UI/UX responsiveness, multimedia precision, thermal stability, and dual packaging synchronization.
- Derived strictly from `ORIGINAL_REQUEST.md` and user-facing acceptance criteria.

## Feature Inventory & Test Mapping
| # | Feature | Requirement | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) | Tier 4 (Workload) |
|---|---------|-------------|:-----------------:|:-----------------:|:----------------------:|:-----------------:|
| F1 | 1440p / Ultrawide Viewport Alignment | R1, Criteria 1 | 5 cases | 5 cases | ✓ | ✓ |
| F2 | Responsive Grid Adaptation (1051px-1250px) | R1, Criteria 1 | 5 cases | 5 cases | ✓ | ✓ |
| F3 | Production Level Description Multi-Line Wrapping | R1, Criteria 1 | 5 cases | 5 cases | ✓ | ✓ |
| F4 | Duplicate Select Options & Contrast Fix | R1, Criteria 3 | 5 cases | 5 cases | ✓ | ✓ |
| F5 | SFX Attack Micro-Fade | R2, Criteria 4 | 5 cases | 5 cases | ✓ | ✓ |
| F6 | SFX Buffer Step Discontinuity Ramp | R2, Criteria 4 | 5 cases | 5 cases | ✓ | ✓ |
| F7 | Expanded Audio Bit Depth Support | R2, Criteria 4 | 5 cases | 5 cases | ✓ | ✓ |
| F8 | Universal Laptop Thermal Fallback Pacing | R3, Criteria 7 | 5 cases | 5 cases | ✓ | ✓ |
| F9 | Global Import Fixes in app.py | R3, Criteria 4 | 5 cases | 5 cases | ✓ | ✓ |
| F10 | Desktop Executable Compilation & Local Install Sync | R4, Criteria 6 | 5 cases | 5 cases | ✓ | ✓ |
| F11 | Full Automated Test & Smoke Test Gate Verification | Criteria 4, 5 | 5 cases | 5 cases | ✓ | ✓ |

## Test Architecture
- **Automated Regression Suite**:
  - Command: `.\.venv-build311\Scripts\python.exe -m unittest tests.test_stability tests.test_auto_mode tests.test_regressions`
  - Pass criterion: Exactly 97 tests pass with exit code 0.
- **Full Discovery Suite**:
  - Command: `.\.venv-build311\Scripts\python.exe -m unittest discover -s tests`
  - Pass criterion: All 114 tests pass with exit code 0.
- **Native Desktop Smoke Test**:
  - Command: `.\'Glide Studio.exe' --smoke-test` (and `python desktop_app.py --smoke-test`)
  - Pass criterion: Exit code 0, `desktop_smoke_ok.json` output with `"ok": true` and HTTP 200 on all 14 routes.
- **Static Code Quality / Lint**:
  - Command: `.\.venv-build311\Scripts\python.exe -m ruff check --select F821,F822,F823,E9 *.py tests/*.py`
  - Pass criterion: 0 errors reported.
- **Frontend Syntax Validation**:
  - Command: `node --check frontend/app.js frontend/modules/runtime-config.js`
  - Pass criterion: Exit code 0.
- **Binary & Hash Integrity Check**:
  - Command: PowerShell `Get-FileHash` comparing root, `dist/`, and `%LOCALAPPDATA%\Programs\Glide Studio\Glide Studio.exe`
  - Pass criterion: Identical SHA-256 across all targets.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Full Auto Mode render with dual 9:16 export and ASS subtitles | F5, F6, F7, F8, F9 | High |
| 2 | Desktop window resize from 1440p down to 1080x680 minimum size | F1, F2, F3, F4 | Medium |
| 3 | Continuous multi-segment batch render under mobile thermal throttling profile | F8, F9, F11 | High |
| 4 | Offline Web Server launch vs Native Desktop Executable parity check | F10, F11 | Medium |
