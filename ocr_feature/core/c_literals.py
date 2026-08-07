"""Shared pattern for locating C string/char literals.

Both `c_code_cleanup.py` (which auto-fixes tokens) and `c_code_suggestions.py`
(which proposes fixes) must never touch anything inside a quoted literal — that
is student content, verbatim. Defining the pattern once here keeps the two
consumers from ever drifting in what they consider a literal. This module holds
a read-only constant only; it never mutates text, so it does not widen the
"only c_code_cleanup.py rewrites graded content" boundary.
"""

import re

# Matches a full string literal "..." or char literal '...', honoring escapes.
C_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"' r"|'(?:\\.|[^'\\])*'")
