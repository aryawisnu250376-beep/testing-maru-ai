"""Pengujian unit lengkap untuk paket maru_github_sync (tanpa koneksi internet nyata)."""
from __future__ import annotations

import base64
import io
import json
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path

from maru_github_sync.client import GitHubContentsClient, git_blob_sha1
from maru_github_sync.config import GitHubSyncConfig, redact_secret
from maru_github_sync.sync_service import MaruGitHubSyncService


class FakeRemoteGitHub:
    """Simulasi server GitHub Contents + Git Trees REST API di memori."""

    def __init__(self, repo: str = "aryawisnu250376-beep/testing-maru-ai") -> None:
        self.repo = repo
        self.files: dict[str, bytes] = {}
        self.puts: list[str] = []

    def urlopen(self, req, timeout: int = 20):
        method = req.get_method()
        url = req.full_url
        path = url.split("https://api.github.com", 1)[1]

        if method == "GET" and path == f"/repos/{self.repo}":
            return self._json_resp(
                {
                    "full_name": self.repo,
                    "private": True,
                    "default_branch": "main",
                    "permissions": {"push": True},
                    "description": "untuk penyimpanan skill dan memori",
                }
            )

        if method == "GET" and "/git/trees/" in path:
            tree = [
                {"path": p, "type": "blob", "sha": git_blob_sha1(b)}
                for p, b in sorted(self.files.items())
            ]
            return self._json_resp({"tree": tree})

        if method == "GET" and "/contents/" in path:
            rel = path.split("/contents/", 1)[1].split("?", 1)[0]
            if rel not in self.files:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b'{"message":"Not Found"}'))
            raw = self.files[rel]
            return self._json_resp(
                {
                    "path": rel,
                    "sha": git_blob_sha1(raw),
                    "size": len(raw),
                    "content": base64.b64encode(raw).decode("ascii"),
                }
            )

        if method == "PUT" and "/contents/" in path:
            rel = path.split("/contents/", 1)[1]
            body = json.loads(req.data.decode("utf-8"))
            raw = base64.b64decode(body["content"])
            self.files[rel] = raw
            self.puts.append(rel)
            return self._json_resp({"content": {"path": rel, "sha": git_blob_sha1(raw)}})

        raise AssertionError(f"Unhandled request: {method} {path}")

    @staticmethod
    def _json_resp(data: dict):
        raw = json.dumps(data).encode("utf-8")
        resp = io.BytesIO(raw)
        resp. __enter__ = lambda s=resp: s  # type: ignore[attr-defined]
        resp.__exit__ = lambda *args: False  # type: ignore[attr-defined]
        return resp


class TestMaruGitHubSync(unittest.TestCase):
    def test_secret_redaction(self) -> None:
        tok = "github_pat_11ABCDEF0123456789_secretXYZ"
        msg = f"Authorization failed for {tok} on repo"
        cleaned = redact_secret(msg, tok)
        self.assertNotIn(tok, cleaned)
        self.assertIn("***REDACTED_TOKEN***", cleaned)

    def test_export_push_and_pull_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Siapkan struktur mini divisi Social Media & Academic AI
            sm_skill = root / "01-social-media-agent/skills/cek-mutu/SKILL.md"
            sm_skill.parent.mkdir(parents=True)
            sm_skill.write_text("# cek-mutu\nDeskripsi uji\n", encoding="utf-8")

            ac_skill = root / "02-academic-ai/prompts/skills/answer.md"
            ac_skill.parent.mkdir(parents=True)
            ac_skill.write_text("# Skill: Menjawab\nIsi skill\n", encoding="utf-8")

            # Buat SQLite Academic AI dengan 1 fact & 1 answer_skill
            db_path = root / "02-academic-ai/data/academic_ai.db"
            db_path.parent.mkdir(parents=True)
            conn = sqlite3.connect(str(db_path))
            conn.executescript(
                """
                CREATE TABLE user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    fact TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE answer_skills (
                    name TEXT PRIMARY KEY,
                    subject_code TEXT NOT NULL DEFAULT '',
                    task_mode TEXT NOT NULL DEFAULT '',
                    hint TEXT NOT NULL,
                    uses INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO user_facts(user_id, fact) VALUES (101, 'Nama user: Arya');
                INSERT INTO answer_skills(name, subject_code, task_mode, hint, uses, wins)
                VALUES ('answer:ilkom', 'ILKOM', 'answer', 'jawaban ~120 kata, 2 sumber', 3, 2);
                """
            )
            conn.commit()
            conn.close()

            # Pastikan file .env di dalam skills/ tidak akan pernah ikut terunggah
            (root / "skills").mkdir(parents=True, exist_ok=True)
            (root / "skills/.env").write_text("SECRET=123", encoding="utf-8")

            fake_remote = FakeRemoteGitHub()
            cfg = GitHubSyncConfig(
                repo_root=root,
                enabled=True,
                repo="aryawisnu250376-beep/testing-maru-ai",
                branch="main",
                token="github_pat_dummy_token_for_unit_test",
            )
            client = GitHubContentsClient(cfg, urlopen_fn=fake_remote.urlopen)
            svc = MaruGitHubSyncService(cfg, client)

            push_res = svc.push_skills_and_memory(academic_db_path=db_path)
            self.assertTrue(push_res["ok"])
            self.assertIn("skills/social-media/cek-mutu/SKILL.md", fake_remote.files)
            self.assertIn("skills/academic/answer/SKILL.md", fake_remote.files)
            self.assertIn("memory/academic/user_facts.json", fake_remote.files)
            self.assertIn("skills/learned/academic_answer_skills.json", fake_remote.files)
            self.assertNotIn("skills/.env", fake_remote.files)

            # Push kedua tanpa perubahan harus idempotent (0 PUT baru untuk file yang sama)
            puts_before = len(fake_remote.puts)
            push_res_2 = svc.push_skills_and_memory(academic_db_path=db_path)
            # Hanya user_facts.json & academic_answer_skills.json punya updated_at jika detik berubah,
            # tetapi SKILL.md wajib unchanged
            self.assertGreaterEqual(push_res_2["unchanged_count"], 3)
            self.assertLessEqual(len(fake_remote.puts) - puts_before, 2)

            # Uji pull & import ke database baru yang masih kosong
            db_path_2 = root / "fresh_academic.db"
            conn2 = sqlite3.connect(str(db_path_2))
            conn2.executescript(
                """
                CREATE TABLE user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    fact TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE answer_skills (
                    name TEXT PRIMARY KEY,
                    subject_code TEXT NOT NULL DEFAULT '',
                    task_mode TEXT NOT NULL DEFAULT '',
                    hint TEXT NOT NULL,
                    uses INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn2.commit()
            conn2.close()

            pull_res = svc.pull_skills_and_memory(academic_db_path=db_path_2)
            self.assertEqual(pull_res["imported_academic_facts"], 1)
            self.assertEqual(pull_res["imported_academic_skills"], 1)

    def test_add_skill_from_external_github_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "01-social-media-agent/skills").mkdir(parents=True)
            (root / "02-academic-ai/prompts/skills").mkdir(parents=True)

            sample_skill = (
                "---\nname: pdf-analyzer\ndescription: Analisis dokumen PDF presisi\n---\n"
                "# PDF Analyzer\n1. Periksa setiap halaman.\n"
            )

            def fake_external_urlopen(req, timeout: int = 20):
                url = req.full_url
                if url.endswith("/contents/skills/pdf?ref=main"):
                    return FakeRemoteGitHub._json_resp(
                        [{"name": "SKILL.md", "path": "skills/pdf/SKILL.md", "type": "file"}]
                    )
                if "/contents/skills/pdf/SKILL.md?ref=main" in url:
                    raw = sample_skill.encode("utf-8")
                    resp = io.BytesIO(raw)
                    resp.__enter__ = lambda s=resp: s  # type: ignore[attr-defined]
                    resp.__exit__ = lambda *args: False  # type: ignore[attr-defined]
                    return resp
                raise AssertionError(f"Unexpected external URL: {url}")

            fake_maru_remote = FakeRemoteGitHub()
            cfg = GitHubSyncConfig(
                repo_root=root,
                enabled=True,
                repo="aryawisnu250376-beep/testing-maru-ai",
                branch="main",
                token="github_pat_dummy_token_for_unit_test",
            )
            svc = MaruGitHubSyncService(
                cfg, GitHubContentsClient(cfg, urlopen_fn=fake_maru_remote.urlopen)
            )
            res = svc.add_skill_from_github(
                "https://github.com/anthropics/skills/tree/main/skills/pdf",
                division="shared",
                urlopen_fn=fake_external_urlopen,
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["skill_id"], "shared/pdf-analyzer")
            self.assertTrue((root / "skills/shared/pdf-analyzer/SKILL.md").is_file())
            # Karena division="shared", otomatis terdistribusi ke kedua divisi:
            self.assertTrue((root / "01-social-media-agent/skills/pdf-analyzer/SKILL.md").is_file())
            self.assertTrue((root / "02-academic-ai/prompts/skills/custom/pdf-analyzer.md").is_file())
            # Dan otomatis ter-push ke repo MARU:
            self.assertIn("skills/shared/pdf-analyzer/SKILL.md", fake_maru_remote.files)
            self.assertIn("skills/REGISTRY.json", fake_maru_remote.files)


if __name__ == "__main__":
    unittest.main()
