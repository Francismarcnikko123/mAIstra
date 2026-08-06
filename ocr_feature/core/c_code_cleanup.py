import re

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

# Matches a full string literal "..." or char literal '...' so we can shield
# their contents from replacement.
_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"' r"|'(?:\\.|[^'\\])*'")

# Standard headers are a small closed set, so an #include line is safe to
# normalize even when OCR mangles the extension ('.h' -> '.n') or the closing
# '>' (often read as '7') -- only a line that already looks like an #include
# with a known header gets touched. A stray '7' or '>' elsewhere is left
# alone since it could be real content.
_KNOWN_HEADERS = ("stdio", "stdlib", "stddef", "string", "math", "ctype", "time")
# '#' is optional in the pattern: OCR sometimes drops it, but "include
# <stdio.h>" is still unambiguous, so it gets added back.
_INCLUDE_LINE = re.compile(
    r"^\s*#?\s*[Ii]nclude\s*<\s*(" + "|".join(_KNOWN_HEADERS) + r")\b.*$"
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
        pattern = r"(?<![\w#])" + re.escape(wrong) + r"(?![\w])"
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
    for match in _LITERAL.finditer(text):
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
