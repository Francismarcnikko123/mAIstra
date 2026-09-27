"""Find a block of code written in the margin and move it into place.

Only whole detected lines are moved; recognized text is never added,
removed or changed.
"""

import bisect
import math

from core.numeric import finite_float
from core.layout.braces import _brace_delta, _is_definition_close


# Fragments on one row sit side by side; fragments on stacked rows overlap
# horizontally. Measured: same-row overlap at most 8%, stacked rows at least 37%.
MAX_SAME_LINE_X_OVERLAP = 0.3

# Widths below are in median box widths (about one word). A gap over 0.75
# widths starts a check for a margin block, but lines are split only if the
# block is confirmed (at most 12 detections within 300 px). Otherwise
# fragments up to 6 widths apart are merged as usual; lowering 6.0 made a
# test page worse.
REGION_GAP_MULTIPLIER = 0.75
BASELINE_REGION_GAP_MULTIPLIER = 6.0
MAX_DISPLACED_REGION_LINES = 12
MAX_DISPLACED_REGION_SPAN = 300.0

# Margin block found from repeated gaps: at least 3 rows with a gap over 0.8
# widths (at least 40 px) at the same x, within 1.2 widths. Requiring only 2
# rows made a test page worse.
SEVER_GAP_MULTIPLIER = 0.8
MIN_SEVER_ROWS = 3
SEVER_X_ALIGN_MULTIPLIER = 1.2

# Fallback when no gap marks the block: 2 or more aligned rows shifted right
# by at least 2 widths (at least 80 px), moved only if the braces prove where
# they belong.
BRACE_CANDIDATE_MIN_ROWS = 2
BRACE_CANDIDATE_X_SHIFT_MULTIPLIER = 2.0
BRACE_CANDIDATE_X_SHIFT_FLOOR = 80.0

def _reassemble_displaced_regions(lines: list) -> list:
    """Move the lines marked `severed_by_gap` to the end of the code if that
    is the only arrangement with balanced braces; otherwise return `lines`
    unchanged.

    - Balanced: the brace depth never goes below 0 and ends at 0.
    - Lines after the last marked line may belong to the block too. Every
      number of them is tried, and exactly one must give balanced braces.
    - Refused if the remaining main code closes an if/loop scope by itself
      (a plain `}`): the block might belong inside that scope, and brace
      counting can't tell. A `};` (struct, union, enum) is allowed, because
      code can't belong inside a type definition.

    This only handles a block whose place is at the end of the code, such as
    a switch body written in the margin after its last `case` line.
    """
    severed_indices = [
        i for i, line in enumerate(lines) if line.get("severed_by_gap")
    ]
    if not severed_indices:
        return lines

    severed_set = set(severed_indices)
    last_severed = severed_indices[-1]
    block_core = [lines[i] for i in severed_indices]
    fixed_normal = [
        lines[i] for i in range(last_severed + 1) if i not in severed_set
    ]
    tail_candidates = lines[last_severed + 1:]

    def line_text(line: dict) -> str:
        return "\n".join(member["text"] for member in line["members"])

    def is_well_formed(sequence: list) -> bool:
        depth = 0
        for line in sequence:
            depth += _brace_delta(line_text(line))
            if depth < 0:
                return False
        return depth == 0

    # Try every number of trailing lines joining the block. The gap trace
    # marks whole blocks; this also handles a block with only its first line
    # marked.
    valid_reorderings = []
    for tail_len in range(0, len(tail_candidates) + 1):
        block = block_core + tail_candidates[:tail_len]
        normal = fixed_normal + tail_candidates[tail_len:]
        reordering = normal + block
        if is_well_formed(reordering):
            valid_reorderings.append((reordering, normal))

    if len(valid_reorderings) != 1:
        return lines
    reordering, normal = valid_reorderings[0]
    # Refuse if the main code closes an if/loop scope by itself (see above).
    if any(_brace_delta(text := line_text(line)) < 0 and not _is_definition_close(text)
           for line in normal):
        return lines
    return reordering


def _line_identity_order(lines):
    """The line order as detection identities, for comparing two orderings."""
    return tuple(tuple(id(member) for member in line["members"])
                 for line in lines)



def _expected_line_y(members, candidate_x):
    """Predict the vertical center a box at `candidate_x` would have if it
    continued this line, from a straight-line fit through the members (so
    slanted handwriting still groups). None if the fit fails."""
    if len(members) == 1:
        return members[0]["y"]

    try:
        x_mean = sum(member["x"] for member in members) / len(members)
        y_mean = sum(member["y"] for member in members) / len(members)
        if not all(math.isfinite(value) for value in (x_mean, y_mean)):
            return None

        denominator = sum((member["x"] - x_mean) ** 2 for member in members)
        if not math.isfinite(denominator):
            return None
        if denominator == 0:
            return members[0]["y"]

        covariance = sum(
            (member["x"] - x_mean) * (member["y"] - y_mean)
            for member in members
        )
        if not math.isfinite(covariance):
            return None
        slope = covariance / denominator
        if not math.isfinite(slope):
            return None
        predicted_y = y_mean + slope * (candidate_x - x_mean)
        return predicted_y if math.isfinite(predicted_y) else None
    except OverflowError:
        return None


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


def _trace_displaced_region(items, left_max, right_min):
    """Return the detections of a margin block to the right of the gap
    (left_max, right_min), or [] if none is confirmed.

    Walks the boxes by their top edge. The block ends at the first box that
    crosses the gap; with no such box, it counts only if the right side
    ended before the page did. It must stay within
    MAX_DISPLACED_REGION_LINES detections and MAX_DISPLACED_REGION_SPAN px.
    If the gap closes, nothing is returned.
    """
    by_top = sorted(items, key=lambda item: item["y_min"])
    start_y = by_top[0]["y_min"]

    def confirm(accepted, close_y):
        # Only boxes that start above the closing line belong to the block.
        accepted = [c for c in accepted if c["y_min"] < close_y]
        if (len(accepted) > MAX_DISPLACED_REGION_LINES
                or close_y - start_y > MAX_DISPLACED_REGION_SPAN):
            return []
        return accepted

    candidates = []
    last_was_right = False
    for item in by_top:
        if item["x_max"] <= right_min:
            left_max = max(left_max, item["x_max"])
            last_was_right = False
        elif item["x"] >= left_max:
            right_min = min(right_min, item["x"])
            candidates.append(item)
            last_was_right = True
        else:
            return confirm(candidates, item["y_min"])
        if left_max >= right_min:
            return []
    # No box crossed the gap. If the right side runs to the end of the page,
    # it's a column, not a margin block; otherwise the block had ended.
    if candidates and not last_was_right:
        return confirm(candidates, by_top[-1]["y_min"] + 1)
    return []


def _sweep_detection_records(items, line_tol, seed_gap_threshold,
                             baseline_gap_threshold, severed_ids):
    """Group detections (sorted top to bottom) into lines.

    A detection joins the current line if it lines up vertically, barely
    overlaps the line's members, and is within `baseline_gap_threshold` of
    the nearest one. Detections in `severed_ids` never share a line with the
    others; their lines are marked `severed_by_gap`.

    Returns (lines, seed). The seed is the first gap wider than
    `seed_gap_threshold`, as (left_x_max, right_x), where a margin block may
    start; None if there isn't one. Returns (None, None) if the line fit fails.
    """
    lines = []
    first_seed = None
    for it in items:
        severed = id(it) in severed_ids
        if lines and bool(lines[-1].get("severed_by_gap")) == severed:
            members = lines[-1]["members"]
            expected_y = _expected_line_y(members, it["x"])
            if expected_y is None:
                return None, None
            mean_y = sum(member["y"] for member in members) / len(members)
            trend_delta = abs(it["y"] - expected_y)
            center_delta = abs(it["y"] - mean_y)
            within_vertical_tolerance = (
                trend_delta <= line_tol
                and (center_delta <= line_tol
                     or trend_delta <= line_tol * 0.5)
            )
            if within_vertical_tolerance:
                overlap_fractions = (
                    max(0.0, min(member["x_max"], it["x_max"])
                        - max(member["x"], it["x"]))
                    / min(member["x_max"] - member["x"], it["x_max"] - it["x"])
                    for member in members
                )
                # Overlap is measured against each member, not the line's span.
                if max(overlap_fractions) <= MAX_SAME_LINE_X_OVERLAP:
                    def gap(member):
                        return max(0.0, it["x"] - member["x_max"],
                                   member["x"] - it["x_max"])

                    nearest = min(members, key=gap)
                    distance = gap(nearest)
                    if first_seed is None and distance > seed_gap_threshold:
                        left, right = sorted((nearest, it), key=lambda m: m["x"])
                        first_seed = (left["x_max"], right["x"])
                    if distance <= baseline_gap_threshold:
                        members.append(it)
                        continue
        line = {"members": [it]}
        if severed:
            line["severed_by_gap"] = True
        lines.append(line)
    return lines, first_seed
