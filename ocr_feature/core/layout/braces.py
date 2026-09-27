"""Count C braces in recognized text.

Braces inside strings, character literals and comments are ignored: they are
content, not structure. Used to check whether moving a block gives balanced
braces.
"""
import re

from core.c_literals import C_LITERAL

# Strings, character literals and comments. Literals come first, so a "//"
# inside a string stays part of the string. core.continuation masks the same
# way, so both brace checks agree.
_LITERAL_OR_COMMENT = re.compile(
    C_LITERAL.pattern + r"|//[^\n]*|/\*.*?\*/", re.S
)


def _brace_delta(text: str) -> int:
    """Opening minus closing braces in `text`, ignoring strings, character
    literals and comments."""
    delta = 0
    last = 0
    for match in _LITERAL_OR_COMMENT.finditer(text):
        segment = text[last:match.start()]
        delta += segment.count("{") - segment.count("}")
        last = match.end()
    segment = text[last:]
    delta += segment.count("{") - segment.count("}")
    return delta


def _is_definition_close(text: str) -> bool:
    """True if every `}` on the line is followed by `;`, the end of a struct,
    union, enum or initializer (strings and comments ignored).

    A block moved from the margin is executable code: it can belong inside
    an if or a loop (closed by `}`), but never inside a type definition
    (closed by `};`). A line that mixes both, such as `} };`, returns False.
    """
    stripped = ""
    last = 0
    for match in _LITERAL_OR_COMMENT.finditer(text):
        stripped += text[last:match.start()]
        last = match.end()
    stripped += text[last:]
    for match in re.finditer(r"\}", stripped):
        if not re.match(r"\s*;", stripped[match.end():]):
            return False
    return True
