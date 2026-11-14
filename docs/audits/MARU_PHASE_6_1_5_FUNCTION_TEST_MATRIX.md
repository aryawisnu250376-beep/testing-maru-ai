# MARU HQ — PHASE 6.1.5 FUNCTION TEST MATRIX
**Branch:** `fix/phase-6-1-5-comprehensive-audit-remediation`  
**Base Target:** `fix/phase-6-1-4-security-closure`  
**Execution Timestamp:** 2026-11-02  

| Subsystem | File Path | Function / Method | Normal Test | Boundary / Unauthorized Test | Result |
|---|---|---|---|---|---|
| **HQ Memory** | `src/hq/memory.py` | `InternalAuthAuthority.issue_principal` | Token session generation | Invalid actor rejection | **VERIFIED (PASS)** |
| **HQ Memory** | `src/hq/memory.py` | `CallerContext.resolve_authenticated` | Valid token resolution | Expired / revoked / malformed token rejection | **VERIFIED (PASS)** |
| **HQ Memory** | `src/hq/memory.py` | `HQMemoryStore.store` | Authorized store in scope | Unauthenticated store in private scope rejected | **VERIFIED (PASS)** |
| **HQ Memory** | `src/hq/memory.py` | `HQMemoryStore.update` | Authorized editor update | Cross-agent update rejected (PermissionError) | **VERIFIED (PASS)** |
| **HQ Memory** | `src/hq/memory.py` | `HQMemoryStore.delete` | Authorized tombstone delete | Cross-agent delete rejected (PermissionError) | **VERIFIED (PASS)** |
| **HQ Memory** | `src/hq/memory.py` | `HQMemoryStore.query` | Scoped retrieval | Reader ID spoofing fails closed | **VERIFIED (PASS)** |
| **HQ Worker** | `src/hq/worker.py` | `HQWorker.execute_one_cycle` | Normal task completion | Non-cooperative hard timeout (OS process kill) | **VERIFIED (PASS)** |
| **HQ Queue** | `src/hq/queue.py` | `HQJobQueue.enqueue` | Idempotent deduplication | Nonexistent dependency / loop rejection | **VERIFIED (PASS)** |
| **HQ Queue** | `src/hq/queue.py` | `HQJobQueue.complete_job` | Valid worker lease | Stale worker / expired fencing token rejection | **VERIFIED (PASS)** |
| **HQ Router** | `src/hq/router.py` | `HQModelRouter.route_task` | Deterministic fallback | Offline mode returns UNVERIFIED_DRAFT | **VERIFIED (PASS)** |
| **Academic AI** | `02-academic-ai/app` | Full test suite (129 tests) | Vector store, PDF chunking, Sessions | Token expiration, LAN isolation, drive mock | **VERIFIED (PASS)** |
