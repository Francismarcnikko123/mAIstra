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
    core_pkg.preprocess = preprocess
    core_pkg.c_code_cleanup = c_code_cleanup

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


# Frozen detection boxes from real pipeline debug artifacts, geometry only:
# each is [x0, y0, x1, y1] with recognition content stripped and labeled by
# index, so reading-order tests assert the GEOMETRIC split, never CER. Shared
# by DisplacedSeveranceTests and BandedColumnDetectionTests so the two families
# exercise the same real pages without duplicating the fixtures.
#
# WRITER18_BOXES: green_writer18_B2_2 (39 boxes) -- a two-page / side-by-side
# capture whose right block (the 13 boxes with x0 >= 798) occupies only the
# top-right quadrant; the correct reading order is left column fully then right
# column fully (banded two-column). WRITER27_BOXES: green_writer27_B1_3 (10
# boxes) -- a page whose short right cluster must NOT be banded-split.
WRITER18_BOXES = [
    [17, 61, 69, 111], [822, 110, 904, 155], [25, 120, 250, 166],
    [829, 147, 939, 189], [25, 193, 160, 237], [828, 178, 1151, 231],
    [845, 228, 882, 265], [25, 239, 57, 272], [878, 243, 1078, 300],
    [63, 268, 248, 312], [893, 297, 929, 334], [934, 323, 1052, 369],
    [70, 327, 460, 386], [904, 363, 941, 410], [81, 375, 294, 415],
    [855, 400, 896, 445], [77, 397, 461, 460], [858, 438, 1293, 488],
    [86, 449, 311, 491], [827, 483, 866, 519], [77, 517, 232, 559],
    [820, 512, 920, 559], [81, 562, 113, 596], [798, 555, 855, 602],
    [109, 558, 550, 628], [117, 620, 197, 663], [94, 656, 131, 694],
    [73, 697, 314, 738], [92, 740, 127, 773], [124, 772, 564, 812],
    [123, 812, 209, 854], [101, 844, 139, 882], [86, 891, 356, 931],
    [97, 939, 131, 979], [138, 949, 859, 1005], [140, 995, 222, 1036],
    [104, 1029, 149, 1076], [78, 1092, 147, 1140], [79, 1132, 128, 1184],
]
WRITER27_BOXES = [
    [17, 94, 142, 123], [522, 87, 602, 127], [12, 126, 227, 153],
    [479, 121, 598, 149], [11, 142, 575, 187], [43, 177, 166, 209],
    [284, 176, 504, 210], [302, 203, 591, 236], [270, 235, 354, 263],
    [318, 255, 500, 291],
]


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
        # Isolate trace flags from both later reordering passes. The geometry
        # severance pass has its own end-to-end tests below.
        with patch.object(self.pipeline, "_reassemble_displaced_regions",
                          side_effect=lambda lines: lines) as reassemble, \
             patch.object(self.pipeline, "_sever_displaced_regions",
                          side_effect=lambda lines, _width: lines):
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

    def test_full_height_two_column_page_is_split_into_sequential_columns(self):
        # A genuine two-column page (two independent programs side by side)
        # must read as the left column in full, then the right column in full
        # -- never interleaved by the y-sweep. The persistent uncrossed gutter
        # plus substantial content on both sides triggers the split.
        texts, boxes = [], []
        for row in range(24):
            texts.extend([f"L{row}", f"R{row}"])
            boxes.extend([[0, row * 40, 100 if row == 0 else 180, row * 40 + 20],
                          [300 if row == 0 else 250, row * 40, 400, row * 40 + 20]])
        grouped, safe = self.pipeline._group_detection_records(
            texts, [0.9] * len(texts), boxes)
        self.assertTrue(safe)
        flat = [m["text"] for line in grouped for m in line]
        self.assertEqual(
            flat,
            [f"L{i}" for i in range(24)] + [f"R{i}" for i in range(24)],
        )

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


class TwoColumnDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    @staticmethod
    def _col(x0, x1, rows, y0=0, step=40):
        return [{"x": x0, "x_max": x1, "y": y0 + r * step + 10,
                 "y_min": y0 + r * step, "y_max": y0 + r * step + 20}
                for r in range(rows)]

    def test_accepts_a_clean_two_column_layout(self):
        items = self._col(0, 180, 10) + self._col(250, 400, 10)
        gutter = self.pipeline._detect_two_columns(items, 0, 400)
        self.assertIsNotNone(gutter)
        self.assertTrue(180 < gutter < 250)

    def test_rejects_a_thin_second_side(self):
        # A persistent gutter can exist on a single-column page with one stray
        # far-right token, but 1-2 detections is not a genuine second column.
        items = self._col(0, 200, 20)
        items.append({"x": 500, "x_max": 560, "y": 10, "y_min": 0, "y_max": 20})
        self.assertIsNone(self.pipeline._detect_two_columns(items, 0, 800))

    def test_rejects_a_crossed_gutter(self):
        # Two clusters, but a wide line spans both -> not a persistent gutter
        # (this is the displaced-continuation / spanning-title shape, handled
        # by the single-column path instead).
        items = self._col(0, 180, 10) + self._col(250, 400, 10)
        items.append({"x": 0, "x_max": 400, "y": 500,
                      "y_min": 490, "y_max": 510})
        self.assertIsNone(self.pipeline._detect_two_columns(items, 0, 520))

    def test_rejects_a_second_side_that_does_not_span_the_page(self):
        # Right side is substantial in count but bunched in the top third --
        # not a full-height column, so not a two-column layout.
        items = self._col(0, 180, 12) + self._col(250, 400, 5, y0=0, step=15)
        self.assertIsNone(self.pipeline._detect_two_columns(items, 0, 480))


class RealSampleTwoColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()
        # Frozen from the debug artifact for samples/greenbook/
        # green_writer10_B2_1.jpg; no models or ignored outputs are needed.
        fixture = Path(__file__).parent / "fixtures" / "green_writer10_detections.json"
        detections = json.loads(fixture.read_text(encoding="utf-8"))
        cls.rec_texts = [d["text"] for d in detections]
        cls.rec_scores = [d["score"] for d in detections]
        cls.rec_boxes = [d["box"] for d in detections]

    def test_real_sample_gutter_splits_24_left_and_23_right_detections(self):
        items = [
            {"x": x0, "x_max": x1, "y": (y0 + y1) / 2,
             "y_min": y0, "y_max": y1}
            for x0, y0, x1, y1 in self.rec_boxes
        ]
        self.assertEqual(len(items), 47)
        page_top = min(item["y_min"] for item in items)
        page_bot = max(item["y_max"] for item in items)
        gutter = self.pipeline._detect_two_columns(items, page_top, page_bot)

        self.assertIsNotNone(gutter)
        self.assertGreaterEqual(gutter, 300)
        self.assertLessEqual(gutter, 340)
        left = [item for item in items if item["x_max"] <= gutter]
        right = [item for item in items if item["x"] >= gutter]
        self.assertEqual(len(left), 24)
        self.assertEqual(len(right), 23)

    def test_real_sample_reads_entire_left_column_before_right_column(self):
        grouped, safe = self.pipeline._group_detection_records(
            self.rec_texts, self.rec_scores, self.rec_boxes)
        self.assertTrue(safe)
        lines = [" ".join(member["text"] for member in line) for line in grouped]

        def line_index(substring):
            matches = [i for i, text in enumerate(lines) if substring in text]
            self.assertEqual(len(matches), 1, msg=f"Expected one line with {substring!r}")
            return matches[0]

        self.assertLess(line_index("switch(num)"), line_index("while (x <= 10)"))
        self.assertLess(line_index("sum += arr[i]"), line_index("} while(x"))
        # Guard every detection, including repeated braces and return lines,
        # so an interleave outside the distinctive anchors also fails.
        flat = [member for line in grouped for member in line]
        self.assertCountEqual([member["text"] for member in flat], self.rec_texts)
        self.assertEqual(
            [(member["x"] + member["x_max"]) / 2 < 321 for member in flat],
            [True] * 24 + [False] * 23,
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
        })


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


class DisplacedSeveranceTests(unittest.TestCase):
    # Geometry fixtures are shared at module level (see WRITER18_BOXES /
    # WRITER27_BOXES above) so BandedColumnDetectionTests exercises the same
    # real pages without duplicating them.
    WRITER18_BOXES = WRITER18_BOXES
    WRITER27_BOXES = WRITER27_BOXES

    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    @staticmethod
    def _line(*members):
        return {"members": [
            {"text": text, "x": x, "x_max": x_max, "score": 0.9}
            for text, x, x_max in members
        ]}

    @staticmethod
    def _texts(lines):
        return [[member["text"] for member in line["members"]]
                for line in lines]

    def test_severs_a_three_row_right_cluster_to_the_end(self):
        lines = [
            self._line(("L0", 0, 180), ("R0", 340, 440)),
            self._line(("L1", 0, 180), ("R1", 345, 445)),
            self._line(("L2", 0, 180), ("R2", 340, 440)),
            self._line(("L3", 0, 180)),
        ]
        lines[0]["metadata"] = {"row": 0}
        original_texts = self._texts(lines)

        result = self.pipeline._sever_displaced_regions(lines, 150)

        self.assertEqual(self._texts(result),
                         [["L0"], ["L1"], ["L2"], ["L3"],
                          ["R0"], ["R1"], ["R2"]])
        self.assertEqual(self._texts(lines), original_texts)
        self.assertIs(result[3], lines[3])
        self.assertIs(result[0]["metadata"], lines[0]["metadata"])
        self.assertIs(result[4]["metadata"], lines[0]["metadata"])
        for row in range(3):
            self.assertIs(result[row]["members"][0], lines[row]["members"][0])
            self.assertIs(result[row + 4]["members"][0], lines[row]["members"][1])

    def test_does_not_sever_a_two_row_cluster(self):
        lines = [
            self._line(("L0", 0, 180), ("R0", 340, 440)),
            self._line(("L1", 0, 180), ("R1", 345, 445)),
        ]

        self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)

    def test_does_not_sever_when_right_x0_not_aligned(self):
        lines = [
            self._line(("L0", 0, 180), ("R0", 340, 440)),
            self._line(("L1", 0, 180), ("R1", 600, 700)),
            self._line(("L2", 0, 180), ("R2", 340, 440)),
        ]

        self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)

    def test_small_internal_gap_is_not_a_right_fragment(self):
        lines = [self._line(("a", 0, 180), ("b", 190, 260))
                 for _ in range(3)]

        self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)

    def test_end_to_end_single_column_appends_displaced_block(self):
        texts = []
        boxes = []
        for row in range(5):
            texts.append(f"L{row}")
            # A wide header keeps the existing global-gutter trace inactive.
            boxes.append([0, row * 40, 500 if row == 0 else 180, row * 40 + 20])
            if 1 <= row <= 3:
                texts.append(f"R{row}")
                boxes.append([340, row * 40, 480, row * 40 + 20])

        lines, safe = self.pipeline._group_detection_records(
            texts, [0.9] * len(texts), boxes)

        self.assertTrue(safe)
        self.assertEqual(
            [member["text"] for line in lines for member in line],
            ["L0", "L1", "L2", "L3", "L4", "R1", "R2", "R3"])

    def _separated_rows(self, count=3):
        lines = []
        for row in range(count):
            for text, x, x_max in ((f"L{row}", 0, 180),
                                   (f"R{row}", 340, 440)):
                line = self._line((text, x, x_max))
                line["members"][0].update(
                    y=row * 40 + 10, y_min=row * 40, y_max=row * 40 + 20)
                line["metadata"] = {"label": text}
                lines.append(line)
        return lines

    def test_separated_three_row_cluster_preserves_original_left_lines(self):
        lines = self._separated_rows()
        result = self.pipeline._sever_displaced_regions(lines, 150)

        self.assertEqual(self._texts(result),
                         [["L0"], ["L1"], ["L2"], ["R0"], ["R1"], ["R2"]])
        for row in range(3):
            self.assertIs(result[row], lines[row * 2])
            self.assertIs(result[row + 3]["members"][0],
                          lines[row * 2 + 1]["members"][0])
            self.assertIs(result[row + 3]["metadata"], lines[row * 2 + 1]["metadata"])
        self.assertEqual(len(lines), 6)

    def test_separated_two_row_cluster_returns_original_list(self):
        lines = self._separated_rows(2)
        self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)

    def test_end_to_end_preseparated_cluster_without_wide_header(self):
        texts, boxes = [], []
        for row in range(5):
            texts.append(f"L{row}")
            boxes.append([0, row * 40, 180, row * 40 + 20])
            if 1 <= row <= 3:
                texts.append(f"R{row}")
                boxes.append([340, row * 40, 480, row * 40 + 20])

        grouped, safe = self.pipeline._group_detection_records(
            texts, [0.9] * len(texts), boxes)

        self.assertTrue(safe)
        self.assertEqual([m["text"] for line in grouped for m in line],
                         ["L0", "L1", "L2", "L3", "L4", "R1", "R2", "R3"])

    def test_invalid_or_incomplete_vertical_geometry_returns_original_list(self):
        def fused_rows():
            separated = self._separated_rows()
            return [{"members": separated[row * 2]["members"]
                     + separated[row * 2 + 1]["members"]} for row in range(3)]

        for fields in ({"y": float("nan")}, {"y_min": float("inf")},
                       {"y_max": float("-inf")}, {"y_max": 0},
                       {"y_min": 21}, {"y": 30}, {"y": "bad"},
                       {"y_max": None}, {"y_max": 1e308, "y_min": -1e308}):
            with self.subTest(fields=fields):
                lines = fused_rows()
                lines[0]["members"][0].update(fields)
                self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)
        for missing in ("y", "y_min", "y_max"):
            with self.subTest(missing=missing):
                lines = fused_rows()
                del lines[0]["members"][0][missing]
                self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)
        lines = fused_rows()
        for key in ("y", "y_min", "y_max"):
            del lines[0]["members"][0][key]
        self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)

    def test_unsafe_visual_sweep_returns_original_list(self):
        lines = self._separated_rows()
        with patch.object(self.pipeline, "_sweep_detection_records",
                          return_value=(None, None)) as sweep:
            self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)
        sweep.assert_called_once()

    def test_invalid_horizontal_geometry_or_width_returns_original_list(self):
        for fields in ({"x": float("nan")}, {"x_max": float("inf")},
                       {"x_max": 0}, {"x_max": -1}, {"x": None}):
            with self.subTest(fields=fields):
                lines = [self._line(("L", 0, 180), ("R", 340, 440))
                         for _ in range(3)]
                lines[0]["members"][0].update(fields)
                self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)
        for width in (None, float("nan"), float("inf"), 0, -1):
            with self.subTest(width=width):
                lines = self._separated_rows()
                self.assertIs(self.pipeline._sever_displaced_regions(lines, width), lines)

    def test_same_row_right_pieces_keep_text_and_member_identity(self):
        lines = self._separated_rows()
        for row in range(3):
            right = lines[row * 2 + 1]
            right["members"].append({**right["members"][0],
                                     "text": f"piece{row}", "x": 445, "x_max": 480})
        original = [member for line in lines for member in line["members"]]
        result = self.pipeline._sever_displaced_regions(lines, 150)

        self.assertEqual(self._texts(result),
                         [["L0"], ["L1"], ["L2"], ["R0", "piece0"],
                          ["R1", "piece1"], ["R2", "piece2"]])
        self.assertCountEqual([id(m) for line in result for m in line["members"]],
                              [id(m) for m in original])

    def test_crossed_zero_and_negative_shared_gutters_return_original_list(self):
        for left_end in (340, 360):
            with self.subTest(left_end=left_end):
                lines = [self._line(("L0", 0, 180), ("R0", 340, 400)),
                         self._line(("L1", 0, left_end), ("R1", 500, 560)),
                         self._line(("L2", 0, 180), ("R2", 340, 400))]
                self.assertIs(self.pipeline._sever_displaced_regions(lines, 150), lines)
        lines = [self._line(("L0", 0, 150), ("R0", 340, 440)),
                 self._line(("L1", 350, 400), ("R1", 570, 670)),
                 self._line(("L2", 0, 150), ("R2", 340, 440))]
        self.assertIs(self.pipeline._sever_displaced_regions(lines, 200), lines)

    def test_real_writer18_geometry_appends_expected_right_rows(self):
        texts = [str(i) for i in range(len(self.WRITER18_BOXES))]
        grouped, safe = self.pipeline._group_detection_records(
            texts, [0.9] * len(texts), self.WRITER18_BOXES)

        self.assertTrue(safe)
        self.assertEqual([[m["text"] for m in line] for line in grouped[-7:]],
                         [["5"], ["6", "8"], ["10"], ["11"], ["13"], ["15"], ["17"]])
        self.assertCountEqual([m["text"] for line in grouped for m in line], texts)

    def test_real_writer27_geometry_retains_baseline_grouping(self):
        texts = [str(i) for i in range(len(self.WRITER27_BOXES))]
        args = (texts, [0.9] * len(texts), self.WRITER27_BOXES)
        with patch.object(self.pipeline, "_sever_displaced_regions",
                          side_effect=lambda lines, _: lines):
            baseline = self.pipeline._group_detection_records(*args)
        self.assertEqual(self.pipeline._group_detection_records(*args), baseline)

    def test_real_two_column_page_never_calls_severance_helper(self):
        fixture = Path(__file__).parent / "fixtures" / "green_writer10_detections.json"
        detections = json.loads(fixture.read_text(encoding="utf-8"))
        with patch.object(self.pipeline, "_sever_displaced_regions",
                          wraps=self.pipeline._sever_displaced_regions) as sever:
            _grouped, safe = self.pipeline._group_detection_records(
                [d["text"] for d in detections], [d["score"] for d in detections],
                [d["box"] for d in detections])
        self.assertTrue(safe)
        sever.assert_not_called()


class BandedColumnDetectionTests(unittest.TestCase):
    """Pure-geometry unit tests for _detect_banded_column: a persistent
    right-side block occupying a contiguous y-band with a clean uncrossed
    gutter WITHIN that band is read left column fully, then right column fully
    -- even when the block spans less than half the page and a stray wide line
    elsewhere bridges the full-page x-projection. Grade-safety: any
    degenerate/ambiguous geometry returns None (today's behavior). See
    docs/superpowers/specs/2026-09-12-banded-column-detection-design.md."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    @staticmethod
    def _items(boxes):
        return [{"x": float(x0), "x_max": float(x1), "y": (y0 + y1) / 2.0,
                 "y_min": float(y0), "y_max": float(y1)}
                for x0, y0, x1, y1 in boxes]

    def _detect(self, boxes):
        """Build items and call the detector the way _group_detection_records
        does (median box width, 60%-of-median-height line tolerance)."""
        items = self._items(boxes)
        widths = sorted(it["x_max"] - it["x"] for it in items)
        heights = sorted(it["y_max"] - it["y_min"] for it in items)
        median_width = widths[len(widths) // 2] if widths else 0.0
        median_h = heights[len(heights) // 2] if heights else 0.0
        line_tol = max(median_h * 0.6, 1.0)
        page_top = min(it["y_min"] for it in items)
        page_bot = max(it["y_max"] for it in items)
        result = self.pipeline._detect_banded_column(
            items, page_top, page_bot, median_width, line_tol)
        return items, result

    def test_writer18_bands_the_top_right_block(self):
        items, result = self._detect(WRITER18_BOXES)
        self.assertIsNotNone(result)
        gutter, left, right = result
        # Gutter sits in the clean 248px band between left content (max x1=550)
        # and the right cluster (min x0=798); the stray y~977 wide line that
        # bridges the full-page projection lies OUTSIDE the band and is ignored.
        self.assertTrue(550 < gutter < 798, msg=f"gutter={gutter}")
        idx_of = {id(it): i for i, it in enumerate(items)}
        right_idx = {idx_of[id(it)] for it in right}
        left_idx = {idx_of[id(it)] for it in left}
        expected_right = {i for i, b in enumerate(WRITER18_BOXES) if b[0] >= 798}
        self.assertEqual(len(expected_right), 13)
        self.assertEqual(right_idx, expected_right)
        self.assertEqual(left_idx, set(range(len(WRITER18_BOXES))) - expected_right)
        self.assertEqual(len(left), 26)
        # Concatenating left then right places all 13 right boxes last, in
        # ascending index order -- the left-fully-then-right-fully rule.
        order = [idx_of[id(it)] for it in left + right]
        self.assertEqual(order[-13:], sorted(expected_right))

    def test_writer27_is_not_banded(self):
        # green_writer27_B1_3 has no persistent right column separated by a
        # clean gutter, so no banded split -> today's behavior (0.342).
        _items, result = self._detect(WRITER27_BOXES)
        self.assertIsNone(result)

    def test_single_wide_line_does_not_band(self):
        # A normal single column plus one wide bridging line: the wide line's
        # x0 is on the left, so there is no persistent right cluster.
        boxes = [[20, r * 40, 200, r * 40 + 20] for r in range(6)]
        boxes.append([20, 240, 900, 260])
        _items, result = self._detect(boxes)
        self.assertIsNone(result)

    def test_two_row_right_cluster_is_below_min_band_rows(self):
        # A clean right cluster on only 2 rows must NOT band-split
        # (MIN_BAND_ROWS = 3); this is the green_writer27 rule at unit level.
        left = [[0, r * 40, 180, r * 40 + 20] for r in range(6)]
        right = [[400, 0, 520, 20], [400, 200, 520, 220]]
        _items, result = self._detect(left + right)
        self.assertIsNone(result)

    def test_crossed_gutter_is_not_banded(self):
        # A member straddling the band collapses the gutter (no clean,
        # uncrossed separation within the band) -> None.
        left = [[0, r * 40, 100, r * 40 + 20] for r in range(4)]
        right = [[400, 0, 500, 20], [400, 40, 500, 60], [400, 80, 500, 100]]
        straddle = [[50, 40, 450, 60]]
        _items, result = self._detect(left + right + straddle)
        self.assertIsNone(result)

    def test_normal_single_column_is_not_banded(self):
        # Mild indentation, one column: the cluster spans the whole page, so
        # there is no left complement and no banded split.
        boxes = [[20 + (r % 3) * 15, r * 40, 220, r * 40 + 20] for r in range(8)]
        _items, result = self._detect(boxes)
        self.assertIsNone(result)

    def test_too_few_items_is_not_banded(self):
        # Fewer than 2 * MIN_BAND_ROWS detections cannot form two persistent
        # columns.
        boxes = [[0, 0, 100, 20], [400, 0, 500, 20], [0, 40, 100, 60],
                 [400, 40, 500, 60], [0, 80, 100, 100]]
        _items, result = self._detect(boxes)
        self.assertIsNone(result)


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
        lines = rbnode_reassembly_lines()

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
        lines = compressor_reassembly_lines()

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

    def test_relocates_past_a_multiline_struct_in_the_main_flow(self):
        # Real scenario (reassemble_example_isolate_2): a merge function whose
        # else-branch was written in the top-right margin, so in the y-sweep it
        # appears early -- interleaved with a struct written across several
        # lines that ends in a standalone `};` in the main flow. The `};`
        # closing the struct is a definition close, not a control close -- the
        # displaced executable block can't belong inside a struct -- so the
        # guard must let this reorder through. Before the definition-close
        # exemption, the standalone `};` blocked every such page.
        lines = [
            _line("Question 1:"),
            _line("} else {", severed=True),
            _line("struct node {"),
            _line("l2->next = merge_lists(l1, l2->next, cmp);", severed=True),
            _line("struct node *next, *prev;"),
            _line("l2->next->prev = l2;", severed=True),
            _line("void *data;"),
            _line("l2->prev = NULL;", severed=True),
            _line("};"),
            _line("return l2;", severed=True),
            _line("}", severed=True),
            _line("}", severed=True),
            _line("struct node *merge_lists(struct node *l1, struct node *l2,"
                  " int (*cmp)(void*, void*)) {"),
            _line("if (!l1) return l2;"),
            _line("if (!l2) return l1;"),
            _line("if (cmp(l1->data, l2->data) <= 0) {"),
            _line("l1->next = merge_lists(l1->next, l2, cmp);"),
            _line("l1->next->prev = l1;"),
            _line("l1->prev = NULL;"),
            _line("return l1;"),
        ]

        result = self.pipeline._reassemble_displaced_regions(lines)

        self.assertEqual(
            self.texts_of(result),
            [
                "Question 1:",
                "struct node {",
                "struct node *next, *prev;",
                "void *data;",
                "};",
                "struct node *merge_lists(struct node *l1, struct node *l2,"
                " int (*cmp)(void*, void*)) {",
                "if (!l1) return l2;",
                "if (!l2) return l1;",
                "if (cmp(l1->data, l2->data) <= 0) {",
                "l1->next = merge_lists(l1->next, l2, cmp);",
                "l1->next->prev = l1;",
                "l1->prev = NULL;",
                "return l1;",
                "} else {",
                "l2->next = merge_lists(l1, l2->next, cmp);",
                "l2->next->prev = l2;",
                "l2->prev = NULL;",
                "return l2;",
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
        # winning normal contains its own plain "}" (delta -1, a control
        # close, NOT a definition close), so reject it.
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


def rbnode_reassembly_lines():
    return [
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


def compressor_reassembly_lines():
    return [
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


def small_reassembly_lines():
    return [
        _line("struct S { int x; };"),
        _line("}", severed=True),
        _line("int main() {"),
    ]


def load_green_writer10_fixture():
    fixture = Path(__file__).parent / "fixtures" / "green_writer10_detections.json"
    detections = json.loads(fixture.read_text(encoding="utf-8"))
    return (
        [d["text"] for d in detections],
        [d["score"] for d in detections],
        [d["box"] for d in detections],
    )


def demo_reassembly(case_name):
    pipeline = load_pipeline_without_models()
    cases = {
        "rbnode": ("RBNode rotate_rb", rbnode_reassembly_lines),
        "compressor": ("Compressor pack_flags", compressor_reassembly_lines),
        "small": ("Small displaced closer", small_reassembly_lines),
    }
    selected = cases.keys() if case_name == "all" else [case_name]

    for position, name in enumerate(selected):
        if name not in cases:
            valid = ", ".join(sorted([*cases, "all"]))
            raise SystemExit(f"Unknown reassembly demo '{name}'. Use one of: {valid}")
        title, build_lines = cases[name]
        lines = build_lines()

        if position:
            print()
        print(f"DEMO: {title}")
        print("BEFORE: synthetic detected order")
        for index, line in enumerate(lines, 1):
            marker = "  <- displaced" if line.get("severed_by_gap") else ""
            print(f"{index}. {line['members'][0]['text']}{marker}")

        ordered = pipeline._reassemble_displaced_regions(lines)

        print("\nAFTER: reassembled continuation")
        for index, line in enumerate(ordered, 1):
            print(f"{index}. {line['members'][0]['text']}")


def demo_two_column():
    pipeline = load_pipeline_without_models()
    rec_texts, rec_scores, rec_boxes = load_green_writer10_fixture()
    items = [
        {
            "text": text,
            "x": x0,
            "x_max": x1,
            "y": (y0 + y1) / 2,
            "y_min": y0,
            "y_max": y1,
        }
        for text, (x0, y0, x1, y1) in zip(rec_texts, rec_boxes)
    ]
    page_top = min(item["y_min"] for item in items)
    page_bot = max(item["y_max"] for item in items)
    gutter = pipeline._detect_two_columns(items, page_top, page_bot)
    left = [item for item in items if item["x_max"] <= gutter]
    right = [item for item in items if item["x"] >= gutter]

    print("DEMO: green_writer10_B2_1 two-column split")
    print(f"GUTTER: x={gutter:.1f}")
    print(f"LEFT COLUMN: {len(left)} detections")
    for index, item in enumerate(left, 1):
        print(f"{index}. {item['text']}")

    print(f"\nRIGHT COLUMN: {len(right)} detections")
    for index, item in enumerate(right, 1):
        print(f"{index}. {item['text']}")

    grouped, geometry_safe = pipeline._group_detection_records(
        rec_texts, rec_scores, rec_boxes)
    ordered = [member for line in grouped for member in line]

    print("\nAFTER: final grouped reading order")
    print(f"geometry_safe={geometry_safe}")
    print("LEFT COLUMN FIRST")
    for index, member in enumerate(ordered[:len(left)], 1):
        print(f"{index}. {member['text']}")
    print("\nRIGHT COLUMN SECOND")
    for index, member in enumerate(ordered[len(left):], 1):
        print(f"{index}. {member['text']}")


class IndentationReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    def test_assign_indent_levels_measures_from_column_left(self):
        p = self.pipeline
        unit = p.INDENT_STEP_CHARS * 100.0  # char_width == 100
        lines = [
            {"members": [{"x": 50.0, "x_max": 150.0, "text": "a"}]},
            {"members": [{"x": 50.0 + unit, "x_max": 150.0 + unit, "text": "b"}]},
            {"members": [{"x": 50.0 + 2 * unit, "x_max": 150.0 + 2 * unit,
                          "text": "c"}]},
        ]
        p._assign_indent_levels(lines, 100.0)
        self.assertEqual(
            [line["members"][0]["indent"] for line in lines], [0, 1, 2]
        )

    def test_assign_indent_levels_clamps_to_max(self):
        p = self.pipeline
        unit = p.INDENT_STEP_CHARS * 100.0
        far = 50.0 + (p.MAX_INDENT_LEVELS + 5) * unit
        lines = [
            {"members": [{"x": 50.0, "x_max": 150.0, "text": "a"}]},
            {"members": [{"x": far, "x_max": far + 100.0, "text": "b"}]},
        ]
        p._assign_indent_levels(lines, 100.0)
        self.assertEqual(lines[1]["members"][0]["indent"], p.MAX_INDENT_LEVELS)

    def test_assign_indent_levels_degenerate_width_is_flat(self):
        p = self.pipeline
        lines = [
            {"members": [{"x": 50.0, "x_max": 150.0, "text": "a"}]},
            {"members": [{"x": 9999.0, "x_max": 10099.0, "text": "b"}]},
        ]
        p._assign_indent_levels(lines, 0.0)  # zero median width -> no unit
        self.assertEqual(
            [line["members"][0]["indent"] for line in lines], [0, 0]
        )

    def test_single_column_text_carries_reconstructed_indentation(self):
        p = self.pipeline
        unit = p.INDENT_STEP_CHARS * 100.0   # boxes 100 wide, text len 1 -> char_width 100
        texts = ["a", "b", "c"]
        boxes = [
            [50, 0, 150, 20],
            [50 + unit, 40, 150 + unit, 60],
            [50 + 2 * unit, 80, 150 + 2 * unit, 100],
        ]
        structured = p._group_structured_lines(texts, [0.9] * 3, boxes, 1000)
        ind = p.INDENT_STRING
        self.assertEqual(
            [line["text"] for line in structured],
            ["a", ind + "b", ind * 2 + "c"],
        )

    def test_flush_left_lines_stay_unindented(self):
        p = self.pipeline
        texts = ["a", "b"]
        boxes = [[50, 0, 150, 20], [50, 40, 150, 60]]
        structured = p._group_structured_lines(texts, [0.9] * 2, boxes, 1000)
        self.assertEqual([line["text"] for line in structured], ["a", "b"])

    def test_two_columns_indent_from_each_columns_own_margin(self):
        p = self.pipeline
        unit = p.INDENT_STEP_CHARS * 25.0   # boxes 50 wide, text len 2 -> char_width 25
        texts, boxes = [], []
        for row in range(6):
            left_x = 20 if row < 3 else 20 + unit    # left col: flush, then +1
            right_x = 300 if row < 3 else 300 + unit  # right col: flush, then +1
            texts.extend([f"L{row}", f"R{row}"])
            boxes.extend([
                [left_x, row * 30, left_x + 50, row * 30 + 20],
                [right_x, row * 30, right_x + 50, row * 30 + 20],
            ])
        grouped, safe = p._group_detection_records(
            texts, [0.9] * len(texts), boxes)
        self.assertTrue(safe)
        flat = [member["text"] for line in grouped for member in line]
        self.assertEqual(
            flat, [f"L{i}" for i in range(6)] + [f"R{i}" for i in range(6)])
        indents = [line[0]["indent"] for line in grouped]
        # Left col measured from x=20, right col from x=300 -- NOT from page-left.
        self.assertEqual(indents, [0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1])

    def test_unsafe_geometry_falls_back_to_flat_text(self):
        p = self.pipeline
        # A malformed box (too short) forces the geometry-unsafe fallback:
        # one detection per line, original order, and no reconstructed indent.
        texts = ["first", "second"]
        boxes = [[1, 2, 3], [10, 20, 30, 40]]
        structured = p._group_structured_lines(texts, [0.2, 0.3], boxes, 1000)
        self.assertEqual(
            [line["text"] for line in structured], ["first", "second"])


class VerticalSpacingReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_pipeline_without_models()

    @staticmethod
    def sline(text, y_center, h=0.02):
        return {"text": text, "y_min": y_center - h / 2, "y_max": y_center + h / 2}

    def test_even_spacing_inserts_no_blanks(self):
        p = self.pipeline
        lines = [self.sline("a", 0.10), self.sline("b", 0.20),
                 self.sline("c", 0.30), self.sline("d", 0.40)]
        self.assertEqual(p._join_lines_with_vertical_gaps(lines), "a\nb\nc\nd")

    def test_double_gap_inserts_one_blank(self):
        p = self.pipeline
        lines = [self.sline("a", 0.10), self.sline("b", 0.20),
                 self.sline("c", 0.30), self.sline("d", 0.50)]
        self.assertEqual(p._join_lines_with_vertical_gaps(lines), "a\nb\nc\n\nd")

    def test_large_gap_is_clamped(self):
        p = self.pipeline
        lines = [self.sline("a", 0.10), self.sline("b", 0.20),
                 self.sline("c", 0.30), self.sline("d", 0.80)]
        expected = "a\nb\nc" + "\n" * (p.MAX_BLANK_LINES + 1) + "d"
        self.assertEqual(p._join_lines_with_vertical_gaps(lines), expected)

    def test_column_seam_inserts_no_blank(self):
        p = self.pipeline
        lines = [self.sline("L0", 0.10), self.sline("L1", 0.20),
                 self.sline("L2", 0.30), self.sline("R0", 0.10),
                 self.sline("R1", 0.20), self.sline("R2", 0.30)]
        self.assertEqual(
            p._join_lines_with_vertical_gaps(lines), "L0\nL1\nL2\nR0\nR1\nR2")

    def test_missing_geometry_stays_compact(self):
        p = self.pipeline
        lines = [{"text": "a", "y_min": None, "y_max": None},
                 {"text": "b", "y_min": None, "y_max": None}]
        self.assertEqual(p._join_lines_with_vertical_gaps(lines), "a\nb")

    def test_empty_input(self):
        self.assertEqual(self.pipeline._join_lines_with_vertical_gaps([]), "")

    def test_end_to_end_boxes_produce_blank_lines(self):
        p = self.pipeline
        texts = ["a", "b", "c", "d"]
        boxes = [[0, 0, 100, 20], [0, 40, 100, 60],
                 [0, 80, 100, 100], [0, 240, 100, 260]]
        structured = p._group_structured_lines(texts, [0.9] * 4, boxes, 1000)
        result = p._join_lines_with_vertical_gaps(structured)
        expected = "a\nb\nc" + "\n" * (p.MAX_BLANK_LINES + 1) + "d"
        self.assertEqual(result, expected)


if __name__ == "__main__":
    if "--demo-reassembly" in sys.argv:
        flag_index = sys.argv.index("--demo-reassembly")
        case = sys.argv[flag_index + 1] if len(sys.argv) > flag_index + 1 else "rbnode"
        del sys.argv[flag_index:flag_index + 2]
        demo_reassembly(case)
        raise SystemExit(0)
    if "--demo-two-column" in sys.argv:
        sys.argv.remove("--demo-two-column")
        demo_two_column()
        raise SystemExit(0)
    unittest.main()
