"""C brace-depth primitives for reading-order reassembly.

Two small, pure helpers that measure `{}` structure in a line of recognized
text while ignoring anything inside a string/char literal -- that is student
content, never real C structure. They back the displaced-region reassembly
guard in core.layout (brace-well-formedness and definition-close checks).

Split out of core/layout.py on 2026-09-17 as a behavior-preserving refactor
-- the function bodies are unchanged. Depends only on the standard library
`re` and core.c_literals (the same C_LITERAL segment pattern
c_code_cleanup.py walks, so literal handling never drifts between call sites).
core.layout re-exports `_brace_delta` so existing callers -- including
core.ocr_pipeline -- keep importing it from core.layout unchanged.
"""
import re

from core.c_literals import C_LITERAL


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
