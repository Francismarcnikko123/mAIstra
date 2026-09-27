"""The pattern for C string and character literals, shared so every module
treats literals the same way. Literals are student content and are never
changed."""

import re

# Matches a full string literal "..." or char literal '...', honoring escapes.
C_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"' r"|'(?:\\.|[^'\\])*'")
