"""Production continuation-association rules and safety boundaries."""

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from core import layout
from core.continuation import associate_continuation
from evaluators.evaluate_continuation_development import replay


FIXTURES = Path(__file__).parent / "fixtures"


def detection(text, x, y):
    return {"text": text, "score": .95, "box": [x, y, x + 180, y + 20]}


def baseline_ids(records):
    rows, _events = replay(records)
    return [identifier for row in rows for identifier in row]


class ContinuationAssociationTests(unittest.TestCase):
    def test_three_real_local_continuations_match_annotations(self):
        annotations = json.loads(
            (FIXTURES / "writerX_development_annotations.json").read_text()
        )
        for example in (5, 6, 8):
            with self.subTest(example=example):
                records = json.loads(
                    (FIXTURES / f"writerX_page{example:02d}_detections.json").read_text()
                )
                untouched = copy.deepcopy(records)
                result = associate_continuation(records, baseline_ids(records))
                page = next(
                    page for page in annotations["pages"]
                    if page["example"] == example
                )
                expected = [
                    identifier
                    for row in page["expected_detection_rows"]
                    for identifier in row
                ]
                self.assertEqual(result["ordered_ids"], expected)
                self.assertEqual(records, untouched)
                self.assertEqual(
                    sum(relation["decision"] == "continuation"
                        for relation in result["relations"]),
                    2,
                )

    def test_distinct_question_headings_support_independence(self):
        records = [
            detection("Question 1:", 0, 0),
            detection("int f() {", 0, 40),
            detection("return 1; }", 0, 80),
            detection("Question 2:", 400, 0),
            detection("int g() {", 400, 40),
            detection("return 2; }", 400, 80),
        ]
        result = associate_continuation(records, list(range(len(records))))
        self.assertEqual(result["relations"][0]["decision"], "independent")
        self.assertFalse(result["changed_order"])

    def test_two_unnumbered_functions_abstain(self):
        records = [
            detection("int f() {", 0, 0),
            detection("return 1; }", 0, 40),
            detection("int g() {", 400, 0),
            detection("return 2; }", 400, 40),
        ]
        result = associate_continuation(records, list(range(len(records))))
        self.assertEqual(result["relations"][0]["decision"], "ambiguous")
        self.assertFalse(result["changed_order"])

    def test_misread_closer_cannot_authorize_move(self):
        records = [
            detection("int f() {", 0, 0),
            detection("work();", 0, 40),
            detection("return 1;", 400, 0),
            detection(")", 400, 40),
        ]
        result = associate_continuation(records, list(range(len(records))))
        self.assertFalse(any(
            relation["decision"] == "continuation"
            for relation in result["relations"]
        ))

    def test_braces_in_comments_and_literals_do_not_open_scope(self):
        for text in ("/* { */", 'puts("{");'):
            with self.subTest(text=text):
                records = [
                    detection(text, 0, 0),
                    detection("work();", 0, 40),
                    detection("return 1;", 400, 0),
                    detection("}", 400, 40),
                ]
                result = associate_continuation(
                    records, list(range(len(records)))
                )
                self.assertFalse(any(
                    relation["decision"] == "continuation"
                    for relation in result["relations"]
                ))

    def test_unterminated_literal_abstains(self):
        records = [
            detection("int f() {", 0, 0),
            detection('puts("oops', 0, 40),
            detection("return 1;", 400, 0),
            detection("}", 400, 40),
        ]
        result = associate_continuation(records, list(range(len(records))))
        self.assertFalse(any(
            relation["decision"] == "continuation"
            for relation in result["relations"]
        ))

    def test_invalid_geometry_preserves_baseline(self):
        records = [detection("x;", 0, 0), detection("}", 400, 40)]
        records[0]["box"][0] = float("nan")
        baseline = [1, 0]
        result = associate_continuation(records, baseline)
        self.assertEqual(result["ordered_ids"], baseline)
        self.assertEqual(result["reasons"], ["invalid_detection_geometry_or_payload"])

    def test_scale_invariance(self):
        records = json.loads(
            (FIXTURES / "writerX_page05_detections.json").read_text()
        )
        baseline = baseline_ids(records)
        before = associate_continuation(records, baseline)
        for factor in (.5, 2):
            scaled = copy.deepcopy(records)
            for record in scaled:
                record["box"] = [value * factor for value in record["box"]]
            after = associate_continuation(scaled, baseline)
            self.assertEqual(after["ordered_ids"], before["ordered_ids"])
            self.assertEqual(
                [relation["decision"] for relation in after["relations"]],
                [relation["decision"] for relation in before["relations"]],
            )

    def test_repeated_payloads_keep_distinct_ids(self):
        records = [detection("}", 0, 0), detection("}", 0, 0)]
        result = associate_continuation(records, [0, 1])
        self.assertEqual(sorted(result["ordered_ids"]), [0, 1])

    def test_narrow_local_gap_abstains(self):
        records = [
            detection("int f() {", 0, 0),
            detection("work();", 0, 40),
            detection("return 1;", 190, 0),
            detection("}", 190, 40),
        ]
        result = associate_continuation(records, list(range(len(records))))
        self.assertEqual(
            result["relations"][0]["reasons"],
            ["insufficient_local_gutter"],
        )
        self.assertFalse(result["changed_order"])

    def test_competing_right_blocks_abstain(self):
        records = [
            detection("int f() { {", 0, 0),
            detection("work();", 0, 40),
            detection("work();", 0, 80),
            detection("work();", 0, 120),
            detection("work();", 0, 160),
            detection("return 1;", 400, 0),
            detection("}", 400, 40),
            detection("return 2;", 400, 120),
            detection("}", 400, 160),
        ]
        baseline = list(range(len(records)))
        result = associate_continuation(records, baseline)
        self.assertEqual(len(result["relations"]), 2)
        self.assertTrue(all(
            relation["reasons"] == ["competing_blocks_for_insertion_point"]
            for relation in result["relations"]
        ))
        self.assertEqual(result["ordered_ids"], baseline)

    def test_invalid_baseline_order_uses_natural_safe_fallback(self):
        records = [detection("x;", 0, 0), detection("y;", 400, 0)]
        result = associate_continuation(records, [0, 0])
        self.assertEqual(result["ordered_ids"], [0, 1])
        self.assertEqual(result["reasons"], ["invalid_baseline_order"])


class ContinuationLayoutFinalizerTests(unittest.TestCase):
    @staticmethod
    def member(text, x, y):
        return {
            "text": text,
            "score": .95,
            "x": x,
            "x_max": x + 20,
            "y": y + 10,
            "y_min": y,
            "y_max": y + 20,
        }

    def test_moves_only_whole_visual_rows(self):
        members = [
            self.member("a", 0, 0),
            self.member("b", 30, 0),
            self.member("c", 0, 40),
            self.member("d", 0, 80),
        ]
        rows = [[members[0], members[1]], [members[2]], [members[3]]]
        identities = {id(member): index for index, member in enumerate(members)}
        records = [
            detection(member["text"], member["x"], member["y_min"])
            for member in members
        ]
        with patch.object(layout, "associate_continuation", return_value={
            "ordered_ids": [2, 0, 1, 3],
        }):
            result = layout._associate_continuation(rows, records, identities)
        self.assertEqual(
            result,
            [[members[2]], [members[0], members[1]], [members[3]]],
        )
        self.assertEqual(
            {id(member) for row in result for member in row},
            {id(member) for member in members},
        )

    def test_rejects_proposal_that_splits_a_visual_row(self):
        members = [
            self.member("a", 0, 0),
            self.member("b", 30, 0),
            self.member("c", 0, 40),
        ]
        rows = [[members[0], members[1]], [members[2]]]
        identities = {id(member): index for index, member in enumerate(members)}
        records = [
            detection(member["text"], member["x"], member["y_min"])
            for member in members
        ]
        with patch.object(layout, "associate_continuation", return_value={
            "ordered_ids": [0, 2, 1],
        }):
            result = layout._associate_continuation(rows, records, identities)
        self.assertIs(result, rows)

    def test_rejects_incomplete_or_duplicate_proposal(self):
        members = [self.member("a", 0, 0), self.member("b", 0, 40)]
        rows = [[members[0]], [members[1]]]
        identities = {id(member): index for index, member in enumerate(members)}
        records = [
            detection(member["text"], member["x"], member["y_min"])
            for member in members
        ]
        for proposed in ([0], [0, 0], [0, 1, 2]):
            with self.subTest(proposed=proposed), patch.object(
                    layout, "associate_continuation",
                    return_value={"ordered_ids": proposed}):
                self.assertIs(
                    layout._associate_continuation(rows, records, identities),
                    rows,
                )


if __name__ == "__main__":
    unittest.main()
