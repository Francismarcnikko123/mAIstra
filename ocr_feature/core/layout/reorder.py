"""Compatibility imports for the former :mod:`core.layout.reorder` module.

The reading-order implementation is now separated by concern under
:mod:`core.layout`. New callers should import from ``core.layout``; this module
keeps direct legacy imports working without owning an independent call path.
"""

from . import (
    BAND_GUTTER_MIN_FLOOR, BAND_GUTTER_MIN_MULTIPLIER, BAND_X_ALIGN_MULTIPLIER,
    BASELINE_REGION_GAP_MULTIPLIER, BRACE_CANDIDATE_MIN_ROWS,
    BRACE_CANDIDATE_X_SHIFT_FLOOR, BRACE_CANDIDATE_X_SHIFT_MULTIPLIER,
    INDENT_STEP_CHARS, INDENT_STRING, MAX_BLANK_LINES, MAX_DISPLACED_REGION_LINES,
    MAX_DISPLACED_REGION_SPAN, MAX_INDENT_LEVELS, MAX_SAME_LINE_X_OVERLAP,
    MIN_BAND_ROWS, MIN_COLUMN_LINES, MIN_COLUMN_VSPAN_FRACTION, MIN_SEVER_ROWS,
    REGION_GAP_MULTIPLIER, SEVER_GAP_MULTIPLIER, SEVER_X_ALIGN_MULTIPLIER,
    _associate_continuation, _assign_indent_levels, _brace_delta,
    _detect_banded_column, _detect_two_columns, _finalize_grouped_lines,
    _expected_line_y, _group_detection_records, _group_structured_lines,
    _is_definition_close, _join_lines_with_vertical_gaps, _line_identity_order,
    _order_column_items, _original_detection_records, _reassemble_displaced_regions,
    _reassemble_margin_candidates, _sever_displaced_regions,
    _sweep_detection_records, _trace_displaced_region, line_member_bounds,
)
