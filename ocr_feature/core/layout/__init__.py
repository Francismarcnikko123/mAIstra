"""Reading-order and indentation geometry for the OCR pipeline.

Pure geometry, no recognition runtime. ``columns`` identifies full-height and
partial-height columns; ``displacement`` traces and reassembles displaced
regions; ``braces`` supplies C brace-depth primitives; and ``format`` restores
paper-faithful indentation and blank lines. This module owns the grouping
orchestration and remains the compatibility surface for ``core.ocr_pipeline``
and tests.
"""

import math

from core.continuation import associate_continuation
from core.numeric import finite_float
from .braces import _brace_delta, _is_definition_close
from .columns import (
    BAND_GUTTER_MIN_FLOOR, BAND_GUTTER_MIN_MULTIPLIER,
    BAND_X_ALIGN_MULTIPLIER, MIN_BAND_ROWS, MIN_COLUMN_LINES,
    MIN_COLUMN_VSPAN_FRACTION, _detect_banded_column, _detect_two_columns,
)
from .displacement import (
    BASELINE_REGION_GAP_MULTIPLIER, BRACE_CANDIDATE_MIN_ROWS,
    BRACE_CANDIDATE_X_SHIFT_FLOOR, BRACE_CANDIDATE_X_SHIFT_MULTIPLIER,
    MAX_DISPLACED_REGION_LINES, MAX_DISPLACED_REGION_SPAN,
    MAX_SAME_LINE_X_OVERLAP, MIN_SEVER_ROWS, REGION_GAP_MULTIPLIER,
    SEVER_GAP_MULTIPLIER, SEVER_X_ALIGN_MULTIPLIER,
    _expected_line_y, _line_identity_order, _reassemble_displaced_regions,
    _sweep_detection_records, _trace_displaced_region,
)
from .format import (
    INDENT_STEP_CHARS, INDENT_STRING, MAX_BLANK_LINES,
    MAX_INDENT_LEVELS, _assign_indent_levels,
    _join_lines_with_vertical_gaps, line_member_bounds,
)

def _sever_displaced_regions(lines, median_width):
    """Append aligned right clusters from consecutive rows using geometry only.

    Reconstruct visual rows when boxes are available, because the baseline
    sweep may already have separated the right fragments. Apply accepted
    moves to the original lines so unrelated grouping and metadata survive.
    X-only callers retain the existing pre-grouped-row contract.
    """
    width = finite_float(median_width)
    if width is None or width <= 0 or not isinstance(lines, (list, tuple)):
        return lines

    items = []
    source_lines = {}
    for line in lines:
        if not isinstance(line, dict):
            return lines
        members = line.get("members")
        if not isinstance(members, (list, tuple)) or not members:
            return lines
        for member in members:
            if not isinstance(member, dict):
                return lines
            x = finite_float(member.get("x"))
            x_max = finite_float(member.get("x_max"))
            if x is None or x_max is None or x_max <= x:
                return lines
            items.append(member)
            source_lines[id(member)] = line

    visual_lines = lines
    if any(key in member for member in items for key in ("y", "y_min", "y_max")):
        heights = []
        for member in items:
            y, y_min, y_max = (finite_float(member.get(key))
                               for key in ("y", "y_min", "y_max"))
            if (y is None or y_min is None or y_max is None
                    or not y_min <= y <= y_max or y_max <= y_min
                    or not math.isfinite(y_max - y_min)):
                return lines
            heights.append(y_max - y_min)
        heights.sort()
        line_tol = max(heights[len(heights) // 2] * 0.6, 1.0)
        try:
            visual_lines, _seed = _sweep_detection_records(
                sorted(items, key=lambda member: member["y"]), line_tol,
                max(REGION_GAP_MULTIPLIER * width, 1.0), float("inf"), set())
        except (TypeError, ValueError, OverflowError):
            return lines
        if visual_lines is None:
            return lines

    gap_threshold = max(SEVER_GAP_MULTIPLIER * width, 40.0)
    align_tolerance = SEVER_X_ALIGN_MULTIPLIER * width
    candidates = []
    for line in visual_lines:
        geometry = [(member, finite_float(member["x"]), finite_float(member["x_max"]))
                    for member in line["members"]]
        geometry.sort(key=lambda entry: entry[1])
        candidate = None
        for split in range(1, len(geometry)):
            if geometry[split][1] - geometry[split - 1][2] > gap_threshold:
                candidate = (geometry, split, geometry[split][1])
                break
        candidates.append(candidate)

    accepted = {}
    start = 0
    while start < len(candidates):
        first = candidates[start]
        if first is None:
            start += 1
            continue
        end = start + 1
        while (end < len(candidates)
               and candidates[end] is not None
               and abs(candidates[end][2] - first[2]) <= align_tolerance):
            end += 1
        if end - start >= MIN_SEVER_ROWS:
            gutter = min(candidate[2] for candidate in candidates[start:end])
            left_max = max(
                x_max
                for geometry, split, _right_x in candidates[start:end]
                for _member, _x, x_max in geometry[:split]
            )
            crossed = any(
                x < gutter < x_max
                for geometry, _split, _right_x in candidates[start:end]
                for _member, x, x_max in geometry
            )
            # A shared gutter needs positive width, including when a left
            # fragment touches or lies entirely beyond the right boundary.
            if left_max < gutter and not crossed:
                accepted.update((index, candidates[index])
                                for index in range(start, end))
        start = end

    if not accepted:
        return lines
    displaced = []
    for geometry, split, _right_x in accepted.values():
        members = [entry[0] for entry in geometry[split:]]
        displaced.append({**source_lines[id(members[0])], "members": members})
    moved_ids = {id(member) for line in displaced for member in line["members"]}
    remaining = []
    for line in lines:
        members = [member for member in line["members"] if id(member) not in moved_ids]
        if members:
            remaining.append(line if len(members) == len(line["members"])
                             else {**line, "members": members})
    return remaining + displaced


def _reassemble_margin_candidates(lines, median_width):
    """Brace-assisted fallback for missed right-margin continuation blocks.

    This deliberately does not correct symbols. It only marks whole existing
    lines as a candidate displaced block, then reuses _reassemble_displaced_regions
    to accept a unique brace-balanced move.
    """
    width = finite_float(median_width)
    if width is None or width <= 0 or not isinstance(lines, (list, tuple)):
        return lines

    bounds = []
    for line in lines:
        members = line.get("members") if isinstance(line, dict) else None
        if not members:
            return lines
        try:
            x0, y0, x1, y1 = line_member_bounds(members)
        except (TypeError, KeyError, ValueError, OverflowError):
            return lines
        values = (finite_float(x0), finite_float(y0),
                  finite_float(x1), finite_float(y1))
        if any(value is None for value in values):
            return lines
        x0, y0, x1, y1 = values
        if x1 <= x0 or y1 <= y0:
            return lines
        bounds.append((x0, y0, x1, y1))

    page_left = min(x0 for x0, _y0, _x1, _y1 in bounds)
    min_shift = max(BRACE_CANDIDATE_X_SHIFT_MULTIPLIER * width,
                    BRACE_CANDIDATE_X_SHIFT_FLOOR)
    align_tolerance = SEVER_X_ALIGN_MULTIPLIER * width
    right_indices = [
        i for i, (x0, _y0, _x1, _y1) in enumerate(bounds)
        if x0 - page_left >= min_shift
    ]
    if len(right_indices) < BRACE_CANDIDATE_MIN_ROWS:
        return lines

    clusters = []
    current = []
    current_x0s = []
    for index in right_indices:
        x0 = bounds[index][0]
        if not current:
            current = [index]
            current_x0s = [x0]
            continue
        median_x0 = sorted(current_x0s)[len(current_x0s) // 2]
        if abs(x0 - median_x0) <= align_tolerance:
            current.append(index)
            current_x0s.append(x0)
        else:
            clusters.append(current)
            current = [index]
            current_x0s = [x0]
    if current:
        clusters.append(current)

    original_order = _line_identity_order(lines)
    accepted = []
    for cluster in clusters:
        if len(cluster) < BRACE_CANDIDATE_MIN_ROWS:
            continue
        cluster_set = set(cluster)
        block_text = "\n".join(
            "\n".join(member["text"] for member in lines[i]["members"])
            for i in cluster
        )
        if _brace_delta(block_text) >= 0:
            continue

        band_top = min(bounds[i][1] for i in cluster)
        band_bot = max(bounds[i][3] for i in cluster)
        right_min = min(bounds[i][0] for i in cluster)
        complement_in_band = [
            i for i, (_x0, y0, _x1, y1) in enumerate(bounds)
            if i not in cluster_set and y1 >= band_top and y0 <= band_bot
        ]
        if not complement_in_band:
            continue
        if any(bounds[i][0] < right_min < bounds[i][2]
               for i in complement_in_band):
            continue
        left_in_band = [i for i in complement_in_band
                        if bounds[i][2] < right_min]
        if not left_in_band:
            continue
        if max(bounds[i][2] for i in left_in_band) >= right_min:
            continue

        trial = []
        for i, line in enumerate(lines):
            copy = {key: value for key, value in line.items()
                    if key != "severed_by_gap"}
            if i in cluster_set:
                copy["severed_by_gap"] = True
            trial.append(copy)
        reassembled = _reassemble_displaced_regions(trial)
        new_order = _line_identity_order(reassembled)
        if new_order == original_order:
            continue
        if (len(new_order) == len(original_order)
                and set(new_order) == set(original_order)):
            accepted.append(reassembled)

    if len(accepted) == 1:
        return accepted[0]
    return lines


def _original_detection_records(rec_texts, rec_scores):
    """Return one geometry-free record per detection in original order."""
    return [[{
        "text": text,
        "score": rec_scores[i] if i < len(rec_scores) else 0.0,
        "x": None,
        "y": None,
        "y_min": None,
        "y_max": None,
    }] for i, text in enumerate(rec_texts)]


def _associate_continuation(rows, records, detection_ids_by_member):
    """Apply only a complete, row-preserving continuation permutation."""
    try:
        row_ids = [
            [detection_ids_by_member[id(member)] for member in row]
            for row in rows
        ]
        baseline_ids = [identifier for identifiers in row_ids
                        for identifier in identifiers]
    except (KeyError, TypeError):
        return rows

    expected_ids = list(range(len(records)))
    if len(baseline_ids) != len(records) or sorted(baseline_ids) != expected_ids:
        return rows

    result = associate_continuation(records, baseline_ids)
    proposed_ids = result.get("ordered_ids") if isinstance(result, dict) else None
    if (not isinstance(proposed_ids, list)
            or len(proposed_ids) != len(records)
            or sorted(proposed_ids) != expected_ids):
        return rows

    rank = {identifier: position
            for position, identifier in enumerate(proposed_ids)}
    for identifiers in row_ids:
        positions = [rank[identifier] for identifier in identifiers]
        if (positions != sorted(positions)
                or max(positions) - min(positions) + 1 != len(positions)):
            return rows

    paired = list(zip(rows, row_ids))
    paired.sort(key=lambda pair: min(rank[identifier] for identifier in pair[1]))
    return [row for row, _identifiers in paired]


def _finalize_grouped_lines(lines, median_char_width, records,
                            detection_ids_by_member):
    """Apply safe association to lines whose column indentation is assigned."""
    rows = [
        sorted(line["members"], key=lambda member: member["x"])
        for line in lines
    ]
    return _associate_continuation(rows, records, detection_ids_by_member)



def _order_column_items(items, line_tol, region_gap_threshold,
                        baseline_gap_threshold):
    """Order one column while resolving its own displaced regions.

    Kept at package scope because grouping tests patch the helpers by this
    namespace and must observe the calls made by the live coordinator.
    """
    lines, seed = _sweep_detection_records(
        items, line_tol, region_gap_threshold, baseline_gap_threshold, set())
    if lines is None:
        return None
    if seed is not None:
        displaced = _trace_displaced_region(items, *seed)
        if displaced:
            lines, _ = _sweep_detection_records(
                items, line_tol, region_gap_threshold, baseline_gap_threshold,
                {id(item) for item in displaced})
            if lines is None:
                return None
    return _reassemble_displaced_regions(lines)

def _group_detection_records(rec_texts, rec_scores, rec_boxes):
    """Group detections and retain the box geometry used for ordering.

    The boolean return value indicates whether every detection had safe,
    finite geometry. Unsafe geometry falls back to one detection per line in
    original order so callers never infer coordinates that Paddle did not
    provide reliably.
    """
    if not rec_boxes or len(rec_boxes) != len(rec_texts):
        return _original_detection_records(rec_texts, rec_scores), False

    items = []
    heights = []
    widths = []
    for i, box in enumerate(rec_boxes):
        try:
            x_min, y_min, x_max, y_max = (float(box[0]), float(box[1]),
                                          float(box[2]), float(box[3]))
        except (TypeError, IndexError, ValueError, OverflowError):
            # Malformed box -> don't risk regrouping; keep original order.
            return _original_detection_records(rec_texts, rec_scores), False
        width = x_max - x_min
        height = y_max - y_min
        if (not all(math.isfinite(value)
                    for value in (x_min, y_min, x_max, y_max, width, height))
                or width <= 0 or height <= 0):
            # Invalid geometry -> don't risk regrouping; keep original order.
            return _original_detection_records(rec_texts, rec_scores), False
        y_center = y_min + height / 2.0
        if not math.isfinite(y_center):
            # Invalid geometry -> don't risk regrouping; keep original order.
            return _original_detection_records(rec_texts, rec_scores), False
        score = rec_scores[i] if i < len(rec_scores) else 0.0
        items.append({"text": rec_texts[i], "score": score,
                      "x": x_min, "x_max": x_max, "y": y_center,
                      "y_min": y_min, "y_max": y_max})
        heights.append(height)
        widths.append(width)

    records = [
        {
            "text": item["text"],
            "score": item["score"],
            "box": [item["x"], item["y_min"], item["x_max"], item["y_max"]],
        }
        for item in items
    ]
    detection_ids_by_member = {
        id(item): identifier for identifier, item in enumerate(items)
    }

    # Two boxes belong to the same visual line if their vertical centers are
    # within ~60% of a typical line height. Using the median height keeps this
    # robust to one unusually tall/short detection.
    heights.sort()
    median_h = heights[len(heights) // 2] if heights else 0.0
    line_tol = max(median_h * 0.6, 1.0)

    widths.sort()
    median_width = widths[len(widths) // 2] if widths else 0.0
    region_gap_threshold = max(REGION_GAP_MULTIPLIER * median_width, 1.0)

    # Character-scale width (box width / text length) is the unit for indent
    # reconstruction -- see INDENT_STEP_CHARS. Box width alone spans a whole
    # word, so it is far too coarse to resolve a few-character indent.
    char_widths = sorted(
        (it["x_max"] - it["x"]) / len(it["text"].strip())
        for it in items if it["text"] and it["text"].strip()
    )
    median_char_width = (
        char_widths[len(char_widths) // 2] if char_widths else 0.0
    )

    # Sort by vertical position first so we can sweep top-to-bottom.
    items.sort(key=lambda it: it["y"])

    baseline_gap_threshold = max(BASELINE_REGION_GAP_MULTIPLIER * median_width, 1.0)

    # A genuine two-column page (two independent programs side by side) reads
    # as left column fully, then right column fully -- NOT interleaved by the
    # y-sweep. Detect it, and if found, order each column on its own and
    # concatenate. Only applied when detection is confident (see
    # _detect_two_columns); every other page takes the single-column path.
    page_top = min(it["y_min"] for it in items)
    page_bot = max(it["y_max"] for it in items)
    gutter_x = _detect_two_columns(items, page_top, page_bot)
    if gutter_x is not None:
        left = [it for it in items
                if (it["x"] + it["x_max"]) / 2.0 < gutter_x]
        right = [it for it in items
                 if (it["x"] + it["x_max"]) / 2.0 >= gutter_x]
        left_lines = _order_column_items(
            left, line_tol, region_gap_threshold, baseline_gap_threshold)
        right_lines = _order_column_items(
            right, line_tol, region_gap_threshold, baseline_gap_threshold)
        if left_lines is not None and right_lines is not None:
            _assign_indent_levels(left_lines, median_char_width)
            _assign_indent_levels(right_lines, median_char_width)
            ordered_lines = _finalize_grouped_lines(
                left_lines + right_lines, median_char_width, records,
                detection_ids_by_member)
            return ordered_lines, True
        # Either column had unsafe geometry -- fall through to single-column.
    else:
        # No full-height split. Try the banded generalization: a partial-height
        # right column (a two-page / side-by-side capture whose continuation
        # fills only the top-right quadrant). Read it left column fully, then
        # right column fully -- the same rule as the full-height split, applied
        # to a right block that spans less than half the page. If it fires,
        # severance is skipped; otherwise the single-column path runs unchanged.
        banded = _detect_banded_column(items, median_width, line_tol)
        if banded is not None:
            _gutter_b, left, right = banded
            left_lines = _order_column_items(
                left, line_tol, region_gap_threshold, baseline_gap_threshold)
            right_lines = _order_column_items(
                right, line_tol, region_gap_threshold, baseline_gap_threshold)
            if left_lines is not None and right_lines is not None:
                _assign_indent_levels(left_lines, median_char_width)
                _assign_indent_levels(right_lines, median_char_width)
                ordered_lines = _finalize_grouped_lines(
                    left_lines + right_lines, median_char_width, records,
                    detection_ids_by_member)
                return ordered_lines, True
            # Either column had unsafe geometry -- fall through to single-column.

    lines = _order_column_items(
        items, line_tol, region_gap_threshold, baseline_gap_threshold)
    if lines is None:
        return _original_detection_records(rec_texts, rec_scores), False
    if gutter_x is None:
        before_severance = _line_identity_order(lines)
        lines = _sever_displaced_regions(lines, median_width)
        if _line_identity_order(lines) == before_severance:
            lines = _reassemble_margin_candidates(lines, median_width)
    # The single-column mechanisms may already have made a higher-confidence
    # brace-balanced move. Do not let column association override that result.
    _assign_indent_levels(lines, median_char_width)
    ordered_lines = [
        sorted(line["members"], key=lambda member: member["x"])
        for line in lines
    ]
    return ordered_lines, True


def _group_structured_lines(rec_texts, rec_scores, rec_boxes, image_height):
    """Return nonempty OCR lines with confidence and normalized geometry."""
    grouped, geometry_safe = _group_detection_records(
        rec_texts, rec_scores, rec_boxes
    )
    normalized_height = finite_float(image_height)
    geometry_safe = (
        geometry_safe
        and normalized_height is not None
        and normalized_height > 0
    )

    structured = []
    for members in grouped:
        parts = [
            member["text"].strip()
            for member in members
            if member["text"] and member["text"].strip()
        ]
        if not parts:
            continue

        scores = []
        for member in members:
            score = finite_float(member["score"])
            if score is not None:
                scores.append(score)

        mean_confidence = None
        if scores:
            try:
                candidate_mean = math.fsum(
                    score / len(scores) for score in scores
                )
            except OverflowError:
                candidate_mean = None
            if candidate_mean is not None and math.isfinite(candidate_mean):
                mean_confidence = candidate_mean

        y_min = None
        y_max = None
        if geometry_safe:
            try:
                _, raw_y_min, _, raw_y_max = line_member_bounds(members)
                y_min = raw_y_min / normalized_height
                y_max = raw_y_max / normalized_height
            except (TypeError, ValueError, OverflowError, ZeroDivisionError):
                y_min = None
                y_max = None
            if (y_min is None or y_max is None
                    or not all(math.isfinite(value) for value in (y_min, y_max))):
                y_min = None
                y_max = None

        indent_level = members[0].get("indent", 0) if members else 0
        structured.append({
            "text": INDENT_STRING * indent_level + " ".join(parts),
            "members": [
                (member["text"], member["score"]) for member in members
            ],
            "scores": scores,
            "mean_confidence": mean_confidence,
            "y_min": y_min,
            "y_max": y_max,
        })
    return structured
