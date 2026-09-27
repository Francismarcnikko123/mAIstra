"""Detect pages written in two columns.

Finds a vertical gap that no detection crosses, with enough writing on both
sides. Returns positions only; the caller decides the reading order.
"""

import bisect

from core.numeric import finite_float

# Full-height columns (two programs side by side). Strict on purpose: at
# least 4 detections per side, each side spanning at least half the page
# height. Tested on 35 real pages: it found the one two-column page and none
# of the 34 single-column pages.
MIN_COLUMN_LINES = 4
MIN_COLUMN_VSPAN_FRACTION = 0.5

# Partial-height right column: a block on the right covering only part of
# the page, with a clear gap beside it at that height. Checked only when
# there is no full-height column. Widths are median box widths.
MIN_BAND_ROWS = 3                 # rows the right block must span
BAND_X_ALIGN_MULTIPLIER = 2.0     # max distance from the block's median left edge
# Minimum gap: 0.5 widths, at least 60 px. Real margin photos had gaps of
# 0.57 and 1.24 widths; the old 1.5 missed both, and 0.5 changed no other
# test result.
BAND_GUTTER_MIN_MULTIPLIER = 0.5
BAND_GUTTER_MIN_FLOOR = 60.0


def _detect_two_columns(items, page_top, page_bot):
    """Return the x position of the gap between two full-height columns, or
    None.

    The gap is the widest vertical strip that no detection crosses. It counts
    only if each side has at least MIN_COLUMN_LINES detections spanning at
    least MIN_COLUMN_VSPAN_FRACTION of the page height."""
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
    # Nothing crosses the gap by construction; check both sides are columns.
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
    """Return (gap_x, left_items, right_items) for a right column that
    covers only part of the page height, such as a continuation written in
    the top-right corner, or None.

    The right block must have aligned left edges, span at least
    MIN_BAND_ROWS rows, and be separated from the writing beside it by a
    clear gap. Missing or invalid geometry returns None.
    """
    width = finite_float(median_width)
    tol = finite_float(line_tol)
    if width is None or width <= 0 or tol is None or tol <= 0:
        return None
    if not isinstance(items, (list, tuple)) or len(items) < 2 * MIN_BAND_ROWS:
        return None
    # Every box needs a valid position and size.
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

    # Number of rows the members occupy: a new row starts more than line_tol
    # below the first box of the previous row.
    def distinct_rows(members):
        count, anchor = 0, None
        for member in sorted(members, key=lambda m: m["y"]):
            if anchor is None or member["y"] - anchor > tol:
                count += 1
                anchor = member["y"]
        return count

    # Find the right block: try each box as a seed, rightmost first, and grow
    # a group of boxes whose left edge is near the group's median. The first
    # group spanning MIN_BAND_ROWS rows wins, so a stray mark at the page edge
    # can't hide the real column. Boxes further right than the seed join the
    # block too.
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
    # Keep the caller's top-to-bottom order on both sides.
    right = [it for it in items if id(it) in cluster_ids]
    left = [it for it in items if id(it) not in cluster_ids]
    if not left:
        return None

    # At the block's height, the writing on the left must end at least
    # band_gutter_min before the block starts.
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

    # The midpoint of that gap; nothing at the block's height crosses it.
    gutter = (left_max + right_min) / 2.0
    return gutter, left, right
