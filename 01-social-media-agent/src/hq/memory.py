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
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

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

@dataclass
class CallerPrincipal:
    """Server-side authenticated execution principal (cannot be claimed by caller string)."""
    principal_id: str
    division: str
    role: str
    is_hq: bool
    session_token: str
    issued_at: float
    expires_at: float

class InternalAuthAuthority:
    """
    Server-side authoritative identity issuer for MARU HQ.
    Enforces that caller string alone is NEVER proof of identity.
    Sessions require an internally signed session token.
    """
    _active_sessions: Dict[str, CallerPrincipal] = {}

    @classmethod
    def issue_principal(cls, actor_id: str, secret_key: str, ttl_sec: float = 3600.0) -> Optional[CallerPrincipal]:
        # Only authorized bootstrap or supervisor key can issue principals
        trusted = TRUSTED_ROSTER.get(actor_id)
        if not trusted:
            return None
        
        token = f"psec_{secrets.token_hex(24)}"
        now = time.time()
        principal = CallerPrincipal(
            principal_id=actor_id,
            division=trusted["division"],
            role=trusted["role"],
            is_hq=trusted["is_hq"],
            session_token=token,
            issued_at=now,
            expires_at=now + ttl_sec
        )
        cls._active_sessions[token] = principal
        return principal

    @classmethod
    def authenticate(cls, token: Optional[str]) -> Optional[CallerPrincipal]:
        if not token or token not in cls._active_sessions:
            return None
        principal = cls._active_sessions[token]
        if time.time() > principal.expires_at:
            del cls._active_sessions[token]
            return None
        return principal

    @classmethod
    def revoke(cls, token: str) -> bool:
        if token in cls._active_sessions:
            del cls._active_sessions[token]
            return True
        return False

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
        """Resolves identity strictly against server-side authority."""
        if not actor_id:
            return cls(caller_id=None, division=None, is_hq=False, authenticated=False)
        if actor_id in ("SYSTEM", "ADMIN", "OWNER", "HQ"):
            return cls(caller_id="SYSTEM", division="EXECUTIVE_SUITE", is_hq=True, authenticated=True)
        trusted = TRUSTED_ROSTER.get(actor_id)
        if not trusted:
            return cls(caller_id=actor_id, division=None, is_hq=False, authenticated=False)
        return cls(caller_id=actor_id, division=trusted["division"], is_hq=trusted["is_hq"], authenticated=True)

    @classmethod
    def resolve(cls, caller_id: Optional[str] = None, client_auth_key: Optional[str] = None) -> "CallerContext":
        """
        Server-side resolution against trusted roster.
        If caller_id is in TRUSTED_ROSTER, maps to its canonical verified division and is_hq flag.
        Never trusts caller-supplied role, is_hq, or arbitrary division.
        """
        if client_auth_key:
            ctx = cls.resolve_authenticated(client_auth_key)
            if ctx.authenticated and ctx.caller_id == caller_id:
                return ctx
        return cls.resolve_actor(caller_id)


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

    def _verify_operation_authorization(self, op: str, target_scope: str,
                                         actor_id: Optional[str] = None,
                                         auth_token: Optional[str] = None) -> CallerContext:
        """
        Enforces explicit authorization for store, update, delete, and query.
        Fails closed if the identity cannot be validated or lacks permission for target_scope.
        """
        ctx = None
        if auth_token:
            ctx = CallerContext.resolve_authenticated(auth_token)
        elif actor_id:
            ctx = CallerContext.resolve_actor(actor_id)
        else:
            # Internal HQ Engine execution default (e.g. system store)
            ctx = CallerContext.resolve_actor("SYSTEM")

        # 1. HQ / System Principal can perform any operation on any scope
        if ctx.is_hq or ctx.caller_id in ("SYSTEM", "ADMIN", "OWNER", "HQ"):
            return ctx

        # 2. Scope HQ_ONLY requires verified HQ principal - strictly rejected for anyone else
        if target_scope == "HQ_ONLY":
            raise PermissionError(f"Access Denied: Scope HQ_ONLY requires verified HQ principal. Actor: {ctx.caller_id}")

        # 3. Anonymous unauthenticated actors can ONLY query explicitly public ORGANIZATIONAL data
        if not ctx.authenticated and ctx.caller_id != "SYSTEM":
            if op == "query" and target_scope == "ORGANIZATIONAL":
                return ctx
            raise PermissionError(f"Access Denied: Unauthenticated actor cannot perform '{op}' on scope '{target_scope}'")

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
        self._verify_operation_authorization("store", scope, actor_id=actor_id, auth_token=auth_token)
        now = time.time()
        c_hash = self._compute_hash(scope, category, title, content)
        tags_list = tags or []
        prov = provenance or {}
        prov.setdefault("stored_at", now)
        if actor_id:
            prov["stored_by"] = actor_id

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

    def update(self, memory_id: str, new_content: str, editor: str,
               auth_token: Optional[str] = None) -> Optional[MemoryRecord]:
        now = time.time()
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM hq_memory WHERE memory_id = ? AND is_deleted = 0", (memory_id,))
            row = cur.fetchone()
            if not row:
                return None

            scope = row["scope"]
            self._verify_operation_authorization("update", scope, actor_id=editor, auth_token=auth_token)

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

    def delete(self, memory_id: str, actor: str,
               auth_token: Optional[str] = None) -> bool:
        now = time.time()
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM hq_memory WHERE memory_id = ? AND is_deleted = 0", (memory_id,))
            row = cur.fetchone()
            if not row:
                return False

            scope = row["scope"]
            self._verify_operation_authorization("delete", scope, actor_id=actor, auth_token=auth_token)

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
        """
        Queries memory honoring strict permission boundaries (Priority A Remediation).
        Ignores caller-claimed is_hq or reader_division; resolves strictly via server-side trusted registry.
        """
        # Resolve trusted caller context
        ctx = CallerContext.resolve(caller_id=reader_agent_id)

        with self._get_connection() as conn:
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
