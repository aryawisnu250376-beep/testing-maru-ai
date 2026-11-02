"""Layanan sinkronisasi Skill & Memori MARU AI <-> GitHub Repository.

Menangani:
1. Ekspor/impor state lokal dari kedua divisi (`01-social-media-agent` & `02-academic-ai`)
   ke struktur kanonis `skills/` dan `memory/` di root repository.
2. Push perubahan `skills/` dan `memory/` ke GitHub secara idempotent (hanya file yang berubah).
3. Pull pembaruan `skills/` dan `memory/` dari GitHub ke lokal agar multi-perangkat /
   antar-divisi tetap sinkron.
4. Proteksi ketat agar tidak pernah mengunggah file rahasia (.env, token, kunci privat).
"""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import GitHubContentsClient, GitHubSyncError
from .config import GitHubSyncConfig, redact_secret

logger = logging.getLogger(__name__)

FORBIDDEN_FILENAMES = {
    ".env",
    "drive_credentials.json",
    "drive_token.json",
}
FORBIDDEN_SUFFIXES = (".db", ".db-shm", ".db-wal", ".sqlite", ".sqlite3", ".pem", ".key", ".mp4")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_safe_sync_file(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    name = Path(rel_path).name.lower()
    if any(p.startswith(".git") or p == "__pycache__" for p in parts):
        return False
    if name in FORBIDDEN_FILENAMES or name.startswith(".env"):
        return False
    if any(name.endswith(sfx) for sfx in FORBIDDEN_SUFFIXES):
        return False
    return True


class MaruGitHubSyncService:
    """Koordinator sinkronisasi Skill & Memori terpusat MARU AI."""

    def __init__(
        self,
        config: GitHubSyncConfig | None = None,
        client: GitHubContentsClient | None = None,
    ) -> None:
        self.config = config or GitHubSyncConfig.from_env()
        self.client = client or GitHubContentsClient(self.config)
        self.root = self.config.repo_root

    # ------------------------------------------------------------------
    # 1. Koleksi & distribusi lokal (Divisi <-> Folder Terpusat skills/ & memory/)
    # ------------------------------------------------------------------

    def export_local_to_central(
        self,
        academic_db_path: Path | None = None,
    ) -> dict[str, Any]:
        """Salin skill & memori terbaru dari kedua divisi ke folder root `skills/` & `memory/`."""
        exported: list[str] = []
        sm_root = self.root / "01-social-media-agent"
        ac_root = self.root / "02-academic-ai"

        # A. Social Media skills -> skills/social-media/
        if (sm_root / "skills").is_dir():
            for sdir in sorted((sm_root / "skills").iterdir()):
                if sdir.is_dir() and (sdir / "SKILL.md").is_file():
                    target = self.root / "skills" / "social-media" / sdir.name / "SKILL.md"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sdir / "SKILL.md", target)
                    exported.append(str(target.relative_to(self.root)).replace("\\", "/"))

        konten_skill = sm_root / "config" / "hermes" / "skills" / "konten-ai" / "SKILL.md"
        if konten_skill.is_file():
            target = self.root / "skills" / "social-media" / "konten-ai" / "SKILL.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(konten_skill, target)
            exported.append(str(target.relative_to(self.root)).replace("\\", "/"))

        # Winning patterns Social Media -> skills/learned/
        win_txt = sm_root / "data" / "winning_patterns.txt"
        if win_txt.is_file():
            txt = win_txt.read_text(encoding="utf-8").strip()
            target = self.root / "skills" / "learned" / "social_media_winning_patterns.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# Social Media Winning Patterns\n\n{txt}\n", encoding="utf-8")
            exported.append(str(target.relative_to(self.root)).replace("\\", "/"))

        # B. Social Media state/memory -> memory/social-media/
        for fname in ("orchestrator_state.json", "watch_state.json", "reference_watchlist.json"):
            src = sm_root / "data" / fname
            if src.is_file():
                target = self.root / "memory" / "social-media" / fname
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                exported.append(str(target.relative_to(self.root)).replace("\\", "/"))

        # C. Academic AI builtin skills -> skills/academic/
        if (ac_root / "prompts" / "skills").is_dir():
            for md in sorted((ac_root / "prompts" / "skills").glob("*.md")):
                slug = md.stem.replace("_", "-")
                target = self.root / "skills" / "academic" / slug / "SKILL.md"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(md, target)
                exported.append(str(target.relative_to(self.root)).replace("\\", "/"))

        # D. Academic AI SQLite (user_facts & answer_skills) -> memory/academic/ & skills/learned/
        db_candidate = academic_db_path or (ac_root / "data" / "academic_ai.db")
        if db_candidate.is_file():
            conn = sqlite3.connect(f"file:{db_candidate.as_posix()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                tables = {
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if "user_facts" in tables:
                    facts = [
                        dict(r)
                        for r in conn.execute(
                            "SELECT user_id, fact, created_at FROM user_facts ORDER BY id ASC"
                        ).fetchall()
                    ]
                    facts_path = self.root / "memory" / "academic" / "user_facts.json"
                    facts_path.parent.mkdir(parents=True, exist_ok=True)
                    facts_path.write_text(
                        json.dumps(
                            {"version": 1, "updated_at": _utc_now_iso(), "facts": facts},
                            indent=2,
                            ensure_ascii=False,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    exported.append("memory/academic/user_facts.json")

                if "answer_skills" in tables:
                    skills_rows = [
                        dict(r)
                        for r in conn.execute(
                            "SELECT name, subject_code, task_mode, hint, uses, wins, updated_at "
                            "FROM answer_skills ORDER BY name ASC"
                        ).fetchall()
                    ]
                    sk_path = self.root / "skills" / "learned" / "academic_answer_skills.json"
                    sk_path.parent.mkdir(parents=True, exist_ok=True)
                    sk_path.write_text(
                        json.dumps(
                            {"version": 1, "updated_at": _utc_now_iso(), "skills": skills_rows},
                            indent=2,
                            ensure_ascii=False,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    exported.append("skills/learned/academic_answer_skills.json")
            finally:
                conn.close()

        self._refresh_registry_and_index()
        return {"exported_count": len(exported), "files": exported}

    def import_central_to_local(
        self,
        academic_db_path: Path | None = None,
    ) -> dict[str, Any]:
        """Terapkan skill & memori dari folder `skills/` dan `memory/` kembali ke modul divisi."""
        imported_facts = 0
        imported_skills = 0
        mirrored_skill_files: list[str] = []
        sm_root = self.root / "01-social-media-agent"
        ac_root = self.root / "02-academic-ai"

        # Distribusi skill baru dari skills/social-media & skills/shared -> 01-social-media-agent/skills/
        if sm_root.is_dir():
            for scope in ("social-media", "shared"):
                scope_dir = self.root / "skills" / scope
                if not scope_dir.is_dir():
                    continue
                for sk_md in sorted(scope_dir.glob("*/SKILL.md")):
                    slug = sk_md.parent.name
                    if slug == "konten-ai":
                        continue
                    dest = sm_root / "skills" / slug / "SKILL.md"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sk_md, dest)
                    mirrored_skill_files.append(str(dest.relative_to(self.root)).replace("\\", "/"))

        # Distribusi skill kustom dari skills/academic & skills/shared -> 02-academic-ai/prompts/skills/custom/
        builtin_academic_slugs = {
            "answer",
            "citation-discipline",
            "quiz",
            "summary",
            "explain-simple",
            "quiz-maker",
            "summarize-id",
        }
        if ac_root.is_dir():
            custom_dir = ac_root / "prompts" / "skills" / "custom"
            for scope in ("academic", "shared"):
                scope_dir = self.root / "skills" / scope
                if not scope_dir.is_dir():
                    continue
                for sk_md in sorted(scope_dir.glob("*/SKILL.md")):
                    slug = sk_md.parent.name
                    if scope == "academic" and slug in builtin_academic_slugs:
                        continue
                    custom_dir.mkdir(parents=True, exist_ok=True)
                    dest = custom_dir / f"{slug}.md"
                    shutil.copy2(sk_md, dest)
                    mirrored_skill_files.append(str(dest.relative_to(self.root)).replace("\\", "/"))

        db_candidate = academic_db_path or (ac_root / "data" / "academic_ai.db")

        if db_candidate.is_file():
            conn = sqlite3.connect(str(db_candidate))
            conn.row_factory = sqlite3.Row
            try:
                facts_file = self.root / "memory" / "academic" / "user_facts.json"
                if facts_file.is_file():
                    payload = json.loads(facts_file.read_text(encoding="utf-8"))
                    existing = {
                        (int(r["user_id"]), str(r["fact"]))
                        for r in conn.execute("SELECT user_id, fact FROM user_facts").fetchall()
                    }
                    for item in payload.get("facts") or []:
                        key = (int(item["user_id"]), str(item["fact"]))
                        if key not in existing:
                            conn.execute(
                                "INSERT INTO user_facts(user_id, fact) VALUES (?, ?)",
                                key,
                            )
                            existing.add(key)
                            imported_facts += 1

                sk_file = self.root / "skills" / "learned" / "academic_answer_skills.json"
                if sk_file.is_file():
                    payload = json.loads(sk_file.read_text(encoding="utf-8"))
                    for item in payload.get("skills") or []:
                        conn.execute(
                            """INSERT INTO answer_skills(name, subject_code, task_mode, hint, uses, wins)
                               VALUES (?, ?, ?, ?, ?, ?)
                               ON CONFLICT(name) DO UPDATE SET
                                 hint = excluded.hint,
                                 uses = MAX(answer_skills.uses, excluded.uses),
                                 wins = MAX(answer_skills.wins, excluded.wins)""",
                            (
                                str(item["name"]),
                                str(item.get("subject_code", "")),
                                str(item.get("task_mode", "")),
                                str(item.get("hint", "")),
                                int(item.get("uses", 1)),
                                int(item.get("wins", 0)),
                            ),
                        )
                        imported_skills += 1
                conn.commit()
            finally:
                conn.close()

        return {
            "imported_academic_facts": imported_facts,
            "imported_academic_skills": imported_skills,
            "mirrored_skill_files": mirrored_skill_files,
        }

    def add_skill_from_github(
        self,
        source: str,
        *,
        division: str = "shared",
        custom_name: str | None = None,
        push_remote: bool = True,
        urlopen_fn: Any = None,
    ) -> dict[str, Any]:
        """Impor SKILL.md dari URL/repo GitHub mana pun, daftarkan ke REGISTRY, & sinkronkan."""
        from .skill_importer import GitHubSkillImporter

        importer = GitHubSkillImporter(self.config, urlopen_fn=urlopen_fn)
        installed = importer.install_skill(source, division=division, custom_name=custom_name)
        self._refresh_registry_and_index()
        mirror_info = self.import_central_to_local()

        pushed_files: list[str] = []
        if push_remote and self.config.is_ready:
            for rel in (installed["local_path"], "skills/REGISTRY.json"):
                if self.best_effort_push_single(rel, commit_label="add-skill"):
                    pushed_files.append(rel)

        return {
            **installed,
            "mirrored_to": mirror_info["mirrored_skill_files"],
            "pushed_to_github": pushed_files,
        }

    def _refresh_registry_and_index(self) -> None:
        """Perbarui `skills/REGISTRY.json` dan `memory/index.json` secara deterministik."""
        skills_dir = self.root / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        entries: list[dict[str, str]] = []
        for sk_md in sorted(skills_dir.rglob("SKILL.md")):
            rel = str(sk_md.relative_to(self.root)).replace("\\", "/")
            parts = sk_md.relative_to(skills_dir).parts
            division = parts[0] if len(parts) > 1 else "shared"
            skill_id = parts[1] if len(parts) > 1 else sk_md.stem
            first_desc = ""
            for ln in sk_md.read_text(encoding="utf-8", errors="replace").splitlines():
                s = ln.strip()
                if s.lower().startswith("description:"):
                    first_desc = s.split(":", 1)[1].strip()
                    break
                if s.startswith("# ") and not first_desc:
                    first_desc = s.lstrip("# ").strip()
            entries.append(
                {
                    "id": f"{division}/{skill_id}",
                    "division": division,
                    "name": skill_id,
                    "path": rel,
                    "description": first_desc,
                }
            )

        registry = {
            "schema_version": "1.0",
            "repository": self.config.repo,
            "total_skills": len(entries),
            "skills": entries,
            "learned_artifacts": [
                "skills/learned/academic_answer_skills.json",
                "skills/learned/social_media_winning_patterns.md",
            ],
        }
        (skills_dir / "REGISTRY.json").write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        mem_dir = self.root / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        mem_files = [
            str(p.relative_to(self.root)).replace("\\", "/")
            for p in sorted(mem_dir.rglob("*"))
            if p.is_file() and p.name != "index.json" and _is_safe_sync_file(str(p.relative_to(self.root)))
        ]
        mem_index = {
            "schema_version": "1.0",
            "repository": self.config.repo,
            "scopes": ["social-media", "academic", "hq"],
            "tracked_files": mem_files,
        }
        (mem_dir / "index.json").write_text(
            json.dumps(mem_index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # 2. Push & Pull ke GitHub Repository (`skills/` & `memory/`)
    # ------------------------------------------------------------------

    def collect_syncable_files(self, scopes: tuple[str, ...] = ("skills", "memory")) -> list[Path]:
        files: list[Path] = []
        for scope in scopes:
            base = self.root / scope
            if not base.is_dir():
                continue
            for p in sorted(base.rglob("*")):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(self.root)).replace("\\", "/")
                if _is_safe_sync_file(rel):
                    files.append(p)
        return files

    def push_skills_and_memory(
        self,
        *,
        academic_db_path: Path | None = None,
        commit_prefix: str = "chore(maru-sync)",
    ) -> dict[str, Any]:
        """Ekspor state terbaru lalu unggah file `skills/` & `memory/` yang berubah ke GitHub."""
        self.export_local_to_central(academic_db_path=academic_db_path)
        if not self.config.is_ready:
            raise GitHubSyncError(
                "Konfigurasi GitHub Sync belum aktif atau MARU_GITHUB_TOKEN kosong."
            )

        remote_sha_map: dict[str, str] = {}
        try:
            for item in self.client.list_files_recursive():
                remote_sha_map[item["path"]] = item["sha"]
        except GitHubSyncError:
            remote_sha_map = {}

        created, updated, unchanged = [], [], []
        for local_file in self.collect_syncable_files():
            rel = str(local_file.relative_to(self.root)).replace("\\", "/")
            res = self.client.put_file(
                remote_path=rel,
                content_bytes=local_file.read_bytes(),
                message=f"{commit_prefix}: update {rel}",
                known_sha=remote_sha_map.get(rel),
            )
            if res["status"] == "created":
                created.append(rel)
            elif res["status"] == "updated":
                updated.append(rel)
            else:
                unchanged.append(rel)

        return {
            "ok": True,
            "repo": self.config.repo,
            "branch": self.config.branch,
            "created": created,
            "updated": updated,
            "unchanged_count": len(unchanged),
        }

    def pull_skills_and_memory(
        self,
        *,
        academic_db_path: Path | None = None,
    ) -> dict[str, Any]:
        """Tarik seluruh isi `skills/` dan `memory/` dari GitHub ke lokal lalu impor ke DB."""
        if not self.config.is_ready:
            raise GitHubSyncError(
                "Konfigurasi GitHub Sync belum aktif atau MARU_GITHUB_TOKEN kosong."
            )

        downloaded: list[str] = []
        for scope in ("skills", "memory"):
            for item in self.client.list_files_recursive(prefix=scope):
                rel = item["path"]
                if not _is_safe_sync_file(rel):
                    continue
                fetched = self.client.get_file(rel)
                if not fetched:
                    continue
                dest = (self.root / rel).resolve()
                if not str(dest).startswith(str(self.root.resolve())):
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(fetched["bytes"])
                downloaded.append(rel)

        import_stats = self.import_central_to_local(academic_db_path=academic_db_path)
        return {
            "ok": True,
            "repo": self.config.repo,
            "branch": self.config.branch,
            "downloaded_count": len(downloaded),
            "downloaded": downloaded,
            **import_stats,
        }

    def best_effort_push_single(self, rel_path: str, commit_label: str = "auto-sync") -> bool:
        """Unggah satu file skill/memori tanpa pernah memicu crash pada pemanggil."""
        if not self.config.is_ready:
            return False
        clean_rel = rel_path.lstrip("/").replace("\\", "/")
        if not _is_safe_sync_file(clean_rel):
            return False
        local_file = (self.root / clean_rel).resolve()
        if not local_file.is_file():
            return False
        try:
            self.client.put_file(
                remote_path=clean_rel,
                content_bytes=local_file.read_bytes(),
                message=f"chore({commit_label}): sync {clean_rel}",
            )
            return True
        except Exception as exc:
            logger.warning(
                "[WARN] GitHub auto-sync dilewati (%s).",
                redact_secret(str(exc), self.config.token),
            )
            return False
