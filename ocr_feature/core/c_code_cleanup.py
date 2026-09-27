"""Fix common OCR misreads of C keywords and #include lines.

Only the fixed list below is corrected; strings and character literals are
never changed.
"""
import re

from core.c_literals import C_LITERAL

# Known OCR misread -> correct C token. Whole-token, case-sensitive. Keep this
# list small and obvious -- every entry should be defensible on its own.
FIXES = {

    # types
    "1nt": "int",
    "vo1d": "void",
    "cnar": "char",
    "f1oat": "float",
    "doub1e": "double",

    # keywords / control flow
    "1f": "if",
    "e1se": "else",
    "wh1le": "while",
    "f0r": "for",
    "retvrn": "return",
    "s1zeof": "sizeof",
    "swltch": "switch",
    "struc t": "struct",
    "cont1nue": "continue",

    # functions / headers
    "ma1n": "main",
    "pr1ntf": "printf",
    "1nclude": "include",
    "#inc1ude": "#include",
    "std1o": "stdio",
    "stdlo": "stdio",
    "std1ib": "stdlib",
}

# An #include line naming one of these headers is rewritten in full, which
# also fixes a misread extension (".n") or closing ">" (read as "7").
_KNOWN_HEADERS = ("stdio", "stdlib", "stddef", "string", "math", "ctype", "time")
# The "#" may be missing. After the header name only an extension and ">"
# may follow, so a line with more code after it is left alone, not cut off.
_INCLUDE_LINE = re.compile(
    r"^\s*#?\s*[Ii]nclude\s*<\s*(" + "|".join(_KNOWN_HEADERS)
    + r")\b\s*\.?\s*[A-Za-z]?\s*[>7]?\s*$"
)


def _fix_include_line(line: str) -> str:
    """Snap a recognizable but garbled #include line to its canonical form."""
    match = _INCLUDE_LINE.match(line)
    if match:
        return f"#include <{match.group(1)}.h>"
    return line


def _fix_segment(segment: str) -> str:
    """Apply whole-token keyword fixes to a chunk that has no string literals."""
    for wrong, right in FIXES.items():
        # \b won't help around '#', so match the token bounded by non-word chars.
        before = r"(?<![\w#])"
        if wrong[0].isdigit():
            # A misread starting with a digit ("1f", "1nt") is only fixed at
            # the start of a statement, so "1.1f" doesn't become "1.if".
            before = r"(?<![^\s{};(,])"
        pattern = before + re.escape(wrong) + r"(?![\w])"
        segment = re.sub(pattern, right, segment)
    return segment


def clean_c_code(text: str) -> str:
    """Return `text` with known keyword misreads fixed and #include lines
    rewritten in standard form. Strings and character literals are unchanged."""
    if not text:
        return text

    # 1) Keyword pass, shielding string/char literals from replacement.
    out = []
    last = 0
    for match in C_LITERAL.finditer(text):
        # Fix the code between literals, then re-attach the literal untouched.
        out.append(_fix_segment(text[last:match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(_fix_segment(text[last:]))
    fixed = "".join(out)

    # 2) Then #include lines, so a header fixed above (std1o -> stdio) counts.
    return "\n".join(_fix_include_line(line) for line in fixed.split("\n"))
