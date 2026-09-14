"""Replay annotated development detections; never open reserved photographs.

This measures ordering only. The current pipeline emits no answer-membership
decision, so association accuracy is unavailable, not inferred from line order.
Run from ocr_feature: PYTHONPATH=. .venv/bin/python -m
evaluators.evaluate_continuation_development
"""
from collections import Counter, defaultdict, deque
from contextlib import ExitStack
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
            before = (None if name.startswith("_detect_")
                      else layout._line_identity_order(args[0]))
            result = implementation(*args, **kwargs)
            if name.startswith("_detect_"):
                events.append({"mechanism": name, "found": result is not None})
            else:
                after = layout._line_identity_order(result)
                events.append({"mechanism": name, "changed_order": before != after})
            return result
        return wrapped

    names = ("_detect_two_columns", "_detect_banded_column",
             "_sever_displaced_regions", "_reassemble_margin_candidates",
             "_reassemble_displaced_regions")
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


def evaluate():
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
            association_note="Current pipeline does not predict answer membership",
            actual_text_rows=[" ".join(records[i]["text"] for i in row) for row in rows],
            intended_text_rows=[" ".join(records[i]["text"] for i in row)
                                for row in page["expected_detection_rows"]]))
    return {"scope": "development only; frozen OCR detections",
            "reserved_examples_excluded": sorted(RESERVED), "pages": results}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
