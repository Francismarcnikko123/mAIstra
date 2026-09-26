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

# Standard headers are a small closed set, so an #include line is safe to
# normalize even when OCR mangles the extension ('.h' -> '.n') or the closing
# '>' (often read as '7') -- only a line that already looks like an #include
# with a known header gets touched. A stray '7' or '>' elsewhere is left
# alone since it could be real content.
_KNOWN_HEADERS = ("stdio", "stdlib", "stddef", "string", "math", "ctype", "time")
# '#' is optional in the pattern: OCR sometimes drops it, but "include
# <stdio.h>" is still unambiguous, so it gets added back.
#
# The tail after the header name is bounded to just a (possibly garbled) file
# extension and closing bracket -- an optional '.', an optional single letter
# ('.h', or '.n' when 'h' is misread), and an optional close ('>' or a '7'
# misread of it). It deliberately does NOT end in '.*': a broad tail would let
# a line that merely STARTS like an include but continues with real student
# code (a fused OCR row such as "#include <stdio.h> printf(...)") match, and the
# canonical replacement below would then silently drop everything after the
# header. Bounding the tail means such a line simply fails to match and is
# returned untouched -- never normalized, but never truncated either, keeping
# the module's promise to leave content outside literals intact.
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
            # A misread starting with a digit ("1f", "1nt") must start a
            # statement or declaration, so it is only fixed after whitespace,
            # a brace, ';', '(' or ','. Otherwise the float suffix in
            # "1.1f" or "b-1f" would be rewritten to "1.if" / "b-if".
            before = r"(?<![^\s{};(,])"
        pattern = before + re.escape(wrong) + r"(?![\w])"
        segment = re.sub(pattern, right, segment)
    return segment


def clean_c_code(text: str) -> str:
    """
    Return a lightly cleaned copy of `text`: known #include lines are snapped to
    canonical form and garbled C keywords are corrected. String/char literals
    are left exactly as extracted.
    """
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

    # 2) Then normalize #include lines. Running this after the keyword pass means
    # a header already corrected to a known name (e.g. std1o -> stdio) is now
    # recognized and snapped to its canonical "#include <stdio.h>" form.
    return "\n".join(_fix_include_line(line) for line in fixed.split("\n"))
