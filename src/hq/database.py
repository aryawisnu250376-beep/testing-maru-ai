"""
MARU HQ Core Database Connection Manager — Phase 6.1
Manages SQLite WAL Mode, Pragmas, Table Schemas, and Safe Connections
Location: data/hq_core.db (Isolated from legacy division databases)
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path("data/hq_core.db")

SCHEMA_SQL = """
-- 1. Persistent Job Queue Table
CREATE TABLE IF NOT EXISTS hq_jobs (
    task_id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    parent_task_id TEXT,
    division TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    goal TEXT NOT NULL,
    input_payload TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    priority INTEGER DEFAULT 1,
    status TEXT NOT NULL,
    assigned_agent TEXT NOT NULL,
    dependencies TEXT DEFAULT '[]',
    budget_payload TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    lease_owner TEXT,
    lease_expires_at REAL,
    fencing_token INTEGER DEFAULT 0,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    result_payload TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_hq_jobs_status_priority ON hq_jobs(status, priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_hq_jobs_correlation ON hq_jobs(correlation_id);
CREATE INDEX IF NOT EXISTS idx_hq_jobs_lease ON hq_jobs(lease_owner, lease_expires_at);

-- 2. Audit Event Logs Table
CREATE TABLE IF NOT EXISTS hq_event_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    fencing_token INTEGER DEFAULT 0,
    previous_state TEXT,
    new_state TEXT,
    details TEXT,
    timestamp REAL NOT NULL,
    FOREIGN KEY(task_id) REFERENCES hq_jobs(task_id)
);

CREATE INDEX IF NOT EXISTS idx_hq_events_task_id ON hq_event_logs(task_id);
"""

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = db_path or DEFAULT_DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(
        str(target),
        timeout=10.0,
        isolation_level=None  # Enable autocommit / manual transaction control
    )
    # Enable WAL mode, busy timeout, and foreign keys
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db(db_path: Optional[Path] = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()
