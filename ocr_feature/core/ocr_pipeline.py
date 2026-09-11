import math
import os
import re
from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from core.preprocess import preprocess_image, PreprocessConfig, DEFAULT_CONFIG
from core.numeric import finite_float
from core.debug_artifact import write_debug_artifact
from core.c_code_cleanup import clean_c_code
from core.c_literals import C_LITERAL
from core.c_code_suggestions import suggest_c_code


# Detection is pinned by name -- passing a model name makes PaddleOCR
# silently ignore lang/ocr_version, so setting those too would be misleading.
# Recognition is pinned by directory instead (see the fine-tuned recognizer
# block below), since the fine-tuned weights are the only recognizer this
# pipeline runs -- there is no stock-model fallback.
#
# No orientation/unwarp passes: captures are already gated upright/flat by
# the mobile app, so these passes only add cost (~80s -> a few seconds/image
# on CPU) with nothing to correct.
#
# v6_medium (det+rec) is the selected pairing over the v5 alternatives: it
# won on CER across every paper/writer subgroup tested, and bigger isn't
# better here -- the v5 server recognizer is multilingual and substitutes
# CJK characters for C symbols (e.g. '二' for '='), which is why an English-
# only recognizer is pinned rather than the largest available one. v6_medium
# still emits occasional CJK, but rare enough to be cosmetic, not an accuracy
# problem. Full sweep numbers: docs/ocr/EVALUATION.md.

# Fine-tuned recognizer (2026-08-30): trained on 2,491 handwritten C-code
# line crops, cut recognition CER on the held-out samples/ set from 0.274
# (stock PP-OCRv6_medium_rec) to 0.126 (-54%), improving every sample with
# no regressions. That 0.274 -> 0.126 is the historical recognition-only
# fine-tune comparison, before the two-column reading-order split. Current
# samples/ end-to-end metrics after that split are clean_ws CER 0.099,
# clean WER 0.328, and clean token accuracy 0.716 (evaluate_cer).
# This is the ONLY recognizer this pipeline runs -- no
# stock-model fallback -- so the result the thesis measured is always what's
# actually running, never silently swapped for something weaker. Weights
# aren't committed (see models/README.md -- ~76MB, distributed via a GitHub
# Release) and reproduced via docs/ocr/COLAB_SETUP_WORKING.md. A teammate who
# hasn't downloaded them yet gets a clear error below, not a silent
# degradation to stock.
# Default is the shipped fine-tuned recognizer. An offline eval experiment can
# point the pipeline at a DIFFERENT recognizer (e.g. the cross-writer
# measurement model in models/fine_tuned_rec_crosswriter/) by setting
# MAISTRA_REC_MODEL_DIR, without editing this file -- see
# evaluators/crosswriter_eval.py. The default is resolved from this file so
# demo tools can also run from the repository root; explicit overrides retain
# their caller-supplied path semantics.
_FINE_TUNED_REC_DIR = os.environ.get(
    "MAISTRA_REC_MODEL_DIR",
    str(Path(__file__).resolve().parent.parent / "models/fine_tuned_rec/inference"),
)
if not Path(_FINE_TUNED_REC_DIR).exists():
    raise FileNotFoundError(
        f"Fine-tuned recognizer not found at '{_FINE_TUNED_REC_DIR}'. "
        "Download it from the GitHub Release and unzip it there -- see "
        "models/README.md for instructions."
    )
print(f"[ocr_pipeline] recognizer: fine-tuned ({_FINE_TUNED_REC_DIR})")

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_dir=_FINE_TUNED_REC_DIR,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    # Lowered from PaddleOCR's default 0.60 to 0.30, decided by measurement
    # (2026-09-04). The fine-tuned recognizer reads braces well (0.9-1.0 conf),
    # but standalone braces and some faint code lines were being LOST AT
    # DETECTION -- their box score fell below the 0.60 cutoff, so the recognizer
    # never saw them. A/B on the 20-image gate set, sweeping 0.60/0.40/0.30:
    # historical recognition-only clean_ws CER stayed 0.126 at every value
    # (no phantom-detection regression), while closing-brace recovery rose
    # 82 -> 86 -> 87 of 89. This sweep preceded the two-column split; current
    # end-to-end samples/ clean_ws CER is 0.099 with the shipped setting.
    # A sharper 0.40-vs-0.30 diff confirmed every extra box at 0.30 is REAL
    # content (1 brace + 4 whole code lines that were missing), zero junk. For a
    # grading app "misread beats missing" -- a recovered line is teacher-fixable
    # in the widget, a dropped line may never be noticed. REC_SCORE_FLOOR (0.3)
    # still guards the recognition stage against genuine junk. Full A/B:
    # docs/ocr/EVALUATION.md, docs/ocr/DEFENSE_PREP.md.
    text_det_box_thresh=0.30,
    device="cpu"
)


def warmup() -> None:
    """Run one throwaway prediction so PaddleOCR loads its models now, at
    startup, instead of on the first real request. Called from main.py's
    lifespan hook."""
    dummy = np.full((80, 240, 3), 255, dtype=np.uint8)
    cv2.putText(
        dummy, "int main", (5, 55),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2
    )
    try:
        ocr.predict(dummy)
    except Exception:
        # Warm-up is best-effort; a failure here must never block startup.
        pass


# Below this score a detection is almost always the detector firing on a
# smudge or stray mark rather than real writing, not a genuine hard-to-read
# character. Re-verified against the current v6 recognizer on the gate-framed
# test set: everything dropped is either an empty-text phantom (score 0.0) or
# obvious junk (highest dropped 0.291: 's', '>', 'a', '2222'), while the
# lowest real kept detection is 0.334 and the median kept score is 0.936.
# 0.3 sits cleanly in the 0.291 -> 0.334 gap, so it removes noise without
# touching real text.
REC_SCORE_FLOOR = 0.3

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

# Two-column split (two independent programs written side by side to save
# paper). Detection is deliberately conservative: a vertical gutter that NO
# detection crosses, with substantial vertically-distributed content on both
# sides. Validated against the real dataset -- fires on the one genuine
# two-column page (green_writer10_B2_1.jpg) and none of the 34 single-column
# pages. See docs/superpowers/specs/2026-09-10-displaced-region-tracking-design.md.
MIN_COLUMN_LINES = 4
MIN_COLUMN_VSPAN_FRACTION = 0.5

# Reconstruct the student's handwritten indentation from box geometry -- NOT
# brace depth. A line indented on paper has a larger left-edge x; one indent
# level is INDENT_UNIT_FRACTION median-box-widths of rightward offset from the
# line's own column left margin. Recognition-independent and presentation-only:
# it prepends whitespace, never changing which characters are emitted.
INDENT_UNIT_FRACTION = 2.0
MAX_INDENT_LEVELS = 8
INDENT_STRING = "  "


def _filter_low_confidence(rec_texts, rec_scores, rec_boxes):
    """Drop entries below REC_SCORE_FLOOR, keeping the three lists aligned.
    A missing score passes through rather than getting dropped. Also returns
    the dropped entries so the debug artifact can show what was discarded."""
    if not rec_scores or len(rec_scores) != len(rec_texts):
        return rec_texts, rec_scores, rec_boxes, []
    keep_texts, keep_scores, keep_boxes = [], [], []
    dropped = []
    for i, text in enumerate(rec_texts):
        score = rec_scores[i]
        try:
            passes = float(score) >= REC_SCORE_FLOOR
        except (TypeError, ValueError):
            passes = True
        if passes:
            keep_texts.append(text)
            keep_scores.append(score)
            if i < len(rec_boxes):
                keep_boxes.append(rec_boxes[i])
        else:
            dropped.append({
                "text": text,
                "score": score,
                "box": rec_boxes[i] if i < len(rec_boxes) else None,
            })
    return keep_texts, keep_scores, keep_boxes, dropped


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
            _assign_indent_levels(left_lines, median_width)
            _assign_indent_levels(right_lines, median_width)
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
    _assign_indent_levels(lines, median_width)
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


def _assign_indent_levels(column_lines, median_width):
    """Set each line's reconstructed indent level on its member dicts.

    `column_lines` is a list of line dicts (each with a "members" list whose
    members carry "x"), all belonging to ONE column. Indent is measured from
    that column's own left margin, so a two-column page's right column is not
    read as deeply indented. Quantized into levels of
    INDENT_UNIT_FRACTION * median_width and clamped to [0, MAX_INDENT_LEVELS].
    Mutates members in place, adding an "indent" key. Any degenerate geometry
    (no unit, non-finite x) yields level 0, i.e. today's flat behavior."""
    if not column_lines:
        return
    unit = INDENT_UNIT_FRACTION * median_width
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


def _build_line_details(grouped_lines):
    """Build additive per-line review data without judging correctness."""
    details = []
    for members in grouped_lines:
        parts = [text.strip() for text, _ in members if text and text.strip()]
        if not parts:
            continue

        scores = []
        for _, score in members:
            numeric_score = finite_float(score)
            if numeric_score is not None:
                scores.append(numeric_score)

        details.append({
            "line": len(details) + 1,
            "text": " ".join(parts),
            "scores": scores,
            "min_confidence": min(scores) if scores else None,
            "mean_confidence": (
                sum(scores) / len(scores) if scores else None
            ),
            "review_reasons": [],
        })
    return details


def _attach_suggestion_reasons(line_details, suggestions) -> None:
    """Attach rule identifiers to line details for teacher navigation."""
    details_by_line = {detail["line"]: detail for detail in line_details}
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue
        try:
            line_number = int(suggestion.get("line"))
        except (TypeError, ValueError, OverflowError):
            continue
        rule_id = suggestion.get("rule_id")
        detail = details_by_line.get(line_number)
        if not detail or not isinstance(rule_id, str) or not rule_id:
            continue
        if rule_id not in detail["review_reasons"]:
            detail["review_reasons"].append(rule_id)


def _recognize_preprocessed(preprocessed_path: str) -> dict:
    """Recognize one preprocessed image and preserve per-line geometry."""
    try:
        image = cv2.imread(preprocessed_path, cv2.IMREAD_GRAYSCALE)
        image_height = image.shape[0] if image is not None else None
        numeric_height = float(image_height)
    except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
        numeric_height = 0.0
    if not math.isfinite(numeric_height) or numeric_height <= 0:
        raise ValueError(
            f"could not read preprocessed image: {preprocessed_path}"
        )

    results = ocr.predict(preprocessed_path)
    structured_lines = []
    confidence_scores = []
    debug_detections = []
    debug_dropped = []

    for page in results:
        data = page.json
        result_data = data.get("res", {})

        rec_texts = result_data.get("rec_texts", [])
        rec_scores = result_data.get("rec_scores", [])
        rec_boxes = result_data.get("rec_boxes", [])

        rec_texts, rec_scores, rec_boxes, dropped = _filter_low_confidence(
            rec_texts, rec_scores, rec_boxes
        )
        debug_dropped.extend(dropped)
        for i, text in enumerate(rec_texts):
            debug_detections.append({
                "text": text,
                "score": rec_scores[i] if i < len(rec_scores) else None,
                "box": rec_boxes[i] if i < len(rec_boxes) else None,
            })
            score = rec_scores[i] if i < len(rec_scores) else 0.0
            try:
                confidence_scores.append(float(score))
            except Exception:
                pass

        structured_lines.extend(_group_structured_lines(
            rec_texts, rec_scores, rec_boxes, numeric_height
        ))

    average_confidence = None
    if confidence_scores:
        average_confidence = sum(confidence_scores) / len(confidence_scores)

    return {
        "raw_text": "\n".join(line["text"] for line in structured_lines),
        "lines": structured_lines,
        "grouped_lines": [line["members"] for line in structured_lines],
        "average_confidence": average_confidence,
        "detections": debug_detections,
        "dropped_low_confidence": debug_dropped,
        "debug_lines": [
            [
                {"text": text, "score": score}
                for text, score in line["members"]
            ]
            for line in structured_lines
        ],
    }


def extract_text_from_image(
    image_path: str,
    preprocess_config: PreprocessConfig = DEFAULT_CONFIG,
    output_dir: str = "outputs",
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    preprocessed_path = preprocess_image(
        image_path=image_path,
        output_dir=str(output_path),
        config=preprocess_config,
    )

    selected_attempt = _recognize_preprocessed(preprocessed_path)

    raw_text = selected_attempt["raw_text"]
    grouped_lines = selected_attempt["grouped_lines"]

    # Light keyword-only tidy so the teacher has fewer edits. The raw text is
    # kept separately; cleaning never touches string literals or arbitrary
    # content. See c_code_cleanup.py.
    cleaned_text = clean_c_code(raw_text)
    line_details = _build_line_details(grouped_lines)

    # Suggestions are teacher-review hints only. They never modify either OCR
    # text field, and a failure here must not turn a successful extraction into
    # an API error.
    try:
        review_suggestions = suggest_c_code(raw_text, line_details)
        review_diagnostics = []
    except Exception as exc:
        review_suggestions = []
        review_diagnostics = [
            f"suggestion engine failed: {type(exc).__name__}"
        ]
    _attach_suggestion_reasons(line_details, review_suggestions)

    average_confidence = selected_attempt["average_confidence"]

    debug = {
        "source_image": image_path,
        "preprocessed_image": preprocessed_path,
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "average_confidence": average_confidence,
        "rec_score_floor": REC_SCORE_FLOOR,
        "detections": selected_attempt["detections"],
        "dropped_low_confidence": selected_attempt["dropped_low_confidence"],
        "grouped_lines": selected_attempt["debug_lines"],
        "line_details": line_details,
        "review_suggestions": review_suggestions,
        "review_diagnostics": review_diagnostics,
    }
    write_debug_artifact(preprocessed_path, debug)

    result = {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "average_confidence": average_confidence,
        "preprocessed_image": preprocessed_path,
        "line_details": line_details,
        "review_suggestions": review_suggestions,
        "review_diagnostics": review_diagnostics,
    }
    return result
