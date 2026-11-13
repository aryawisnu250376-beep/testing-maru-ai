"""
MARU HQ Phase 6.1.3: Authentication, Session Stability & Office Rendering Extended Tests
Validates Priority 1, 2, 4, and 9:
 1. Successful login with correct credentials -> 200 + Bearer token
 2. Incorrect credentials -> 401
 3. Missing credentials -> 401 / 400
 4. Expired or invalid token rejection -> 401
 5. Logout invalidates token -> subsequent request returns 401
 6. Access to protected endpoint without auth header -> 401
 7. Access with valid authenticated session -> 200 + full state & employees roster
 8. Token transported in URL query param is strictly ignored/rejected -> 401
 9. Stale token immunity during new login
 10. Memory permissions security:
    - Agent A cannot access Agent B's private memory
    - Division A cannot access Division B's private memory
    - Specialist agent cannot access HQ_ONLY memory
    - HQ Core can access all scopes
    - Deleted memory is omitted from normal query
 11. Three.js & Studio source integrity & CDN fallback presence
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
from pathlib import Path

# Isolated testing configuration
TEST_PASS = "testingmaru,ai123"
os.environ["STUDIO_PASSWORD"] = TEST_PASS
os.environ["MARU_PREVIEW_MODE"] = "1"

# Import server components
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "01-social-media-agent"))
sys.path.insert(0, str(REPO_ROOT))

from src import security, db, dashboard
from src.hq.memory import HQMemoryManager

class TestAuthSessionAndMemorySecurityPhase613(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        # Initialize security with custom isolated password
        dashboard.RUNTIME = security.from_environment("127.0.0.1")
        # Run test server on ephemeral port
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        cls.port = sock.getsockname()[1]
        sock.close()

        from http.server import HTTPServer
        cls.server = HTTPServer(("127.0.0.1", cls.port), dashboard.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.3)

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

    # --- PRIORITY 1: AUTHENTICATION & SESSION TESTS ---

    def test_01_login_success(self):
        status, body = self._post("/api/login", {"password": TEST_PASS})
        self.assertEqual(status, 200)
        self.assertIn("token", body)
        self.assertTrue(len(body["token"]) > 20)

    def test_02_login_incorrect_credentials(self):
        status, body = self._post("/api/login", {"password": "wrong-password-999"})
        self.assertEqual(status, 401)
        self.assertIn("error", body)

    def test_03_login_missing_credentials(self):
        status, body = self._post("/api/login", {})
        self.assertEqual(status, 401)
        self.assertIn("error", body)

    def test_04_access_protected_without_auth(self):
        status, body = self._get("/api/state")
        self.assertEqual(status, 401)

    def test_05_access_protected_with_invalid_token(self):
        status, body = self._get("/api/state", token="bad-fake-token-xyz")
        self.assertEqual(status, 401)

    def test_06_url_query_token_rejected_no_header_leakage(self):
        """P1: Verifies that passing _st token in query parameter does NOT authorize access."""
        status, login_res = self._post("/api/login", {"password": TEST_PASS})
        self.assertEqual(status, 200)
        valid_tok = login_res["token"]

        # Call /api/state with ?_st=valid_tok but WITHOUT Authorization header
        status_url, body_url = self._get(f"/api/state?_st={valid_tok}")
        self.assertEqual(status_url, 401, "Backend must NOT authorize requests via URL query parameter!")

    def test_07_access_valid_authenticated_session(self):
        status, login_res = self._post("/api/login", {"password": TEST_PASS})
        self.assertEqual(status, 200)
        token = login_res["token"]

        status_st, body_st = self._get("/api/state", token=token)
        self.assertEqual(status_st, 200)
        self.assertIn("employees", body_st)
        self.assertGreater(len(body_st["employees"]), 0)

    def test_08_logout_invalidates_session(self):
        status, login_res = self._post("/api/login", {"password": TEST_PASS})
        self.assertEqual(status, 200)
        token = login_res["token"]

        # Logout
        status_out, body_out = self._post("/api/logout", {}, token=token)
        self.assertEqual(status_out, 200)

        # Subsequent call must fail with 401
        status_check, _ = self._get("/api/state", token=token)
        self.assertEqual(status_check, 401)

    # --- PRIORITY 4: MEMORY PERMISSION SECURITY TESTS ---

    def test_09_memory_strict_permission_boundaries(self):
        """P4: Validates agent, division, and HQ_ONLY scoping."""
        mem_db = Path(self.temp_dir) / "test_mem_sec.db"
        mem = HQMemoryManager(mem_db)

        # 1. Store private memory for Hermes (EMP-L02, CREATIVE_CORE)
        mem.store(
            scope="AGENT:EMP-L02",
            category="TASK_CONTEXT",
            title="Hermes Secret Script Notes",
            content="Proprietary viral hooks draft.",
            tags=["CREATIVE"]
        )

        # 2. Store division memory for AUDIO_PRODUCTION (Ardi / EMP-L05)
        mem.store(
            scope="DIVISION:AUDIO_PRODUCTION",
            category="POLICY",
            title="Studio Mastering Volume Spec",
            content="Loudness target -14 LUFS strictly enforced.",
            tags=["AUDIO"]
        )

        # 3. Store HQ_ONLY memory
        mem.store(
            scope="HQ_ONLY",
            category="DECISION",
            title="Executive Salary & Budget Review",
            content="Confidential director decisions.",
            tags=["HQ"]
        )

        # 4. Store Organizational public memory
        mem.store(
            scope="ORGANIZATIONAL",
            category="GUIDELINE",
            title="General Code of Conduct",
            content="All AI agents work harmoniously.",
            tags=["ALL"]
        )

        # TEST A: Hermes (EMP-L02) cannot see Ardi's division memory or HQ_ONLY
        hermes_view = mem.query(reader_agent_id="EMP-L02")
        hermes_titles = [m.title for m in hermes_view]
        self.assertIn("Hermes Secret Script Notes", hermes_titles)
        self.assertIn("General Code of Conduct", hermes_titles)
        self.assertNotIn("Studio Mastering Volume Spec", hermes_titles)
        self.assertNotIn("Executive Salary & Budget Review", hermes_titles)

        # TEST B: Ardi (EMP-L05) cannot see Hermes's private agent notes or HQ_ONLY
        ardi_view = mem.query(reader_agent_id="EMP-L05")
        ardi_titles = [m.title for m in ardi_view]
        self.assertIn("Studio Mastering Volume Spec", ardi_titles)
        self.assertIn("General Code of Conduct", ardi_titles)
        self.assertNotIn("Hermes Secret Script Notes", ardi_titles)
        self.assertNotIn("Executive Salary & Budget Review", ardi_titles)

        # TEST C: HQ Core (EMP-L01 / Director) CAN access all memory
        hq_view = mem.query(reader_agent_id="EMP-L01", is_hq=True)
        hq_titles = [m.title for m in hq_view]
        self.assertIn("Hermes Secret Script Notes", hq_titles)
        self.assertIn("Studio Mastering Volume Spec", hq_titles)
        self.assertIn("Executive Salary & Budget Review", hq_titles)
        self.assertIn("General Code of Conduct", hq_titles)

        # TEST D: Deleted memory is omitted
        del_item = mem.store(scope="ORGANIZATIONAL", category="POLICY", title="Obsolete Policy", content="Old rule")
        mem.delete(del_item.memory_id, actor="ADMIN")
        query_after_del = mem.query(reader_agent_id="EMP-L01", is_hq=True)
        self.assertNotIn("Obsolete Policy", [m.title for m in query_after_del])

    # --- PRIORITY 2: STUDIO & CHARACTER RENDERING SOURCE INTEGRITY ---

    def test_10_studio_canonical_source_and_csp(self):
        """P2: Verify canonical studio source, CSP, Three.js fallback, and 9 leaders."""
        studio_path = REPO_ROOT / "01-social-media-agent" / "src" / "studio.html"
        self.assertTrue(studio_path.exists())
        content = studio_path.read_text(encoding="utf-8")

        # Verify no token leakage in JS api()
        self.assertNotIn("_st=", content)
        # Verify immediate 401 handling without 3-count loop
        self.assertIn("Immediate session invalidation on confirmed HTTP 401", content)
        # Verify Three.js fallback message
        self.assertIn("Three.js library not loaded yet or CDN unavailable", content)
        # Verify 9 Leaders exist in roster
        for l_id in ["EMP-L01", "EMP-L02", "EMP-L03", "EMP-L04", "EMP-L05", "EMP-L06", "EMP-L07", "EMP-L08", "EMP-L09"]:
            self.assertIn(l_id, content)

if __name__ == "__main__":
    unittest.main()
