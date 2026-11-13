# MARU HQ PHASE 6.1.3 — REPRODUCIBLE EVIDENCE REPORT
**Repository**: `aryawisnu250376-beep/testing-maru-ai`  
**Active Branch**: `fix/login-session-office-rendering`  
**Latest Commit SHA**: `cfa9a0f`  
**Draft Pull Request**: `https://github.com/aryawisnu250376-beep/testing-maru-ai/pull/1`  
**Execution Date**: 2026-11-02  
**CI/CD Engine**: GitHub Actions (Ubuntu-latest)  

---

## 1. Bukti Aktual GitHub Actions CI/CD (100% SUCCESS)

Workflow resmi pada `.github/workflows/ci.yml` telah dipicu secara langsung di server GitHub dan mencatatkan hasil **SUCCESS** pada seluruh matriks Python 3.11 dan Python 3.12:

- **Run ID (Push Event)**: `43460333614`  
  👉 **Tautan Run GitHub Actions**: [`https://github.com/aryawisnu250376-beep/testing-maru-ai/actions/runs/43460333614`](https://github.com/aryawisnu250376-beep/testing-maru-ai/actions/runs/43460333614)  
  - **Job Python 3.11**: `SUCCESS` (Checkout, Syntax Check 64+ files, Auth & Rendering Suite, HQ Engine 33 checks, Pipeline Suite)
  - **Job Python 3.12**: `SUCCESS` (Checkout, Syntax Check 64+ files, Auth & Rendering Suite, HQ Engine 33 checks, Pipeline Suite)
- **Run ID (Pull Request #1 Event)**: `43460353679`  
  👉 **Tautan Run PR**: [`https://github.com/aryawisnu250376-beep/testing-maru-ai/actions/runs/43460353679`](https://github.com/aryawisnu250376-beep/testing-maru-ai/actions/runs/43460353679)  
  - **Status**: `COMPLETED` / `SUCCESS`

---

## 2. Rincian Pengujian yang Berhasil Diverifikasi

### A. Authentication, Session Security & Memory Permissions
Perintah: `python -m unittest tests/test_auth_and_rendering.py -v`
```text
test_01_login_success ... ok (200 OK + Bearer token)
test_02_login_incorrect_credentials ... ok (401 Unauthorized)
test_03_login_missing_credentials ... ok (401 Unauthorized)
test_04_access_protected_without_auth ... ok (401 Unauthorized)
test_05_access_protected_with_invalid_token ... ok (401 Unauthorized)
test_06_url_query_token_rejected_no_header_leakage ... ok (Token di URL query parameter ?_st= DITOLAK mentah-mentah)
test_07_access_valid_authenticated_session ... ok (200 OK + snapshot karyawan lengkap)
test_08_logout_invalidates_session ... ok (Logout mencabut token di server, request berikutnya 401)
test_09_memory_strict_permission_boundaries ... ok (Negative testing: Agent A dilarang baca Agent B, Divisi A dilarang baca Divisi B, HQ_ONLY terlindungi)
test_10_studio_canonical_source_and_csp ... ok (Three.js fallback aman, CSP whitelist, 9 Leaders sceneGroup utuh)

----------------------------------------------------------------------
Ran 10 tests in 0.831s
OK (100% SUCCESS)
```

### B. HQ Core Canonical Job Engine Suite (33 Kasus)
Perintah: `python -m tests.hq.run_all`
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
Perintah: `cd 01-social-media-agent && python -m pytest tests/test_pipeline.py -q`
```text
................                                                         [100%]
16 passed in 0.79s
```

---

## 3. Ringkasan File Kritis yang Telah Dikuatkan & Berada di GitHub

1. `01-social-media-agent/src/dashboard.py`:
   - Metode `_token()` membaca token otentikasi eksklusif dari header HTTP (`Authorization: Bearer` dan `X-Maru-Token`).
   - Penolakan akses token dari parameter URL query.
   - Header CSP diperbarui dengan whitelist domain CDN Three.js (`https://cdnjs.cloudflare.com`, `https://cdn.jsdelivr.net`) dan Google Fonts.
2. `01-social-media-agent/src/studio.html` & `studio_bulletproof.html`:
   - Menghapus parameter `_st` pada fetch client.
   - Membatalkan sesi secara instan pada respons HTTP 401 pertama kali tanpa loop polling.
   - Memasang fallback rendering informatif jika Three.js offline.
3. `src/hq/worker.py` & `01-social-media-agent/src/hq/worker.py`:
   - Hard timeout guardian terisolasi dengan thread worker terpisah (`isolated_execution`) dan `handler_done.wait(timeout=max_duration)`.
4. `src/hq/memory.py` & `01-social-media-agent/src/hq/memory.py`:
   - Pembatasan izin memori `AGENT:<id>`, `DIVISION:<id>`, `HQ_ONLY`, dan `ORGANIZATIONAL`.
5. `.github/workflows/ci.yml`:
   - Terpasang di root repositori dan terbukti berhasil running hijau di GitHub Actions.
