# MARU HQ — PHASE 6.1.4 SECURITY CLOSURE REMEDIATION EVIDENCE & LOGS
**Status:** DRAFT / AUDIT EVIDENCE  
**Branch:** `fix/phase-6-1-4-security-closure`  
**Base Repository:** `aryawisnu250376-beep/testing-maru-ai`  
**Execution Timestamp:** 2026-11-02  

---

## 1. Bukti Eksekusi Remediation & Security Suite (`tests/test_auth_and_rendering.py`)

Perintah:
```bash
python3 -m unittest tests/test_auth_and_rendering.py -v
```

Log Output Terminal:
```text
test_01_memory_rejects_is_hq_spoofing (tests.test_auth_and_rendering.TestPhase613Remediation.test_01_memory_rejects_is_hq_spoofing)
Negative test: Specialist agent (EMP-L02) cannot pass is_hq=True to access HQ_ONLY memory. ... ok
test_02_memory_rejects_division_spoofing (tests.test_auth_and_rendering.TestPhase613Remediation.test_02_memory_rejects_division_spoofing)
Negative test: Agent A cannot spoof reader_division to access Division B's private memory. ... ok
test_03_cross_division_isolation (tests.test_auth_and_rendering.TestPhase613Remediation.test_03_cross_division_isolation)
Agent A (Creative) cannot retrieve Agent B (Audio) private memory. ... ok
test_04_authorized_hq_access_success (tests.test_auth_and_rendering.TestPhase613Remediation.test_04_authorized_hq_access_success)
Authorized HQ Core (EMP-L01 / Director) can access all memory categories. ... ok
test_05_deleted_memory_omitted (tests.test_auth_and_rendering.TestPhase613Remediation.test_05_deleted_memory_omitted)
Soft-deleted memory cannot be retrieved. ... ok
test_06_process_hard_timeout_terminates_non_cooperative_handler (tests.test_auth_and_rendering.TestPhase613Remediation.test_06_process_hard_timeout_terminates_non_cooperative_handler)
P4: Non-cooperative hanging handler is terminated at OS process level and cannot complete. ... ok
test_07_normal_process_handler_completes (tests.test_auth_and_rendering.TestPhase613Remediation.test_07_normal_process_handler_completes)
Normal handler running in process-isolation mode completes successfully. ... ok
test_08_deterministic_ttl_expiration (tests.test_auth_and_rendering.TestPhase613Remediation.test_08_deterministic_ttl_expiration)
P5: AuthManager token expiration is proven deterministically via simulated clock. ... ok
test_09_logout_invalidates_token_deterministically (tests.test_auth_and_rendering.TestPhase613Remediation.test_09_logout_invalidates_token_deterministically) ... ok
test_10_url_query_token_rejected_no_header_leakage (tests.test_auth_and_rendering.TestPhase613Remediation.test_10_url_query_token_rejected_no_header_leakage)
Verified: Passing ?_st=token in URL parameter without header is rejected with 401. ... ok
test_11_access_valid_authenticated_session (tests.test_auth_and_rendering.TestPhase613Remediation.test_11_access_valid_authenticated_session) ... ok
test_12_studio_canonical_source_and_csp (tests.test_auth_and_rendering.TestPhase613Remediation.test_12_studio_canonical_source_and_csp)
P2: Verify canonical studio source, CSP header, and Three.js fallback. ... ok

----------------------------------------------------------------------
Ran 12 tests in 1.854s

OK
```

---

## 2. Bukti Eksekusi HQ Canonical Suite (`tests/hq/run_all.py`)

Perintah:
```bash
python3 -m tests.hq.run_all
```

Log Output Terminal:
```text
======================================================================
TOTAL TESTS RUN: 33
FAILURES: 0
ERRORS: 0
FINAL RESULT: PASS (100% SUCCESS)
======================================================================
```

---

## 3. Bukti Visual Audit Browser & Rendering

Bukti visual disimpan pada folder repository:
`docs/audits/evidence/phase-6-1-4/`
1. `docs/audits/evidence/phase-6-1-4/studio_office_canvas_inspection.png`: Struktur layout 3D Office, Canvas Three.js element, CSP verification, dan Roster integritas 27 karakter.
2. `docs/audits/evidence/phase-6-1-4/auth_and_security_verification.png`: Diagram bukti TTL 24 jam deterministik, penolakan token leakage via URL query parameter, otorisasi server-side roster memori, dan terminasi hard-timeout proses OS.
