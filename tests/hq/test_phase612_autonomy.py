"""
MARU HQ Phase 6.1.2 Internal Autonomy Test Suite
Validates:
 Category A: Job Engine Hardening Extensions (Dependency Non-Existence, Hard Timeouts, Cooperative vs Non-cooperative isolation)
 Category B: Internal Subsystem Integration (HQ Core -> AI Manager -> Router -> Memory)
 Category C: Autonomous Multi-Agent Workflows & Decomposition
 Category D: Memory Persistence & Scoped Permissions Across Restarts
 Category E: Resilience & Offline Deterministic Fallbacks
 Category F: End-to-End Operational Workflow (No external platforms needed)
"""

import unittest
import tempfile
import time
import shutil
from pathlib import Path

from src.hq import (
    HQJobQueue,
    HQWorker,
    HQMemoryManager,
    HQModelRouter,
    HQAIManager,
    HQOrchestrator,
    CanonicalJob,
    JobPriority,
    JobStatus,
    JobBudget,
    CancellationToken,
    DependencyNotFoundError,
    DependencyLoopError,
    BudgetExceededError
)

class TestHQInternalAutonomyPhase612(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_hq_core.db"
        self.mem_db_path = Path(self.test_dir) / "test_hq_mem.db"
        self.queue = HQJobQueue(self.db_path)
        self.memory = HQMemoryManager(self.mem_db_path)
        self.router = HQModelRouter()
        self.ai_manager = HQAIManager(router=self.router, memory=self.memory)
        self.orchestrator = HQOrchestrator(
            queue=self.queue,
            manager=self.ai_manager,
            memory=self.memory,
            router=self.router
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ------------------ CATEGORY A: JOB ENGINE EXTENSIONS ------------------

    def test_27_dependency_non_existent_rejected_on_enqueue(self):
        """Job with nonexistent dependency must be rejected immediately at enqueue time."""
        with self.assertRaises(DependencyNotFoundError):
            self.queue.enqueue(
                division="CREATIVE",
                requested_by="TESTER",
                goal="Draft video script",
                input_payload={"topic": "viral hooks"},
                acceptance_criteria=[],
                assigned_agent="EMP-L02",
                idempotency_key="IDEMPO-NONEXISTENT-01",
                dependencies=["JOB-DOES-NOT-EXIST-999"]
            )

    def test_28_dependency_loop_rejected_on_enqueue(self):
        """Self loop or direct loop must be rejected at registration."""
        with self.assertRaises(DependencyLoopError):
            self.queue.enqueue(
                division="CREATIVE",
                requested_by="TESTER",
                goal="Self dependent task",
                input_payload={},
                acceptance_criteria=[],
                assigned_agent="EMP-L02",
                idempotency_key="IDEMPO-LOOP-01",
                parent_task_id="JOB-PARENT-1",
                dependencies=["JOB-PARENT-1"]
            )

    # ------------------ CATEGORY B & D: MEMORY & PERSISTENCE ------------------

    def test_29_memory_store_and_scoped_retrieval(self):
        """Memory stores organizational knowledge and respects agent scopes."""
        # 1. Store organizational memory
        m1 = self.memory.store(
            scope="ORGANIZATIONAL",
            category="POLICY",
            title="Brand Guideline",
            content="Official MARU character must wear retro pixel art sunglasses.",
            tags=["BRAND", "AVATAR"]
        )
        self.assertIsNotNone(m1.memory_id)

        # 2. Store agent-specific memory
        m2 = self.memory.store(
            scope="AGENT:EMP-L02",
            category="TASK_CONTEXT",
            title="Hermes Draft Notes",
            content="Hook: 3 psychology tricks to double your video comments.",
            tags=["HOOK", "CREATIVE"]
        )

        # Query as EMP-L02: should see organizational AND own agent memory
        hermes_view = self.memory.query(reader_agent_id="EMP-L02")
        titles_hermes = [m.title for m in hermes_view]
        self.assertIn("Brand Guideline", titles_hermes)
        self.assertIn("Hermes Draft Notes", titles_hermes)

        # Query as EMP-L05 (Ardi): should see organizational, but NOT EMP-L02 private memory
        ardi_view = self.memory.query(reader_agent_id="EMP-L05")
        titles_ardi = [m.title for m in ardi_view]
        self.assertIn("Brand Guideline", titles_ardi)
        self.assertNotIn("Hermes Draft Notes", titles_ardi)

    def test_30_memory_persistence_across_restart(self):
        """Memory survives manager re-instantiation and restart."""
        self.memory.store(
            scope="ORGANIZATIONAL",
            category="DECISION",
            title="Strategic Priority 2026",
            content="Focus purely on Internal Autonomy before external platforms."
        )

        # Re-initialize Memory Manager with same database file
        new_mem_manager = HQMemoryManager(self.mem_db_path)
        results = new_mem_manager.query(scope="ORGANIZATIONAL", keyword="Internal Autonomy")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Strategic Priority 2026")

    # ------------------ CATEGORY B & E: MODEL ROUTER & FALLBACK ------------------

    def test_31_model_router_offline_deterministic_fallback(self):
        """Router guarantees intelligent, deterministic output when offline without throwing unhandled errors."""
        res = self.router.route_task(
            task_type="research",
            prompt="Analyze audience retention psychology in 60-second video format."
        )
        self.assertIsNotNone(res.content)
        self.assertTrue(res.is_fallback)
        self.assertGreater(res.usage.total_tokens, 0)
        self.assertIn("findings", res.content.lower())

    # ------------------ CATEGORY C & F: AUTONOMOUS WORKFLOW & ORCHESTRATION ------------------

    def test_32_ai_manager_task_decomposition(self):
        """AI Manager decomposes a high-level operational goal into specialist subtasks."""
        subtasks = self.ai_manager.decompose_task(
            goal="Produce viral educational episode about social media cognitive bias"
        )
        self.assertGreaterEqual(len(subtasks), 2)
        agents = [s.get("assigned_agent") for s in subtasks]
        # Must involve specialists
        self.assertTrue(any(a.startswith("EMP-") for a in agents))

    def test_33_end_to_end_autonomous_workflow_without_external_platforms(self):
        """Complete workflow: Owner Goal -> HQ Plan -> Specialists Execution -> AI Manager Consolidation -> HQ Decision."""
        report = self.orchestrator.execute_autonomous_goal(
            goal="Internal Factual Analysis: Why Cognitive Framing Hook Works on Audiences",
            requested_by="HQ_OWNER"
        )

        self.assertEqual(report.status, "COMPLETED")
        self.assertEqual(report.hq_decision, "APPROVED")
        self.assertGreater(report.total_jobs, 0)
        self.assertEqual(report.completed_jobs, report.total_jobs)
        self.assertEqual(report.failed_jobs, 0)
        self.assertIn("results", report.consolidated_output)

        # Verify that HQ decision is archived in organizational persistent memory
        mem_decision = self.memory.query(scope="ORGANIZATIONAL", category="DECISION", limit=1)
        self.assertEqual(len(mem_decision), 1)
        self.assertIn(report.workflow_id, mem_decision[0].title)

if __name__ == "__main__":
    unittest.main()
