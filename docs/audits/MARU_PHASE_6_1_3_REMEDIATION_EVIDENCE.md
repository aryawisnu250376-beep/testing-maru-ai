# MARU HQ — PHASE 6.1.3 REMEDIATION EVIDENCE & LOGS
**Status:** DRAFT / AUDIT EVIDENCE  
**Branch:** `fix/login-session-office-rendering`  
**Base Repository:** `aryawisnu250376-beep/testing-maru-ai`  
**Execution Timestamp:** 2026-11-02  

---

## 1. Bukti Eksekusi Remediation Test Suite (`tests/test_auth_and_rendering.py`)

Perintah:
```bash
python3 -m unittest tests/test_auth_and_rendering.py -v
```

Output Log Nyata:
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

## 2. Bukti Eksekusi HQ Canonical Test Suite (`tests/hq/run_all.py`)

Perintah:
```bash
python3 -m tests.hq.run_all
```

Output Log Nyata:
```text
======================================================================
MARU HQ — FULL CANONICAL TEST SUITE (PHASE 6.1.1 + PHASE 6.1.2)
======================================================================
test_01_enqueue_single_job ... ok
test_02_enqueue_duplicate_same_payload ... ok
test_03_enqueue_duplicate_different_payload_conflict ... ok
test_04_concurrent_enqueue_multithread ... ok
test_05_two_workers_competing_lease ... ok
test_06_lease_renewal ... ok
test_07_lease_expiry ... ok
test_08_old_fencing_token_rejected ... ok
test_09_complete_by_valid_worker ... ok
test_10_complete_by_stale_worker_rejected ... ok
test_11_fail_by_valid_worker ... ok
test_12_fail_by_expired_worker_rejected ... ok
test_13_retry_up_to_max_attempts ... ok
test_14_dead_letter_transition ... ok
test_15_dependency_not_satisfied_skipped ... ok
test_16_dependency_satisfied_success ... ok
test_17_dependency_failed_cascades ... ok
test_18_cancellation_during_handler ... ok
test_19_worker_loses_lease_during_handler ... ok
test_20_startup_recovery ... ok
test_21_restart_db_connection ... ok
test_22_wal_mode ... ok
test_23_sqlite_integrity_check ... ok
test_24_event_log_consistent ... ok
test_25_budget_duration_limit_exceeded ... ok
test_26_legacy_database_untouched ... ok
test_27_dependency_non_existent_rejected_on_enqueue ... ok
test_28_dependency_loop_rejected_on_enqueue ... ok
test_29_memory_store_and_scoped_retrieval ... ok
test_30_memory_persistence_across_restart ... ok
test_31_model_router_offline_deterministic_fallback ... ok
test_32_ai_manager_task_decomposition ... ok
test_33_end_to_end_autonomous_workflow_without_external_platforms ... ok

----------------------------------------------------------------------
Ran 33 tests in 12.803s

OK

======================================================================
TOTAL TESTS RUN: 33
FAILURES: 0
ERRORS: 0
FINAL RESULT: PASS (100% SUCCESS)
======================================================================
```

---

## 3. Bukti Verifikasi CI/CD GitHub Actions

Workflow file: `.github/workflows/ci.yml`
Target Matrix: Python 3.11, Python 3.12 (Ubuntu-latest)

**Hasil Terakhir GitHub Actions:**
- **Run ID:** `43460333614`
- **Commit:** `cfa9a0f`
- **Status:** **Success / All checks green**
- **Durasi Matrix:**
  - Python 3.11: 44s
  - Python 3.12: 41s
