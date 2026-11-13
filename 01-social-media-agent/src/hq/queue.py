"""
MARU HQ Persistent Job Queue Engine — Phase 6.1
Implements 11 Core Operations with Fencing Tokens, Atomic Transactions & Stale Lease Recovery
"""

import sqlite3
import json
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from src.hq.models import CanonicalJob, JobStatus, JobPriority, JobBudget
from src.hq.database import get_connection, init_db, DEFAULT_DB_PATH

class HQJobQueue:
    def __init__(self, db_path: Optional[Path] = None, lease_duration_sec: float = 30.0):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.lease_duration_sec = lease_duration_sec
        init_db(self.db_path)

    def _log_event(self, conn: sqlite3.Connection, task_id: str, event_type: str, actor: str,
                   fencing_token: int, prev_state: Optional[str], new_state: str, details: Dict[str, Any]) -> None:
        conn.execute(
            """INSERT INTO hq_event_logs (task_id, event_type, actor, fencing_token, previous_state, new_state, details, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, event_type, actor, fencing_token, prev_state, new_state, json.dumps(details), time.time())
        )

    # 1. ENQUEUE
    def enqueue(self, division: str, requested_by: str, goal: str, input_payload: Dict[str, Any],
                acceptance_criteria: List[str], assigned_agent: str, idempotency_key: str,
                priority: int = JobPriority.NORMAL.value, budget: Optional[JobBudget] = None,
                parent_task_id: Optional[str] = None, dependencies: Optional[List[str]] = None) -> CanonicalJob:
        conn = get_connection(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            
            # Check idempotency key first
            cur = conn.execute("SELECT * FROM hq_jobs WHERE idempotency_key = ?", (idempotency_key,))
            row = cur.fetchone()
            if row:
                conn.execute("COMMIT")
                return CanonicalJob.from_row(row)

            now = time.time()
            task_id = f"JOB-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            corr_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"
            budget_obj = budget or JobBudget()

            conn.execute(
                """INSERT INTO hq_jobs (
                    task_id, correlation_id, parent_task_id, division, requested_by, goal,
                    input_payload, acceptance_criteria, priority, status, assigned_agent,
                    dependencies, budget_payload, attempts, max_attempts, lease_owner,
                    lease_expires_at, fencing_token, idempotency_key, created_at, updated_at,
                    result_payload, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id, corr_id, parent_task_id, division, requested_by, goal,
                    json.dumps(input_payload), json.dumps(acceptance_criteria), priority,
                    JobStatus.QUEUED.value, assigned_agent, json.dumps(dependencies or []),
                    json.dumps(budget_obj.to_dict()), 0, 3, None, None, 0,
                    idempotency_key, now, now, None, None
                )
            )

            self._log_event(conn, task_id, "JOB_ENQUEUED", requested_by, 0, None, JobStatus.QUEUED.value,
                            {"goal": goal, "assigned_agent": assigned_agent, "priority": priority})
            
            conn.execute("COMMIT")
            return self.get_job(task_id, conn)
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # 2. ACQUIRE LEASE (ATOMIC WITH FENCING TOKEN)
    def acquire_lease(self, worker_id: str, assigned_agent: Optional[str] = None) -> Optional[CanonicalJob]:
        conn = get_connection(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = time.time()
            lease_expiry = now + self.lease_duration_sec

            # Select highest priority eligible job that is QUEUED or RETRYING
            query = """
                SELECT task_id, fencing_token, attempts, status FROM hq_jobs
                WHERE status IN (?, ?)
            """
            params = [JobStatus.QUEUED.value, JobStatus.RETRYING.value]
            if assigned_agent:
                query += " AND assigned_agent = ?"
                params.append(assigned_agent)
            query += " ORDER BY priority DESC, created_at ASC LIMIT 1"

            cur = conn.execute(query, params)
            row = cur.fetchone()
            if not row:
                conn.execute("COMMIT")
                return None

            task_id, current_fence, current_attempts, prev_status = row
            new_fence = current_fence + 1
            new_attempts = current_attempts + 1

            conn.execute(
                """UPDATE hq_jobs SET
                    status = ?, lease_owner = ?, lease_expires_at = ?,
                    fencing_token = ?, attempts = ?, updated_at = ?
                   WHERE task_id = ? AND fencing_token = ?""",
                (JobStatus.LEASED.value, worker_id, lease_expiry, new_fence, new_attempts, now, task_id, current_fence)
            )

            self._log_event(conn, task_id, "LEASE_ACQUIRED", worker_id, new_fence, prev_status,
                            JobStatus.LEASED.value, {"lease_duration_sec": self.lease_duration_sec, "attempts": new_attempts})

            conn.execute("COMMIT")
            return self.get_job(task_id, conn)
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # 3. HEARTBEAT
    def heartbeat(self, worker_id: str, task_id: str, fencing_token: int) -> bool:
        """Returns True if lease is active and fencing token matches."""
        conn = get_connection(self.db_path)
        try:
            now = time.time()
            cur = conn.execute(
                """SELECT 1 FROM hq_jobs
                   WHERE task_id = ? AND lease_owner = ? AND fencing_token = ? AND lease_expires_at > ?""",
                (task_id, worker_id, fencing_token, now)
            )
            return cur.fetchone() is not None
        finally:
            conn.close()

    # 4. RENEW LEASE
    def renew_lease(self, worker_id: str, task_id: str, fencing_token: int) -> bool:
        conn = get_connection(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = time.time()
            new_expiry = now + self.lease_duration_sec

            cur = conn.execute(
                """UPDATE hq_jobs SET
                    lease_expires_at = ?, updated_at = ?
                   WHERE task_id = ? AND lease_owner = ? AND fencing_token = ? AND lease_expires_at > ?""",
                (new_expiry, now, task_id, worker_id, fencing_token, now)
            )
            renewed = cur.rowcount > 0
            if renewed:
                self._log_event(conn, task_id, "LEASE_RENEWED", worker_id, fencing_token,
                                JobStatus.LEASED.value, JobStatus.LEASED.value, {"new_expires_at": new_expiry})
            conn.execute("COMMIT")
            return renewed
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # 5. COMPLETE JOB (PROTECTED BY FENCING TOKEN)
    def complete_job(self, worker_id: str, task_id: str, fencing_token: int, result_payload: Dict[str, Any]) -> bool:
        conn = get_connection(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = time.time()

            cur = conn.execute(
                """UPDATE hq_jobs SET
                    status = ?, lease_owner = NULL, lease_expires_at = NULL,
                    result_payload = ?, updated_at = ?
                   WHERE task_id = ? AND lease_owner = ? AND fencing_token = ? AND lease_expires_at > ?""",
                (JobStatus.COMPLETED.value, json.dumps(result_payload), now, task_id, worker_id, fencing_token, now)
            )
            success = cur.rowcount > 0
            if success:
                self._log_event(conn, task_id, "JOB_COMPLETED", worker_id, fencing_token,
                                JobStatus.LEASED.value, JobStatus.COMPLETED.value, {"result_keys": list(result_payload.keys())})
            conn.execute("COMMIT")
            return success
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # 6. FAIL JOB (PROTECTED BY FENCING TOKEN)
    def fail_job(self, worker_id: str, task_id: str, fencing_token: int, error_message: str) -> bool:
        conn = get_connection(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = time.time()

            # Retrieve current attempts and max_attempts
            cur = conn.execute("SELECT attempts, max_attempts FROM hq_jobs WHERE task_id = ? AND fencing_token = ?", (task_id, fencing_token))
            row = cur.fetchone()
            if not row:
                conn.execute("COMMIT")
                return False

            attempts, max_attempts = row
            can_retry = attempts < max_attempts
            new_status = JobStatus.RETRYING.value if can_retry else JobStatus.DEAD_LETTER.value

            cur = conn.execute(
                """UPDATE hq_jobs SET
                    status = ?, lease_owner = NULL, lease_expires_at = NULL,
                    error_message = ?, updated_at = ?
                   WHERE task_id = ? AND lease_owner = ? AND fencing_token = ?""",
                (new_status, error_message, now, task_id, worker_id, fencing_token)
            )
            success = cur.rowcount > 0
            if success:
                self._log_event(conn, task_id, "JOB_FAILED", worker_id, fencing_token,
                                JobStatus.LEASED.value, new_status, {"error": error_message, "attempts": attempts, "can_retry": can_retry})
            conn.execute("COMMIT")
            return success
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # 7. RETRY JOB (MANUAL OR SCHEDULED TRIGGER)
    def retry_job(self, task_id: str, actor: str = "ORCHESTRATOR") -> bool:
        conn = get_connection(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = time.time()
            cur = conn.execute(
                """UPDATE hq_jobs SET
                    status = ?, lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                   WHERE task_id = ? AND status IN (?, ?) AND attempts < max_attempts""",
                (JobStatus.QUEUED.value, now, task_id, JobStatus.FAILED.value, JobStatus.RETRYING.value)
            )
            success = cur.rowcount > 0
            if success:
                self._log_event(conn, task_id, "JOB_RETRY_SCHEDULED", actor, 0,
                                "RETRY_PENDING", JobStatus.QUEUED.value, {})
            conn.execute("COMMIT")
            return success
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # 8. RECOVER STALE JOBS (CRASHED / EXPIRED LEASE RECOVERY)
    def recover_stale_jobs(self, actor: str = "RECOVERY_DAEMON") -> int:
        conn = get_connection(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = time.time()

            # Find jobs where lease_expires_at is strictly in the past
            cur = conn.execute(
                """SELECT task_id, attempts, max_attempts, fencing_token, lease_owner
                   FROM hq_jobs
                   WHERE status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?""",
                (JobStatus.LEASED.value, now)
            )
            stale = cur.fetchall()
            recovered_count = 0

            for task_id, attempts, max_attempts, fence, old_owner in stale:
                can_retry = attempts < max_attempts
                next_status = JobStatus.QUEUED.value if can_retry else JobStatus.DEAD_LETTER.value
                new_fence = fence + 1  # Invalidate old worker's fencing token!

                conn.execute(
                    """UPDATE hq_jobs SET
                        status = ?, lease_owner = NULL, lease_expires_at = NULL,
                        fencing_token = ?, error_message = ?, updated_at = ?
                       WHERE task_id = ? AND fencing_token = ?""",
                    (next_status, new_fence, f"Lease expired from worker {old_owner}", now, task_id, fence)
                )
                self._log_event(conn, task_id, "STALE_LEASE_RECOVERED", actor, new_fence,
                                JobStatus.LEASED.value, next_status, {"old_owner": old_owner, "can_retry": can_retry})
                recovered_count += 1

            conn.execute("COMMIT")
            return recovered_count
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # 9. CANCEL JOB
    def cancel_job(self, task_id: str, actor: str = "PEMILIK_HQ", reason: str = "Dibatalkan oleh pengguna") -> bool:
        conn = get_connection(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = time.time()
            cur = conn.execute(
                """UPDATE hq_jobs SET
                    status = ?, lease_owner = NULL, lease_expires_at = NULL,
                    error_message = ?, updated_at = ?
                   WHERE task_id = ? AND status NOT IN (?, ?)""",
                (JobStatus.CANCELLED.value, reason, now, task_id, JobStatus.COMPLETED.value, JobStatus.CANCELLED.value)
            )
            success = cur.rowcount > 0
            if success:
                self._log_event(conn, task_id, "JOB_CANCELLED", actor, 0, None, JobStatus.CANCELLED.value, {"reason": reason})
            conn.execute("COMMIT")
            return success
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # 10. GET JOB
    def get_job(self, task_id: str, external_conn: Optional[sqlite3.Connection] = None) -> Optional[CanonicalJob]:
        conn = external_conn or get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT * FROM hq_jobs WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            return CanonicalJob.from_row(row)
        finally:
            if not external_conn:
                conn.close()

    # 11. LIST JOBS
    def list_jobs(self, status: Optional[str] = None, division: Optional[str] = None, limit: int = 50) -> List[CanonicalJob]:
        conn = get_connection(self.db_path)
        try:
            query = "SELECT * FROM hq_jobs"
            clauses = []
            params = []
            if status:
                clauses.append("status = ?")
                params.append(status)
            if division:
                clauses.append("division = ?")
                params.append(division)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cur = conn.execute(query, params)
            return [CanonicalJob.from_row(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # AUDIT LOG VIEWER
    def get_event_logs(self, task_id: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT * FROM hq_event_logs WHERE task_id = ? ORDER BY timestamp ASC", (task_id,))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()
