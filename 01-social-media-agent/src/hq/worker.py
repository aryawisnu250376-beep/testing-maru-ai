"""
MARU HQ Worker Framework — Phase 6.1.3 Remediation
Priority B: Process Isolation & True Hard Timeout Guardian
Implements:
 - Genuine OS Process-Level Isolation via multiprocessing (or cooperative thread where appropriate)
 - Hard Timeout Guardian with OS SIGTERM / SIGKILL Process Termination
 - Inter-Process Result & Error Serialization via Queue / Pipe
 - Safe Process Reaping (Clean Exit & Zombie Prevention)
 - Fencing Token Invalidation upon Timeout
 - Instant Heartbeat Termination
 - Automatic Startup Stale Recovery
"""

import time
import uuid
import os
import signal
import threading
import multiprocessing
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

def _isolated_process_runner(job_dict: Dict[str, Any], handler_code_or_callable: Any, result_queue: Any):
    """Entry point for isolated child process execution."""
    try:
        # Reconstruct CanonicalJob from dict representation to avoid unpicklable DB connections
        job = CanonicalJob.from_dict(job_dict)
        # In isolated process, execute handler
        res = handler_code_or_callable(job, CancellationToken(threading.Event()))
        result_queue.put({"success": True, "result": res})
    except Exception as e:
        result_queue.put({"success": False, "error": str(e)})

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

        if auto_recover_startup:
            self.queue.recover_stale_jobs(actor=f"STARTUP_{self.worker_id}")

    def execute_one_cycle(self, job_handler: Callable[[CanonicalJob, CancellationToken], Dict[str, Any]],
                          use_process_isolation: Optional[bool] = None) -> bool:
        """
        Attempts to acquire a lease and safely execute one job.
        If use_process_isolation=True, runs in an OS child process with SIGTERM/SIGKILL hard termination.
        Otherwise runs in isolated guardian thread with cooperative cancellation token.
        """
        job = self.queue.acquire_lease(self.worker_id, self.assigned_agent)
        if not job:
            return False

        self._current_job = job
        stop_heartbeat = threading.Event()
        cancel_token = CancellationToken(stop_heartbeat)

        # Heartbeat & renewal thread
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
        start_time = time.time()

        # Default: Process isolation if not explicitly set to False and handler is picklable
        if use_process_isolation is None:
            # Check if job handler is a module-level picklable function
            import inspect
            is_nested = "<locals>" in getattr(job_handler, "__qualname__", "")
            use_process_isolation = not is_nested

        if use_process_isolation:
            # PRIORITY B: True OS Process Isolation for Hard Timeout
            import inspect
            is_nested = "<locals>" in getattr(job_handler, "__qualname__", "")
            if is_nested:
                err_msg = "Process Isolation Failure: Job handler is not a picklable top-level function. Silent thread downgrade prohibited for hard timeout jobs."
                stop_heartbeat.set()
                if self._renewal_thread.is_alive():
                    self._renewal_thread.join(timeout=1.0)
                self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, err_msg)
                self._current_job = None
                return False

            ipc_queue = multiprocessing.Queue()
            proc = multiprocessing.Process(
                target=_isolated_process_runner,
                args=(job.to_dict(), job_handler, ipc_queue),
                daemon=True
            )
            proc.start()
            poll_interval = 0.25
            while proc.is_alive():
                proc.join(timeout=poll_interval)
                duration = time.time() - start_time
                if duration >= max_duration:
                    break
                if stop_heartbeat.is_set():
                    # Lease expired, job cancelled, or worker stopped! Terminate child process immediately!
                    break
            duration = time.time() - start_time

            # Stop heartbeat thread
            stop_heartbeat.set()
            if self._renewal_thread.is_alive():
                self._renewal_thread.join(timeout=1.0)

            if proc.is_alive():
                # Hard timeout reached! Terminate and kill child process
                proc.terminate()
                proc.join(timeout=1.0)
                if proc.is_alive():
                    try:
                        sig_kill = getattr(signal, "SIGKILL", signal.SIGTERM)
                        os.kill(proc.pid, sig_kill)
                        proc.join(timeout=1.0)
                    except Exception:
                        pass

                if duration >= max_duration:
                    err_msg = f"Job exceeded max duration budget: {duration:.2f}s > {max_duration}s (Process Terminated via SIGTERM/SIGKILL)"
                else:
                    err_msg = f"Job execution aborted: lease lost, cancelled, or heartbeat failed (Process Terminated via SIGTERM/SIGKILL)"
                self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, err_msg)
                self._current_job = None
                return False

            # Process finished within timeout
            if not ipc_queue.empty():
                payload = ipc_queue.get_nowait()
                if payload.get("success"):
                    completed = self.queue.complete_job(self.worker_id, job.task_id, job.fencing_token, payload.get("result", {}))
                    self._current_job = None
                    return completed
                else:
                    self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, payload.get("error", "Process handler error"))
                    self._current_job = None
                    return False
            else:
                self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, f"Process exited with exitcode {proc.exitcode}")
                self._current_job = None
                return False

        else:
            # Guardian Thread with Cooperative Cancellation Token
            handler_result: Dict[str, Any] = {}
            handler_error: Optional[Exception] = None
            handler_done = threading.Event()

            def thread_runner():
                nonlocal handler_result, handler_error
                try:
                    res = job_handler(job, cancel_token)
                    cancel_token.check()
                    handler_result = res
                except Exception as e:
                    handler_error = e
                finally:
                    handler_done.set()

            worker_thread = threading.Thread(target=thread_runner, daemon=True)
            worker_thread.start()

            finished_in_time = handler_done.wait(timeout=max_duration)
            duration = time.time() - start_time

            stop_heartbeat.set()
            if self._renewal_thread.is_alive():
                self._renewal_thread.join(timeout=1.0)

            if not finished_in_time:
                err_msg = f"Job exceeded max duration budget: {duration:.2f}s > {max_duration}s (Cooperative Timeout Reached)"
                self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, err_msg)
                self._current_job = None
                return False

            if handler_error:
                self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token, str(handler_error))
                self._current_job = None
                return False

            completed = self.queue.complete_job(self.worker_id, job.task_id, job.fencing_token, handler_result)
            self._current_job = None
            return completed
