"""
MARU HQ Worker Framework — Phase 6.1
Implements Worker ID, Autonomous Lease Acquisition, Periodic Heartbeat, and Safe Job Execution
"""

import time
import uuid
import threading
from typing import Callable, Optional, Dict, Any

from src.hq.queue import HQJobQueue
from src.hq.models import CanonicalJob, JobStatus

class HQWorker:
    def __init__(self, queue: HQJobQueue, worker_id: Optional[str] = None,
                 assigned_agent: Optional[str] = None, heartbeat_interval_sec: float = 5.0,
                 lease_renewal_interval_sec: float = 10.0):
        self.queue = queue
        self.worker_id = worker_id or f"WORKER-{uuid.uuid4().hex[:6].upper()}"
        self.assigned_agent = assigned_agent
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.lease_renewal_interval_sec = lease_renewal_interval_sec
        self.running = False
        self._current_job: Optional[CanonicalJob] = None
        self._renewal_thread: Optional[threading.Thread] = None

    def execute_one_cycle(self, job_handler: Callable[[CanonicalJob], Dict[str, Any]]) -> bool:
        """Attempts to acquire a lease and safely execute one job."""
        job = self.queue.acquire_lease(self.worker_id, self.assigned_agent)
        if not job:
            return False

        self._current_job = job
        stop_heartbeat = threading.Event()

        # Dedicated background heartbeat & renewal thread
        def renewal_loop():
            last_renewal = time.time()
            while not stop_heartbeat.is_set():
                time.sleep(self.heartbeat_interval_sec)
                if stop_heartbeat.is_set():
                    break
                
                # Check heartbeat
                alive = self.queue.heartbeat(self.worker_id, job.task_id, job.fencing_token)
                if not alive:
                    # Lease lost or stolen!
                    break

                # Renew lease periodically
                if time.time() - last_renewal >= self.lease_renewal_interval_sec:
                    renewed = self.queue.renew_lease(self.worker_id, job.task_id, job.fencing_token)
                    if renewed:
                        last_renewal = time.time()
                    else:
                        break

        self._renewal_thread = threading.Thread(target=renewal_loop, daemon=True)
        self._renewal_thread.start()

        try:
            # Execute dummy or real task handler
            result = job_handler(job)
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
