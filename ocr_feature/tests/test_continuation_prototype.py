import copy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

from evaluators.continuation_prototype import associate

FIXTURES = Path(__file__).parent / "fixtures"


def detection(text, x, y):
    return {"text": text, "score": .95, "box": [x, y, x + 180, y + 20]}


class ContinuationPrototypeTests(unittest.TestCase):
    def test_reserved_evaluation_rejects_changed_rules_before_reading_labels(self):
        from evaluators import evaluate_continuation_reserved as reserved
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'reports').mkdir()
            (root / 'rule.py').write_text('changed')
            (root / 'reports/2026-09-14-offline-association-freeze.json').write_text(json.dumps(
                dict(prototype_path='rule.py', prototype_sha256='old')))
            with patch.object(reserved, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Rules changed after freeze'):
                    reserved.evaluate()

    def test_association_score_detects_wrong_answer_link(self):
        from evaluators.evaluate_continuation_development import score_association
        page = dict(blocks=[dict(id='left', answer_id='q1', detection_ids=[0, 1]),
                            dict(id='right', answer_id='q2', detection_ids=[2, 3])],
                    continuation_edges=[])
        prediction = dict(relations=[dict(decision='continuation',
                          target_detection_ids=[0, 1], source_detection_ids=[2, 3])])
        result = score_association(page, prediction)
        self.assertEqual(result['false_cross_answer_links'], 1)
        self.assertEqual(result['false_continuation_links'], 1)
        self.assertEqual(result['continuation_precision'], 0)

    def test_three_real_local_continuations(self):
        annotations = json.loads((FIXTURES / "writerX_development_annotations.json").read_text())
        for n in (5, 6, 8):
            with self.subTest(example=n):
                records = json.loads((FIXTURES / f"writerX_page{n:02d}_detections.json").read_text())
                untouched = copy.deepcopy(records)
                result = associate(records)
                expected = next(p for p in annotations["pages"] if p["example"] == n)
                self.assertEqual(result["ordered_ids"], [i for row in expected["expected_detection_rows"] for i in row])
                self.assertEqual(records, untouched)
                self.assertEqual(sum(r["decision"] == "continuation" for r in result["relations"]), 2)

    def test_different_question_headings_support_independence(self):
        records = [detection('Question 1:', 0, 0), detection('int f() {', 0, 40),
                   detection('return 1; }', 0, 80), detection('Question 2:', 400, 0),
                   detection('int g() {', 400, 40), detection('return 2; }', 400, 80)]
        result = associate(records)
        self.assertEqual(result['relations'][0]['decision'], 'independent')

    def test_two_unnumbered_functions_do_not_prove_answer_membership(self):
        records = [detection('int f() {', 0, 0), detection('return 1; }', 0, 40),
                   detection('int g() {', 400, 0), detection('return 2; }', 400, 40)]
        result = associate(records)
        self.assertEqual(result['relations'][0]['decision'], 'ambiguous')

    def test_misread_closer_cannot_authorize_a_move(self):
        records = [detection('int f() {', 0, 0), detection('work();', 0, 40),
                   detection('return 1;', 400, 0), detection(')', 400, 40)]
        result = associate(records)
        self.assertFalse(any(r['decision'] == 'continuation' for r in result['relations']))

    def test_braces_inside_comment_and_literal_do_not_create_open_scope(self):
        for text in ('/* { */', 'puts("{");'):
            records = [detection(text, 0, 0), detection('work();', 0, 40),
                       detection('return 1;', 400, 0), detection('}', 400, 40)]
            self.assertFalse(any(r['decision'] == 'continuation' for r in associate(records)['relations']))

    def test_unterminated_quote_abstains(self):
        records = [detection('int f() {', 0, 0), detection('puts("oops', 0, 40),
                   detection('return 1;', 400, 0), detection('}', 400, 40)]
        self.assertFalse(any(r['decision'] == 'continuation' for r in associate(records)['relations']))

    def test_invalid_geometry_preserves_input_ids(self):
        records = [detection('x;', 0, 0), detection('}', 400, 40)]
        records[0]['box'][0] = float('nan')
        self.assertEqual(associate(records)['ordered_ids'], [0, 1])

    def test_scale_invariance(self):
        records = json.loads((FIXTURES / 'writerX_page05_detections.json').read_text())
        before = associate(records)
        for factor in (.5, 2):
            scaled = copy.deepcopy(records)
            for record in scaled:
                record['box'] = [v * factor for v in record['box']]
            after = associate(scaled)
            self.assertEqual(after['ordered_ids'], before['ordered_ids'])
            self.assertEqual([r['decision'] for r in after['relations']], [r['decision'] for r in before['relations']])

    def test_repeated_identical_records_preserved(self):
        records = [detection('}', 0, 0), detection('}', 0, 0)]
        self.assertEqual(sorted(associate(records)['ordered_ids']), [0, 1])

    def test_narrow_local_gap_abstains_even_with_braces(self):
        records = [detection('int f() {', 0, 0), detection('work();', 0, 40),
                   detection('return 1;', 190, 0), detection('}', 190, 40)]
        result = associate(records)
        self.assertEqual(result['relations'][0]['reasons'], ['insufficient_local_gutter'])
        self.assertEqual(result['ordered_ids'], result['baseline_ids'])

    def test_competing_right_blocks_abstain(self):
        records = [detection('int f() { {', 0, 0), detection('work();', 0, 40),
                   detection('work();', 0, 80), detection('work();', 0, 120),
                   detection('work();', 0, 160), detection('return 1;', 400, 0),
                   detection('}', 400, 40), detection('return 2;', 400, 120),
                   detection('}', 400, 160)]
        result = associate(records)
        self.assertEqual(len(result['relations']), 2)
        self.assertTrue(all(r['reasons'] == ['competing_blocks_for_insertion_point']
                            for r in result['relations']))
        self.assertEqual(result['ordered_ids'], result['baseline_ids'])

    def test_all_development_records_preserved(self):
        for n in (1, 2, 4, 5, 6, 8, 9, 11):
            records = json.loads((FIXTURES / f'writerX_page{n:02d}_detections.json').read_text())
            original = copy.deepcopy(records)
            self.assertEqual(sorted(associate(records)['ordered_ids']), list(range(len(records))))
            self.assertEqual(records, original)


if __name__ == '__main__':
    unittest.main()
