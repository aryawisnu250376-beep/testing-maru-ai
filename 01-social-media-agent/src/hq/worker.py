"""
MARU HQ Worker Framework — Phase 6.1.3 Hardened
Implements:
 - Instant Heartbeat Termination with stop_event.wait()
 - Cooperative Cancellation Token passed to Job Handler
 - Isolated Thread Execution with Strict Hard Timeout Guardian
 - Non-cooperative Handler Abandonment & Fencing Revocation
 - Automatic Startup Stale Recovery
 - Hard Budget & Execution Time Limits
"""

import time
import uuid
import threading
from typing import Callable, Optional, Dict, Any

from src.hq.queue import HQJobQueue
from src.hq.models import CanonicalJob, JobStatus, BudgetExceededError

class CancellationToken:
    def __init__(self, stop_event: threading.Event):
        self._stop_event = stop_event

    @property
    def is_cancelled(self) -> bool:
        return self._stop_event.is_set()

    def check(self):
        if self._stop_event.is_set():
            raise TimeoutError("Execution cancelled: lease lost or job cancelled by owner")

class HQWorker:
    def __init__(self, queue: HQJobQueue, worker_id: Optional[str] = None,
                 assigned_agent: Optional[str] = None, heartbeat_interval_sec: float = 5.0,
                 lease_renewal_interval_sec: float = 10.0, auto_recover_startup: bool = True):
        self.queue = queue
        self.worker_id = worker_id or f"WORKER-{uuid.uuid4().hex[:6].upper()}"
        self.assigned_agent = assigned_agent
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.lease_renewal_interval_sec = lease_renewal_interval_sec
        self.running = False
        self._current_job: Optional[CanonicalJob] = None
        self._renewal_thread: Optional[threading.Thread] = None

        # Automatic Startup Stale Recovery
        if auto_recover_startup:
            self.queue.recover_stale_jobs(actor=f"STARTUP_{self.worker_id}")

    def execute_one_cycle(self, job_handler: Callable[[CanonicalJob, CancellationToken], Dict[str, Any]]) -> bool:
        """Attempts to acquire a lease and safely execute one job with isolated thread hard-timeout & cancellation."""
        job = self.queue.acquire_lease(self.worker_id, self.assigned_agent)
        if not job:
            return False

        self._current_job = job
        stop_heartbeat = threading.Event()
        cancel_token = CancellationToken(stop_heartbeat)

        # Dedicated background heartbeat & renewal thread
        def renewal_loop():
            last_renewal = time.time()
            while not stop_heartbeat.is_set():
                interrupted = stop_heartbeat.wait(timeout=self.heartbeat_interval_sec)
                if interrupted or stop_heartbeat.is_set():
                    break
                
                alive = self.queue.heartbeat(self.worker_id, job.task_id, job.fencing_token)
                if not alive:
                    stop_heartbeat.set()
                    break

                if time.time() - last_renewal >= self.lease_renewal_interval_sec:
                    renewed = self.queue.renew_lease(self.worker_id, job.task_id, job.fencing_token)
                    if renewed:
                        last_renewal = time.time()
                    else:
                        stop_heartbeat.set()
                        break

        self._renewal_thread = threading.Thread(target=renewal_loop, daemon=True)
        self._renewal_thread.start()

        max_duration = job.budget.max_duration_sec
        handler_result: Dict[str, Any] = {}
        handler_error: Optional[Exception] = None
        handler_done = threading.Event()

        def isolated_execution():
            nonlocal handler_result, handler_error
            try:
                res = job_handler(job, cancel_token)
                # Ensure cancellation check upon completion
                cancel_token.check()
                handler_result = res
            except Exception as e:
                handler_error = e
            finally:
                handler_done.set()

        worker_thread = threading.Thread(target=isolated_execution, daemon=True)
        start_time = time.time()
        worker_thread.start()

        # Hard-timeout guardian: Wait strictly up to max_duration
        finished_in_time = handler_done.wait(timeout=max_duration)
        duration = time.time() - start_time

        # Stop heartbeat thread
        stop_heartbeat.set()
        if self._renewal_thread.is_alive():
            self._renewal_thread.join(timeout=1.0)

        if not finished_in_time:
            # P3: Hard timeout! The handler is non-cooperative or hung.
            # Signal cancellation token so cooperative subroutines can abort
            err_msg = f"Job exceeded max duration budget: {duration:.2f}s > {max_duration}s (Hard Timeout Reached)"
            self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, err_msg)
            self._current_job = None
            return False

        if handler_error:
            self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, str(handler_error))
            self._current_job = None
            return False

        # Attempt to complete job with fencing token
        completed = self.queue.complete_job(self.worker_id, job.task_id, job.fencing_token, handler_result)
        self._current_job = None
        return completed
