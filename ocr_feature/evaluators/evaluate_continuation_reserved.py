"""Explicit frozen-rule evaluation on reserved fixtures, never development input.

Run only after freezing the prototype. Reject changed rules or fixture hashes.
This replays the recorded first reserved evaluation; it does not run recognition.
"""
import hashlib
import json
from pathlib import Path

from evaluators.continuation_prototype import associate
from evaluators.evaluate_continuation_development import pairwise_order_accuracy, score_association

ROOT = Path(__file__).resolve().parents[1]


def evaluate():
    freeze = json.loads((ROOT / 'reports/2026-09-14-offline-association-freeze.json').read_text())
    digest = hashlib.sha256((ROOT / freeze['prototype_path']).read_bytes()).hexdigest()
    if digest != freeze['prototype_sha256']:
        raise ValueError('Rules changed after freeze; these results are no longer held-out validation')
    fixtures = ROOT / 'tests/fixtures/continuation_reserved'
    annotations = json.loads((fixtures / 'writerX_annotations.json').read_text())
    if annotations['split'] != 'reserved_evaluation':
        raise ValueError('Reserved annotations required')
    pages = []
    if sorted(p['example'] for p in annotations['pages']) != freeze['available_reserved']:
        raise ValueError('Reserved page set changed')
    for page in annotations['pages']:
        payload = (fixtures / f"writerX_page{page['example']:02d}_detections.json").read_bytes()
        if hashlib.sha256(payload).hexdigest() != page['fixture_sha256']:
            raise ValueError('Reserved fixture changed')
        records = json.loads(payload)
        prediction = associate(records)
        expected = [i for row in page['expected_detection_rows'] for i in row]
        if sorted(expected) != list(range(len(records))):
            raise ValueError('Incomplete reserved annotation')
        actual = prediction['ordered_ids']
        if sorted(actual) != sorted(expected):
            raise ValueError('Detection loss/duplication')
        pages.append(dict(example=page['example'], detection_count=len(records),
                          expected_order=expected, baseline_exact=prediction['baseline_ids'] == expected,
                          exact_order=actual == expected,
                          pairwise_order_accuracy=pairwise_order_accuracy(expected, actual),
                          association=score_association(page, prediction), prediction=prediction,
                          all_detections_preserved=True,
                          actual_text=[records[i]['text'] for i in actual],
                          expected_text=[records[i]['text'] for i in expected]))
    return dict(scope='First reserved evaluation after development freeze; one writer',
                prototype_sha256=digest, missing_examples=freeze['missing_reserved'], pages=pages)


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
