"""Reading-order and indentation geometry for the OCR pipeline.

Pure geometry, no recognition runtime. This module turns PaddleOCR detection
records (recognized text plus box coordinates) into ordered, indented visual
lines: brace-depth reassembly, two-column / banded / severance reading-order
detection, and indentation / blank-line reconstruction. It imports nothing
heavy (no cv2 / numpy / paddleocr) -- only the standard library and the pure
core.numeric / core.c_literals helpers -- so it can be exercised without
loading the recognizer.

core.ocr_pipeline owns recognition and calls _group_structured_lines /
_join_lines_with_vertical_gaps from here; it also re-exports these names, so
existing callers (tests, evaluators/build_recognition_dataset) keep importing
them from core.ocr_pipeline unchanged.

Split out of core/ocr_pipeline.py on 2026-09-13 as a behavior-preserving
refactor -- no logic changed; the file had grown past 1,200 lines. Two-column /
banded / severance reading-order work lives here.
"""
import bisect
import math
import re

from core.numeric import finite_float
from core.c_literals import C_LITERAL


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

# Two-column split (two independent programs written side by side to save
# paper). Detection is deliberately conservative: a vertical gutter that NO
# detection crosses, with substantial vertically-distributed content on both
# sides. Validated against the real dataset -- fires on the one genuine
# two-column page (green_writer10_B2_1.jpg) and none of the 34 single-column
# pages. See docs/superpowers/specs/2026-09-10-displaced-region-tracking-design.md.
MIN_COLUMN_LINES = 4
MIN_COLUMN_VSPAN_FRACTION = 0.5

# Banded two-column split: a persistent right-side block occupying a contiguous
# y-band with a clean, wide, uncrossed gutter WITHIN that band -- even when the
# block spans less than half the page height and even when a wide line elsewhere
# bridges the full-page x-projection (so _detect_two_columns reports gutter 0).
# Generalizes _detect_two_columns to a partial-height right column; runs only
# when that full-height split returns None. Grounded on green_writer18_B2_2
# (median box width ~86px; real gutter 248px; right-cluster x0 spread 136px) and
# confirmed on the corpus scan. See
# docs/superpowers/specs/2026-09-12-banded-column-detection-design.md.
MIN_BAND_ROWS = 3                 # distinct visual rows the right cluster must occupy
BAND_X_ALIGN_MULTIPLIER = 2.0     # x0 drift from the cluster median to join the right cluster
# Real writerX margin B/C photos (2026-09-13): clean band gutters are
# 108px / 189px = 0.571 widths and 171px / 138px = 1.239 widths. The former
# 1.5 rejected both despite intact braces and confirmed separate columns.
# Use 0.5 with the unchanged 60px floor, persistence and uncrossed-band gates.
# All 315 historical artifact replays and live held-out metrics are unchanged.
# REGION_GAP_MULTIPLIER remains 0.75: it only seeds tracing and lowering it
# does not fix these pages. See reports/2026-09-13-real-margin-validation.md.
BAND_GUTTER_MIN_MULTIPLIER = 0.5  # min clean gutter within the band, in median widths
BAND_GUTTER_MIN_FLOOR = 60.0      # px floor for the gutter

# Reconstruct the student's handwritten indentation from box geometry -- NOT
# brace depth. A line indented on paper has a larger left-edge x; one indent
# level is INDENT_STEP_CHARS character-widths of rightward offset from the line's
# own column left margin. The unit is CHARACTER-scale on purpose: a detection
# box spans a whole word, so median box width is ~10x a character, and a
# student's indent is only a few characters -- a box-width unit rounds every
# real indent to zero (measured on green_writer10: box width 109px vs char
# width 10.7px vs a 47px case-indent). Recognition-independent and
# presentation-only: it prepends whitespace, never changing which characters
# are emitted.
INDENT_STEP_CHARS = 3.0
MAX_INDENT_LEVELS = 8
INDENT_STRING = "  "

# Reconstruct the student's vertical spacing (blank lines) from box geometry:
# a gap between consecutive lines much larger than the normal line pitch means
# the student left blank line(s). Quantized into whole blank lines and capped so
# one runaway gap can't inject a wall of blanks. The vertical mirror of the
# indentation reconstruction above; recognition-independent, presentation-only.
MAX_BLANK_LINES = 2


def _brace_delta(text: str) -> int:
    """Net change in {}-depth contributed by `text`, skipping anything
    inside a string/char literal -- that's student content, never real C
    structure. Walks the same C_LITERAL segment pattern c_code_cleanup.py
    uses, so literal handling never drifts between the two call sites."""
    delta = 0
    last = 0
    for match in C_LITERAL.finditer(text):
        segment = text[last:match.start()]
        delta += segment.count("{") - segment.count("}")
        last = match.end()
    segment = text[last:]
    delta += segment.count("{") - segment.count("}")
    return delta


def _is_definition_close(text: str) -> bool:
    """True if every closing brace on this line is a definition terminator --
    a `}` immediately followed by `;` (a struct/union/enum/initializer close),
    literal contents shielded the same way _brace_delta shields them.

    Used by the displaced-reassembly guard. A displaced block is executable
    code, so it can belong INSIDE a control-flow scope (closed by a plain
    `}`) -- the genuinely ambiguous case the guard must reject. But it can
    never belong inside a type definition (closed by `};`): definitions hold
    declarations, not statements. So a negative-delta normal line whose closes
    are ALL `};` is a self-contained, unrelated scope, safe to allow past the
    guard. Requiring EVERY `}` to be a `};` keeps a line that mixes a control
    close and a definition close (e.g. `} };`) on the reject side.
    """
    stripped = ""
    last = 0
    for match in C_LITERAL.finditer(text):
        stripped += text[last:match.start()]
        last = match.end()
    stripped += text[last:]
    for match in re.finditer(r"\}", stripped):
        if not re.match(r"\s*;", stripped[match.end():]):
            return False
    return True


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


def _order_column_items(items, line_tol, region_gap_threshold,
                        baseline_gap_threshold):
    """Sweep, sever/trace a displaced region, and reassemble -- the full
    ordering pipeline for one column of items. That column is either a whole
    single-column page or one side of a two-column split. Returns grouped
    lines, or None if the geometry is unsafe (caller falls back)."""
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


def _detect_two_columns(items, page_top, page_bot):
    """Return the x of a clean column gutter if this page is a genuine
    two-column layout (two independent programs side by side), else None.

    The widest gap in the union of all detection x-intervals supplies the
    gutter midpoint, guaranteeing that no detection crosses it at any height.
    A wide line or a gutter that closes partway down covers that candidate
    gap. The remaining gates require substantial columns: at least
    MIN_COLUMN_LINES detections per side, each spanning at least
    MIN_COLUMN_VSPAN_FRACTION of the page height. Pages without a qualifying
    gap take the single-column path (including displaced-region reassembly).
    The coherence-based verification that was explored was found unreliable
    on real data (a single-column page can split into two coincidentally
    brace-balanced halves); the geometric persistence signal separates the
    two-column page from single-column ones."""
    if len(items) < 2 * MIN_COLUMN_LINES:
        return None
    page_height = page_bot - page_top
    if page_height <= 0:
        return None
    intervals = sorted((it["x"], it["x_max"]) for it in items)
    covered = intervals[0][1]
    best_gap, best_x = 0.0, None
    for x0, x1 in intervals[1:]:
        gap = x0 - covered
        if gap > best_gap:
            best_gap, best_x = gap, covered + gap / 2.0
        covered = max(covered, x1)
    if best_x is None or best_gap <= 0:
        return None
    # The coverage-gap midpoint already guarantees no crossing. Check that
    # both sides have enough detections and vertical span to be columns.
    left = [it for it in items if it["x_max"] <= best_x]
    right = [it for it in items if it["x"] >= best_x]
    if len(left) < MIN_COLUMN_LINES or len(right) < MIN_COLUMN_LINES:
        return None

    def vspan(side):
        ys = [it["y"] for it in side]
        return (max(ys) - min(ys)) / page_height

    if (vspan(left) < MIN_COLUMN_VSPAN_FRACTION
            or vspan(right) < MIN_COLUMN_VSPAN_FRACTION):
        return None
    return best_x


def _detect_banded_column(items, median_width, line_tol):
    """Return (gutter_x, left_items, right_items) if this page has a banded
    right-side column, else None.

    A banded right column is a persistent right cluster occupying a contiguous
    y-band with a clean, wide, uncrossed gutter WITHIN that band. This
    generalizes _detect_two_columns to a right block that spans less than half
    the page height -- a two-page / side-by-side capture whose continuation
    fills only the top-right quadrant, where the full-page x-projection is
    bridged by a stray wide line elsewhere so _detect_two_columns reports no
    gutter. Meant to run only when _detect_two_columns returns None.

    The band is derived from the right cluster itself, so no page-height gate is
    applied (the design deliberately has no minimum band height -- that is the
    point: it catches sub-0.5 blocks).

    Pure geometry and grade-safe: only whole detected pieces are partitioned by
    position; no character is added, edited, split, or dropped. Any degenerate
    or ambiguous geometry (missing boxes, too few items, no clean band, a
    crossed gutter) returns None, i.e. today's behavior. See
    docs/superpowers/specs/2026-09-12-banded-column-detection-design.md.
    """
    width = finite_float(median_width)
    tol = finite_float(line_tol)
    if width is None or width <= 0 or tol is None or tol <= 0:
        return None
    if not isinstance(items, (list, tuple)) or len(items) < 2 * MIN_BAND_ROWS:
        return None
    # Every item needs finite, well-formed horizontal and vertical geometry;
    # otherwise regrouping is unsafe -> decline.
    for it in items:
        x, x_max = finite_float(it.get("x")), finite_float(it.get("x_max"))
        y = finite_float(it.get("y"))
        y_min, y_max = finite_float(it.get("y_min")), finite_float(it.get("y_max"))
        if (x is None or x_max is None or y is None
                or y_min is None or y_max is None
                or x_max <= x or y_max <= y_min):
            return None

    band_x_align = BAND_X_ALIGN_MULTIPLIER * width
    band_gutter_min = max(BAND_GUTTER_MIN_MULTIPLIER * width, BAND_GUTTER_MIN_FLOOR)

    # Count distinct visual rows in a set of members, grouping by line_tol on the
    # y-center (each row anchored at its first member). This is the persistence
    # measure for the right cluster.
    def distinct_rows(members):
        count, anchor = 0, None
        for member in sorted(members, key=lambda m: m["y"]):
            if anchor is None or member["y"] - anchor > tol:
                count += 1
                anchor = member["y"]
        return count

    # Build the right cluster by x0. Seeding from the single largest-x0 item is
    # fragile: a lone far-right stray (a page-edge mark) beyond band_x_align of a
    # real right column would seed a one-item cluster and hide that column. So
    # try each item as a seed in descending-x0 order and take the first whose
    # greedy median-aligned group is a persistent column (>= MIN_BAND_ROWS
    # distinct rows). Any higher-x0 strays sitting above the chosen seed are
    # folded into the right cluster, so no content is dropped and a stray cannot
    # inflate the left column's reach. Cluster-median membership (not pairwise)
    # tolerates the gradual right-margin drift of handwriting.
    ordered = sorted(items, key=lambda it: it["x"], reverse=True)
    cluster_ids = None
    for start in range(len(ordered) - MIN_BAND_ROWS + 1):
        ids = {id(ordered[start])}
        cluster_x0s = [ordered[start]["x"]]  # kept sorted via bisect.insort
        for it in ordered[start + 1:]:
            median_x0 = cluster_x0s[len(cluster_x0s) // 2]
            if abs(it["x"] - median_x0) <= band_x_align:
                ids.add(id(it))
                bisect.insort(cluster_x0s, it["x"])
            else:
                break
        if distinct_rows([it for it in ordered if id(it) in ids]) >= MIN_BAND_ROWS:
            for j in range(start):
                ids.add(id(ordered[j]))
            cluster_ids = ids
            break
    if cluster_ids is None:
        return None
    # Preserve the caller's item order (y-sorted in the live pipeline) in both
    # partitions so the column ordering sweep reads top-to-bottom.
    right = [it for it in items if id(it) in cluster_ids]
    left = [it for it in items if id(it) not in cluster_ids]
    if not left:
        return None

    # Clean banded gutter: WITHIN the right cluster's y-band, the widest left
    # reach must clear the leftmost right edge by at least band_gutter_min.
    band_top = min(member["y_min"] for member in right)
    band_bot = max(member["y_max"] for member in right)

    def intersects_band(it):
        return it["y_max"] >= band_top and it["y_min"] <= band_bot

    left_in_band = [it for it in left if intersects_band(it)]
    if not left_in_band:
        return None
    left_max = max(it["x_max"] for it in left_in_band)
    right_min = min(member["x"] for member in right)
    if right_min - left_max < band_gutter_min:
        return None

    # The gutter is the midpoint of the clean band gap gated just above. By
    # construction every band item lies wholly on one side of it (a left-in-band
    # reach <= left_max < gutter < right_min <= every right x0), so no band item
    # can straddle it -- the band-gap gate already rejects any crossing.
    gutter = (left_max + right_min) / 2.0
    return gutter, left, right


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
            ordered_lines = [
                sorted(line["members"], key=lambda member: member["x"])
                for line in left_lines + right_lines
            ]
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
                ordered_lines = [
                    sorted(line["members"], key=lambda member: member["x"])
                    for line in left_lines + right_lines
                ]
                return ordered_lines, True
            # Either column had unsafe geometry -- fall through to single-column.

    lines = _order_column_items(
        items, line_tol, region_gap_threshold, baseline_gap_threshold)
    if lines is None:
        return _original_detection_records(rec_texts, rec_scores), False
    if gutter_x is None:
        lines = _sever_displaced_regions(lines, median_width)
    _assign_indent_levels(lines, median_char_width)
    ordered_lines = [
        sorted(line["members"], key=lambda member: member["x"])
        for line in lines
    ]
    return ordered_lines, True


def line_member_bounds(members):
    """Union bounding box (x_min, y_min, x_max, y_max) in raw pixel space over
    a line's grouped members. Members must carry finite x/x_max/y_min/y_max --
    i.e. come from the geometry-safe path of _group_detection_records; callers
    guard for that before calling. Shared so the live pipeline and the offline
    crop builder compute a line's box the same way."""
    x_min = min(member["x"] for member in members)
    x_max = max(member["x_max"] for member in members)
    y_min = min(member["y_min"] for member in members)
    y_max = max(member["y_max"] for member in members)
    return x_min, y_min, x_max, y_max


def _assign_indent_levels(column_lines, char_width):
    """Set each line's reconstructed indent level on its member dicts.

    `column_lines` is a list of line dicts (each with a "members" list whose
    members carry "x"), all belonging to ONE column. `char_width` is the median
    character width (box width / text length) of the page. Indent is measured
    from that column's own left margin, so a two-column page's right column is
    not read as deeply indented. Quantized into levels of
    INDENT_STEP_CHARS * char_width and clamped to [0, MAX_INDENT_LEVELS].
    Mutates members in place, adding an "indent" key. Any degenerate geometry
    (no unit, non-finite x) yields level 0, i.e. today's flat behavior."""
    if not column_lines:
        return
    unit = INDENT_STEP_CHARS * char_width
    lefts = [min(member["x"] for member in line["members"])
             for line in column_lines]
    column_left = min(lefts)
    for line, x_min in zip(column_lines, lefts):
        if unit > 0 and math.isfinite(x_min) and math.isfinite(column_left):
            level = round((x_min - column_left) / unit)
            level = max(0, min(level, MAX_INDENT_LEVELS))
        else:
            level = 0
        for member in line["members"]:
            member["indent"] = level


def _join_lines_with_vertical_gaps(structured_lines):
    """Join structured line texts with `\n`, inserting blank lines where the
    student left a vertical gap. `blanks = round(gap / pitch) - 1` per gap,
    where pitch is the median positive consecutive center delta, clamped to
    [0, MAX_BLANK_LINES]. Missing/degenerate geometry -> compact single-`\n`
    join (today's behavior). Two-column seams are negative deltas -> 0 blanks."""
    if not structured_lines:
        return ""
    centers = []
    for line in structured_lines:
        y_min = line.get("y_min")
        y_max = line.get("y_max")
        if y_min is None or y_max is None:
            centers.append(None)
        else:
            centers.append((y_min + y_max) / 2.0)
    deltas = sorted(
        centers[i] - centers[i - 1]
        for i in range(1, len(centers))
        if centers[i] is not None and centers[i - 1] is not None
        and centers[i] - centers[i - 1] > 0
    )
    pitch = deltas[len(deltas) // 2] if deltas else 0.0

    parts = [structured_lines[0]["text"]]
    for i in range(1, len(structured_lines)):
        blanks = 0
        if pitch > 0 and centers[i] is not None and centers[i - 1] is not None:
            gap = centers[i] - centers[i - 1]
            if gap > 0:
                blanks = round(gap / pitch) - 1
                blanks = max(0, min(blanks, MAX_BLANK_LINES))
        parts.append("\n" * (blanks + 1) + structured_lines[i]["text"])
    return "".join(parts)


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
