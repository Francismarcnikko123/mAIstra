"""Indentation and blank-line reconstruction for the OCR pipeline.

Turns already-ordered visual lines into presentation text: reconstructs the
student's handwritten indentation from box geometry (NOT brace depth), the
student's vertical spacing (blank lines) from inter-line gaps, and a line's
union bounding box. Recognition-independent and presentation-only -- it
prepends whitespace and inserts blank lines, never changing which characters
are emitted.

Split out of core/layout.py on 2026-09-17 as a behavior-preserving refactor
-- the function bodies are unchanged. Pure standard library (math only).
core.layout re-exports these names (and the INDENT_* / MAX_BLANK_LINES
constants) for package-level callers and the geometry tests. `line_member_bounds`
is also re-exported from core.ocr_pipeline (used by
evaluators/build_recognition_dataset); the other former ocr_pipeline re-exports
from here, such as `_expected_line_y`, were removed 2026-09-18 as unused --
import them directly from core.layout.
"""
import math


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
