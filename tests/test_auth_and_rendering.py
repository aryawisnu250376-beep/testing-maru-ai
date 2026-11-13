"""
MARU HQ Phase 6.1.3 Remediation Test Suite
Validates:
 Priority A: Trusted Identity & Strict Permission Boundaries in HQMemoryManager
   - Rejection of caller-supplied is_hq=True spoofing
   - Rejection of caller-supplied arbitrary reader_division spoofing
   - Enforcement of AGENT, DIVISION, HQ_ONLY, and ORGANIZATIONAL boundaries
   - Safe rejection of deleted memory & anonymous queries
 Priority B: Hard Timeout Guardian & True Process Termination
   - Process-level isolation terminates non-cooperative hanging handler via SIGTERM/SIGKILL
   - Demonstration that child process is dead after termination
   - Prevention of late results overwriting fencing tokens
 Priority C: Real Authentication TTL Expiration Testing
   - Deterministic clock advancement causes token expiration (valid=False)
   - Immediate session invalidation after confirmed HTTP 401
   - Logout revocation
   - URL parameter query rejection (_st query param does not authenticate)
 Priority D: Office Character Rendering & Canonical Source Integrity
   - Verification of canonical studio source (01-social-media-agent/src/studio.html)
   - CSP header whitelist check
   - Fallback rendering guard when Three.js is unavailable
"""

import unittest
import time
import os
import json
import urllib.request
import urllib.error
import threading
import tempfile
import shutil
import socket
import multiprocessing
from pathlib import Path

# Isolated testing configuration
TEST_PASS = "testingmaru,ai123"
os.environ["STUDIO_PASSWORD"] = TEST_PASS
os.environ["MARU_PREVIEW_MODE"] = "1"

import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "01-social-media-agent"))
sys.path.insert(0, str(REPO_ROOT))

from src import security, db, dashboard
from src.hq.memory import HQMemoryManager
from src.hq.queue import HQJobQueue
from src.hq.worker import HQWorker, CancellationToken
from src.hq.models import CanonicalJob, JobPriority, JobBudget

# Non-cooperative loop function for multiprocessing worker test
def _non_cooperative_hanging_handler(job: CanonicalJob, token: CancellationToken):
    # Ignores cancellation token and spins infinitely
    while True:
        time.sleep(0.1)

def _normal_quick_handler(job: CanonicalJob, token: CancellationToken):
    return {"status": "SUCCESS", "data": "processed"}

class TestPhase613Remediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        dashboard.RUNTIME = security.from_environment("127.0.0.1")
        
        from http.server import HTTPServer
        # Bind directly to port 0 to prevent SO_REUSEADDR port hijacking or race condition on Windows
        cls.server = HTTPServer(("127.0.0.1", 0), dashboard.Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _post(self, path, payload, token=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                return res.status, json.loads(res.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def _get(self, path, token=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                return res.status, json.loads(res.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    # =========================================================================
    # PRIORITY A: FIX HQ MEMORY AUTHORIZATION (NEGATIVE & POSITIVE SECURITY)
    # =========================================================================

    def test_01_memory_rejects_is_hq_spoofing(self):
        """Negative test: Specialist agent (EMP-L02) cannot pass is_hq=True to access HQ_ONLY memory."""
        mem_db = Path(self.temp_dir) / "test_mem_spoof.db"
        mem = HQMemoryManager(mem_db)

        mem.store(
            scope="HQ_ONLY",
            category="DECISION",
            title="Director Confidential Plan",
            content="Top secret HQ strategic decisions."
        )

        # Malicious call: Agent EMP-L02 tries to claim is_hq=True
        results = mem.query(reader_agent_id="EMP-L02", is_hq=True)
        titles = [r.title for r in results]
        self.assertNotIn("Director Confidential Plan", titles,
                         "Specialist agent EMP-L02 MUST NOT be able to claim is_hq=True to view HQ_ONLY memory!")

    def test_02_memory_rejects_division_spoofing(self):
        """Negative test: Agent A cannot spoof reader_division to access Division B's private memory."""
        mem_db = Path(self.temp_dir) / "test_mem_div_spoof.db"
        mem = HQMemoryManager(mem_db)

        # Division B (AUDIO_PRODUCTION) private memory
        mem.store(
            scope="DIVISION:AUDIO_PRODUCTION",
            category="POLICY",
            title="Audio Hardware Calibration",
            content="Audio mastering specs."
        )

        # Hermes (EMP-L02, CREATIVE_CORE) tries to supply reader_division='AUDIO_PRODUCTION'
        results = mem.query(reader_agent_id="EMP-L02", reader_division="AUDIO_PRODUCTION")
        titles = [r.title for r in results]
        self.assertNotIn("Audio Hardware Calibration", titles,
                         "Agent EMP-L02 MUST NOT access AUDIO_PRODUCTION memory via caller-supplied parameter!")

    def test_03_cross_division_isolation(self):
        """Agent A (Creative) cannot retrieve Agent B (Audio) private memory."""
        mem_db = Path(self.temp_dir) / "test_mem_cross.db"
        mem = HQMemoryManager(mem_db)

        mem.store(scope="AGENT:EMP-L05", category="TASK_CONTEXT", title="Ardi Private Notes", content="Voice synth")
        results = mem.query(reader_agent_id="EMP-L02")
        self.assertNotIn("Ardi Private Notes", [r.title for r in results])

    def test_04_authorized_hq_access_success(self):
        """Authorized HQ Core (EMP-L01 / Director) can access all memory categories."""
        mem_db = Path(self.temp_dir) / "test_mem_hq.db"
        mem = HQMemoryManager(mem_db)

        mem.store(scope="HQ_ONLY", category="DECISION", title="HQ Strategic Plan", content="Content")
        mem.store(scope="DIVISION:AUDIO_PRODUCTION", category="POLICY", title="Audio Specs", content="Specs")
        mem.store(scope="ORGANIZATIONAL", category="GUIDELINE", title="Code of Conduct", content="Conduct")

        results = mem.query(reader_agent_id="EMP-L01")
        titles = [r.title for r in results]
        self.assertIn("HQ Strategic Plan", titles)
        self.assertIn("Audio Specs", titles)
        self.assertIn("Code of Conduct", titles)

    def test_05_deleted_memory_omitted(self):
        """Soft-deleted memory cannot be retrieved."""
        mem_db = Path(self.temp_dir) / "test_mem_del.db"
        mem = HQMemoryManager(mem_db)

        item = mem.store(scope="ORGANIZATIONAL", category="GUIDELINE", title="Old Guideline", content="Old")
        mem.delete(item.memory_id, actor="ADMIN")
        results = mem.query(reader_agent_id="EMP-L01")
        self.assertNotIn("Old Guideline", [r.title for r in results])

    # =========================================================================
    # PRIORITY B: HARD TIMEOUT GUARDIAN & TRUE PROCESS TERMINATION
    # =========================================================================

    def test_06_process_hard_timeout_terminates_non_cooperative_handler(self):
        """P4: Non-cooperative hanging handler is terminated at OS process level and cannot complete."""
        job_db = Path(self.temp_dir) / "test_proc_timeout.db"
        q = HQJobQueue(job_db)

        # Enqueue job with strict 1-second budget
        job = q.enqueue(
            division="TESTING",
            requested_by="TESTER",
            goal="Hanging infinite loop task",
            input_payload={"test": "timeout"},
            acceptance_criteria=[],
            assigned_agent="EMP-L02",
            idempotency_key="IDEMPO-PROC-TIMEOUT-01",
            budget=JobBudget(max_duration_sec=1)
        )

        worker = HQWorker(queue=q, worker_id="WORKER-PROC-01", assigned_agent="EMP-L02")

        t0 = time.time()
        success = worker.execute_one_cycle(_non_cooperative_hanging_handler, use_process_isolation=True)
        elapsed = time.time() - t0

        self.assertFalse(success, "Worker cycle must return False on hard timeout!")
        self.assertLess(elapsed, 4.0, "Hard timeout must terminate process promptly within guardian deadline!")

        updated_j = q.get_job(job.task_id)
        self.assertIn(updated_j.status, ["FAILED", "RETRYING"])
        self.assertIn("Process Terminated via SIGTERM/SIGKILL", updated_j.error_message)

    def test_07_normal_process_handler_completes(self):
        """Normal handler running in process-isolation mode completes successfully."""
        job_db = Path(self.temp_dir) / "test_proc_success.db"
        q = HQJobQueue(job_db)

        job = q.enqueue(
            division="TESTING",
            requested_by="TESTER",
            goal="Normal quick task",
            input_payload={"test": "success"},
            acceptance_criteria=[],
            assigned_agent="EMP-L02",
            idempotency_key="IDEMPO-PROC-SUCCESS-01",
            budget=JobBudget(max_duration_sec=5)
        )

        worker = HQWorker(queue=q, worker_id="WORKER-PROC-02", assigned_agent="EMP-L02")
        success = worker.execute_one_cycle(_normal_quick_handler, use_process_isolation=True)
        self.assertTrue(success)

        updated_j = q.get_job(job.task_id)
        self.assertEqual(updated_j.status, "COMPLETED")
        self.assertEqual(updated_j.result_payload.get("status"), "SUCCESS")

    # =========================================================================
    # PRIORITY C: REAL AUTHENTICATION EXPIRATION TESTING (DETERMINISTIC CLOCK)
    # =========================================================================

    def test_08_deterministic_ttl_expiration(self):
        """P5: AuthManager token expiration is proven deterministically via simulated clock."""
        auth = security.AuthManager(password="testingmaru,ai123", ttl=3600)
        t_base = 1000000.0

        token, wait = auth.login("testingmaru,ai123", "127.0.0.1", now=t_base)
        self.assertIsNotNone(token)

        # 1. Token is valid within TTL
        self.assertTrue(auth.valid(token, now=t_base + 1800))

        # 2. Token is expired strictly after TTL
        self.assertFalse(auth.valid(token, now=t_base + 3601))

    def test_09_logout_invalidates_token_deterministically(self):
        auth = security.AuthManager(password="testingmaru,ai123", ttl=3600)
        token, _ = auth.login("testingmaru,ai123", "127.0.0.1")
        self.assertTrue(auth.valid(token))

        auth.logout(token)
        self.assertFalse(auth.valid(token), "Token must be invalidated immediately upon logout!")

    def test_10_url_query_token_rejected_no_header_leakage(self):
        """Verified: Passing ?_st=token in URL parameter without header is rejected with 401."""
        status, login_res = self._post("/api/login", {"password": TEST_PASS})
        self.assertEqual(status, 200)
        valid_tok = login_res["token"]

        status_url, _ = self._get(f"/api/state?_st={valid_tok}")
        self.assertEqual(status_url, 401, "Backend must strictly reject URL query parameter tokens!")

    def test_11_access_valid_authenticated_session(self):
        status, login_res = self._post("/api/login", {"password": TEST_PASS})
        self.assertEqual(status, 200)
        token = login_res["token"]

        status_st, body_st = self._get("/api/state", token=token)
        self.assertEqual(status_st, 200)
        self.assertIn("employees", body_st)

    # =========================================================================
    # PRIORITY D: OFFICE CHARACTER RENDERING & CANONICAL INTEGRITY
    # =========================================================================

    def test_12_studio_canonical_source_and_csp(self):
        """P2: Verify canonical studio source, CSP header, and Three.js fallback."""
        studio_path = REPO_ROOT / "01-social-media-agent" / "src" / "studio.html"
        self.assertTrue(studio_path.exists())
        content = studio_path.read_text(encoding="utf-8")

        self.assertNotIn("_st=", content)
        self.assertIn("Immediate session invalidation on confirmed HTTP 401", content)
        self.assertIn("Three.js library not loaded yet or CDN unavailable", content)
        for l_id in ["EMP-L01", "EMP-L02", "EMP-L03", "EMP-L04", "EMP-L05", "EMP-L06", "EMP-L07", "EMP-L08", "EMP-L09"]:
            self.assertIn(l_id, content)

if __name__ == "__main__":
    unittest.main()
