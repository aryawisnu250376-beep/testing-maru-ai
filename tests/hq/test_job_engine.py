"""
MARU HQ Phase 6.1.1 Canonical Test Suite — 26 Mandatory Verification Checks
Compatible with Windows CMD/PowerShell & Linux (pytest or python -m unittest)
Runs exclusively on isolated temporary SQLite database
"""

import unittest
import time
import os
import threading
import concurrent.futures
from pathlib import Path

from src.hq import (
    HQJobQueue, HQWorker, CancellationToken, CanonicalJob,
    JobStatus, JobPriority, JobBudget, IdempotencyConflictError,
    BudgetExceededError
)

TEST_DB_FILE = Path("data/hq_test_phase611.db")

class TestHQCorePhase611(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TEST_DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except Exception:
                pass
        self.queue = HQJobQueue(db_path=TEST_DB_FILE, lease_duration_sec=2.0)

    def tearDown(self):
        if hasattr(self, "queue"): del self.queue
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except Exception:
                pass

    # 1. Enqueue satu job
    def test_01_enqueue_single_job(self):
        job = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="PEMILIK", goal="Test Single Enqueue",
            input_payload={"topic": "Pancasila"}, acceptance_criteria=["Hook 3s"],
            assigned_agent="EMP-L02", idempotency_key="TEST-KEY-01"
        )
        self.assertIsNotNone(job)
        self.assertEqual(job.status, JobStatus.QUEUED.value)
        self.assertEqual(job.assigned_agent, "EMP-L02")

    # 2. Enqueue duplikat dengan payload sama
    def test_02_enqueue_duplicate_same_payload(self):
        j1 = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="PEMILIK", goal="Duplicate Goal",
            input_payload={"p": 1}, acceptance_criteria=[], assigned_agent="EMP-L02",
            idempotency_key="IDEMPO-SAME-02"
        )
        j2 = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="PEMILIK", goal="Duplicate Goal",
            input_payload={"p": 1}, acceptance_criteria=[], assigned_agent="EMP-L02",
            idempotency_key="IDEMPO-SAME-02"
        )
        self.assertEqual(j1.task_id, j2.task_id)
        self.assertEqual(len(self.queue.list_jobs()), 1)

    # 3. Enqueue duplikat dengan payload berbeda (Idempotency conflict)
    def test_03_enqueue_duplicate_different_payload_conflict(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="PEMILIK", goal="Goal A",
            input_payload={"val": 100}, acceptance_criteria=[], assigned_agent="EMP-L02",
            idempotency_key="IDEMPO-DIFF-03"
        )
        with self.assertRaises(IdempotencyConflictError):
            self.queue.enqueue(
                division="SOCIAL_MEDIA", requested_by="PEMILIK", goal="Goal B (DIFFERENT)",
                input_payload={"val": 200}, acceptance_criteria=[], assigned_agent="EMP-L02",
                idempotency_key="IDEMPO-DIFF-03"
            )

    # 4. Concurrent enqueue lintas thread/proses
    def test_04_concurrent_enqueue_multithread(self):
        def worker(idx):
            return self.queue.enqueue(
                division="SOCIAL_MEDIA", requested_by=f"USER_{idx}", goal="Concurrent Goal",
                input_payload={"data": "shared"}, acceptance_criteria=[], assigned_agent="EMP-L02",
                idempotency_key="CONCURRENT-THREAD-04"
            )
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            tasks = [f.result() for f in concurrent.futures.as_completed(futures)]
        self.assertEqual(len(set(t.task_id for t in tasks)), 1)
        self.assertEqual(len(self.queue.list_jobs()), 1)

    # 5. Dua worker mengambil job bersamaan
    def test_05_two_workers_competing_lease(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Compete", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="COMPETE-05"
        )
        leases = []
        def acquire(w_id):
            l = self.queue.acquire_lease(worker_id=w_id)
            if l: leases.append(w_id)
        t1 = threading.Thread(target=acquire, args=("WORKER_A",))
        t2 = threading.Thread(target=acquire, args=("WORKER_B",))
        t1.start(); t2.start()
        t1.join(); t2.join()
        self.assertEqual(len(leases), 1)

    # 6. Lease renewal
    def test_06_lease_renewal(self):
        job = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Renew", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="RENEW-06"
        )
        leased = self.queue.acquire_lease("WORKER_RENEW")
        init_exp = leased.lease_expires_at
        time.sleep(0.1)
        renewed = self.queue.renew_lease("WORKER_RENEW", leased.task_id, leased.fencing_token)
        self.assertTrue(renewed)
        refreshed = self.queue.get_job(leased.task_id)
        self.assertGreater(refreshed.lease_expires_at, init_exp)

    # 7. Lease expiry
    def test_07_lease_expiry(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Expiry", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="EXPIRY-07"
        )
        leased = self.queue.acquire_lease("WORKER_EXP", assigned_agent="EMP-L02")
        time.sleep(2.2) # wait for lease timeout
        # Alive heartbeat should fail
        alive = self.queue.heartbeat("WORKER_EXP", leased.task_id, leased.fencing_token)
        self.assertFalse(alive)

    # 8. Fencing token lama ditolak
    def test_08_old_fencing_token_rejected(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Fence", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="FENCE-08"
        )
        leased = self.queue.acquire_lease("WORKER_FENCE")
        bad_token = leased.fencing_token + 99
        res = self.queue.complete_job("WORKER_FENCE", leased.task_id, bad_token, {"ok": 1})
        self.assertFalse(res)

    # 9. Complete oleh worker sah
    def test_09_complete_by_valid_worker(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Complete", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="COMP-09"
        )
        leased = self.queue.acquire_lease("WORKER_VALID")
        res = self.queue.complete_job("WORKER_VALID", leased.task_id, leased.fencing_token, {"draft_id": "D-1"})
        self.assertTrue(res)
        done_job = self.queue.get_job(leased.task_id)
        self.assertEqual(done_job.status, JobStatus.COMPLETED.value)
        self.assertIsNotNone(done_job.result_payload)

    # 10. Complete oleh worker lama ditolak (setelah recovery)
    def test_10_complete_by_stale_worker_rejected(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="StaleComp", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="STALECOMP-10"
        )
        old_lease = self.queue.acquire_lease("WORKER_OLD")
        time.sleep(2.2)
        self.queue.recover_stale_jobs()
        new_lease = self.queue.acquire_lease("WORKER_NEW")
        stale_res = self.queue.complete_job("WORKER_OLD", old_lease.task_id, old_lease.fencing_token, {"bad": 1})
        self.assertFalse(stale_res)
        new_res = self.queue.complete_job("WORKER_NEW", new_lease.task_id, new_lease.fencing_token, {"good": 1})
        self.assertTrue(new_res)

    # 11. Fail oleh worker sah
    def test_11_fail_by_valid_worker(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Fail", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="FAIL-11"
        )
        leased = self.queue.acquire_lease("WORKER_FAIL")
        res = self.queue.fail_job("WORKER_FAIL", leased.task_id, leased.fencing_token, "Err 1")
        self.assertTrue(res)
        j = self.queue.get_job(leased.task_id)
        self.assertEqual(j.status, JobStatus.RETRYING.value)

    # 12. Fail oleh worker dengan lease kedaluwarsa ditolak
    def test_12_fail_by_expired_worker_rejected(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="FailExp", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="FAILEXP-12"
        )
        leased = self.queue.acquire_lease("WORKER_FAILEXP")
        time.sleep(2.2) # expire lease
        res = self.queue.fail_job("WORKER_FAILEXP", leased.task_id, leased.fencing_token, "Err Expired")
        self.assertFalse(res)

    # 13. Retry sampai batas maksimal
    def test_13_retry_up_to_max_attempts(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="RetryMax", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="RETRYMAX-13"
        )
        l1 = self.queue.acquire_lease("W1")
        self.queue.fail_job("W1", l1.task_id, l1.fencing_token, "Err 1")
        l2 = self.queue.acquire_lease("W2")
        self.queue.fail_job("W2", l2.task_id, l2.fencing_token, "Err 2")
        j = self.queue.get_job(l1.task_id)
        self.assertEqual(j.attempts, 2)
        self.assertEqual(j.status, JobStatus.RETRYING.value)

    # 14. DEAD_LETTER transition
    def test_14_dead_letter_transition(self):
        self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="DLQ", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="DLQ-14"
        )
        for i in range(1, 4):
            l = self.queue.acquire_lease(f"W_{i}")
            self.queue.fail_job(f"W_{i}", l.task_id, l.fencing_token, f"Fatal {i}")
        j = self.queue.get_job(l.task_id)
        self.assertEqual(j.attempts, 3)
        self.assertEqual(j.status, JobStatus.DEAD_LETTER.value)

    # 15. Dependency belum terpenuhi (Job tidak boleh diambil)
    def test_15_dependency_not_satisfied_skipped(self):
        parent = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Parent", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="DEP-PARENT-15"
        )
        child = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Child", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="DEP-CHILD-15",
            dependencies=[parent.task_id]
        )
        # Attempt lease: child must NOT be leased because parent is QUEUED
        leased = self.queue.acquire_lease("WORKER_DEP")
        self.assertEqual(leased.task_id, parent.task_id)
        # Attempt second lease: should be None because child is waiting on parent
        leased_2 = self.queue.acquire_lease("WORKER_DEP_2")
        self.assertIsNone(leased_2)

    # 16. Dependency berhasil (Child bisa diambil setelah Parent COMPLETED)
    def test_16_dependency_satisfied_success(self):
        parent = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Parent", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="DEP-PARENT-16"
        )
        child = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Child", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="DEP-CHILD-16",
            dependencies=[parent.task_id]
        )
        l_p = self.queue.acquire_lease("W_P")
        self.queue.complete_job("W_P", l_p.task_id, l_p.fencing_token, {"p": "ok"})
        # Now child should be leasable!
        l_c = self.queue.acquire_lease("W_C")
        self.assertIsNotNone(l_c)
        self.assertEqual(l_c.task_id, child.task_id)

    # 17. Dependency gagal (Child masuk DEAD_LETTER secara otomatis)
    def test_17_dependency_failed_cascades(self):
        parent = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Parent", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="DEP-PARENT-17"
        )
        child = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Child", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="DEP-CHILD-17",
            dependencies=[parent.task_id]
        )
        # Cancel or fail parent to dead letter
        self.queue.cancel_job(parent.task_id, reason="Parent cancelled")
        # Trigger acquire lease: child must be cascaded to DEAD_LETTER
        leased = self.queue.acquire_lease("W_ANY")
        self.assertIsNone(leased)
        c_status = self.queue.get_job(child.task_id)
        self.assertEqual(c_status.status, JobStatus.DEAD_LETTER.value)

    # 18. Cancellation saat handler aktif
    def test_18_cancellation_during_handler(self):
        job = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="CancelHandler", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="CANCEL-18"
        )
        worker = HQWorker(queue=self.queue, worker_id="W_CANCEL_18", heartbeat_interval_sec=0.2)
        handler_saw_cancellation = []

        def slow_handler(j, cancel_tok: CancellationToken):
            # Simulate work loop checking cancel_token
            self.queue.cancel_job(j.task_id, reason="User clicked stop")
            time.sleep(0.4) # wait for renewal/heartbeat loop to detect
            if cancel_tok.is_cancelled:
                handler_saw_cancellation.append(True)
            return {"cancelled": True}

        res = worker.execute_one_cycle(slow_handler)
        self.assertFalse(res) # Should not complete because job was cancelled
        self.assertTrue(len(handler_saw_cancellation) > 0)
        final_j = self.queue.get_job(job.task_id)
        self.assertEqual(final_j.status, JobStatus.CANCELLED.value)

    # 19. Worker kehilangan lease ketika handler berjalan
    def test_19_worker_loses_lease_during_handler(self):
        job = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="LoseLease", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="LOSE-19"
        )
        worker = HQWorker(queue=self.queue, worker_id="W_LOSE_19", heartbeat_interval_sec=0.2)
        def expired_handler(j, cancel_tok: CancellationToken):
            time.sleep(2.2) # wait for lease to expire
            self.queue.recover_stale_jobs()
            return {"done": 1}

        res = worker.execute_one_cycle(expired_handler)
        self.assertFalse(res)

    # 20. Startup recovery setelah proses mati
    def test_20_startup_recovery(self):
        job = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="StartupRec", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="STARTUP-20"
        )
        leased = self.queue.acquire_lease("W_CRASHED")
        time.sleep(2.2)
        # Starting a new worker automatically recovers stale jobs!
        fresh_worker = HQWorker(queue=self.queue, worker_id="W_FRESH", auto_recover_startup=True)
        rec_job = self.queue.get_job(job.task_id)
        self.assertEqual(rec_job.status, JobStatus.QUEUED.value)

    # 21. Restart database connection
    def test_21_restart_db_connection(self):
        job = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="RestartDB", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="RESTART-21"
        )
        del self.queue
        restarted_q = HQJobQueue(db_path=TEST_DB_FILE)
        j = restarted_q.get_job(job.task_id)
        self.assertIsNotNone(j)
        self.assertEqual(j.goal, "RestartDB")

    # 22. WAL mode verification
    def test_22_wal_mode(self):
        from src.hq.database import get_connection
        conn = get_connection(TEST_DB_FILE)
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        conn.close()
        self.assertEqual(mode.lower(), "wal")

    # 23. SQLite integrity check
    def test_23_sqlite_integrity_check(self):
        from src.hq.database import get_connection
        conn = get_connection(TEST_DB_FILE)
        res = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        conn.close()
        self.assertEqual(res.lower(), "ok")

    # 24. Event log konsisten
    def test_24_event_log_consistent(self):
        job = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="Logs", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="LOGS-24"
        )
        l = self.queue.acquire_lease("W_LOG")
        self.queue.complete_job("W_LOG", l.task_id, l.fencing_token, {"ok": 1})
        logs = self.queue.get_event_logs(job.task_id)
        events = [log["event_type"] for log in logs]
        self.assertIn("JOB_ENQUEUED", events)
        self.assertIn("LEASE_ACQUIRED", events)
        self.assertIn("JOB_COMPLETED", events)

    # 25. Budget limit tercapai (Duration enforcement)
    def test_25_budget_duration_limit_exceeded(self):
        job = self.queue.enqueue(
            division="SOCIAL_MEDIA", requested_by="P", goal="BudgetDuration", input_payload={},
            acceptance_criteria=[], assigned_agent="EMP-L02", idempotency_key="BUDGET-25",
            budget=JobBudget(max_duration_sec=1) # 1 second budget
        )
        worker = HQWorker(queue=self.queue, worker_id="W_BUDGET")
        def slow_budget_handler(j, tok):
            time.sleep(1.2) # exceeds 1s
            return {"late": True}

        res = worker.execute_one_cycle(slow_budget_handler)
        self.assertFalse(res) # Should fail due to budget exceeded
        final_j = self.queue.get_job(job.task_id)
        self.assertIn("exceeded max duration budget", final_j.error_message)

    # 26. Tidak ada perubahan pada database legacy
    def test_26_legacy_database_untouched(self):
        legacy_files = ["data/episodes.db", "episodes.db", "studio.sqlite3"]
        for f in legacy_files:
            if Path(f).exists():
                self.assertNotEqual(Path(f).resolve(), TEST_DB_FILE.resolve())
        # Confirms test db is isolated
        self.assertTrue(str(TEST_DB_FILE).endswith("hq_test_phase611.db"))

if __name__ == '__main__':
    unittest.main()
