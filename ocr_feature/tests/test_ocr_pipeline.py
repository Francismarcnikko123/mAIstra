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
    c_literals = load_real("c_literals")

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
        "core.c_literals": c_literals,
        "core.c_code_suggestions": c_code_suggestions,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


def box(x, y_center):
    return [x, y_center - 5, x + 10, y_center + 5]


def wide_box(x, y_center):
    """Like box(), but realistically word-scale (100px wide) rather than
    10px. Needed for tests whose x-positions must stay merge-eligible under
    the real, evidence-based REGION_GAP_MULTIPLIER=0.75 -- box()'s tiny 10px
    width makes any nonzero gap exceed that threshold (0.75 * 10 = 7.5px),
    which has nothing to do with what these particular tests are actually
    checking (vertical-tolerance/slope/sort logic, not gap-severance)."""
    return [x, y_center - 5, x + 100, y_center + 5]


def _line(text, severed=False):
    """Build one minimal line dict, matching what _group_detection_records
    produces internally: a single member carrying `text`, optionally
    flagged as severed by the Phase 1 gap check."""
    line = {"members": [{"text": text, "score": 0.9}]}
    if severed:
        line["severed_by_gap"] = True
    return line


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
            [wide_box(0, 10), wide_box(130, 11), wide_box(260, 12), wide_box(0, 17)],
        )

        self.assertEqual(lines, [["a", "b", "c"], ["next"]])

    def test_keeps_a_sloped_handwritten_line_together(self):
        lines = self.group_texts(
            ["a", "b", "c"],
            [wide_box(0, 10), wide_box(130, 14), wide_box(260, 18)],
        )

        self.assertEqual(lines, [["a", "b", "c"]])

    def test_keeps_a_four_fragment_slope_together(self):
        lines = self.group_texts(
            ["a", "b", "c", "d"],
            [wide_box(0, 10), wide_box(130, 14), wide_box(260, 18), wide_box(390, 22)],
        )

        self.assertEqual(lines, [["a", "b", "c", "d"]])

    def test_rejects_an_indented_next_row_after_a_shallow_slope(self):
        lines = self.group_texts(
            ["a", "b", "c", "next"],
            [wide_box(0, 10), wide_box(130, 11), wide_box(260, 12), wide_box(520, 18)],
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
        lines = self.group_texts(["a", "b"], [wide_box(0, 10), wide_box(130, 16)])

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

    def test_severs_a_far_apart_same_height_fragment_instead_of_fusing_it(self):
        # Median width here is ~100 (both boxes are 100 wide), so the gap
        # threshold is 0.75 * 100 = 75. A 700px gap must sever, not merge.
        lines = self.group_lines(
            ["struct Compressor { unsigned int flags; };", "c->flags |= 1;"],
            [[0, 10, 100, 20], [800, 10, 900, 20]],
        )

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0][0][0], "struct Compressor { unsigned int flags; };")
        self.assertEqual(lines[1][0][0], "c->flags |= 1;")

    def test_keeps_a_moderate_gap_merged_as_one_line(self):
        # Same widths (median 100, threshold 75), but only a 50px gap --
        # must still merge as before this change.
        lines = self.group_texts(
            ["int main()", "{"],
            [[0, 10, 100, 20], [150, 10, 250, 20]],
        )

        self.assertEqual(lines, [["int main()", "{"]])

    def test_accepts_a_finite_box_centered_at_zero(self):
        lines = self.group_texts(["a", "b"], [wide_box(0, 0), wide_box(130, 0)])

        self.assertEqual(lines, [["a", "b"]])

    def test_sorts_members_left_to_right_within_a_line(self):
        # Input list order is scrambled (right, left, middle) to test the
        # final within-line sort -- but y-values are distinct (not tied) so
        # the sweep processes them in genuine spatial order (left, then
        # middle, then right), not input-list order. With tied y-values,
        # same-y ties break by input order, which would compare "right"
        # directly against "left" (the farthest pair) before "middle" ever
        # joins the line -- fine under the old 600px threshold, but exceeds
        # the real 75px one even though every *adjacent* pair is well within
        # it.
        lines = self.group_texts(
            ["right", "left", "middle"],
            [wide_box(325, 11), wide_box(0, 10), wide_box(163, 10.5)],
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

    def test_end_to_end_severs_and_reassembles_a_displaced_case_body(self):
        # End-to-end wiring test. Geometry hand-traced before writing this,
        # and picked SPECIFICALLY so the well-formedness search is
        # unambiguous (only one block length yields a valid reordering) --
        # a smaller "case 0:" flavored fixture was tried first and rejected
        # because two block lengths both yielded well-formed sequences,
        # which the algorithm's ambiguity guard correctly declined.
        #
        # Raw geometric sweep (y then x, gap-check on same-y merge):
        #   struct (y=10, x=[0,100])
        #   }      (y=10, x=[800,900])   <- 700px gap > 600px threshold
        #                                   at ~100px median width -> severed
        #   main   (y=30, x=[0,100])     <- 20px y-diff > line_tol(6) -> own line
        # sweep order: [struct, } (severed), main]  -- misordered, "}"
        # sits before the opener it's meant to close.
        #
        # Reassembly search (start=1):
        #   L=1: block=[}], normal=[struct, main]
        #        reordering=[struct, main, }]  depths 0, 1, 0  -> well-formed
        #   L=2: block=[}, main], normal=[struct]
        #        reordering=[struct, }, main]  depths 0, -1 -> NOT well-formed
        # exactly one valid L -> reorder applied.
        texts = [
            "struct S { int x; };",   # y=10, x=[0,100]        delta 0
            "}",                       # y=10, x=[800,900] sev  delta -1
            "int main() {",            # y=30, x=[0,100]        delta +1
        ]
        boxes = [
            [0, 5, 100, 15],
            [800, 5, 900, 15],
            [0, 25, 100, 35],
        ]

        grouped, geometry_safe = self.pipeline._group_detection_records(
            texts, [0.9] * 3, boxes
        )

        self.assertTrue(geometry_safe)
        result_texts = [
            member["text"] for line in grouped for member in line
        ]
        self.assertEqual(
            result_texts,
            ["struct S { int x; };", "int main() {", "}"],
        )


class DynamicGutterGroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    def inspect_grouping(self, texts, boxes):
        # Observe the actual geometry flags independently of brace inference.
        with patch.object(self.pipeline, "_reassemble_displaced_regions",
                          side_effect=lambda lines: lines) as reassemble:
            grouped, safe = self.pipeline._group_detection_records(
                texts, [0.9] * len(texts), boxes
            )
        self.assertTrue(safe)
        reassemble.assert_called_once()
        flagged = [
            member["text"]
            for line in reassemble.call_args.args[0]
            if line.get("severed_by_gap")
            for member in line["members"]
        ]
        return [[m["text"] for m in line] for line in grouped], flagged

    def test_interleaved_region_includes_adjacent_right_rows_only(self):
        # Synthetic text on the measured first-photo geometry. R0/R1 and
        # R5/R6 separate via overlap; intervening LEFT rows must stay normal.
        texts = ["R0", "R1", "L0", "R2", "L1", "R3", "L2",
                 "R4", "L3", "R5", "R6", "L4", "signature"]
        boxes = [
            [606, 185, 693, 225], [628, 188, 942, 250],
            [221, 221, 324, 259], [629, 247, 693, 282],
            [245, 253, 381, 293], [631, 255, 831, 307],
            [267, 274, 475, 319], [656, 285, 816, 328],
            [271, 308, 381, 346], [667, 302, 797, 357],
            [662, 345, 677, 360], [230, 348, 264, 379],
            [247, 349, 700, 421],
        ]
        grouped, flagged = self.inspect_grouping(texts, boxes)
        self.assertEqual(flagged, [f"R{i}" for i in range(7)])
        self.assertEqual(grouped, [[text] for text in texts])

    def test_boundary_box_is_included_by_range_even_after_closer_center(self):
        grouped, flagged = self.inspect_grouping(
            ["left", "right", "boundary", "bridge"],
            [[0, 0, 100, 20], [300, 0, 400, 20],
             [300, 30, 400, 100], [0, 40, 400, 60]],
        )
        self.assertEqual(flagged, ["right", "boundary"])
        self.assertEqual(grouped, [["left"], ["right"], ["bridge"], ["boundary"]])

    def test_same_side_extensions_narrow_until_a_real_straddle(self):
        _, flagged = self.inspect_grouping(
            ["left", "right", "wider left", "wider right", "bridge"],
            [[0, 0, 100, 20], [300, 0, 400, 20],
             [0, 30, 180, 50], [250, 30, 400, 50], [0, 60, 400, 80]],
        )
        self.assertEqual(flagged, ["right", "wider right"])

    def test_full_height_columns_discard_candidates_and_keep_baseline_merges(self):
        texts, boxes = [], []
        for row in range(24):
            texts.extend([f"L{row}", f"R{row}"])
            boxes.extend([[0, row * 40, 100 if row == 0 else 180, row * 40 + 20],
                          [300 if row == 0 else 250, row * 40, 400, row * 40 + 20]])
        grouped, flagged = self.inspect_grouping(texts, boxes)
        self.assertEqual(flagged, [])
        self.assertEqual(grouped, [[f"L{i}", f"R{i}"] for i in range(24)])

    def test_confirmed_window_respects_line_count_cap(self):
        for count in (12, 13):
            with self.subTest(count=count):
                texts, boxes = [], []
                for row in range(count):
                    texts.extend([f"L{row}", f"R{row}"])
                    boxes.extend([[0, row * 20, 100, row * 20 + 10],
                                  [300, row * 20, 400, row * 20 + 10]])
                texts.append("bridge")
                boxes.append([0, count * 20, 400, count * 20 + 10])
                _, flagged = self.inspect_grouping(texts, boxes)
                self.assertEqual(flagged, [f"R{i}" for i in range(count)]
                                 if count == 12 else [])

    def test_confirmed_window_respects_vertical_span_cap(self):
        for close_y in (300, 301):
            with self.subTest(close_y=close_y):
                _, flagged = self.inspect_grouping(
                    ["left", "right", "bridge"],
                    [[0, 0, 100, 20], [300, 0, 400, 20],
                     [0, close_y, 400, close_y + 20]],
                )
                self.assertEqual(flagged, ["right"] if close_y == 300 else [])

    def test_collapsed_gutter_discards_candidates_even_with_later_wide_line(self):
        _, flagged = self.inspect_grouping(
            ["left", "right", "fills gap", "bridge"],
            [[0, 0, 100, 20], [300, 0, 400, 20],
             [100, 30, 300, 50], [0, 60, 400, 80]],
        )
        self.assertEqual(flagged, [])

    def test_later_independent_window_is_not_selected(self):
        _, flagged = self.inspect_grouping(
            ["left", "right", "bridge", "later left", "later right", "later bridge"],
            [[0, 0, 100, 20], [300, 0, 400, 20], [0, 30, 400, 50],
             [0, 70, 100, 90], [300, 70, 400, 90], [0, 100, 400, 120]],
        )
        self.assertEqual(flagged, ["right"])

    def test_confirms_a_block_with_no_bridging_line_at_all(self):
        # A displaced block isn't guaranteed to be followed by a line that
        # straddles back across the gutter -- it can simply be followed by
        # more single-column content, or nothing further at all. This is
        # the exact shape that broke test_end_to_end_severs_and_reassembles
        # _a_displaced_case_body under the first cut of the dynamic trace.
        _, flagged = self.inspect_grouping(
            ["left0", "right0", "left1"],
            [[0, 0, 100, 20], [300, 0, 400, 20], [0, 30, 100, 50]],
        )
        self.assertEqual(flagged, ["right0"])

    def test_right_side_resuming_after_a_gap_is_not_excluded(self):
        # No fixed-distance inactivity trigger exists (see
        # _trace_displaced_region's docstring for why one was tried and
        # removed) -- a RIGHT match that resumes after a quiet stretch is
        # still a legitimate candidate, not treated as a new/separate
        # window. Reaching the end of the page with RIGHT still matching
        # means "not yet confirmed", so the whole run is discarded here,
        # not partially confirmed up to the gap.
        _, flagged = self.inspect_grouping(
            ["left0", "right0", "left1", "right1"],
            [[0, 0, 100, 20], [300, 0, 400, 20],
             [0, 130, 100, 150], [300, 140, 400, 160]],
        )
        self.assertEqual(flagged, [])


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


class BraceDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    def test_counts_a_single_opener(self):
        self.assertEqual(self.pipeline._brace_delta("void f() {"), 1)

    def test_counts_a_single_closer(self):
        self.assertEqual(self.pipeline._brace_delta("}"), -1)

    def test_self_balanced_line_is_zero(self):
        self.assertEqual(
            self.pipeline._brace_delta("struct S { int a; };"), 0
        )

    def test_multiple_closers_in_one_line(self):
        self.assertEqual(self.pipeline._brace_delta("} } }"), -3)

    def test_ignores_braces_inside_a_string_literal(self):
        self.assertEqual(
            self.pipeline._brace_delta('printf("{ not real }");'), 0
        )

    def test_ignores_braces_inside_a_char_literal(self):
        self.assertEqual(self.pipeline._brace_delta("char c = '{';"), 0)

    def test_counts_real_brace_alongside_a_shielded_literal(self):
        self.assertEqual(
            self.pipeline._brace_delta('if (x) { printf("}"); '), 1
        )


class ReassembleDisplacedRegionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    def texts_of(self, lines):
        return [line["members"][0]["text"] for line in lines]

    def test_no_severed_line_returns_input_unchanged(self):
        lines = [_line("int main() {"), _line("return 0;"), _line("}")]

        result = self.pipeline._reassemble_displaced_regions(lines)

        self.assertEqual(result, lines)

    def test_relocates_the_rbnode_example_to_the_end(self):
        # The user's real motivating example: a struct def and a function
        # opening through a dangling `case 0:`, with the case body written
        # in margin space and severed by Phase 1's gap check.
        lines = [
            _line("struct RBNode { int val; int color; struct RBNode *child[2]; };"),
            _line("(*root)->child[!dir] = save->child[dir];", severed=True),
            _line("save->child[dir] = *root;"),
            _line("(*root)->color = 1;"),
            _line("save->color = 0;"),
            _line("*root = save;"),
            _line("break;"),
            _line("}"),
            _line("}"),
            _line("}"),
            _line("void rotate_rb(struct RBNode **root, int dir) {"),
            _line("if (*root != NULL && (*root)->child[!dir] != NULL) {"),
            _line("struct RBNode *save = (*root)->child[!dir];"),
            _line("switch (save->color) {"),
            _line("case 0:"),
        ]

        result = self.pipeline._reassemble_displaced_regions(lines)

        self.assertEqual(
            self.texts_of(result),
            [
                "struct RBNode { int val; int color; struct RBNode *child[2]; };",
                "void rotate_rb(struct RBNode **root, int dir) {",
                "if (*root != NULL && (*root)->child[!dir] != NULL) {",
                "struct RBNode *save = (*root)->child[!dir];",
                "switch (save->color) {",
                "case 0:",
                "(*root)->child[!dir] = save->child[dir];",
                "save->child[dir] = *root;",
                "(*root)->color = 1;",
                "save->color = 0;",
                "*root = save;",
                "break;",
                "}",
                "}",
                "}",
            ],
        )

    def test_relocates_the_compressor_example_to_the_end(self):
        lines = [
            _line("struct Compressor { unsigned int flags; int shift_count; };"),
            _line("c->flags |= (inputs[i] & 0xFF) << c->shift_count;", severed=True),
            _line("c->shift_count += 8;"),
            _line("break;"),
            _line("}"),
            _line("i++;"),
            _line("}"),
            _line("}"),
            _line("void pack_flags(struct Compressor *c, unsigned int inputs[], int size) {"),
            _line("int i = 0;"),
            _line("while (i < size && c->shift_count <= 24) {"),
            _line("switch (inputs[i] != 0 && !(inputs[i] & 0x01) ? 1 : 0) {"),
            _line("case 1:"),
        ]

        result = self.pipeline._reassemble_displaced_regions(lines)

        self.assertEqual(
            self.texts_of(result),
            [
                "struct Compressor { unsigned int flags; int shift_count; };",
                "void pack_flags(struct Compressor *c, unsigned int inputs[], int size) {",
                "int i = 0;",
                "while (i < size && c->shift_count <= 24) {",
                "switch (inputs[i] != 0 && !(inputs[i] & 0x01) ? 1 : 0) {",
                "case 1:",
                "c->flags |= (inputs[i] & 0xFF) << c->shift_count;",
                "c->shift_count += 8;",
                "break;",
                "}",
                "i++;",
                "}",
                "}",
            ],
        )

    def test_refuses_when_normal_contains_a_closer(self):
        # The severed block ("work(); }") belongs inside the switch, with
        # after_switch() following it outside the switch. Appending the block
        # is brace-well-formed but puts both statements in the wrong scopes.
        # The unique winning L=2 gives depths 0, 1, 2, 2, 2, 1, 1, 0;
        # longer blocks leave a negative depth and cannot qualify. The
        # winning normal contains its own "}" (delta -1), so reject it.
        lines = [
            _line("struct S { int x; };"),
            _line("work();", severed=True),
            _line("}", severed=True),
            _line("void f() {"),
            _line("switch (x) {"),
            _line("case 0:"),
            _line("after_switch();"),
            _line("}"),
        ]

        result = self.pipeline._reassemble_displaced_regions(lines)

        self.assertEqual(result, lines)

    def test_two_severed_blocks_is_ambiguous_and_stays_unchanged(self):
        lines = [
            _line("int main() {"),
            _line("a();", severed=True),
            _line("b();", severed=True),
            _line("}"),
        ]

        result = self.pipeline._reassemble_displaced_regions(lines)

        self.assertEqual(result, lines)

    def test_unbalanced_result_stays_unchanged(self):
        # The severed block's braces don't bring the page back to a clean
        # close -- must not guess.
        lines = [
            _line("int main() {"),
            _line("return 0;", severed=True),
            _line("}"),
            _line("}"),  # one extra closer -- never balances to 0
        ]

        result = self.pipeline._reassemble_displaced_regions(lines)

        self.assertEqual(result, lines)


if __name__ == "__main__":
    unittest.main()
