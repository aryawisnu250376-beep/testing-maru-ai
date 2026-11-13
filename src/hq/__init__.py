"""
MARU HQ Core Package — Phase 6.1.1 Hardened
Exposes HQJobQueue, HQWorker, CancellationToken, CanonicalJob, JobStatus, and Exceptions
"""

from src.hq.models import (
    CanonicalJob,
    JobStatus,
    JobPriority,
    JobBudget,
    IdempotencyConflictError,
    DependencyNotSatisfiedError,
    DependencyLoopError,
    LeaseExpiredError,
    BudgetExceededError,
)
from src.hq.database import init_db, get_connection, DEFAULT_DB_PATH
from src.hq.queue import HQJobQueue
from src.hq.worker import HQWorker, CancellationToken

__all__ = [
    "CanonicalJob",
    "JobStatus",
    "JobPriority",
    "JobBudget",
    "IdempotencyConflictError",
    "DependencyNotSatisfiedError",
    "DependencyLoopError",
    "LeaseExpiredError",
    "BudgetExceededError",
    "init_db",
    "get_connection",
    "DEFAULT_DB_PATH",
    "HQJobQueue",
    "HQWorker",
    "CancellationToken",
]
