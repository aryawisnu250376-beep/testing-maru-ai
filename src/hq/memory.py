"""
MARU HQ Persistent Organizational Memory & Knowledge Base Subsystem
Phase 6.1.3 Remediation — Trusted Identity & Strict Permission Boundaries
Implements:
 - Persistent SQLite Storage with WAL Mode
 - Explicit Server-Side Registry / Token Resolution (Identity cannot be self-claimed)
 - Strict Scope & Permission Model:
    * ORGANIZATIONAL: Shared knowledge accessible to all authenticated callers & anonymous
    * HQ_ONLY: Accessible ONLY to verified HQ Core (is_hq verified via server-side authority)
    * AGENT:<id>: Accessible ONLY to that specific Agent and verified HQ Core
    * DIVISION:<id>: Accessible ONLY to verified members of that specific division and verified HQ Core
 - Negative Security Protection: Rejects caller-supplied arbitrary impersonation
 - Audit Provenance, Content-Hash Deduplication, and Tombstone Deletion
"""

import sqlite3
import time
import json
import hashlib
import hmac
import math
import threading
from contextlib import closing
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field, replace

DEFAULT_MEMORY_DB = Path(__file__).resolve().parent.parent.parent / "data" / "hq_memory.db"

# Server-Side Trusted Agent & Division Registry
# A caller cannot simply pass reader_division='XYZ' or is_hq=True; identity must resolve here.
TRUSTED_ROSTER = {
    "EMP-L01": {"name": "Bima", "division": "EXECUTIVE_SUITE", "role": "HQ_DIRECTOR", "is_hq": True},
    "EMP-L02": {"name": "Hermes", "division": "CREATIVE_CORE", "role": "LEAD_CREATIVE", "is_hq": False},
    "EMP-L03": {"name": "Cendekia", "division": "ACADEMIC_INTELLIGENCE", "role": "HEAD_RESEARCH", "is_hq": False},
    "EMP-L04": {"name": "Wira", "division": "TELEMETRY_GROWTH", "role": "LEAD_TELEMETRY", "is_hq": False},
    "EMP-L05": {"name": "Ardi", "division": "AUDIO_PRODUCTION", "role": "SOUND_DIRECTOR", "is_hq": False},
    "EMP-L06": {"name": "Sena", "division": "QUALITY_ASSURANCE", "role": "CHIEF_INSPECTOR", "is_hq": False},
    "EMP-L07": {"name": "Kirana", "division": "VISUAL_DESIGN", "role": "AESTHETIC_DIRECTOR", "is_hq": False},
    "EMP-L08": {"name": "Danu", "division": "SYSTEM_OPERATIONS", "role": "SYSTEMS_ARCHITECT", "is_hq": False},
    "EMP-L09": {"name": "Ootto", "division": "PIPELINE_ORCHESTRATION", "role": "QUEUE_MASTER", "is_hq": False},
    "HQ": {"name": "HQ Core Command", "division": "EXECUTIVE_SUITE", "role": "CENTRAL_AUTHORITY", "is_hq": True},
    "PEMILIK": {"name": "Owner Superuser", "division": "EXECUTIVE_SUITE", "role": "OWNER", "is_hq": True},
}

import secrets

@dataclass(frozen=True)
class CallerPrincipal:
    """Server-side authenticated execution principal (cannot be claimed by caller string)."""
    principal_id: str
    division: str
    role: str
    is_hq: bool
    session_token: str = field(repr=False)
    issued_at: float
    expires_at: float

class InternalAuthAuthority:
    """
    Server-side authoritative identity issuer for MARU HQ.
    Enforces that caller string alone is NEVER proof of identity.
    Sessions require an internally signed session token issued by a verified authority.
    """
    _active_sessions: Dict[str, CallerPrincipal] = {}
    _server_bootstrap_secret: str = os.getenv("MARU_INTERNAL_BOOTSTRAP_SECRET", "")
    _agent_secrets: Dict[str, str] = {}
    _lock = threading.RLock()

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def set_bootstrap_secret(cls, secret: str) -> None:
        """Trusted startup / rotation hook. Rotating revokes prior credentials."""
        with cls._lock:
            cls._server_bootstrap_secret = secret
            cls._active_sessions.clear()
            cls._agent_secrets.clear()

    @classmethod
    def register_agent_credential(cls, agent_id: str, secret: str, bootstrap_key: str) -> bool:
        if not isinstance(agent_id, str) or not isinstance(secret, str) or not secret or not isinstance(bootstrap_key, str):
            return False
        with cls._lock:
            if agent_id not in TRUSTED_ROSTER or not cls._server_bootstrap_secret or not hmac.compare_digest(
                cls._digest(cls._server_bootstrap_secret), cls._digest(bootstrap_key)
            ) or hmac.compare_digest(cls._digest(cls._server_bootstrap_secret), cls._digest(secret)):
                return False
            cls._agent_secrets[agent_id] = cls._digest(secret)
            cls._active_sessions = {k: v for k, v in cls._active_sessions.items() if v.principal_id != agent_id}
            return True

    @classmethod
    def issue_principal(cls, actor_id: str, secret_key: str, ttl_sec: float = 3600.0) -> Optional[CallerPrincipal]:
        if not isinstance(actor_id, str) or not isinstance(secret_key, str) or not secret_key:
            return None
        if not isinstance(ttl_sec, (int, float)) or not math.isfinite(ttl_sec) or not 0 < ttl_sec <= 3600:
            return None
        trusted = TRUSTED_ROSTER.get(actor_id)
        if not trusted:
            return None
        digest = cls._digest(secret_key)
        with cls._lock:
            supervisor = bool(cls._server_bootstrap_secret) and hmac.compare_digest(cls._digest(cls._server_bootstrap_secret), digest)
            agent = cls._agent_secrets.get(actor_id)
            if not supervisor and not (agent and hmac.compare_digest(agent, digest)):
                return None
            token = f"psec_{secrets.token_hex(24)}"
            now = time.monotonic()
            principal = CallerPrincipal(actor_id, trusted["division"], trusted["role"], trusted["is_hq"], token, now, now + ttl_sec)
            cls._active_sessions = {k: v for k, v in cls._active_sessions.items() if v.expires_at > now}
            cls._active_sessions[cls._digest(token)] = replace(principal, session_token="")
            return principal

    @classmethod
    def authenticate(cls, token: Optional[str]) -> Optional[CallerPrincipal]:
        if not isinstance(token, str) or not token or len(token) > 128:
            return None
        key = cls._digest(token)
        with cls._lock:
            principal = cls._active_sessions.get(key)
            if principal and principal.expires_at <= time.monotonic():
                cls._active_sessions.pop(key, None)
                return None
            return principal

    @classmethod
    def revoke(cls, token: str) -> bool:
        if not isinstance(token, str) or not token or len(token) > 128:
            return False
        with cls._lock:
            return cls._active_sessions.pop(cls._digest(token), None) is not None

@dataclass
class CallerContext:
    caller_id: Optional[str]
    division: Optional[str]
    is_hq: bool
    authenticated: bool = False
    principal: Optional[CallerPrincipal] = None

    @classmethod
    def resolve_authenticated(cls, token: Optional[str] = None) -> "CallerContext":
        """Strict server-side identity resolution. Fails closed to anonymous if token invalid."""
        if not token:
            return cls(caller_id=None, division=None, is_hq=False, authenticated=False, principal=None)
        
        principal = InternalAuthAuthority.authenticate(token)
        if not principal:
            return cls(caller_id=None, division=None, is_hq=False, authenticated=False, principal=None)
        
        return cls(
            caller_id=principal.principal_id,
            division=principal.division,
            is_hq=principal.is_hq,
            authenticated=True,
            principal=principal
        )

    @classmethod
    def resolve_actor(cls, actor_id: Optional[str]) -> "CallerContext":
        """A claimed identity, including a roster ID, is never authentication."""
        return cls(caller_id=None, division=None, is_hq=False, authenticated=False)

    @classmethod
    def resolve(cls, caller_id: Optional[str] = None, client_auth_key: Optional[str] = None) -> "CallerContext":
        ctx = cls.resolve_authenticated(client_auth_key)
        if caller_id and ctx.caller_id != caller_id:
            return cls.resolve_actor(caller_id)
        return ctx


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
        with closing(self._get_connection()) as conn, conn:
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

    def _verify_operation_authorization(self, op: str, target_scope: str,
                                         actor_id: Optional[str] = None,
                                         auth_token: Optional[str] = None) -> CallerContext:
        """
        Enforces explicit authorization for store, update, delete, and query.
        Fails closed if the identity cannot be validated or lacks permission for target_scope.
        """
        ctx = CallerContext.resolve(caller_id=actor_id, client_auth_key=auth_token)
        if ctx.authenticated and ctx.is_hq:
            return ctx
        if not ctx.authenticated:
            raise PermissionError("Access Denied: authenticated memory principal required")
        if target_scope == "HQ_ONLY":
            raise PermissionError("Access Denied: HQ scope requires verified HQ authority")

        # 4. Authenticated specialist agent:
        # Can access ORGANIZATIONAL, AGENT:<self>, DIVISION:<self_division>
        allowed_scopes = {"ORGANIZATIONAL", f"AGENT:{ctx.caller_id}"}
        if ctx.division:
            allowed_scopes.add(f"DIVISION:{ctx.division}")

        if target_scope not in allowed_scopes:
            raise PermissionError(
                f"Access Denied: Actor '{ctx.caller_id}' from division '{ctx.division}' "
                f"is not authorized for scope '{target_scope}'. Allowed: {allowed_scopes}"
            )
        return ctx

    def store(self, scope: str, category: str, title: str, content: str,
              tags: Optional[List[str]] = None,
              provenance: Optional[Dict[str, Any]] = None,
              actor_id: Optional[str] = None,
              auth_token: Optional[str] = None) -> MemoryRecord:
        """Stores a memory entry with deduplication, provenance, and scope authorization."""
        ctx = self._verify_operation_authorization("store", scope, actor_id=actor_id, auth_token=auth_token)
        now = time.time()
        c_hash = self._compute_hash(scope, category, title, content)
        tags_list = tags or []
        prov = dict(provenance or {})
        prov["stored_at"] = now
        # Provenance must derive from verified principal, not untrusted caller input!
        prov["stored_by"] = ctx.caller_id or "ANONYMOUS"

        with closing(self._get_connection()) as conn, conn:
            cur = conn.execute("SELECT * FROM hq_memory WHERE content_hash = ?", (c_hash,))
            row = cur.fetchone()
            if row:
                if row["is_deleted"] == 1:
                    conn.execute(
                        "UPDATE hq_memory SET is_deleted = 0, updated_at = ? WHERE memory_id = ?",
                        (now, row["memory_id"])
                    )
                return self._row_to_record(conn.execute("SELECT * FROM hq_memory WHERE memory_id = ?", (row["memory_id"],)).fetchone())

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

    def update(self, memory_id: str, new_content: str, editor: str,
               auth_token: Optional[str] = None) -> Optional[MemoryRecord]:
        now = time.time()
        with closing(self._get_connection()) as conn, conn:
            cur = conn.execute("SELECT * FROM hq_memory WHERE memory_id = ? AND is_deleted = 0", (memory_id,))
            row = cur.fetchone()
            if not row:
                return None

            scope = row["scope"]
            ctx = self._verify_operation_authorization("update", scope, actor_id=editor, auth_token=auth_token)

            cat = row["category"]
            title = row["title"]
            new_hash = self._compute_hash(scope, cat, title, new_content)

            prov = json.loads(row["provenance_json"])
            updates = prov.get("updates", [])
            updates.append({"editor": ctx.caller_id or "ANONYMOUS", "timestamp": now, "previous_hash": row["content_hash"]})
            prov["updates"] = updates

            new_version = row["version"] + 1
            conn.execute("""
            UPDATE hq_memory 
            SET content = ?, content_hash = ?, provenance_json = ?, version = ?, updated_at = ?
            WHERE memory_id = ?
            """, (new_content, new_hash, json.dumps(prov), new_version, now, memory_id))

            cur = conn.execute("SELECT * FROM hq_memory WHERE memory_id = ?", (memory_id,))
            return self._row_to_record(cur.fetchone())

    def delete(self, memory_id: str, actor: str,
               auth_token: Optional[str] = None) -> bool:
        now = time.time()
        with closing(self._get_connection()) as conn, conn:
            cur = conn.execute("SELECT * FROM hq_memory WHERE memory_id = ? AND is_deleted = 0", (memory_id,))
            row = cur.fetchone()
            if not row:
                return False

            scope = row["scope"]
            ctx = self._verify_operation_authorization("delete", scope, actor_id=actor, auth_token=auth_token)

            prov = json.loads(row["provenance_json"])
            prov["deleted_by"] = ctx.caller_id or "ANONYMOUS"
            prov["deleted_at"] = now

            conn.execute(
                "UPDATE hq_memory SET is_deleted = 1, provenance_json = ?, updated_at = ? WHERE memory_id = ?",
                (json.dumps(prov), now, memory_id)
            )
            return True

    def count_organizational(self) -> int:
        """Count only organizational records, without reading their contents."""
        conn = self._get_connection()
        try:
            return conn.execute("SELECT COUNT(*) FROM hq_memory WHERE is_deleted = 0 AND scope = 'ORGANIZATIONAL'").fetchone()[0]
        finally:
            conn.close()

    def query(self, reader_agent_id: Optional[str] = None,
              reader_division: Optional[str] = None,
              is_hq: bool = False,
              scope: Optional[str] = None,
              category: Optional[str] = None,
              keyword: Optional[str] = None,
              tag: Optional[str] = None,
              limit: int = 50, *, auth_token: Optional[str] = None) -> List[MemoryRecord]:
        """
        Queries memory honoring strict permission boundaries (Priority A Remediation).
        Ignores caller-claimed is_hq or reader_division; resolves strictly via server-side trusted registry.
        """
        # Resolve trusted caller context
        ctx = CallerContext.resolve(caller_id=reader_agent_id, client_auth_key=auth_token)
        if auth_token is not None and not ctx.authenticated:
            raise PermissionError("Access Denied: invalid memory principal")
        if not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("Invalid memory query limit")

        with closing(self._get_connection()) as conn, conn:
            sql = "SELECT * FROM hq_memory WHERE is_deleted = 0"
            params: List[Any] = []

            # Priority A Enforcement: Trusted Identity Resolution
            if ctx.is_hq:
                # Verified HQ Core: Can access ORGANIZATIONAL, HQ_ONLY, and all AGENT/DIVISION scopes
                if scope:
                    sql += " AND scope = ?"
                    params.append(scope)
            elif ctx.caller_id:
                # Authenticated Specialist Agent (e.g. EMP-L02 Hermes)
                # Allowed:
                # 1. ORGANIZATIONAL
                # 2. AGENT:<caller_id>
                # 3. DIVISION:<verified_division> ONLY
                # NEVER HQ_ONLY or other agents/divisions
                allowed_scopes = ["scope = 'ORGANIZATIONAL'", "scope = ?"]
                params.append(f"AGENT:{ctx.caller_id}")
                
                if ctx.division:
                    allowed_scopes.append("scope = ?")
                    params.append(f"DIVISION:{ctx.division}")

                sql += f" AND ({' OR '.join(allowed_scopes)})"
                sql += " AND scope != 'HQ_ONLY'"

                if scope:
                    # If specific scope requested, ensure it is within caller's allowed set
                    valid_request = (
                        scope == "ORGANIZATIONAL" or 
                        scope == f"AGENT:{ctx.caller_id}" or 
                        (ctx.division and scope == f"DIVISION:{ctx.division}")
                    )
                    if valid_request:
                        sql += " AND scope = ?"
                        params.append(scope)
                    else:
                        # Attempt to query unauthorized scope -> safely return zero records
                        sql += " AND 1 = 0"
            else:
                # Anonymous or unverified caller: strictly ORGANIZATIONAL memory only
                if scope and scope != "ORGANIZATIONAL":
                    # Attempt to query private memory as anonymous -> deny safely
                    sql += " AND 1 = 0"
                else:
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
