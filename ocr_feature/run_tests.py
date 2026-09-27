"""Run every test in tests/, from ocr_feature/ so the tests can import the
source modules.

    .venv/bin/python run_tests.py               # all tests
    .venv/bin/python run_tests.py -v            # verbose
    .venv/bin/python -m tests.test_evaluation   # one test file
"""

import sys
import unittest


def main() -> int:
    verbosity = 2 if "-v" in sys.argv else 1
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", top_level_dir=".")
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
