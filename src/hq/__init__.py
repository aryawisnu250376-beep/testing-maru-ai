"""
MARU HQ Core Package — Phase 6.1.2 Internal Autonomy
Exposes Canonical Engine:
 - Persistent Job Queue & Worker Framework
 - Cooperative Cancellation & Hard Timeouts
 - Internal Memory & Knowledge Subsystem
 - Multi-Provider Model Router & Fallback
 - AI Manager & Specialist Delegation
 - HQ Autonomous Orchestrator & Final Authority
 - Canonical Models, Statuses & Exceptions
"""

from src.hq.models import (
    CanonicalJob,
    JobStatus,
    JobPriority,
    JobBudget,
    IdempotencyConflictError,
    DependencyNotSatisfiedError,
    DependencyNotFoundError,
    DependencyLoopError,
    LeaseExpiredError,
    BudgetExceededError,
)

from src.hq.database import init_db, get_connection, DEFAULT_DB_PATH
from src.hq.queue import HQJobQueue
from src.hq.worker import HQWorker, CancellationToken
from src.hq.memory import HQMemoryManager, MemoryRecord, DEFAULT_MEMORY_DB
from src.hq.router import HQModelRouter, ModelResponse, ModelUsage
from src.hq.agents import ROSTER, AgentProfile, get_agent_profile
from src.hq.manager import HQAIManager, SubtaskResult, ConsolidatedPlanResult
from src.hq.orchestrator import HQOrchestrator, WorkflowExecutionReport

__all__ = [
    # Core Antrean & Worker
    "HQJobQueue",
    "HQWorker",
    "CancellationToken",
    "init_db",
    "get_connection",
    "DEFAULT_DB_PATH",

    # Models & Exceptions
    "CanonicalJob",
    "JobStatus",
    "JobPriority",
    "JobBudget",
    "IdempotencyConflictError",
    "DependencyNotSatisfiedError",
    "DependencyNotFoundError",
    "DependencyLoopError",
    "LeaseExpiredError",
    "BudgetExceededError",

    # Autonomous Subsystems Phase 6.1.2
    "HQMemoryManager",
    "MemoryRecord",
    "DEFAULT_MEMORY_DB",
    "HQModelRouter",
    "ModelResponse",
    "ModelUsage",
    "ROSTER",
    "AgentProfile",
    "get_agent_profile",
    "HQAIManager",
    "SubtaskResult",
    "ConsolidatedPlanResult",
    "HQOrchestrator",
    "WorkflowExecutionReport",
]
