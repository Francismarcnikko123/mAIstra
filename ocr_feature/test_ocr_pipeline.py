import importlib.util
import json
import math
import sys
import tempfile
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
    c_code_suggestions = types.ModuleType("c_code_suggestions")
    recognition_consensus = types.ModuleType("recognition_consensus")

    class StubPaddleOCR:
        def __init__(self, **_kwargs):
            pass

    class StubPreprocessConfig:
        pass

    class StubRecognitionConfig:
        def __init__(self, mode="baseline", angles=(-.5, .5)):
            self.mode = mode
            self.angles = angles

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
    recognition_consensus.RecognitionConfig = StubRecognitionConfig
    recognition_consensus.DEFAULT_RECOGNITION_CONFIG = StubRecognitionConfig()
    recognition_consensus.create_candidate_views = lambda *_args: []
    recognition_consensus.select_consensus_lines = lambda baseline, *_args: (
        baseline,
        [],
    )

    module_name = "ocr_pipeline_grouping_test_module"
    spec = importlib.util.spec_from_file_location(module_name, PIPELINE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "cv2": cv2,
        "numpy": numpy,
        "paddleocr": paddleocr,
        "preprocess": preprocess,
        "c_code_cleanup": c_code_cleanup,
        "c_code_suggestions": c_code_suggestions,
        "recognition_consensus": recognition_consensus,
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
                    recognition_config=pipeline.RecognitionConfig(
                        mode="baseline"
                    ),
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
        self.assertNotIn("baseline_raw_text", result)
        self.assertNotIn("recognition_mode", result)
        self.assertNotIn("recognition_attempts", result)
        self.assertNotIn("consensus_decisions", result)
        self.assertNotIn("recognition_diagnostics", result)

    def test_consensus_selects_variant_and_uses_selected_review_data(self):
        pipeline = self.configured_pipeline()
        baseline = recognition_attempt("return o;", score=0.6)
        negative = recognition_attempt("return 0;", score=0.8)
        positive = recognition_attempt("return 0;", score=0.9)
        decision = {
            "action": "replace",
            "baseline": "return o;",
            "selected": "return 0;",
            "reason": "two-variant-support",
            "y_min": 0.1,
            "y_max": 0.2,
        }
        temporary_paths = {}
        debug_payload = {}

        def create_views(preprocessed_path, output_dir, config):
            temporary_paths["directory"] = Path(output_dir)
            temporary_paths["preprocessed"] = preprocessed_path
            temporary_paths["config"] = config
            negative_path = Path(output_dir) / "negative.png"
            positive_path = Path(output_dir) / "positive.png"
            negative_path.touch()
            positive_path.touch()
            temporary_paths["files"] = [negative_path, positive_path]
            return [
                ("rotate_neg", negative_path),
                ("rotate_pos", positive_path),
            ]

        def capture_debug(_path, payload):
            debug_payload.update(payload)

        pipeline.create_candidate_views = create_views
        pipeline.select_consensus_lines = lambda *_args: (
            positive["lines"],
            [decision],
        )
        pipeline.clean_c_code = lambda text: text.replace("return", "RETURN")

        with patch.object(
            pipeline,
            "_recognize_preprocessed",
            side_effect=[baseline, negative, positive],
        ) as recognize, patch.object(
            pipeline,
            "suggest_c_code",
            return_value=[{"line": 1, "rule_id": "selected-rule"}],
        ) as suggest, patch.object(
            pipeline,
            "_write_debug_artifact",
            side_effect=capture_debug,
        ):
            with tempfile.TemporaryDirectory() as output_dir:
                result = pipeline.extract_text_from_image(
                    "source.jpg",
                    output_dir=output_dir,
                    recognition_config=pipeline.RecognitionConfig(
                        mode="consensus"
                    ),
                )
                self.assertFalse(temporary_paths["directory"].exists())
                self.assertTrue(all(
                    not path.exists() for path in temporary_paths["files"]
                ))

        self.assertEqual(recognize.call_count, 3)
        self.assertEqual(
            [entry.args[0] for entry in recognize.call_args_list],
            [
                str(temporary_paths["preprocessed"]),
                str(temporary_paths["files"][0]),
                str(temporary_paths["files"][1]),
            ],
        )
        self.assertIsInstance(temporary_paths["preprocessed"], Path)
        self.assertEqual(result["raw_text"], "return 0;")
        self.assertEqual(result["cleaned_text"], "RETURN 0;")
        self.assertEqual(result["baseline_raw_text"], "return o;")
        self.assertEqual(result["recognition_mode"], "consensus")
        self.assertEqual(result["consensus_decisions"], [decision])
        self.assertEqual(result["recognition_diagnostics"], [])
        self.assertEqual(result["recognition_attempts"], [
            {
                "name": "baseline",
                "raw_text": "return o;",
                "line_count": 1,
                "average_confidence": 0.6,
            },
            {
                "name": "rotate_neg",
                "raw_text": "return 0;",
                "line_count": 1,
                "average_confidence": 0.8,
            },
            {
                "name": "rotate_pos",
                "raw_text": "return 0;",
                "line_count": 1,
                "average_confidence": 0.9,
            },
        ])
        self.assertEqual(result["average_confidence"], 0.9)
        self.assertEqual(result["line_details"][0]["text"], "return 0;")
        self.assertEqual(
            result["line_details"][0]["review_reasons"],
            ["selected-rule"],
        )
        suggest.assert_called_once()
        self.assertEqual(suggest.call_args.args[0], "return 0;")
        self.assertEqual(suggest.call_args.args[1][0]["text"], "return 0;")
        self.assertEqual(debug_payload["raw_text"], "return 0;")
        self.assertEqual(debug_payload["detections"], [{
            "text": "return 0;",
            "score": 0.9,
            "box": None,
        }])
        self.assertEqual(debug_payload["baseline_raw_text"], "return o;")
        self.assertEqual(debug_payload["recognition_mode"], "consensus")
        self.assertEqual(debug_payload["consensus_decisions"], [decision])

    def test_candidate_creation_failure_returns_complete_baseline(self):
        pipeline = self.configured_pipeline()
        baseline = recognition_attempt("return o;", score=0.6)
        debug_payload = {}
        pipeline.clean_c_code = lambda text: f"clean:{text}"

        def fail_candidate_creation(*_args):
            raise RuntimeError("rotation failed")

        pipeline.create_candidate_views = fail_candidate_creation

        with patch.object(
            pipeline,
            "_recognize_preprocessed",
            return_value=baseline,
        ) as recognize, patch.object(
            pipeline,
            "_write_debug_artifact",
            side_effect=lambda _path, payload: debug_payload.update(payload),
        ):
            with tempfile.TemporaryDirectory() as output_dir:
                result = pipeline.extract_text_from_image(
                    "source.jpg",
                    output_dir=output_dir,
                    recognition_config=pipeline.RecognitionConfig(
                        mode="consensus"
                    ),
                )

        recognize.assert_called_once()
        self.assertEqual(result["raw_text"], "return o;")
        self.assertEqual(result["cleaned_text"], "clean:return o;")
        self.assertEqual(result["average_confidence"], 0.6)
        self.assertEqual(result["consensus_decisions"], [])
        self.assertEqual(
            result["recognition_diagnostics"],
            ["consensus failed: RuntimeError"],
        )
        self.assertEqual(
            [attempt["name"] for attempt in result["recognition_attempts"]],
            ["baseline"],
        )
        self.assertEqual(
            debug_payload["recognition_diagnostics"],
            ["consensus failed: RuntimeError"],
        )

    def test_baseline_summary_failure_returns_complete_baseline(self):
        pipeline = self.configured_pipeline()
        baseline = recognition_attempt("return o;", score=0.6)
        pipeline.clean_c_code = lambda text: f"clean:{text}"

        with patch.object(
            pipeline,
            "_recognize_preprocessed",
            return_value=baseline,
        ) as recognize, patch.object(
            pipeline,
            "_attempt_summary",
            side_effect=RuntimeError("summary failed"),
        ):
            with tempfile.TemporaryDirectory() as output_dir:
                result = pipeline.extract_text_from_image(
                    "source.jpg",
                    output_dir=output_dir,
                    recognition_config=pipeline.RecognitionConfig(
                        mode="consensus"
                    ),
                )

        recognize.assert_called_once()
        self.assertEqual(result["raw_text"], "return o;")
        self.assertEqual(result["cleaned_text"], "clean:return o;")
        self.assertEqual(result["average_confidence"], 0.6)
        self.assertEqual(result["recognition_attempts"], [])
        self.assertEqual(result["consensus_decisions"], [])
        self.assertEqual(
            result["recognition_diagnostics"],
            ["consensus failed: RuntimeError"],
        )

    def test_attempt_summary_is_strict_json_safe(self):
        pipeline = self.configured_pipeline()

        for case, confidence in (
            ("nan", math.nan),
            ("positive-infinity", math.inf),
            ("negative-infinity", -math.inf),
            ("overflow", 10 ** 10000),
            ("unconvertible", object()),
        ):
            with self.subTest(case=case):
                attempt = recognition_attempt("return 0;")
                attempt["average_confidence"] = confidence

                summary = pipeline._attempt_summary("baseline", attempt)

                self.assertEqual(summary["raw_text"], "return 0;")
                self.assertEqual(summary["line_count"], 1)
                self.assertIsNone(summary["average_confidence"])
                json.dumps(summary, allow_nan=False)

        finite_summary = pipeline._attempt_summary(
            "baseline",
            recognition_attempt("return 0;", score=0.75),
        )
        self.assertEqual(finite_summary["average_confidence"], 0.75)
        json.dumps(finite_summary, allow_nan=False)

    def test_selection_failure_returns_complete_baseline(self):
        pipeline = self.configured_pipeline()
        attempts = [
            recognition_attempt("return o;", score=0.6),
            recognition_attempt("return 0;", score=0.8),
            recognition_attempt("return 0;", score=0.9),
        ]
        pipeline.create_candidate_views = lambda _path, output_dir, _config: [
            ("rotate_neg", Path(output_dir) / "negative.png"),
            ("rotate_pos", Path(output_dir) / "positive.png"),
        ]

        def fail_selection(*_args):
            raise ValueError("bad selection")

        pipeline.select_consensus_lines = fail_selection

        with patch.object(
            pipeline,
            "_recognize_preprocessed",
            side_effect=attempts,
        ):
            with tempfile.TemporaryDirectory() as output_dir:
                result = pipeline.extract_text_from_image(
                    "source.jpg",
                    output_dir=output_dir,
                    recognition_config=pipeline.RecognitionConfig(
                        mode="consensus"
                    ),
                )

        self.assertEqual(result["raw_text"], "return o;")
        self.assertEqual(result["consensus_decisions"], [])
        self.assertEqual(
            result["recognition_diagnostics"],
            ["consensus failed: ValueError"],
        )
        self.assertEqual(
            [attempt["name"] for attempt in result["recognition_attempts"]],
            ["baseline", "rotate_neg", "rotate_pos"],
        )

    def test_variant_failure_keeps_completed_attempt_summaries(self):
        pipeline = self.configured_pipeline()
        baseline = recognition_attempt("return o;", score=0.6)
        negative = recognition_attempt("return 0;", score=0.8)
        candidate_directory = {}

        def create_views(_path, output_dir, _config):
            candidate_directory["path"] = Path(output_dir)
            return [
                ("rotate_neg", Path(output_dir) / "negative.png"),
                ("rotate_pos", Path(output_dir) / "positive.png"),
            ]

        pipeline.create_candidate_views = create_views

        with patch.object(
            pipeline,
            "_recognize_preprocessed",
            side_effect=[baseline, negative, OSError("positive failed")],
        ):
            with tempfile.TemporaryDirectory() as output_dir:
                result = pipeline.extract_text_from_image(
                    "source.jpg",
                    output_dir=output_dir,
                    recognition_config=pipeline.RecognitionConfig(
                        mode="consensus"
                    ),
                )
                self.assertFalse(candidate_directory["path"].exists())

        self.assertEqual(result["raw_text"], "return o;")
        self.assertEqual(
            result["recognition_diagnostics"],
            ["consensus failed: OSError"],
        )
        self.assertEqual(
            [attempt["name"] for attempt in result["recognition_attempts"]],
            ["baseline", "rotate_neg"],
        )

    def test_malformed_selected_attempt_returns_complete_baseline(self):
        pipeline = self.configured_pipeline()
        attempts = [
            recognition_attempt("return o;", score=0.6),
            recognition_attempt("return 0;", score=0.8),
            recognition_attempt("return 0;", score=0.9),
        ]
        pipeline.create_candidate_views = lambda _path, output_dir, _config: [
            ("rotate_neg", Path(output_dir) / "negative.png"),
            ("rotate_pos", Path(output_dir) / "positive.png"),
        ]
        pipeline.select_consensus_lines = lambda *_args: (
            [{"text": "return 0;"}],
            [{"action": "replace"}],
        )

        with patch.object(
            pipeline,
            "_recognize_preprocessed",
            side_effect=attempts,
        ):
            with tempfile.TemporaryDirectory() as output_dir:
                result = pipeline.extract_text_from_image(
                    "source.jpg",
                    output_dir=output_dir,
                    recognition_config=pipeline.RecognitionConfig(
                        mode="consensus"
                    ),
                )

        self.assertEqual(result["raw_text"], "return o;")
        self.assertEqual(result["consensus_decisions"], [])
        self.assertEqual(
            result["recognition_diagnostics"],
            ["consensus failed: KeyError"],
        )


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
            {"line": 2, "rule_id": "c-token-return"},
            {"line": "bad", "rule_id": "ignored"},
        ]

        self.pipeline._attach_suggestion_reasons(details, suggestions)

        self.assertEqual(
            details[0]["review_reasons"], ["function-call-printf"]
        )
        self.assertEqual(details[1]["review_reasons"], ["c-token-return"])


if __name__ == "__main__":
    unittest.main()
