"""Checks for development-only evaluation and preservation of repeated text."""
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluators import evaluate_continuation_development as evaluator


class ContinuationEvaluationTests(unittest.TestCase):
    def test_fixtures_are_frozen_and_replay_matches_live_extraction(self):
        annotation = json.loads((evaluator.FIXTURES / "writerX_development_annotations.json").read_text())
        result = evaluator.evaluate()
        self.assertEqual({p["example"] for p in result["pages"]}, {1, 2, 4, 5, 6, 8, 9, 11})
        for page, measured in zip(annotation["pages"], result["pages"]):
            fixture = evaluator.FIXTURES / f"writerX_page{page['example']:02d}_detections.json"
            self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), page["fixture_sha256"])
            self.assertEqual([line.strip() for line in page["live_raw_text"].splitlines() if line.strip()],
                             measured["actual_text_rows"])
            self.assertTrue(measured["all_detections_preserved"])

    def test_pairwise_metric_counts_misordered_and_missing_ids(self):
        self.assertEqual(evaluator.pairwise_order_accuracy([0, 1, 2], [0, 1, 2]), 1)
        self.assertEqual(evaluator.pairwise_order_accuracy([0, 1, 2], [2, 1, 0]), 0)
        self.assertAlmostEqual(evaluator.pairwise_order_accuracy([0, 1, 2], [0, 2, 1]), 2/3)
        self.assertAlmostEqual(evaluator.pairwise_order_accuracy([0, 1, 2], [0, 2]), 1/3)
        with self.assertRaises(ValueError):
            evaluator.pairwise_order_accuracy([0, 1], [0, 0])

    def test_reserved_page_is_rejected_before_fixture_is_opened(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "writerX_development_annotations.json").write_text(json.dumps(
                {"split": "development", "pages": [{"example": 3}]}))
            with patch.object(evaluator, "FIXTURES", root):
                with self.assertRaisesRegex(ValueError, "Reserved example 3"):
                    evaluator.evaluate()

    def test_repeated_braces_keep_distinct_detection_ids(self):
        records = [{"text": "}", "score": .9, "box": [10, y, 30, y+10]}
                   for y in (0, 40, 80)]
        rows, _ = evaluator.replay(records)
        self.assertEqual([i for row in rows for i in row], [0, 1, 2])

    def test_identical_payload_duplicates_are_not_collapsed(self):
        records = [{"text": "}", "score": .9, "box": [10, 0, 30, 10]} for _ in range(2)]
        rows, _ = evaluator.replay(records)
        self.assertEqual(sorted(i for row in rows for i in row), [0, 1])


class LocalContinuationAcceptanceTests(unittest.TestCase):
    def assert_intended_order(self, example):
        page = next(p for p in evaluator.evaluate()["pages"] if p["example"] == example)
        self.assertEqual(page["actual_order"], page["expected_order"])

    def test_example05_finishes_question_one_before_question_two(self):
        self.assert_intended_order(5)

    def test_example06_finishes_each_loop_with_its_own_continuation(self):
        self.assert_intended_order(6)

    def test_example08_keeps_local_continuations_without_headings(self):
        self.assert_intended_order(8)


if __name__ == "__main__":
    unittest.main()
