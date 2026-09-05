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

Two classes of fix live here:

  - A function-call misspelling (e.g. `printe(` -> `printf`): the trailing `(`
    makes it clearly a call, but the identifier itself is student-authored and
    could legitimately be a custom name, so it must stay a suggestion rather
    than an auto-edit.
  - A likely-misread word INSIDE a printed message (string literal), e.g.
    `"Pleace enter..."` -> `please`. This is flagging, not fixing: a word in a
    printf/scanf message is the student's own authored text, and a misspelling
    there could be the OCR's fault OR the student's own genuine mistake --
    this module can't tell which. It only points the teacher at the exact
    word so they compare it with the paper; nothing is ever edited. This is
    the opposite lane from `_overlaps_literal` used elsewhere in this file,
    which exists to make sure code-typo suggestions never fire on message
    text -- this check runs *only* inside message text, and never proposes an
    edit, only a flag.
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

# A small, deliberately narrow set of words common in student console
# prompts/messages. NOT a general English dictionary -- a broad dictionary
# would flag legitimate uncommon words the student actually wrote, which is
# exactly the false-positive this feature must avoid. Only words within a
# short edit distance of one of these are ever flagged, and only as a
# question ("compare with the paper"), never as a claimed error.
_COMMON_MESSAGE_WORDS = {
    "please", "enter", "valid", "invalid", "number", "digit", "digits",
    "error", "correct", "incorrect", "exit", "continue", "again", "sum",
    "average", "total", "result", "value", "values", "hello", "world",
    "name", "grade", "score", "first", "second", "third", "positive",
    "negative", "even", "odd", "prime", "factorial", "array", "input",
    "output", "thank", "you", "welcome", "wrong", "right", "try", "done",
    "complete", "success", "fail", "failed", "count", "index", "size",
    "length", "must", "should", "cannot", "need", "required", "greater",
    "less", "than", "equal", "maximum", "minimum", "largest", "smallest",
}

_LITERAL_WORD = re.compile(r"[A-Za-z]{3,}")


def _edit_distance(a: str, b: str) -> int:
    """Standard Levenshtein distance -- small inputs (word-length strings),
    no need for the memory-saving two-row trick used elsewhere for full lines."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


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


def _literal_word_suggestions(
    line_number: int,
    line: str,
    literal_spans: list[tuple[int, int]],
    confidence: float | None,
) -> list[dict]:
    """Flag words INSIDE message text that closely resemble a common prompt
    word but don't match it exactly -- e.g. "valind" (paper says "valid").
    Never claims the word is wrong: it may be the OCR's misread, or the
    student's own genuine spelling. Only a flag to compare against the paper,
    never an edit."""
    if not literal_spans:
        return []

    out = []
    for match in _LITERAL_WORD.finditer(line):
        if not any(
            match.start() >= start and match.end() <= end
            for start, end in literal_spans
        ):
            continue  # only inside a literal -- code identifiers aren't in scope here

        word = match.group(0)
        lower = word.lower()
        if lower in _COMMON_MESSAGE_WORDS:
            continue  # already a recognized word -- nothing to flag

        # Distance 1 only. Real OCR word-misreads are almost always a single
        # substituted/inserted/dropped letter (valind->valid, numter->number,
        # digt->digit, Pleace->please). Allowing distance 2 lets unrelated words
        # match (printe->prime), which is a false positive this must avoid.
        threshold = 1
        best_word = None
        best_dist = threshold + 1
        tie = False
        for candidate in _COMMON_MESSAGE_WORDS:
            dist = _edit_distance(lower, candidate)
            if dist > threshold:
                continue
            if dist < best_dist:
                best_dist, best_word, tie = dist, candidate, False
            elif dist == best_dist:
                tie = True  # ambiguous which word was meant -- don't guess

        if best_word and not tie:
            out.append(_suggestion(
                line_number,
                match.start(),
                match.end(),
                word,
                best_word,
                "Word in the printed message doesn't match a common word -- "
                "may be an OCR misread or the student's own wording.",
                "literal-word-misread",
                confidence,
            ))
    return out


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

        suggestions.extend(
            _literal_word_suggestions(line_number, line, literal_spans, confidence)
        )

    return suggestions
