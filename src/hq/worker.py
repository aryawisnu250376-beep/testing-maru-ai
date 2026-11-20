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

import json
import time
import uuid
import threading
import multiprocessing
from pickle import PicklingError
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

MAX_IPC_BYTES = 4 * 1024 * 1024


def _isolated_process_runner(job_dict: Dict[str, Any], handler: Any, sender: Any):
    """Only a bounded JSON result crosses the process boundary."""
    with sender:
        try:
            job = CanonicalJob.from_dict(job_dict)
            result = handler(job, CancellationToken(threading.Event()))
            if not isinstance(result, dict):
                raise ValueError("Expected job result object")
            payload = json.dumps({"success": True, "result": result}, allow_nan=False).encode()
            if len(payload) > MAX_IPC_BYTES:
                raise ValueError("Job result exceeds IPC limit")
        except Exception as exc:
            payload = json.dumps({"success": False, "error": f"Job handler failed: {type(exc).__name__}"}).encode()
        sender.send_bytes(payload)


class HQWorker:
    def __init__(self, queue: HQJobQueue, worker_id: Optional[str] = None,
                 assigned_agent: Optional[str] = None, heartbeat_interval_sec: float = 5.0,
                 lease_renewal_interval_sec: float = 10.0, auto_recover_startup: bool = True,
                 process_start_method: Optional[str] = None):
        self.queue = queue
        self.process_context = multiprocessing.get_context(process_start_method)
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
                          use_process_isolation: Optional[bool] = None,
                          shutdown_event: Optional[threading.Event] = None) -> bool:
        """
        Attempts to acquire a lease and safely execute one job.
        If use_process_isolation=True, runs in an OS child process with SIGTERM/SIGKILL hard termination.
        Otherwise runs in isolated guardian thread with cooperative cancellation token.
        """
        if shutdown_event and shutdown_event.is_set():
            return False
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
        start_time = time.monotonic()

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

            receiver, sender = self.process_context.Pipe(duplex=False)
            proc = self.process_context.Process(
                target=_isolated_process_runner,
                args=(job.to_dict(), job_handler, sender), daemon=True,
            )
            payload = None
            err = None
            read_error = None
            reader = None
            received = threading.Event()
            started = False
            deadline = start_time + max_duration

            def read_result():
                nonlocal payload, read_error
                try:
                    payload = json.loads(receiver.recv_bytes(MAX_IPC_BYTES))
                    if not isinstance(payload, dict) or payload.get("success") not in (True, False):
                        raise ValueError("Invalid result envelope")
                except (OSError, EOFError, ValueError, RecursionError):
                    payload = None
                    read_error = "Process exited without a valid result"
                finally:
                    received.set()

            try:
                proc.start()
                started = True
                sender.close()
                # Drain while the child is alive. A partial frame cannot block this supervisor.
                reader = threading.Thread(target=read_result, daemon=True)
                reader.start()
                while not stop_heartbeat.is_set():
                    if shutdown_event and shutdown_event.is_set():
                        err = "Job interrupted by worker shutdown"
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        err = "Job exceeded max duration budget (isolated process)"
                        break
                    if received.wait(min(0.1, remaining)):
                        err = read_error
                        break
                if stop_heartbeat.is_set():
                    err = "Job execution aborted: lease lost, cancelled, or heartbeat failed"
                if payload and not err and time.monotonic() > deadline:
                    err = "Job exceeded max duration budget (isolated process)"
            except (OSError, ValueError, TypeError, EOFError, AttributeError, PicklingError) as exc:
                err = f"Process isolation failed: {type(exc).__name__}"
            finally:
                stop_heartbeat.set()
                sender.close()
                if started:
                    proc.join(timeout=0.25 if payload and not err else 0)
                    if proc.is_alive():
                        proc.terminate()
                        proc.join(timeout=1.0)
                    if proc.is_alive():
                        proc.kill()
                        proc.join(timeout=1.0)
                if not started or not proc.is_alive():
                    proc.close()
                if reader:
                    reader.join(timeout=0.25)
                receiver.close()
                self._renewal_thread.join(timeout=1.0)
                self._current_job = None
            if payload and not err and payload.get("success"):
                return self.queue.complete_job(self.worker_id, job.task_id, job.fencing_token, payload.get("result", {}))
            self.queue.fail_job(self.worker_id, job.task_id, job.fencing_token,
                                err or (payload or {}).get("error", "Process handler error"))
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

            deadline = start_time + max_duration
            while not handler_done.is_set() and not stop_heartbeat.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0 or (shutdown_event and shutdown_event.is_set()):
                    break
                handler_done.wait(min(0.1, remaining))
            finished_in_time = handler_done.is_set()
            duration = time.monotonic() - start_time

            stop_heartbeat.set()
            if self._renewal_thread.is_alive():
                self._renewal_thread.join(timeout=1.0)

            if not finished_in_time:
                worker_thread.join(timeout=0.5)  # Grace period for cooperative cleanup only.
                err_msg = (f"Job exceeded max duration budget: {duration:.2f}s (cooperative handler)"
                           if duration >= max_duration else "Job execution cancelled before completion")
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
