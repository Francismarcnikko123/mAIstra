"""Replay annotated development detections; never open reserved photographs.

This measures ordering only. The current pipeline emits no answer-membership
decision, so association accuracy is unavailable, not inferred from line order.
With --prototype, also measure experimental association edges separately.
Run from ocr_feature: PYTHONPATH=. .venv/bin/python -m
evaluators.evaluate_continuation_development
"""
from collections import Counter, defaultdict, deque
from contextlib import ExitStack
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from core import layout

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
RESERVED = frozenset((3, 7, 10, 12))


def pairwise_order_accuracy(expected, actual):
    """Fraction of annotated pairs in correct order; missing IDs are wrong."""
    if len(set(expected)) != len(expected) or len(set(actual)) != len(actual):
        raise ValueError("Detection IDs must be unique")
    positions = {identifier: i for i, identifier in enumerate(actual)}
    correct = total = 0
    for i, first in enumerate(expected):
        for second in expected[i + 1:]:
            total += 1
            correct += (first in positions and second in positions
                        and positions[first] < positions[second])
    return correct / total if total else None


def replay(records):
    events = []
    def instrument(name):
        implementation = getattr(layout, name)
        def wrapped(*args, **kwargs):
            if name.startswith("_detect_"):
                before = None
            elif name == "_associate_continuation":
                before = tuple(id(member) for row in args[0] for member in row)
            else:
                before = layout._line_identity_order(args[0])
            result = implementation(*args, **kwargs)
            if name.startswith("_detect_"):
                events.append({"mechanism": name, "found": result is not None})
            else:
                after = (
                    tuple(id(member) for row in result for member in row)
                    if name == "_associate_continuation"
                    else layout._line_identity_order(result)
                )
                events.append({"mechanism": name, "changed_order": before != after})
            return result
        return wrapped

    names = ("_detect_two_columns", "_detect_banded_column",
             "_sever_displaced_regions", "_reassemble_margin_candidates",
             "_reassemble_displaced_regions", "_associate_continuation")
    with ExitStack() as stack:
        for name in names:
            stack.enter_context(patch.object(layout, name, side_effect=instrument(name)))
        rows, geometry_valid = layout._group_detection_records(
            *[[d[k] for d in records] for k in ("text", "score", "box")])
    if not geometry_valid:
        raise ValueError("Cannot score a geometry-invalid replay")
    available = defaultdict(deque)
    def key(d):
        return d["text"], d["score"], tuple(d["box"])
    for identifier, record in enumerate(records):
        available[key(record)].append(identifier)
    ordered_rows = []
    for row in rows:
        identifiers = []
        for member in row:
            member_key = (member["text"], member["score"],
                          (member["x"], member["y_min"],
                           member["x_max"], member["y_max"]))
            if not available[member_key]:
                raise ValueError("Grouping changed or duplicated a detection")
            identifiers.append(available[member_key].popleft())
        ordered_rows.append(identifiers)
    if any(available.values()):
        raise ValueError("Grouping dropped a detection")
    return ordered_rows, events


def score_association(page, prediction):
    """Score predicted edges against labels, which never enter the prototype.

    A predicted region must match a complete annotated block to earn edge credit.
    Correct flat ordering alone earns no association credit.
    """
    blocks = page['blocks']
    by_ids = {frozenset(b['detection_ids']): b for b in blocks}
    gold = {tuple(edge) for edge in page['continuation_edges']}
    found = set()
    wrong = cross = independent_correct = independent_wrong = ambiguous = 0
    for relation in prediction['relations']:
        decision = relation['decision']
        if decision == 'ambiguous':
            ambiguous += 1
            continue
        left = by_ids.get(frozenset(relation['target_detection_ids']))
        right = by_ids.get(frozenset(relation['source_detection_ids']))
        if decision == 'continuation':
            edge = (left['id'], right['id']) if left and right else None
            if edge in gold and edge not in found:
                found.add(edge)
            else:
                wrong += 1
            answers = {b['answer_id'] for b in blocks
                       if set(b['detection_ids']) & set(relation['target_detection_ids']
                                                       + relation['source_detection_ids'])}
            cross += len(answers) > 1
        elif decision == 'independent':
            correct = bool(left and right and left['answer_id'] != right['answer_id'])
            independent_correct += correct
            independent_wrong += not correct
    return dict(true_continuation_links=len(found), false_continuation_links=wrong,
                missed_continuation_links=len(gold - found), false_cross_answer_links=cross,
                continuation_precision=len(found)/(len(found)+wrong) if found or wrong else None,
                continuation_recall=len(found)/len(gold) if gold else None,
                correct_independent_links=independent_correct,
                incorrect_independent_links=independent_wrong, ambiguous_relations=ambiguous,
                no_candidate_relationships=not prediction['relations'])


def evaluate(prototype=False):
    annotations = json.loads((FIXTURES / "writerX_development_annotations.json").read_text())
    if annotations["split"] != "development":
        raise ValueError("Development annotations required")
    results = []
    for page in annotations["pages"]:
        n = page["example"]
        if n in RESERVED:
            raise ValueError(f"Reserved example {n} cannot enter development evaluation")
        records = json.loads((FIXTURES / f"writerX_page{n:02d}_detections.json").read_text())
        expected = [i for row in page["expected_detection_rows"] for i in row]
        if Counter(expected) != Counter(range(len(records))):
            raise ValueError(f"Incomplete detection annotation for example {n}")
        rows, events = replay(records)
        actual = [i for row in rows for i in row]
        results.append(dict(
            example=n, detection_count=len(records), expected_order=expected,
            actual_order=actual, exact_order=actual == expected,
            exact_rows=rows == page["expected_detection_rows"],
            pairwise_order_accuracy=pairwise_order_accuracy(expected, actual),
            all_detections_preserved=True, mechanisms=events,
            association_accuracy=None,
            association_note=(
                "Production applies conservative continuation association; "
                "this replay scores final order only. Use --prototype for "
                "the frozen relationship-edge score."
            ),
            actual_text_rows=[" ".join(records[i]["text"] for i in row) for row in rows],
            intended_text_rows=[" ".join(records[i]["text"] for i in row)
                                for row in page["expected_detection_rows"]]))
        if prototype:
            from evaluators.continuation_prototype import associate
            prediction = associate(records)
            results[-1]['prototype'] = dict(
                prediction=prediction, exact_order=prediction['ordered_ids'] == expected,
                pairwise_order_accuracy=pairwise_order_accuracy(expected, prediction['ordered_ids']),
                association=score_association(page, prediction),
                ordered_text=[records[i]['text'] for i in prediction['ordered_ids']])
    return {"scope": "development only; frozen OCR detections",
            "reserved_examples_excluded": sorted(RESERVED), "pages": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prototype', action='store_true', help='Score experimental association offline')
    print(json.dumps(evaluate(prototype=parser.parse_args().prototype), indent=2))
