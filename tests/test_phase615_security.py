import unittest
import time
import os
from pathlib import Path

from src.hq.memory import HQMemoryManager, InternalAuthAuthority, CallerContext

class TestPhase615ComprehensiveSecurity(unittest.TestCase):
    def setUp(self):
        self.test_db = Path("data/test_phase615_mem.db")
        if self.test_db.exists():
            self.test_db.unlink()
        self.memory = HQMemoryManager(db_path=self.test_db)

    def tearDown(self):
        if self.test_db.exists():
            try:
                self.test_db.unlink()
            except Exception:
                pass

    def test_01_impersonation_using_magic_ids_fails_closed(self):
        """Proof: Passing EMP-L01, HQ, or PEMILIK without server-issued token fails closed to unauthenticated."""
        # An attacker claiming to be EMP-L01 / Director without token
        ctx = CallerContext.resolve_authenticated("fake_token_123")
        self.assertFalse(ctx.authenticated)
        self.assertFalse(ctx.is_hq)
        self.assertIsNone(ctx.caller_id)

    def test_02_server_token_issuance_and_revocation(self):
        """Proof: Principals issued by InternalAuthAuthority validate identity and expire/revoke cleanly."""
        principal = InternalAuthAuthority.issue_principal("EMP-L01", "bootstrap_secret", ttl_sec=2.0)
        self.assertIsNotNone(principal)
        self.assertEqual(principal.principal_id, "EMP-L01")
        self.assertTrue(principal.is_hq)

        ctx = CallerContext.resolve_authenticated(principal.session_token)
        self.assertTrue(ctx.authenticated)
        self.assertTrue(ctx.is_hq)

        # Revocation
        InternalAuthAuthority.revoke(principal.session_token)
        revoked_ctx = CallerContext.resolve_authenticated(principal.session_token)
        self.assertFalse(revoked_ctx.authenticated)
        self.assertFalse(revoked_ctx.is_hq)

    def test_03_specialist_cannot_store_in_hq_only(self):
        """Proof: Specialist (EMP-L02) cannot write to HQ_ONLY scope even if authenticated."""
        principal = InternalAuthAuthority.issue_principal("EMP-L02", "secret")
        with self.assertRaises(PermissionError):
            self.memory.store(
                scope="HQ_ONLY",
                category="DECISION",
                title="Unauthorized Store",
                content="Mallory writing to HQ",
                auth_token=principal.session_token
            )

    def test_04_specialist_cannot_modify_other_agent_memory(self):
        """Proof: Specialist A (EMP-L02) cannot write or update Specialist B's (EMP-L05) private memory."""
        p_ardi = InternalAuthAuthority.issue_principal("EMP-L05", "secret")
        rec = self.memory.store(
            scope="AGENT:EMP-L05",
            category="PRIVATE_NOTES",
            title="Ardi Voice Config",
            content="Sample rate 48000Hz",
            auth_token=p_ardi.session_token
        )

        p_hermes = InternalAuthAuthority.issue_principal("EMP-L02", "secret")
        # Hermes tries to update Ardi's record
        with self.assertRaises(PermissionError):
            self.memory.update(rec.memory_id, "Hacked content", editor="EMP-L02", auth_token=p_hermes.session_token)

        # Hermes tries to delete Ardi's record
        with self.assertRaises(PermissionError):
            self.memory.delete(rec.memory_id, actor="EMP-L02", auth_token=p_hermes.session_token)

    def test_05_anonymous_cannot_write_to_organizational_scope(self):
        """Proof: Unauthenticated actors cannot write or modify organizational knowledge."""
        with self.assertRaises(PermissionError):
            self.memory.store(
                scope="ORGANIZATIONAL",
                category="POLICY",
                title="Fake Policy",
                content="Defaced guideline",
                auth_token="invalid_token"
            )

if __name__ == "__main__":
    unittest.main()
