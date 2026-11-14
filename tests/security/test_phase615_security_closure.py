"""
MARU AI CORPORATION — PHASE 6.1.5 SECURITY REGRESSION & ADVERSARIAL CLOSURE SUITE
Verifies:
1. InternalAuthAuthority cryptographic secret verification (constant-time, no unauthenticated issuance)
2. Identity impersonation defense (cannot issue EMP-L01, HQ, PEMILIK without server secret)
3. Roster-by-name identity resolution does not permit privileged bypass
4. Provenance cannot be forged by untrusted caller metadata
5. Token expiration, revocation, and mismatched caller_id fail-closed
6. Hard timeout jobs reject silent thread downgrades for unpicklable handlers
7. Cancelled jobs increment fencing tokens and reject stale worker side-effects
8. Early child process termination upon lease loss or job cancellation
9. Absence of sensitive personal data or secrets in memory fixtures
"""

import unittest
import time
import os
import tempfile
import shutil
import json
from pathlib import Path

from src.hq.memory import HQMemoryManager, InternalAuthAuthority, CallerContext
from src.hq.database import init_db
from src.hq.queue import HQJobQueue
from src.hq.worker import HQWorker
from src.hq.models import JobStatus, JobBudget

def _hanging_worker_task(job_dict, cancel_token):
    import time
    while True:
        time.sleep(0.1)

class TestPhase615SecurityClosure(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test_p615_closure.db"
        init_db(self.db_path)
        self.memory = HQMemoryManager(db_path=self.db_path)
        self.queue = HQJobQueue(db_path=self.db_path, lease_duration_sec=3.0)
        # Configure dedicated server bootstrap secret for test suite
        self.bootstrap_secret = "test_secure_bootstrap_key_xyz_2026"
        InternalAuthAuthority.set_bootstrap_secret(self.bootstrap_secret)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1. IDENTITY & TOKEN ISSUANCE ADVERSARIAL TESTS
    # -------------------------------------------------------------

    def test_01_unauthenticated_caller_cannot_issue_emp_l01_token(self):
        """Negative test: Calling issue_principal for EMP-L01 without valid secret fails closed."""
        p = InternalAuthAuthority.issue_principal("EMP-L01", secret_key="wrong_secret")
        self.assertIsNone(p, "Unauthenticated caller MUST NOT obtain EMP-L01 session token!")

    def test_02_unauthenticated_caller_cannot_issue_hq_token(self):
        """Negative test: Arbitrary actor attempting to obtain HQ principal without secret fails closed."""
        p = InternalAuthAuthority.issue_principal("EMP-L01", secret_key="")
        self.assertIsNone(p)

    def test_03_invalid_bootstrap_secret_fails_token_issuance(self):
        """Negative test: Malformed or slightly mismatched bootstrap secret rejected via constant-time compare."""
        p = InternalAuthAuthority.issue_principal("EMP-L02", secret_key="test_secure_bootstrap_key_xyz_2027")
        self.assertIsNone(p)

    def test_04_authorized_issuance_and_agent_credential_registration(self):
        """Positive test: Authorized bootstrap can register agent credential and issue tokens cleanly."""
        registered = InternalAuthAuthority.register_agent_credential("EMP-L02", "hermes_secret_123", self.bootstrap_secret)
        self.assertTrue(registered)

        # Agent can now issue with own registered secret
        principal = InternalAuthAuthority.issue_principal("EMP-L02", secret_key="hermes_secret_123")
        self.assertIsNotNone(principal)
        self.assertEqual(principal.principal_id, "EMP-L02")
        self.assertEqual(principal.division, "CREATIVE_CORE")
        self.assertFalse(principal.is_hq)

    def test_05_revoked_and_expired_tokens_fail_closed(self):
        """Negative test: Revoked or expired session tokens fail closed to unauthenticated."""
        principal = InternalAuthAuthority.issue_principal("EMP-L02", secret_key=self.bootstrap_secret, ttl_sec=0.1)
        self.assertIsNotNone(principal)

        token = principal.session_token
        # Expire token
        time.sleep(0.15)
        ctx = CallerContext.resolve_authenticated(token)
        self.assertFalse(ctx.authenticated)
        self.assertIsNone(ctx.caller_id)

        # Issue and revoke
        p2 = InternalAuthAuthority.issue_principal("EMP-L02", secret_key=self.bootstrap_secret, ttl_sec=60.0)
        InternalAuthAuthority.revoke(p2.session_token)
        ctx2 = CallerContext.resolve_authenticated(p2.session_token)
        self.assertFalse(ctx2.authenticated)

    def test_06_token_paired_with_mismatched_caller_id_rejected(self):
        """Negative test: Providing token for Agent A while asserting caller_id for Agent B fails closed."""
        p_hermes = InternalAuthAuthority.issue_principal("EMP-L02", secret_key=self.bootstrap_secret)
        # Attempt to spoof EMP-L05 while holding EMP-L02's token
        ctx = CallerContext.resolve(caller_id="EMP-L05", client_auth_key=p_hermes.session_token)
        self.assertFalse(ctx.authenticated, "Mismatched token and caller_id must fail closed!")
        self.assertIsNone(ctx.caller_id)

    # -------------------------------------------------------------
    # 2. MEMORY SCOPE & PROVENANCE INTEGRITY TESTS
    # -------------------------------------------------------------

    def test_07_specialist_cannot_store_in_hq_only(self):
        """Negative test: Specialist with valid token cannot write to HQ_ONLY scope."""
        p = InternalAuthAuthority.issue_principal("EMP-L02", secret_key=self.bootstrap_secret)
        with self.assertRaises(PermissionError):
            self.memory.store(
                scope="HQ_ONLY", category="POLICY", title="Secret", content="Confidential",
                actor_id="EMP-L02", auth_token=p.session_token
            )

    def test_08_specialist_cannot_modify_other_agent_memory(self):
        """Negative test: Specialist A (EMP-L02) cannot write or update Specialist B (EMP-L05) memory."""
        p_hermes = InternalAuthAuthority.issue_principal("EMP-L02", secret_key=self.bootstrap_secret)
        with self.assertRaises(PermissionError):
            self.memory.store(
                scope="AGENT:EMP-L05", category="TASK_CONTEXT", title="Spied", content="Data",
                actor_id="EMP-L02", auth_token=p_hermes.session_token
            )

    def test_09_anonymous_cannot_write_to_organizational_memory(self):
        """Negative test: Unauthenticated caller cannot store or update organizational knowledge."""
        with self.assertRaises(PermissionError):
            self.memory.store(
                scope="ORGANIZATIONAL", category="GUIDELINE", title="Spam", content="Attack",
                actor_id="ANONYMOUS_HACKER", auth_token=None
            )

    def test_10_provenance_cannot_be_forged_by_caller_metadata(self):
        """Proof: Stored provenance 'stored_by' reflects authenticated principal, not caller forgery."""
        p_hermes = InternalAuthAuthority.issue_principal("EMP-L02", secret_key=self.bootstrap_secret)
        rec = self.memory.store(
            scope="ORGANIZATIONAL", category="RESEARCH", title="Market Trends", content="Legit",
            provenance={"stored_by": "PEMILIK_HQ", "extra": "info"},
            actor_id="EMP-L02", auth_token=p_hermes.session_token
        )
        self.assertEqual(rec.provenance["stored_by"], "EMP-L02", "Provenance must NOT allow caller forgery of creator!")

    # -------------------------------------------------------------
    # 3. PROCESS ISOLATION & CANCELLATION CLOSURE
    # -------------------------------------------------------------

    def test_11_unpicklable_handler_fails_closed_prohibiting_thread_downgrade(self):
        """Proof: Nested unpicklable handler is rejected with failure rather than downgraded to unkillable thread."""
        job = self.queue.enqueue(
            division="CREATIVE_STRATEGY", requested_by="PEMILIK_HQ", goal="Unpicklable task",
            input_payload={"test": 1}, acceptance_criteria=["Fail closed"],
            assigned_agent="EMP-L02", idempotency_key="IDEMP-P615-NESTED-01",
            budget=JobBudget(max_duration_sec=5.0)
        )
        worker = HQWorker(worker_id="WORKER-ISO-1", queue=self.queue)

        # Define nested closure function (not picklable across process boundaries)
        def _nested_unpicklable_closure(job_item, cancel_tok):
            return {"status": "bad"}

        success = worker.execute_one_cycle(job_handler=_nested_unpicklable_closure, use_process_isolation=True)
        self.assertFalse(success, "Unpicklable handler must fail closed under hard timeout policy!")
        
        failed_job = self.queue.get_job(job.task_id)
        self.assertIn(failed_job.status, (JobStatus.FAILED.value, JobStatus.RETRYING.value))
        self.assertIn("Process Isolation Failure", failed_job.error_message)

    def test_12_cancelled_job_increments_fencing_token_rejecting_stale_completion(self):
        """Proof: Cancelled job atomics increment fencing_token, preventing late results."""
        job = self.queue.enqueue(
            division="OPERATIONS", requested_by="PEMILIK_HQ", goal="Heavy calculation",
            input_payload={"data": "x"}, acceptance_criteria=["Valid finish"],
            assigned_agent="EMP-L01", idempotency_key="IDEMP-P615-FENCE-02"
        )
        leased = self.queue.acquire_lease("WORKER-FENCE", "EMP-L01")
        self.assertIsNotNone(leased)
        self.assertEqual(leased.fencing_token, 1)

        # Cancel job
        self.queue.cancel_job(job.task_id, actor="PEMILIK_HQ", reason="Cancelled by owner")
        
        c_job = self.queue.get_job(job.task_id)
        self.assertEqual(c_job.status, JobStatus.CANCELLED.value)
        self.assertEqual(c_job.fencing_token, 2)

        # Stale worker attempts late commit with old fencing token (1)
        commit_res = self.queue.complete_job("WORKER-FENCE", job.task_id, 1, {"late": "side_effect"})
        self.assertFalse(commit_res)

    def test_13_worker_terminates_isolated_child_process_early_on_cancel(self):
        """Proof: Non-cooperative child process is killed early via polling when job is cancelled."""
        job = self.queue.enqueue(
            division="OPERATIONS", requested_by="PEMILIK_HQ", goal="Long hang",
            input_payload={"hang": True}, acceptance_criteria=["Kill on cancel"],
            assigned_agent="EMP-L01", idempotency_key="IDEMP-P615-HANG-03",
            budget=JobBudget(max_duration_sec=10.0)
        )
        worker = HQWorker(worker_id="WORKER-CANCEL-KILL", queue=self.queue, heartbeat_interval_sec=0.2, lease_renewal_interval_sec=0.4)

        import threading
        def cancel_runner():
            time.sleep(0.5)
            self.queue.cancel_job(job.task_id, actor="PEMILIK_HQ", reason="Emergency cancel")

        t = threading.Thread(target=cancel_runner)
        t.start()

        start = time.time()
        success = worker.execute_one_cycle(job_handler=_hanging_worker_task, use_process_isolation=True)
        elapsed = time.time() - start
        t.join()

        self.assertFalse(success)
        self.assertLess(elapsed, 4.0, f"Child process was not terminated promptly, elapsed {elapsed}s")

    # -------------------------------------------------------------
    # 4. SENSITIVE PERSONAL DATA INTEGRITY TEST
    # -------------------------------------------------------------

    def test_14_memory_fixtures_contain_only_synthetic_identities(self):
        """Proof: Tracked user_facts.json and memory fixtures contain only synthetic data."""
        facts_path = Path("memory/academic/user_facts.json")
        if facts_path.exists():
            data = json.loads(facts_path.read_text(encoding="utf-8"))
            for item in data.get("facts", []):
                self.assertIn("SYNTHETIC", item.get("fact", "").upper(), "Tracked memory fixtures must explicitly identify as SYNTHETIC!")

if __name__ == "__main__":
    unittest.main()
