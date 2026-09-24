"""Shared pattern for locating C string/char literals.

`c_code_cleanup.py` (which auto-fixes tokens) must never touch anything inside
a quoted literal — that is student content, verbatim. Defining the pattern
once here keeps every consumer from ever drifting in what it considers a
literal. This module holds a read-only constant only; it never mutates text,
so it does not widen the "only c_code_cleanup.py rewrites graded content"
boundary.
"""

import re

# Matches a full string literal "..." or char literal '...', honoring escapes.
C_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"' r"|'(?:\\.|[^'\\])*'")
