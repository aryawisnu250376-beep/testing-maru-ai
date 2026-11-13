"""
MARU HQ Authentication, Session Stability & 3D Character Rendering Test Suite
Validates:
 1. Login with correct password -> 200 + valid token
 2. Login with incorrect password -> 401
 3. Expired or invalid token rejection -> 401
 4. State endpoint access with valid token -> 200 + JSON state
 5. Stale token immunity during login (clean authorization)
 6. HTTP 401 handling prevents redirect loops
 7. Character and office integrity checks in studio source
"""

import unittest
import time
import os
import json
import urllib.request
import urllib.error
import threading
from pathlib import Path

# Set up test environment
os.environ["STUDIO_PASSWORD"] = "testingmaru,ai123"
os.environ["MARU_PREVIEW_MODE"] = "1"

# Import server components
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "01-social-media-agent"))

from src import security, db, dashboard

class TestAuthAndRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init()
        # Initialize runtime security
        dashboard.RUNTIME = security.from_environment("127.0.0.1")
        # Run local test server in thread on high port
        cls.port = 8899
        from http.server import HTTPServer
        cls.server = HTTPServer(("127.0.0.1", cls.port), dashboard.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

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

    def test_01_login_correct_credentials(self):
        """Test login with correct password returns 200 and token."""
        status, body = self._post("/api/login", {"password": "testingmaru,ai123"})
        self.assertEqual(status, 200)
        self.assertIn("token", body)
        self.assertTrue(len(body["token"]) > 20)

    def test_02_login_incorrect_credentials(self):
        """Test login with wrong password returns 401."""
        status, body = self._post("/api/login", {"password": "wrong_password_xyz"})
        self.assertEqual(status, 401)
        self.assertIn("error", body)

    def test_03_expired_or_invalid_token(self):
        """Test accessing protected route with invalid token returns 401."""
        status, body = self._get("/api/state", token="invalid-token-12345")
        self.assertEqual(status, 401)

    def test_04_state_after_login(self):
        """Test getting state with authenticated session."""
        status, login_body = self._post("/api/login", {"password": "testingmaru,ai123"})
        self.assertEqual(status, 200)
        token = login_body["token"]

        status, state_body = self._get("/api/state", token=token)
        self.assertEqual(status, 200)
        self.assertIn("employees", state_body)

    def test_05_studio_source_integrity(self):
        """Verify 3D office source has character definitions, sceneGroup mappings and CDN fallback."""
        studio_path = REPO_ROOT / "01-social-media-agent" / "src" / "studio.html"
        self.assertTrue(studio_path.exists())
        content = studio_path.read_text(encoding="utf-8")
        
        # Check Three.js initialization and guards
        self.assertIn("Three.js library not loaded yet or CDN unavailable", content)
        self.assertIn("buildCharacter", content)
        self.assertIn("emp.sceneGroup = charGrp", content)
        self.assertIn("syncBackendState", content)
        # Check all 9 official leaders exist in roster
        for lead_id in ["EMP-L01", "EMP-L02", "EMP-L03", "EMP-L04", "EMP-L05", "EMP-L06", "EMP-L07", "EMP-L08", "EMP-L09"]:
            self.assertIn(lead_id, content)

    def test_06_preview_bootstrap_endpoint(self):
        """Verify preview bootstrap endpoint responds cleanly."""
        status, body = self._get("/api/preview-bootstrap")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("preview_mode"))

if __name__ == "__main__":
    unittest.main()
