"""
MARU HQ Autonomous Orchestrator & Central Authority Subsystem
Phase 6.1.2 Internal Autonomy
Implements:
 - Final Decision & Authorization Authority (HQ Core)
 - End-to-End Autonomous Workflow Execution
 - Coordinated Multi-Agent Task Life-Cycle
 - Plan Verification, Job Enqueueing, Dependency Chaining & Worker Execution
 - HQ Revision Requests, Rejections, & Final Operational Approvals
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.hq.models import CanonicalJob, JobPriority, JobStatus
from src.hq.queue import HQJobQueue
from src.hq.worker import HQWorker, CancellationToken
from src.hq.manager import HQAIManager
from src.hq.memory import HQMemoryManager
from src.hq.router import HQModelRouter

@dataclass
class WorkflowExecutionReport:
    workflow_id: str
    goal: str
    status: str
    created_at: float
    completed_at: float
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    consolidated_output: Dict[str, Any]
    hq_decision: str
    notes: str

class HQOrchestrator:
    """Central Authority for MARU HQ Autonomous Workflows."""

    def __init__(self, queue: HQJobQueue,
                 manager: Optional[HQAIManager] = None,
                 memory: Optional[HQMemoryManager] = None,
                 router: Optional[HQModelRouter] = None):
        self.queue = queue
        self.memory = memory or HQMemoryManager()
        self.router = router or HQModelRouter()
        self.manager = manager or HQAIManager(router=self.router, memory=self.memory)

    def execute_autonomous_goal(self, goal: str, requested_by: str = "OWNER",
                                context: Optional[Dict[str, Any]] = None) -> WorkflowExecutionReport:
        """Executes full autonomous multi-agent workflow from goal to HQ approval."""
        workflow_id = f"WF-{int(time.time())}"
        start_time = time.time()

        # Step 1: HQ interprets & requests AI Manager decomposition
        subtasks = self.manager.decompose_task(goal, context)

        # Step 2: HQ Authorizes and enqueues jobs with dependency chaining
        enqueued_jobs: List[CanonicalJob] = []
        prev_task_id = None

        for idx, st in enumerate(subtasks):
            sub_id = st.get("subtask_id", f"SUB-{idx+1}")
            agent = st.get("assigned_agent", "EMP-L02")
            sub_goal = st.get("objective", goal)
            deps = [prev_task_id] if prev_task_id else []

            job = self.queue.enqueue(
                division="SPECIALIST_OPERATIONS",
                requested_by=f"HQ_ORCHESTRATOR:{requested_by}",
                goal=sub_goal,
                input_payload={"workflow_id": workflow_id, "subtask_id": sub_id, "context": context or {}},
                acceptance_criteria=["Verify factual truth", "Adhere to brand voice"],
                assigned_agent=agent,
                idempotency_key=f"{workflow_id}-{sub_id}",
                priority=JobPriority.HIGH,
                dependencies=deps
            )
            enqueued_jobs.append(job)
            prev_task_id = job.task_id

        # Step 3: Autonomous Workers execute jobs in dependency sequence
        results: List[Dict[str, Any]] = []
        for job in enqueued_jobs:
            worker = HQWorker(queue=self.queue, worker_id=f"WORKER-{job.assigned_agent}", assigned_agent=job.assigned_agent)
            
            def agent_handler(j: CanonicalJob, token: CancellationToken) -> Dict[str, Any]:
                token.check()
                # Query agent specific or organizational memory
                mems = self.memory.query(reader_agent_id=j.assigned_agent, limit=3)
                # Call model router for agent reasoning
                resp = self.router.route_task(
                    task_type="specialist_execution",
                    prompt=f"Execute task: {j.goal} with payload {j.input_payload}"
                )
                output_data = {
                    "agent": j.assigned_agent,
                    "task_id": j.task_id,
                    "goal": j.goal,
                    "execution_summary": resp.content,
                    "status": "SUCCESS"
                }
                # Store output to memory
                self.memory.store(
                    scope=f"AGENT:{j.assigned_agent}",
                    category="TASK_CONTEXT",
                    title=f"Result for {j.task_id}",
                    content=str(output_data),
                    tags=[j.assigned_agent, workflow_id],
                    provenance={"task_id": j.task_id, "agent": j.assigned_agent}
                )
                return output_data

            success = worker.execute_one_cycle(agent_handler)
            updated_j = self.queue.get_job(job.task_id)
            if success and updated_j:
                results.append({
                    "subtask_id": job.input_payload.get("subtask_id"),
                    "assigned_agent": job.assigned_agent,
                    "output": updated_j.result_payload,
                    "status": "SUCCESS"
                })
            else:
                results.append({
                    "subtask_id": job.input_payload.get("subtask_id"),
                    "assigned_agent": job.assigned_agent,
                    "output": {},
                    "error": updated_j.error_message if updated_j else "Execution failed",
                    "status": "FAILED"
                })

        # Step 4: AI Manager consolidates specialist outputs
        consolidation = self.manager.evaluate_and_consolidate(goal, results)

        # Step 5: HQ Core performs Final Evaluation & Approval
        all_passed = all(r.get("status") == "SUCCESS" for r in results)
        if all_passed and consolidation.ready_for_hq_approval:
            hq_decision = "APPROVED"
            workflow_status = "COMPLETED"
            notes = "Autonomous execution verified and formally approved by HQ Core."
        else:
            hq_decision = "REJECTED_REVISION_REQUIRED"
            workflow_status = "FAILED"
            notes = "One or more specialist tasks failed or did not meet acceptance criteria."

        # Record final organizational memory
        self.memory.store(
            scope="ORGANIZATIONAL",
            category="DECISION",
            title=f"HQ Decision for Workflow {workflow_id}",
            content=f"Goal: {goal} | Decision: {hq_decision} | Summary: {consolidation.consolidated_summary}",
            tags=["WORKFLOW", hq_decision],
            provenance={"workflow_id": workflow_id, "requested_by": requested_by}
        )

        return WorkflowExecutionReport(
            workflow_id=workflow_id,
            goal=goal,
            status=workflow_status,
            created_at=start_time,
            completed_at=time.time(),
            total_jobs=len(enqueued_jobs),
            completed_jobs=sum(1 for r in results if r.get("status") == "SUCCESS"),
            failed_jobs=sum(1 for r in results if r.get("status") != "SUCCESS"),
            consolidated_output={"results": results, "summary": consolidation.consolidated_summary},
            hq_decision=hq_decision,
            notes=notes
        )
