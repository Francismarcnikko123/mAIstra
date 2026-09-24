"""Real-photo margin replays, covering measured geometric calibration.

IDs below are zero-based indices into the unedited detection fixtures.
Expected rows were annotated against the photographs, not derived by grouping.
B's ``dd;`` (ID 7) and C's ``od;`` (ID 0) are fabric false positives. They
remain in every replay: layout must never discard recognition payloads.
See reports/2026-09-13-real-margin-validation.md for calibration evidence.
"""
from collections import Counter
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from core import layout
from core.layout import columns


FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_ROWS = {
    "A": [[0], [2], [4], [6], [8], [9], [11], [12], [13], [14],
          [1], [3], [5], [7], [10]],
    "B": [[1], [3], [7, 5], [8], [9], [10], [0], [2], [4], [6]],
    "C": [[0], [2], [4], [6], [8], [10], [11], [1], [3], [5], [7], [9]],
}
BRACE_COUNTS = {"A": (2, 2), "B": (3, 3), "C": (3, 3)}


def detections(letter):
    return json.loads((FIXTURES / f"writerX_margin{letter}_detections.json")
                      .read_text(encoding="utf-8"))


def group(records):
    return layout._group_detection_records(
        *[[d[key] for d in records] for key in ("text", "score", "box")])


def detection_key(record):
    return record["text"], record["score"], tuple(record["box"])


def member_key(member):
    return (member["text"], member["score"],
            (member["x"], member["y_min"], member["x_max"], member["y_max"]))


def row_ids(rows, records):
    indices = {detection_key(d): i for i, d in enumerate(records)}
    return [[indices[member_key(m)] for m in row] for row in rows]


class RealMarginLayoutTests(unittest.TestCase):
    def assert_geometric_order(self, letter):
        records = detections(letter)
        # Explicitly disable C-structure reasoning: only geometry may order
        # these pages. Preserve actual recognition text, including its errors.
        with patch.object(layout, "_reassemble_displaced_regions",
                          side_effect=lambda lines: lines):
            rows, safe = group(records)
        self.assertTrue(safe)
        self.assertEqual(row_ids(rows, records), EXPECTED_ROWS[letter])

    def test_margin_a_geometric_left_then_margin(self):
        self.assert_geometric_order("A")

    def test_margin_b_geometric_left_then_margin(self):
        self.assert_geometric_order("B")

    def test_margin_c_geometric_left_then_margin(self):
        self.assert_geometric_order("C")

    def test_grouping_preserves_every_detection_verbatim(self):
        for letter in EXPECTED_ROWS:
            with self.subTest(photo=letter):
                records = detections(letter)
                rows, safe = group(records)
                self.assertTrue(safe)
                self.assertEqual(
                    Counter(member_key(m) for row in rows for m in row),
                    Counter(detection_key(d) for d in records))

    def test_photo_braces_survived_recognition(self):
        # Counts include both initializer braces in B. The report matches
        # each brace to its handwritten line; counts alone cannot do that.
        for letter, expected in BRACE_COUNTS.items():
            with self.subTest(photo=letter):
                text = "\n".join(d["text"] for d in detections(letter))
                self.assertEqual((text.count("{"), text.count("}")), expected)

    def test_shipped_mechanisms_and_brace_noop(self):
        for letter in EXPECTED_ROWS:
            with self.subTest(photo=letter):
                events = []
                brace_impl = layout._reassemble_displaced_regions
                def brace(lines):
                    result = brace_impl(lines)
                    events.append(result == lines)
                    return result
                with (patch.object(layout, "_detect_two_columns",
                                   wraps=layout._detect_two_columns) as two,
                      patch.object(layout, "_detect_banded_column",
                                   wraps=layout._detect_banded_column) as band,
                      patch.object(layout, "_sever_displaced_regions",
                                   wraps=layout._sever_displaced_regions) as sever,
                      patch.object(layout, "_reassemble_displaced_regions",
                                   side_effect=brace)):
                    rows, safe = group(detections(letter))
                self.assertTrue(safe)
                two.assert_called_once()
                self.assertEqual(band.call_count, 0 if letter == "A" else 1)
                sever.assert_not_called()
                self.assertEqual(events, [True, True])
                self.assertEqual(row_ids(rows, detections(letter)), EXPECTED_ROWS[letter])

    def test_lower_region_seed_threshold_does_not_change_real_order(self):
        for band_multiplier in (1.5, 0.5):
            with patch.object(columns, "BAND_GUTTER_MIN_MULTIPLIER", band_multiplier):
                for letter in EXPECTED_ROWS:
                    records = detections(letter)
                    baseline = group(records)
                    for multiplier in (0.0, 0.1, 0.25, 0.5):
                        with self.subTest(photo=letter, region=multiplier,
                                          band=band_multiplier):
                            with patch.object(layout, "REGION_GAP_MULTIPLIER", multiplier):
                                self.assertEqual(group(records), baseline)

    def test_banded_gutter_keeps_pixel_floor_and_half_width_boundary(self):
        for width, gap, accepts in ((80, 59, False), (80, 60, True),
                                    (200, 99, False), (200, 100, True)):
            with self.subTest(width=width, gap=gap):
                boxes = [[0, r * 40, 500 if r == 0 else width, r * 40 + 20]
                         for r in range(4)]
                boxes += [[500 + gap, r * 40, 500 + gap + width, r * 40 + 20]
                          for r in range(3)]
                items = [{"x": x0, "x_max": x1, "y_min": y0, "y_max": y1,
                          "y": (y0 + y1) / 2} for x0, y0, x1, y1 in boxes]
                median_width = sorted(b[2] - b[0] for b in boxes)[len(boxes) // 2]
                self.assertEqual(median_width, width)
                result = layout._detect_banded_column(items, median_width, 12)
                self.assertEqual(result is not None, accepts)

    def test_old_banded_threshold_reproduces_b_and_c_order_failures(self):
        with patch.object(columns, "BAND_GUTTER_MIN_MULTIPLIER", 1.5):
            for letter in ("B", "C"):
                with self.subTest(photo=letter):
                    records = detections(letter)
                    rows, safe = group(records)
                    self.assertTrue(safe)
                    self.assertNotEqual(row_ids(rows, records), EXPECTED_ROWS[letter])


if __name__ == "__main__":
    unittest.main()
