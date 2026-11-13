"""
MARU HQ Core Models — Phase 6.1.1 Hardened
Defines Canonical Job Schema, Exceptions, Activity States, Priorities, and Transitions
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional
import json
import time

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"

class JobPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused with a different payload or goal."""
    pass

class DependencyNotSatisfiedError(Exception):
    """Raised when a job's dependencies are not yet completed."""
    pass

class DependencyNotFoundError(Exception):
    """Raised when a dependency task_id does not exist."""
    pass

class DependencyLoopError(Exception):
    """Raised when circular or self-dependencies are detected."""
    pass

class LeaseExpiredError(Exception):
    """Raised when an operation requires an active lease but the lease has expired."""
    pass

class BudgetExceededError(Exception):
    """Raised when a job execution exceeds its configured budget constraints."""
    pass

@dataclass
class JobBudget:
    max_cost_idr: int = 10000
    max_tokens: int = 8000
    max_duration_sec: int = 300

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobBudget":
        if not data:
            return cls()
        return cls(
            max_cost_idr=int(data.get("max_cost_idr", 10000)),
            max_tokens=int(data.get("max_tokens", 8000)),
            max_duration_sec=int(data.get("max_duration_sec", 300))
        )

@dataclass
class CanonicalJob:
    task_id: str
    correlation_id: str
    division: str
    requested_by: str
    goal: str
    input_payload: Dict[str, Any]
    acceptance_criteria: List[str]
    assigned_agent: str
    idempotency_key: str
    payload_hash: str
    parent_task_id: Optional[str] = None
    priority: int = JobPriority.NORMAL.value
    status: str = JobStatus.QUEUED.value
    dependencies: List[str] = field(default_factory=list)
    budget: JobBudget = field(default_factory=JobBudget)
    attempts: int = 0
    max_attempts: int = 3
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[float] = None
    fencing_token: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["budget"] = self.budget.to_dict()
        return res

    @classmethod
    def from_row(cls, row: tuple) -> "CanonicalJob":
        return cls(
            task_id=row[0],
            correlation_id=row[1],
            parent_task_id=row[2],
            division=row[3],
            requested_by=row[4],
            goal=row[5],
            input_payload=json.loads(row[6]) if row[6] else {},
            acceptance_criteria=json.loads(row[7]) if row[7] else [],
            priority=int(row[8]),
            status=row[9],
            assigned_agent=row[10],
            dependencies=json.loads(row[11]) if row[11] else [],
            budget=JobBudget.from_dict(json.loads(row[12])) if row[12] else JobBudget(),
            attempts=int(row[13]),
            max_attempts=int(row[14]),
            lease_owner=row[15],
            lease_expires_at=float(row[16]) if row[16] is not None else None,
            fencing_token=int(row[17]),
            idempotency_key=row[18],
            payload_hash=row[19] if len(row) > 23 else "",
            created_at=float(row[20] if len(row) > 23 else row[19]),
            updated_at=float(row[21] if len(row) > 23 else row[20]),
            result_payload=json.loads(row[22] if len(row) > 23 else row[21]) if (row[22 if len(row) > 23 else 21]) else None,
            error_message=row[23 if len(row) > 23 else 22]
        )
