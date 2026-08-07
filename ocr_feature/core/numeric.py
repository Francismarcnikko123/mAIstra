"""Small numeric guard shared across the OCR modules.

`ocr_pipeline.py` and `c_code_suggestions.py` both take confidence scores
straight from PaddleOCR / caller-supplied dicts, where a value may be missing,
a non-numeric string, or a non-finite float (NaN/inf). Both need the same
"coerce to a real finite float, or give up" rule. Defining it once here keeps
them from drifting — and it lives in its own leaf module rather than in
ocr_pipeline.py, which already imports c_code_suggestions.py (importing back
would be a cycle).
"""

import math


def finite_float(value) -> float | None:
    """Return value as a finite float, or None if it can't be one."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None
