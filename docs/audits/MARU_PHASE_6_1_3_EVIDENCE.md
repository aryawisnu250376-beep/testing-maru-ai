# MARU HQ PHASE 6.1.3 — REPRODUCIBLE EVIDENCE REPORT
**Repository**: `aryawisnu250376-beep/testing-maru-ai`  
**Active Branch**: `fix/login-session-office-rendering`  
**Pull Request**: `https://github.com/aryawisnu250376-beep/testing-maru-ai/pull/1`  
**Execution Date**: 2026-11-02  

---

## 1. Reproducible Test Execution Logs

### A. Authentication, Session Security & Memory Permissions
Command: `python -m unittest tests/test_auth_and_rendering.py -v`
```text
test_01_login_success ... ok
test_02_login_incorrect_credentials ... ok
test_03_login_missing_credentials ... ok
test_04_access_protected_without_auth ... ok
test_05_access_protected_with_invalid_token ... ok
test_06_url_query_token_rejected_no_header_leakage ... ok
test_07_access_valid_authenticated_session ... ok
test_08_logout_invalidates_session ... ok
test_09_memory_strict_permission_boundaries ... ok
test_10_studio_canonical_source_and_csp ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.831s
OK (100% SUCCESS)
```

### B. HQ Core Canonical Job Engine Suite
Command: `python -m tests.hq.run_all`
```text
======================================================================
MARU HQ — FULL CANONICAL TEST SUITE (PHASE 6.1.1 + PHASE 6.1.2)
======================================================================
Ran 33 tests in 12.790s
TOTAL TESTS RUN: 33
FAILURES: 0
ERRORS: 0
FINAL RESULT: PASS (100% SUCCESS)
======================================================================
```

### C. Legacy Division Pipeline Verification
Command: `cd 01-social-media-agent && python -m pytest tests/test_pipeline.py -q`
```text
................                                                         [100%]
16 passed in 0.79s
```

---

## 2. Modified & Hardened Files Inventory
- `01-social-media-agent/src/dashboard.py`: Removed query token parsing; restricted to headers; added CSP whitelist for Three.js CDNs; attached employee roster.
- `01-social-media-agent/src/studio.html`: Stripped `_st` token serialization; immediate 401 session clearing; added CDN offline safety fallback.
- `studio_bulletproof.html`: Synchronized 100% with canonical studio source.
- `src/hq/worker.py` & `01-social-media-agent/src/hq/worker.py`: Implemented isolated execution thread hard-timeout guardian.
- `src/hq/memory.py` & `01-social-media-agent/src/hq/memory.py`: Implemented strict permission boundaries for `AGENT`, `DIVISION`, and `HQ_ONLY` scopes.
- `.github/workflows/ci.yml`: Root-level CI/CD pipeline covering Python 3.11 & 3.12 syntax check and multi-suite testing.
- `tests/test_auth_and_rendering.py`: Comprehensive test suite for session, security, and permissions.
- `docs/audits/MARU_PHASE_6_1_3_REPAIR_REPORT.md`: Comprehensive audit report.
- `docs/audits/MARU_PHASE_6_1_3_EVIDENCE.md`: Evidence and reproducibility document.
