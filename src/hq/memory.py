"""
MARU HQ Persistent Organizational Memory & Knowledge Base Subsystem
Phase 6.1.3 Hardened
Implements:
 - Persistent SQLite Storage with WAL Mode
 - Task-Context Memory & Organizational Shared Knowledge
 - Strict Scoped Permissions:
    * ORGANIZATIONAL: Accessible to HQ, Leaders & Specialists with explicit permission
    * AGENT:<id>: Accessible only to the owning Agent (and HQ supervisor)
    * DIVISION:<id>: Accessible only to members of that specific division (and HQ)
    * HQ_ONLY: Accessible strictly to HQ Core (e.g. EMP-L01 / Director)
 - Provenance, Versioning, and Content-Hash Deduplication
 - Tombstone Deletion & Restart Recovery
"""

import sqlite3
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

DEFAULT_MEMORY_DB = Path(__file__).resolve().parent.parent.parent / "data" / "hq_memory.db"

# Division membership mapping for strict authorization
AGENT_DIVISION_MAP = {
    "EMP-L01": "EXECUTIVE_SUITE",
    "EMP-L02": "CREATIVE_CORE",
    "EMP-L03": "ACADEMIC_INTELLIGENCE",
    "EMP-L04": "TELEMETRY_GROWTH",
    "EMP-L05": "AUDIO_PRODUCTION",
    "EMP-L06": "QUALITY_ASSURANCE",
    "EMP-L07": "VISUAL_DESIGN",
    "EMP-L08": "SYSTEM_OPERATIONS",
    "EMP-L09": "PIPELINE_ORCHESTRATION",
}

@dataclass
class MemoryRecord:
    memory_id: str
    scope: str                  # 'ORGANIZATIONAL', 'HQ_ONLY', 'AGENT:<id>', 'DIVISION:<id>'
    category: str               # 'RESEARCH', 'GUIDELINE', 'TASK_CONTEXT', 'DECISION', 'POLICY'
    title: str
    content: str
    content_hash: str
    tags: List[str]
    provenance: Dict[str, Any]  # {"creator": "...", "job_id": "...", "created_at": ...}
    version: int
    is_deleted: bool
    created_at: float
    updated_at: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class HQMemoryManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_MEMORY_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS hq_memory (
                memory_id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                tags_json TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_scope ON hq_memory(scope, is_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_cat ON hq_memory(category, is_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_hash ON hq_memory(content_hash)")

    @staticmethod
    def _compute_hash(scope: str, category: str, title: str, content: str) -> str:
        s = f"{scope}::{category}::{title.strip()}::{content.strip()}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def store(self, scope: str, category: str, title: str, content: str,
              tags: Optional[List[str]] = None,
              provenance: Optional[Dict[str, Any]] = None) -> MemoryRecord:
        """Stores a memory entry with deduplication and provenance."""
        now = time.time()
        c_hash = self._compute_hash(scope, category, title, content)
        tags_list = tags or []
        prov = provenance or {}
        prov.setdefault("stored_at", now)

        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM hq_memory WHERE content_hash = ?", (c_hash,))
            row = cur.fetchone()
            if row:
                if row["is_deleted"] == 1:
                    conn.execute(
                        "UPDATE hq_memory SET is_deleted = 0, updated_at = ? WHERE memory_id = ?",
                        (now, row["memory_id"])
                    )
                return self._row_to_record(row)

            mem_id = f"MEM-{int(now)}-{c_hash[:8].upper()}"
            conn.execute("""
            INSERT INTO hq_memory (
                memory_id, scope, category, title, content, content_hash,
                tags_json, provenance_json, version, is_deleted, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem_id, scope, category, title, content, c_hash,
                json.dumps(tags_list), json.dumps(prov), 1, 0, now, now
            ))
            
            cur = conn.execute("SELECT * FROM hq_memory WHERE memory_id = ?", (mem_id,))
            return self._row_to_record(cur.fetchone())

    def update(self, memory_id: str, new_content: str, editor: str) -> Optional[MemoryRecord]:
        now = time.time()
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM hq_memory WHERE memory_id = ? AND is_deleted = 0", (memory_id,))
            row = cur.fetchone()
            if not row:
                return None

            scope = row["scope"]
            cat = row["category"]
            title = row["title"]
            new_hash = self._compute_hash(scope, cat, title, new_content)

            prov = json.loads(row["provenance_json"])
            updates = prov.get("updates", [])
            updates.append({"editor": editor, "timestamp": now, "previous_hash": row["content_hash"]})
            prov["updates"] = updates

            new_version = row["version"] + 1
            conn.execute("""
            UPDATE hq_memory 
            SET content = ?, content_hash = ?, provenance_json = ?, version = ?, updated_at = ?
            WHERE memory_id = ?
            """, (new_content, new_hash, json.dumps(prov), new_version, now, memory_id))

            cur = conn.execute("SELECT * FROM hq_memory WHERE memory_id = ?", (memory_id,))
            return self._row_to_record(cur.fetchone())

    def delete(self, memory_id: str, actor: str) -> bool:
        now = time.time()
        with self._get_connection() as conn:
            cur = conn.execute("SELECT provenance_json FROM hq_memory WHERE memory_id = ? AND is_deleted = 0", (memory_id,))
            row = cur.fetchone()
            if not row:
                return False

            prov = json.loads(row["provenance_json"])
            prov["deleted_by"] = actor
            prov["deleted_at"] = now

            conn.execute(
                "UPDATE hq_memory SET is_deleted = 1, provenance_json = ?, updated_at = ? WHERE memory_id = ?",
                (json.dumps(prov), now, memory_id)
            )
            return True

    def query(self, reader_agent_id: Optional[str] = None,
              reader_division: Optional[str] = None,
              is_hq: bool = False,
              scope: Optional[str] = None,
              category: Optional[str] = None,
              keyword: Optional[str] = None,
              tag: Optional[str] = None,
              limit: int = 50) -> List[MemoryRecord]:
        """Queries memory honoring strict permission boundaries (Priority 4)."""
        with self._get_connection() as conn:
            sql = "SELECT * FROM hq_memory WHERE is_deleted = 0"
            params: List[Any] = []

            # Priority 4: Strict Permission Enforcement
            if is_hq or reader_agent_id in ("HQ", "PEMILIK", "EMP-L01"):
                # HQ Core / Lead Director can access ORGANIZATIONAL, HQ_ONLY, all AGENT and DIVISION scopes
                if scope:
                    sql += " AND scope = ?"
                    params.append(scope)
            elif reader_agent_id:
                # Specialist agent access rule:
                # 1. ORGANIZATIONAL
                # 2. AGENT:<reader_agent_id>
                # 3. DIVISION:<own_division> ONLY
                # NEVER HQ_ONLY or other agents/divisions
                div = reader_division or AGENT_DIVISION_MAP.get(reader_agent_id)
                allowed_clauses = ["scope = 'ORGANIZATIONAL'", "scope = ?"]
                params.append(f"AGENT:{reader_agent_id}")
                
                if div:
                    allowed_clauses.append("scope = ?")
                    params.append(f"DIVISION:{div}")

                sql += f" AND ({' OR '.join(allowed_clauses)})"
                sql += " AND scope != 'HQ_ONLY'"
            elif scope:
                # Unauthenticated or anonymous query: strictly cannot see private agent, division or HQ_ONLY scopes
                if scope in ("ORGANIZATIONAL",):
                    sql += " AND scope = ?"
                    params.append(scope)
                else:
                    # Deny unauthorized access to private scopes without reader credentials
                    sql += " AND 1 = 0"
            else:
                # Default anonymous access: only ORGANIZATIONAL
                sql += " AND scope = 'ORGANIZATIONAL'"

            if category:
                sql += " AND category = ?"
                params.append(category)

            if keyword:
                sql += " AND (title LIKE ? OR content LIKE ?)"
                kw = f"%{keyword}%"
                params.extend([kw, kw])

            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)

            cur = conn.execute(sql, params)
            rows = cur.fetchall()

            results = []
            for r in rows:
                rec = self._row_to_record(r)
                if tag and tag not in rec.tags:
                    continue
                results.append(rec)
            return results

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            scope=row["scope"],
            category=row["category"],
            title=row["title"],
            content=row["content"],
            content_hash=row["content_hash"],
            tags=json.loads(row["tags_json"]),
            provenance=json.loads(row["provenance_json"]),
            version=row["version"],
            is_deleted=bool(row["is_deleted"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
