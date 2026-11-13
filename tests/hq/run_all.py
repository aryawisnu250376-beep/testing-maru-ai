"""
MARU HQ Phase 6.1.1 Canonical Test Runner — Single Command Execution
Usage:
  python -m tests.hq.run_all
  or
  pytest tests/hq -v
"""

import unittest
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.hq.test_job_engine import TestHQCorePhase611

def run_all():
    print("======================================================================")
    print("MARU HQ — PHASE 6.1.1 CANONICAL TEST SUITE (26 ACCEPTANCE CHECKS)")
    print("======================================================================\n")

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestHQCorePhase611)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n======================================================================")
    print(f"TESTS RUN: {result.testsRun}")
    print(f"FAILURES: {len(result.failures)}")
    print(f"ERRORS: {len(result.errors)}")
    print(f"RESULT: {'PASS (100% SUCCESS)' if result.wasSuccessful() else 'FAIL'}")
    print("======================================================================")

    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == '__main__':
    run_all()
