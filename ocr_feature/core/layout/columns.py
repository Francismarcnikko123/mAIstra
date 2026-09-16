"""Column-layout detectors for the OCR reading-order pipeline.

This module identifies confident full-height and partial-height right columns
from uncrossed horizontal gutters. It groups or reorders no recognition text;
callers decide how to order the whole detected regions it returns.
"""

import bisect

from core.numeric import finite_float

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
