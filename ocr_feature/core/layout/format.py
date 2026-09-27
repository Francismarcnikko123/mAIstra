"""Restore the student's indentation and blank lines.

Works from box positions, not from the braces: indentation from each line's
left edge, blank lines from the vertical gaps between lines. It only adds
whitespace; the recognized characters are unchanged.
"""
import math


# One indent level = 3 character widths from the column's left edge.
# Measured in characters, not boxes: a box spans a whole word (about 10
# characters), which would round every real indent to zero.
INDENT_STEP_CHARS = 3.0
MAX_INDENT_LEVELS = 8
INDENT_STRING = "  "

# At most 2 blank lines in a row, so one large gap can't add many.
MAX_BLANK_LINES = 2


def line_member_bounds(members):
    """Bounding box (x_min, y_min, x_max, y_max) around a line's members, in
    pixels. Members need valid positions. The training-crop builder uses it
    too, so both cut lines the same way."""
    x_min = min(member["x"] for member in members)
    x_max = max(member["x_max"] for member in members)
    y_min = min(member["y_min"] for member in members)
    y_max = max(member["y_max"] for member in members)
    return x_min, y_min, x_max, y_max


def _assign_indent_levels(column_lines, char_width):
    """Set an "indent" level on every member of the lines of one column.

    The level is the distance from the column's own left edge (so a right
    column isn't read as deeply indented), in steps of
    INDENT_STEP_CHARS * char_width, from 0 to MAX_INDENT_LEVELS.
    `char_width` is the page's median character width. Missing geometry
    gives level 0."""
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
    """Join the lines with newlines, adding blank lines where the student left
    a vertical gap: round(gap / normal line spacing) - 1, at most
    MAX_BLANK_LINES. Without positions, or where the next line is higher up
    (a new column), no blank line is added."""
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
