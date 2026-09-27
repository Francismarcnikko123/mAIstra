"""Safe number conversion for values from PaddleOCR, which may be missing,
text, NaN or infinite."""

import math


def finite_float(value) -> float | None:
    """Return value as a finite float, or None if it can't be one."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None
