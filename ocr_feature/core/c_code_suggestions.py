"""Conservative, non-mutating review suggestions for recognized C code."""

import math
import re


_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"' r"|'(?:\\.|[^'\\])*'")
_INCLUDE_CANDIDATE = re.compile(
    r"^\s*#?\s*(?:include|1nclude)\s*<\s*"
    r"(stdio|std1o|stdlo|stdlib|string|math|ctype|time)\b.*$",
    re.IGNORECASE,
)
_HEADER_FIXES = {"std1o": "stdio", "stdlo": "stdio"}
_CALL_TOKEN = re.compile(r"\b([A-Za-z_]\w*)\s*(?=\()")
_CALL_FIXES = {
    "printe": "printf",
    "printt": "printf",
    "scant": "scanf",
}
_WORD_TOKEN = re.compile(r"(?<!\w)([A-Za-z0-9_]+)(?!\w)")
_TOKEN_FIXES = {
    "1nt": "int",
    "ma1n": "main",
    "retvrn": "return",
    "wh1le": "while",
    "f0r": "for",
}


def _line_confidence(detail) -> float | None:
    if not isinstance(detail, dict):
        return None
    try:
        confidence = float(detail.get("mean_confidence"))
    except (TypeError, ValueError):
        return None
    return confidence if math.isfinite(confidence) else None


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
        literal_spans = [match.span() for match in _LITERAL.finditer(line)]
        confidence = _line_confidence(details_by_line.get(line_number))

        include_match = _INCLUDE_CANDIDATE.match(line)
        if include_match:
            recognized_header = include_match.group(1).lower()
            header = _HEADER_FIXES.get(recognized_header, recognized_header)
            candidate = f"#include <{header}.h>"
            if line.strip() != candidate:
                suggestions.append(_suggestion(
                    line_number,
                    0,
                    len(line),
                    line,
                    candidate,
                    "Recognizable standard header with OCR damage.",
                    "known-header",
                    confidence,
                ))
            continue

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

        for match in _WORD_TOKEN.finditer(line):
            if _overlaps_literal(match, literal_spans):
                continue
            original = match.group(1)
            candidate = _TOKEN_FIXES.get(original)
            if candidate:
                suggestions.append(_suggestion(
                    line_number,
                    match.start(1),
                    match.end(1),
                    original,
                    candidate,
                    f"Looks like an OCR variant of the C token {candidate}.",
                    f"c-token-{candidate}",
                    confidence,
                ))

    return suggestions
