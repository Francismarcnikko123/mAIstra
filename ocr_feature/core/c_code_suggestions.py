"""Non-mutating review suggestions for recognized C code.

This module is the *uncertain* half of OCR correction; c_code_cleanup.py is
the *safe* half. The split is by confidence, not by token, so the two never
overlap:

  - c_code_cleanup.py silently rewrites a small closed vocabulary that is
    safe to auto-correct (C keywords, standard headers). The teacher sees the
    result already applied in `cleaned_text`.
  - This module proposes fixes that are plausible but NOT safe to apply
    automatically, and never edits the text. Each is returned as a suggestion
    the teacher accepts or rejects, with its position and OCR confidence.

The only class of fix that currently belongs here is a function-call
misspelling (e.g. `printe(` -> `printf`): the trailing `(` makes it clearly a
call, but the identifier itself is student-authored and could legitimately be
a custom name, so it must stay a suggestion rather than an auto-edit.
"""

import re

from core.c_literals import C_LITERAL  # masks string/char literals to shield them
from core.numeric import finite_float

# Only tokens immediately followed by '(' are candidates -- a bare "printe"
# elsewhere isn't necessarily a mistyped call, but "printe(" is unambiguous.
_CALL_TOKEN = re.compile(r"\b([A-Za-z_]\w*)\s*(?=\()")
_CALL_FIXES = {
    "printe": "printf",
    "printt": "printf",
    "scant": "scanf",
}


def _line_confidence(detail) -> float | None:
    if not isinstance(detail, dict):
        return None
    return finite_float(detail.get("mean_confidence"))


def _suggestion(
    line: int,
    start: int,
    end: int,
    original: str,
    candidate: str,
    reason: str,
    rule_id: str,
    confidence: float | None,
) -> dict:
    return {
        "line": line,
        "start": start,
        "end": end,
        "original": original,
        "candidate": candidate,
        "reason": reason,
        "rule_id": rule_id,
        "confidence": confidence,
    }


def _overlaps_literal(match, literal_spans: list[tuple[int, int]]) -> bool:
    """True if match falls inside a string/char literal on this line --
    student content there must never be treated as a code typo."""
    return any(
        match.start() < end and match.end() > start
        for start, end in literal_spans
    )


def suggest_c_code(
    text: str,
    line_details: list[dict] | None = None,
) -> list[dict]:
    """Return review suggestions without changing the recognized text."""
    if not text:
        return []

    details_by_line = {
        detail.get("line"): detail
        for detail in (line_details or [])
        if isinstance(detail, dict)
    }
    suggestions = []

    for line_number, line in enumerate(text.splitlines(), 1):
        literal_spans = [match.span() for match in C_LITERAL.finditer(line)]
        confidence = _line_confidence(details_by_line.get(line_number))

        for match in _CALL_TOKEN.finditer(line):
            if _overlaps_literal(match, literal_spans):
                continue
            original = match.group(1)
            candidate = _CALL_FIXES.get(original)
            if candidate:
                suggestions.append(_suggestion(
                    line_number,
                    match.start(1),
                    match.end(1),
                    original,
                    candidate,
                    f"Looks like an OCR variant of {candidate} used as a call.",
                    f"function-call-{candidate}",
                    confidence,
                ))

    return suggestions
