"""
MARU HQ Worker Framework — Phase 6.1.1 Hardened
Implements:
 - Instant Heartbeat Termination with stop_event.wait()
 - Cooperative Cancellation Token passed to Job Handler
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

        # E5. Automatic Startup Recovery
        if auto_recover_startup:
            self.queue.recover_stale_jobs(actor=f"STARTUP_{self.worker_id}")

    def execute_one_cycle(self, job_handler: Callable[[CanonicalJob, CancellationToken], Dict[str, Any]]) -> bool:
        """Attempts to acquire a lease and safely execute one job with budget & cooperative cancellation."""
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
                # E4. Instant wakeup instead of time.sleep
                interrupted = stop_heartbeat.wait(timeout=self.heartbeat_interval_sec)
                if interrupted or stop_heartbeat.is_set():
                    break
                
                # Check heartbeat & cancellation
                alive = self.queue.heartbeat(self.worker_id, job.task_id, job.fencing_token)
                if not alive:
                    # Lease lost, expired, or cancelled!
                    stop_heartbeat.set()
                    break

                # Renew lease periodically
                if time.time() - last_renewal >= self.lease_renewal_interval_sec:
                    renewed = self.queue.renew_lease(self.worker_id, job.task_id, job.fencing_token)
                    if renewed:
                        last_renewal = time.time()
                    else:
                        stop_heartbeat.set()
                        break

        self._renewal_thread = threading.Thread(target=renewal_loop, daemon=True)
        self._renewal_thread.start()

        start_time = time.time()
        max_duration = job.budget.max_duration_sec

        try:
            # E6. Budget & Time Limit Enforcement
            result = job_handler(job, cancel_token)
            duration = time.time() - start_time
            if duration > max_duration:
                raise BudgetExceededError(f"Job exceeded max duration budget: {duration:.2f}s > {max_duration}s")

            # Check if cancelled mid-execution
            cancel_token.check()

            stop_heartbeat.set()
            if self._renewal_thread.is_alive():
                self._renewal_thread.join(timeout=2.0)

            # Complete job with fencing token
            completed = self.queue.complete_job(self.worker_id, job.task_id, job.fencing_token, result)
            return completed
        except Exception as e:
            stop_heartbeat.set()
            if self._renewal_thread.is_alive():
                self._renewal_thread.join(timeout=2.0)
            self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, str(e))
            return False
        finally:
            self._current_job = None
