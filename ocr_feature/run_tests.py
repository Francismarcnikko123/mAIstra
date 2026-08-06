"""Run the whole test suite from tests/.

    .venv/bin/python run_tests.py            # all tests
    .venv/bin/python run_tests.py -v         # verbose

Tests live in tests/ but import the source modules (evaluation, ocr_pipeline,
...) as top-level names, so they must be run with ocr_feature/ as the working
directory / top-level dir. This runner does exactly that. To run one test
module directly instead:

    .venv/bin/python -m tests.test_evaluation
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
