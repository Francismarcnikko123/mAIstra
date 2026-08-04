import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PIPELINE_PATH = Path(__file__).with_name("ocr_pipeline.py")


def load_pipeline_without_models():
    """Load the grouping helpers without importing OCR runtime dependencies."""
    cv2 = types.ModuleType("cv2")
    numpy = types.ModuleType("numpy")
    paddleocr = types.ModuleType("paddleocr")
    preprocess = types.ModuleType("preprocess")
    c_code_cleanup = types.ModuleType("c_code_cleanup")

    class StubPaddleOCR:
        def __init__(self, **_kwargs):
            pass

    paddleocr.PaddleOCR = StubPaddleOCR
    preprocess.preprocess_image = lambda **_kwargs: ""
    c_code_cleanup.clean_c_code = lambda text: text

    module_name = "ocr_pipeline_grouping_test_module"
    spec = importlib.util.spec_from_file_location(module_name, PIPELINE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "cv2": cv2,
        "numpy": numpy,
        "paddleocr": paddleocr,
        "preprocess": preprocess,
        "c_code_cleanup": c_code_cleanup,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


def box(x, y_center):
    return [x, y_center - 5, x + 10, y_center + 5]


class GroupIntoReadingOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    def group_lines(self, texts, boxes, scores=None):
        if scores is None:
            scores = [0.9] * len(texts)
        return self.pipeline._group_into_reading_order(texts, scores, boxes)

    def group_texts(self, texts, boxes, scores=None):
        lines = self.group_lines(texts, boxes, scores)
        return [[text for text, _score in line] for line in lines]

    def test_does_not_merge_next_line_after_running_mean_drift(self):
        lines = self.group_texts(
            ["a", "b", "c", "next"],
            [box(0, 10), box(20, 11), box(40, 12), box(0, 17)],
        )

        self.assertEqual(lines, [["a", "b", "c"], ["next"]])

    def test_keeps_a_sloped_handwritten_line_together(self):
        lines = self.group_texts(
            ["a", "b", "c"],
            [box(0, 10), box(20, 14), box(40, 18)],
        )

        self.assertEqual(lines, [["a", "b", "c"]])

    def test_keeps_a_four_fragment_slope_together(self):
        lines = self.group_texts(
            ["a", "b", "c", "d"],
            [box(0, 10), box(20, 14), box(40, 18), box(60, 22)],
        )

        self.assertEqual(lines, [["a", "b", "c", "d"]])

    def test_rejects_an_indented_next_row_after_a_shallow_slope(self):
        lines = self.group_texts(
            ["a", "b", "c", "next"],
            [box(0, 10), box(20, 11), box(40, 12), box(80, 18)],
        )

        self.assertEqual(lines, [["a", "b", "c"], ["next"]])

    def test_repeated_x_positions_anchor_prediction_to_first_member(self):
        lines = self.group_texts(
            ["a", "b", "c", "next"],
            [box(0, 10), box(0, 11), box(0, 16), box(0, 17)],
        )

        self.assertEqual(lines, [["a", "b", "c"], ["next"]])

    def test_exact_vertical_tolerance_boundary_stays_on_the_line(self):
        lines = self.group_texts(["a", "b"], [box(0, 10), box(20, 16)])

        self.assertEqual(lines, [["a", "b"]])

    def test_accepts_a_finite_box_centered_at_zero(self):
        lines = self.group_texts(["a", "b"], [box(0, 0), box(20, 0)])

        self.assertEqual(lines, [["a", "b"]])

    def test_sorts_members_left_to_right_within_a_line(self):
        lines = self.group_texts(
            ["right", "left", "middle"],
            [box(50, 10), box(0, 10), box(25, 10)],
        )

        self.assertEqual(lines, [["left", "middle", "right"]])

    def test_malformed_box_preserves_original_order_as_separate_lines(self):
        lines = self.group_lines(
            ["first", "second"],
            [box(0, 10), ["bad"]],
            [0.2, 0.3],
        )

        self.assertEqual(lines, [[("first", 0.2)], [("second", 0.3)]])

    def test_invalid_numeric_geometry_preserves_original_order(self):
        invalid_boxes = {
            "nan": [math.nan, 5, 10, 15],
            "infinity": [0, 5, math.inf, 15],
            "zero_width": [0, 5, 0, 15],
            "zero_height": [0, 5, 10, 5],
            "inverted_width": [10, 5, 0, 15],
            "inverted_height": [0, 15, 10, 5],
            "overflowing_height": [0, -1.7e308, 10, 1.7e308],
        }

        for case, invalid_box in invalid_boxes.items():
            with self.subTest(case=case):
                lines = self.group_lines(
                    ["first", "second"],
                    [box(0, 10), invalid_box],
                    [0.2, 0.3],
                )

                self.assertEqual(
                    lines, [[("first", 0.2)], [("second", 0.3)]]
                )

    def test_overflowing_regression_falls_back_to_original_pairs(self):
        lines = self.group_lines(
            ["first", "second", "third"],
            [
                [0, 5, 10, 15],
                [1e308, 5, 1.000000000000001e308, 15],
                [1.2e308, 5, 1.200000000000001e308, 15],
            ],
            [0.2, 0.3, 0.4],
        )

        self.assertEqual(
            lines,
            [[("first", 0.2)], [("second", 0.3)], [("third", 0.4)]],
        )


if __name__ == "__main__":
    unittest.main()
