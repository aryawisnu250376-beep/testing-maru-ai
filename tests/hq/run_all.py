"""
MARU HQ Comprehensive Canonical Test Runner
Phase 6.1.1 (26 Checks) + Phase 6.1.2 Internal Autonomy (7 Checks) = 33 Total Checks
Usage:
  python -m tests.hq.run_all
"""

import unittest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.hq.test_job_engine import TestHQCorePhase611
from tests.hq.test_phase612_autonomy import TestHQInternalAutonomyPhase612

def run_all():
    print("======================================================================")
    print("MARU HQ — FULL CANONICAL TEST SUITE (PHASE 6.1.1 + PHASE 6.1.2)")
    print("======================================================================\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestHQCorePhase611))
    suite.addTests(loader.loadTestsFromTestCase(TestHQInternalAutonomyPhase612))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n======================================================================")
    print(f"TOTAL TESTS RUN: {result.testsRun}")
    print(f"FAILURES: {len(result.failures)}")
    print(f"ERRORS: {len(result.errors)}")
    print(f"FINAL RESULT: {'PASS (100% SUCCESS)' if result.wasSuccessful() else 'FAIL'}")
    print("======================================================================")

    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == '__main__':
    run_all()
