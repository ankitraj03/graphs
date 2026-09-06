"""Test runner script for the graphs project.

Discovers and runs all unit and integration tests with detailed output.
"""

from __future__ import annotations

import sys
import time
import unittest


def main() -> int:
    print("=" * 70)
    print("Running graphs test suite...")
    print("=" * 70)

    start = time.perf_counter()
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    duration = time.perf_counter() - start

    print("=" * 70)
    print(f"Executed {result.testsRun} test cases in {duration:.3f} seconds.")
    if result.wasSuccessful():
        print("ALL TESTS PASSED SUCCESSFULLY! [OK]")
        return 0
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
