# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_build_recognition_pairs
import importlib
import sys
import types
import unittest


def load_builder():
    """Import the crop builder without loading the real OCR model.

    Only the core.ocr_pipeline entry is swapped and restored. patch.dict on
    sys.modules would also drop every module imported meanwhile (cv2's
    submodules included) and break the next test module that imports cv2."""
    fake_pipeline = types.ModuleType("core.ocr_pipeline")
    fake_pipeline.ocr = None
    fake_pipeline._filter_low_confidence = lambda *args, **kwargs: None
    fake_pipeline._group_detection_records = lambda *args, **kwargs: None
    fake_pipeline.line_member_bounds = lambda *args, **kwargs: None
    missing = object()
    real_pipeline = sys.modules.get("core.ocr_pipeline", missing)
    sys.modules["core.ocr_pipeline"] = fake_pipeline
    try:
        sys.modules.pop("evaluators.build_recognition_dataset", None)
        return importlib.import_module("evaluators.build_recognition_dataset")
    finally:
        if real_pipeline is missing:
            sys.modules.pop("core.ocr_pipeline", None)
        else:
            sys.modules["core.ocr_pipeline"] = real_pipeline


builder = load_builder()


def detected(*texts):
    """Detected lines as the builder sees them: (x0, y0, x1, y1, ocr_text),
    top to bottom."""
    return [(0, 10 * i, 100, 10 * i + 8, text) for i, text in enumerate(texts)]


class OneBlockPairingIsUnchangedTests(unittest.TestCase):
    def test_equal_counts_pair_by_position(self):
        pairs, reason = builder._pair_lines(
            ["int a;\nint b;"], detected("int a;", "garbled"))
        self.assertIsNone(reason)
        self.assertEqual(pairs, [("int a;", 0), ("int b;", 1)])

    def test_unequal_counts_use_alignment_and_the_coverage_gate(self):
        pairs, reason = builder._pair_lines(
            ["int a;\nint b;\nint c;"], detected("int a;", "noise xyz", "int b;", "int c;"))
        self.assertIsNone(reason)
        self.assertEqual(pairs, [("int a;", 0), ("int b;", 2), ("int c;", 3)])

        pairs, reason = builder._pair_lines(
            ["int alpha;\nint beta;\nint gamma;"], detected("zzzz", "qqqq"))
        self.assertIsNone(pairs)
        self.assertIn("line count mismatch", reason)


class SplitPagePairingTests(unittest.TestCase):
    # Page order: Program 2 is on the left/top, Program 1 below it. The teacher
    # put them in the other tab order, so blocks must not be read in order.
    PAGE = detected(
        "int is_even(int n) {",
        "return n % 2 == 0;",
        "}",
        "int max_of(int a, int b) {",
        "return a > b ? a : b;",
        "}",
    )

    def test_each_block_is_aligned_on_its_own_whatever_the_tab_order(self):
        blocks = [
            "int max_of(int a, int b) {\nreturn a > b ? a : b;\n}",
            "int is_even(int n) {\nreturn n % 2 == 0;\n}",
        ]
        pairs, reason = builder._pair_lines(blocks, self.PAGE)
        self.assertIsNone(reason)
        by_line = dict((d, text) for text, d in pairs)
        self.assertEqual(by_line[0], "int is_even(int n) {")
        self.assertEqual(by_line[1], "return n % 2 == 0;")
        self.assertEqual(by_line[3], "int max_of(int a, int b) {")
        self.assertEqual(by_line[4], "return a > b ? a : b;")
        # Pairs come back in page order, so crop numbering follows the page.
        self.assertEqual([d for _, d in pairs], sorted(d for _, d in pairs))

    def test_a_line_claimed_by_two_blocks_is_dropped_not_guessed(self):
        # Both programs end with "}": each block claims a closing-brace line,
        # and any line both claim must be dropped from both.
        blocks = [
            "int max_of(int a, int b) {\nreturn a > b ? a : b;\n}",
            "int is_even(int n) {\nreturn n % 2 == 0;\n}",
        ]
        pairs, _ = builder._pair_lines(blocks, self.PAGE)
        claimed = [d for _, d in pairs]
        self.assertEqual(len(claimed), len(set(claimed)))

    def test_a_heading_the_teacher_removed_only_costs_its_own_crop(self):
        page = detected("Question 1:", "int a = 1;", "int b = 2;", "Question 2:", "int c = 3;")
        pairs, reason = builder._pair_lines(["int a = 1;\nint b = 2;", "int c = 3;"], page)
        self.assertIsNone(reason)
        self.assertEqual(pairs, [("int a = 1;", 1), ("int b = 2;", 2), ("int c = 3;", 4)])

    def test_split_page_below_coverage_is_skipped_with_a_reason(self):
        pairs, reason = builder._pair_lines(
            ["int alpha;\nint beta;", "int gamma;\nint delta;"], detected("zzzz", "qqqq", "wwww"))
        self.assertIsNone(pairs)
        self.assertIn("split page (2 programs)", reason)


if __name__ == "__main__":
    unittest.main()
