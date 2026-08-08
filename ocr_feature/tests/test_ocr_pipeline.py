# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_ocr_pipeline
import importlib.util
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PIPELINE_PATH = Path(__file__).resolve().parent.parent / "core" / "ocr_pipeline.py"


def load_pipeline_without_models():
    """Load the grouping helpers without importing OCR runtime dependencies."""
    cv2 = types.ModuleType("cv2")
    numpy = types.ModuleType("numpy")
    paddleocr = types.ModuleType("paddleocr")
    core_pkg = types.ModuleType("core")
    preprocess = types.ModuleType("core.preprocess")
    c_code_cleanup = types.ModuleType("core.c_code_cleanup")
    c_code_suggestions = types.ModuleType("core.c_code_suggestions")

    class StubPaddleOCR:
        def __init__(self, **_kwargs):
            pass

    class StubPreprocessConfig:
        pass

    class StubImage:
        shape = (100, 200)

    cv2.IMREAD_GRAYSCALE = 0
    cv2.imread = lambda _path, _mode: StubImage()
    paddleocr.PaddleOCR = StubPaddleOCR
    preprocess.preprocess_image = lambda **_kwargs: ""
    preprocess.PreprocessConfig = StubPreprocessConfig
    preprocess.DEFAULT_CONFIG = StubPreprocessConfig()
    c_code_cleanup.clean_c_code = lambda text: text
    c_code_suggestions.suggest_c_code = lambda _text, _details=None: []
    core_pkg.preprocess = preprocess
    core_pkg.c_code_cleanup = c_code_cleanup
    core_pkg.c_code_suggestions = c_code_suggestions

    # core.numeric and core.debug_artifact are pure-stdlib (math / json +
    # pathlib) and ocr_pipeline imports from both, so load the REAL modules
    # rather than stub them — otherwise this file only passes when another
    # test happens to import them first (i.e. it can't run in isolation).
    def load_real(name):
        spec = importlib.util.spec_from_file_location(
            f"core.{name}", PIPELINE_PATH.parent / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        setattr(core_pkg, name, module)
        return module

    numeric = load_real("numeric")
    debug_artifact = load_real("debug_artifact")

    module_name = "ocr_pipeline_grouping_test_module"
    spec = importlib.util.spec_from_file_location(module_name, PIPELINE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "cv2": cv2,
        "numpy": numpy,
        "paddleocr": paddleocr,
        "core": core_pkg,
        "core.preprocess": preprocess,
        "core.numeric": numeric,
        "core.debug_artifact": debug_artifact,
        "core.c_code_cleanup": c_code_cleanup,
        "core.c_code_suggestions": c_code_suggestions,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


def box(x, y_center):
    return [x, y_center - 5, x + 10, y_center + 5]


def recognition_attempt(text, score=0.8, y_min=0.1, y_max=0.2):
    """Return one complete mocked structured recognition attempt."""
    members = [(text, score)]
    line = {
        "text": text,
        "members": members,
        "scores": [score],
        "mean_confidence": score,
        "y_min": y_min,
        "y_max": y_max,
    }
    return {
        "raw_text": text,
        "lines": [line],
        "grouped_lines": [members],
        "average_confidence": score,
        "detections": [{"text": text, "score": score, "box": [1, 2, 3, 4]}],
        "dropped_low_confidence": [],
        "debug_lines": [[{"text": text, "score": score}]],
    }


class GroupDetectionRecordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    def group_lines(self, texts, boxes, scores=None):
        if scores is None:
            scores = [0.9] * len(texts)
        grouped, _geometry_safe = self.pipeline._group_detection_records(
            texts, scores, boxes
        )
        return [
            [(member["text"], member["score"]) for member in members]
            for members in grouped
        ]

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
        expected_y = self.pipeline._expected_line_y(
            [
                {"x": 0, "y": 10},
                {"x": 0, "y": 11},
            ],
            candidate_x=20,
        )

        self.assertEqual(expected_y, 10)

    def test_identical_x_boxes_within_tolerance_do_not_merge(self):
        # End-to-end guard for the same-x case: two boxes with identical
        # x-ranges are 100% horizontally overlapped, so even though their
        # vertical centers are within line_tol they must be treated as stacked
        # rows and kept separate. (This is the scenario the direct
        # _expected_line_y test above can no longer cover through grouping.)
        lines = self.group_texts(["a", "b"], [box(0, 10), box(0, 13)])

        self.assertEqual(lines, [["a"], ["b"]])

    def test_exact_vertical_tolerance_boundary_stays_on_the_line(self):
        lines = self.group_texts(["a", "b"], [box(0, 10), box(20, 16)])

        self.assertEqual(lines, [["a", "b"]])

    def test_separates_nearby_rows_with_significant_horizontal_overlap(self):
        lines = self.group_texts(
            ["int main C){", "int result = add (3, 4);"],
            [[162, 438, 455, 511], [253, 477, 780, 552]],
        )

        self.assertEqual(
            lines,
            [["int main C){"], ["int result = add (3, 4);"]],
        )

    def test_separates_nearby_rows_with_moderate_horizontal_overlap(self):
        lines = self.group_texts(
            ["do {", 'printf ("---MENU---\\n");'],
            [[50, 108, 109, 148], [87, 120, 374, 173]],
        )

        self.assertEqual(
            lines,
            [["do {"], ['printf ("---MENU---\\n");']],
        )

    def test_merges_nearby_fragments_without_horizontal_overlap(self):
        lines = self.group_texts(
            ["int main()", "{"],
            [[162, 438, 455, 511], [465, 477, 600, 552]],
        )

        self.assertEqual(lines, [["int main()", "{"]])

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


class StructuredRecognitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    def test_structured_line_keeps_text_scores_and_normalized_geometry(self):
        lines = self.pipeline._group_structured_lines(
            ["int", "main()"],
            [0.8, 0.6],
            [[10, 10, 30, 20], [35, 11, 70, 21]],
            image_height=100,
        )

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["text"], "int main()")
        self.assertEqual(
            lines[0]["members"], [("int", 0.8), ("main()", 0.6)]
        )
        self.assertEqual(lines[0]["scores"], [0.8, 0.6])
        self.assertAlmostEqual(lines[0]["y_min"], 0.10)
        self.assertAlmostEqual(lines[0]["y_max"], 0.21)
        self.assertAlmostEqual(lines[0]["mean_confidence"], 0.70)

    def test_malformed_geometry_preserves_original_lines_without_coordinates(self):
        lines = self.pipeline._group_structured_lines(
            ["first", "second"],
            [0.8, "bad"],
            [[10, 10, 30, 20], ["bad"]],
            image_height=100,
        )

        self.assertEqual(
            [line["members"] for line in lines],
            [[("first", 0.8)], [("second", "bad")]],
        )
        self.assertEqual([line["text"] for line in lines], ["first", "second"])
        self.assertEqual(lines[0]["scores"], [0.8])
        self.assertEqual(lines[1]["scores"], [])
        self.assertIsNone(lines[0]["y_min"])
        self.assertIsNone(lines[0]["y_max"])
        self.assertIsNone(lines[1]["y_min"])
        self.assertIsNone(lines[1]["y_max"])

    def test_structured_mean_stays_finite_for_large_finite_scores(self):
        lines = self.pipeline._group_structured_lines(
            ["int", "main()"],
            [1e308, 1e308],
            [[10, 10, 30, 20], [35, 10, 70, 20]],
            image_height=100,
        )

        self.assertTrue(math.isfinite(lines[0]["mean_confidence"]))
        self.assertEqual(lines[0]["mean_confidence"], 1e308)

    def test_recognize_preprocessed_preserves_page_order_and_debug_data(self):
        pages = [
            types.SimpleNamespace(json={
                "res": {
                    "rec_texts": ["right", "left", "dust"],
                    "rec_scores": [0.6, 0.8, 0.2],
                    "rec_boxes": [
                        [50, 10, 70, 20],
                        [10, 10, 40, 20],
                        [80, 10, 90, 20],
                    ],
                }
            }),
            types.SimpleNamespace(json={
                "res": {
                    "rec_texts": ["return", "}"],
                    "rec_scores": ["bad"],
                    "rec_boxes": [["bad"], [10, 30, 20, 40]],
                }
            }),
        ]

        class MultiPageOCR:
            @staticmethod
            def predict(_path):
                return pages

        self.pipeline.ocr = MultiPageOCR()

        attempt = self.pipeline._recognize_preprocessed("page.png")

        self.assertEqual(attempt["raw_text"], "left right\nreturn\n}")
        self.assertEqual(
            attempt["grouped_lines"],
            [
                [("left", 0.8), ("right", 0.6)],
                [("return", "bad")],
                [("}", 0.0)],
            ],
        )
        self.assertAlmostEqual(attempt["average_confidence"], (0.8 + 0.6) / 3)
        self.assertEqual(
            [entry["text"] for entry in attempt["detections"]],
            ["right", "left", "return", "}"],
        )
        self.assertEqual(
            [entry["text"] for entry in attempt["dropped_low_confidence"]],
            ["dust"],
        )
        self.assertEqual(
            attempt["debug_lines"],
            [
                [{"text": "left", "score": 0.8},
                 {"text": "right", "score": 0.6}],
                [{"text": "return", "score": "bad"}],
                [{"text": "}", "score": 0.0}],
            ],
        )
        self.assertAlmostEqual(attempt["lines"][0]["y_min"], 0.10)
        self.assertAlmostEqual(attempt["lines"][0]["y_max"], 0.20)
        self.assertIsNone(attempt["lines"][1]["y_min"])
        self.assertIsNone(attempt["lines"][2]["y_max"])

    def test_recognize_preprocessed_rejects_an_unreadable_image(self):
        self.pipeline.cv2.imread = lambda _path, _mode: None

        with self.assertRaisesRegex(ValueError, "could not read"):
            self.pipeline._recognize_preprocessed("missing.png")


class ExtractionOutputDirectoryTests(unittest.TestCase):
    def test_uses_requested_output_directory_without_changing_result_shape(self):
        pipeline = load_pipeline_without_models()
        preprocess_call = {}

        def fake_preprocess(**kwargs):
            preprocess_call.update(kwargs)
            return str(Path(kwargs["output_dir"]) / "source_preprocessed.jpg")

        class EmptyOCR:
            @staticmethod
            def predict(_path):
                return []

        pipeline.preprocess_image = fake_preprocess
        pipeline.ocr = EmptyOCR()

        with tempfile.TemporaryDirectory() as output_dir:
            result = pipeline.extract_text_from_image(
                "source.jpg",
                output_dir=output_dir,
            )

        self.assertEqual(preprocess_call["output_dir"], output_dir)
        self.assertEqual(result["raw_text"], "")
        self.assertEqual(result["cleaned_text"], "")
        self.assertIn("average_confidence", result)
        self.assertIn("preprocessed_image", result)
        self.assertEqual(result["line_details"], [])
        self.assertEqual(result["review_suggestions"], [])
        self.assertEqual(result["review_diagnostics"], [])

    def test_suggestion_failure_is_diagnostic_and_does_not_fail_ocr(self):
        pipeline = load_pipeline_without_models()

        def fail_suggestions(_text, _details=None):
            raise RuntimeError("suggestion failure")

        class EmptyOCR:
            @staticmethod
            def predict(_path):
                return []

        pipeline.preprocess_image = lambda **kwargs: str(
            Path(kwargs["output_dir"]) / "source_preprocessed.jpg"
        )
        pipeline.suggest_c_code = fail_suggestions
        pipeline.ocr = EmptyOCR()

        with tempfile.TemporaryDirectory() as output_dir:
            result = pipeline.extract_text_from_image(
                "source.jpg",
                output_dir=output_dir,
            )

        self.assertEqual(result["review_suggestions"], [])
        self.assertEqual(
            result["review_diagnostics"],
            ["suggestion engine failed: RuntimeError"],
        )


class RecognitionConsensusPipelineTests(unittest.TestCase):
    def configured_pipeline(self):
        pipeline = load_pipeline_without_models()
        pipeline.preprocess_image = lambda **kwargs: str(
            Path(kwargs["output_dir"]) / "source_preprocessed.jpg"
        )
        return pipeline

    def test_explicit_baseline_recognizes_once_and_preserves_exact_result(self):
        pipeline = self.configured_pipeline()
        baseline = recognition_attempt("return o;", score=0.6)

        with patch.object(
            pipeline,
            "_recognize_preprocessed",
            return_value=baseline,
        ) as recognize:
            with tempfile.TemporaryDirectory() as output_dir:
                result = pipeline.extract_text_from_image(
                    "source.jpg",
                    output_dir=output_dir,
                )

        recognize.assert_called_once()
        self.assertEqual(result, {
            "raw_text": "return o;",
            "cleaned_text": "return o;",
            "average_confidence": 0.6,
            "preprocessed_image": recognize.call_args.args[0],
            "line_details": [{
                "line": 1,
                "text": "return o;",
                "scores": [0.6],
                "min_confidence": 0.6,
                "mean_confidence": 0.6,
                "review_reasons": [],
            }],
            "review_suggestions": [],
            "review_diagnostics": [],
        })


class LineDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    def test_builds_finite_score_summary_and_ignores_bad_scores(self):
        grouped_lines = [
            [("int", 0.8), ("main()", 0.6)],
            [("return 0;", "bad"), ("}", math.inf)],
        ]

        details = self.pipeline._build_line_details(grouped_lines)

        self.assertEqual(details[0], {
            "line": 1,
            "text": "int main()",
            "scores": [0.8, 0.6],
            "min_confidence": 0.6,
            "mean_confidence": 0.7,
            "review_reasons": [],
        })
        self.assertEqual(details[1], {
            "line": 2,
            "text": "return 0; }",
            "scores": [],
            "min_confidence": None,
            "mean_confidence": None,
            "review_reasons": [],
        })

    def test_skips_empty_line_groups_to_match_raw_text_line_numbers(self):
        details = self.pipeline._build_line_details([
            [("", 0.9)],
            [("return 0;", 0.8)],
        ])

        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["line"], 1)
        self.assertEqual(details[0]["text"], "return 0;")

    def test_attaches_unique_suggestion_rule_ids_to_the_matching_line(self):
        details = self.pipeline._build_line_details([
            [("printe();", 0.9)],
            [("return 0;", 0.8)],
        ])
        suggestions = [
            {"line": 1, "rule_id": "function-call-printf"},
            {"line": 1, "rule_id": "function-call-printf"},
            {"line": 2, "rule_id": "function-call-scanf"},
            {"line": "bad", "rule_id": "ignored"},
        ]

        self.pipeline._attach_suggestion_reasons(details, suggestions)

        self.assertEqual(
            details[0]["review_reasons"], ["function-call-printf"]
        )
        self.assertEqual(details[1]["review_reasons"], ["function-call-scanf"])


if __name__ == "__main__":
    unittest.main()
