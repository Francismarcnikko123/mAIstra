"""Displaced-region mechanics for the OCR reading-order pipeline.

These helpers trace, sever, and brace-check whole detected regions. They are
grade-safe: each operation only reorders existing detection objects and never
inserts, removes, splits, or changes recognized characters.
"""

import bisect
import math

from core.numeric import finite_float
from core.layout.braces import _brace_delta, _is_definition_close


# Same-row fragments are side by side; stacked rows overlap in x. Across the
# available cohort artifacts, the largest overlap retained on one row was 8%
# and the smallest confirmed stacked-row merge was 37%. Keep a margin on both
# sides of that measured gap.
MAX_SAME_LINE_X_OVERLAP = 0.3

# Revision 3: a realistic gap proposes a gutter; only a confirmed bounded
# window authorizes separation. Retain the historical 6.0 merge threshold
# outside that window, including when the trace never closes. Lowering the
# merge threshold itself regressed green_writer10 in the held-out set.
REGION_GAP_MULTIPLIER = 0.75
BASELINE_REGION_GAP_MULTIPLIER = 6.0
MAX_DISPLACED_REGION_LINES = 12
MAX_DISPLACED_REGION_SPAN = 300.0

# Repeated, aligned gaps can identify a displaced block after row grouping.
# A/B testing selected three rows: two regressed a spatial-layout page.
# This changes order/grouping only, never characters. See
# docs/superpowers/specs/2026-09-12-local-gutter-reading-order-design.md.
SEVER_GAP_MULTIPLIER = 0.8
MIN_SEVER_ROWS = 3
SEVER_X_ALIGN_MULTIPLIER = 1.2

# Brace-assisted fallback: when strict gutter geometry does not mark a block,
# try a visibly right-shifted, aligned margin cluster only if C brace depth
# uniquely proves that moving it to the end restores structure.
BRACE_CANDIDATE_MIN_ROWS = 2
BRACE_CANDIDATE_X_SHIFT_MULTIPLIER = 2.0
BRACE_CANDIDATE_X_SHIFT_FLOOR = 80.0

def _reassemble_displaced_regions(lines: list) -> list:
    """If exactly one contiguous run of gap-severed lines can be moved to
    the end of the page such that the resulting sequence has well-formed
    brace structure (cumulative depth never negative, ends at 0), and its
    normal partition has no negative-delta lines, move it there. Otherwise
    return `lines` unchanged.

    Deliberately narrow: this only covers a block whose correct position is
    at the END of the sequence -- e.g. a switch-case body written in the
    margin while the dangling `case N:` opener is the LAST normal line on
    the page. A block belonging mid-sequence is a known, uncovered
    extension (see docs/superpowers/specs/2026-09-07-reading-order-reassembly-design.md).

    The block's fixed core is every severed line, in original relative
    order, wherever it sits -- a real displaced region (see
    docs/superpowers/specs/2026-09-10-displaced-region-tracking-design.md)
    can interleave with unrelated normal lines in the sweep, and those
    interleaved lines must stay in `normal`, not get swept into the block
    just because they sit between two severed indices.

    Beyond that core, the search still varies how many of the *trailing*
    lines (everything after the last severed index) join the block -- this
    is what makes the RBNode/Compressor style case work, where only the
    block's first line is actually flagged severed and the rest of the
    displaced body simply follows it as ordinary un-flagged lines. Lines
    positioned before the last severed index are never candidates for this
    extension, whether severed or not -- only the contiguous tail is
    searched. Any ambiguity -- zero or multiple tail lengths yielding a
    well-formed sequence -- returns `lines` unchanged rather than guessing.

    Only after selecting a unique tail length, reject the candidate if its
    normal partition closes a control-flow scope by itself. The partition
    depends on the tail length: unmarked trailing lines can still belong
    to the displaced block. This guard must not filter candidates before
    uniqueness is established.

    For the supported end-of-sequence displacement, the main text left one
    or more scopes open, and the displaced block closes them. In that case,
    normal contains openers, zero-delta statements, and possibly a
    self-contained type definition -- but no *control-flow* scope that
    normal closed by itself. If the winning normal DOES close a control
    scope on its own (a negative-delta line that isn't a definition close),
    part of the main text closed a scope without the block, so the block may
    belong mid-sequence, which brace math alone cannot solve; refusing is
    safer than a brace-well-formed but semantically wrong reordering.

    The exemption for definition closes (`};`, via _is_definition_close) is
    what lets a normal multi-line `struct { ... };` before the displaced
    block through -- the common real case. It is provably safe because a
    displaced *executable* block can never belong inside a type definition,
    so a `};` in normal is always an unrelated, self-contained scope. A
    plain `}` (control-flow close) stays rejected because the block CAN
    belong inside such a scope. A still-legitimate layout whose main flow
    closes a control scope by itself before the displaced block remains
    rejected and needs human verification.
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

    # Tail extension supports the legacy single-line-flag pattern exercised
    # by synthetic RBNode/Compressor fixtures. The current gutter trace
    # (_trace_displaced_region) flags the whole block, so it does not produce
    # this pattern; retain the search for those legacy inputs.
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
    # Reject if the normal partition closes a CONTROL-FLOW scope by itself: the
    # displaced block might belong inside it (mid-sequence), which brace math
    # can't resolve. A definition close (`};`) is exempt -- a type definition
    # can't contain the displaced executable block, so it's always unrelated
    # (see _is_definition_close). This lets a normal multi-line struct/union
    # before the displaced block through, while still refusing a genuine
    # dangling control scope.
    if any(_brace_delta(text := line_text(line)) < 0 and not _is_definition_close(text)
           for line in normal):
        return lines
    return reordering


def _line_identity_order(lines):
    return tuple(tuple(id(member) for member in line["members"])
                 for line in lines)



def _expected_line_y(members, candidate_x):
    """Predict a candidate's vertical center from the current line members."""
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
    """Confirm the first bounded RIGHT region, or discard every candidate.

    Walk box tops so a tall margin row that overlaps the open window is
    considered before the wide row closing it, even if its center is lower.
    The 12-detection/300px limits apply only to a confirmed window. An open
    or collapsed gutter never authorizes a change to baseline grouping.

    Closing has two independent triggers, not just the straddle case: a
    displaced block isn't guaranteed to be followed by a line that bridges
    back across the gutter. See the end-of-loop check below -- an earlier
    version tried a fixed-distance inactivity trigger instead (closing as
    soon as some number of px passed since the last RIGHT match, without
    waiting for the page to end), but hand-tracing it against
    green_writer10_B2_1.jpg found it fires too early on that page's
    tighter real line spacing: skipping just 2 LEFT lines between RIGHT
    matches there already exceeds a distance threshold sized off a
    different, more widely-spaced real photo, confirming a false 2-line
    "displaced block" on a genuine two-column page. A single value tuned
    from one photo's spacing isn't safe to apply to another's -- removed
    rather than shipped unvalidated. If an early-exit trigger is revisited,
    it needs its own real-data validation across multiple photos, not a
    reused constant from a different measurement.
    """
    by_top = sorted(items, key=lambda item: item["y_min"])
    start_y = by_top[0]["y_min"]

    def confirm(accepted, close_y):
        # A box starting exactly at the close has no overlap with the
        # open window, regardless of input ordering among equal tops.
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
    # Reached the end of the page's content without a straddle. If RIGHT
    # matches were still ongoing at the very last item, this looks like a
    # genuine column that simply hasn't ended yet -- never authorize it.
    # Otherwise the block quietly ended with nothing left to bridge back.
    if candidates and not last_was_right:
        return confirm(candidates, by_top[-1]["y_min"] + 1)
    return []


def _sweep_detection_records(items, line_tol, seed_gap_threshold,
                             baseline_gap_threshold, severed_ids):
    """Retain baseline merges within each partition; observe the first seed."""
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
                # Compare actual members, not the empty space inside the
                # line's span, just as in the original grouping rule.
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
