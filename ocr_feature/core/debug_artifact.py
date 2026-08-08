"""Diagnostic side-output for one extraction: the intermediate data
(detections, dropped entries, grouped lines, suggestions) dumped as JSON
next to the preprocessed image.

Kept out of ocr_pipeline.py so that module stays recognition logic only --
this is developer-facing I/O, not part of producing the text. Nothing in the
API response depends on it; the extraction result is identical whether or not
the artifact is written.

Only stdlib is imported here on purpose: it keeps the module cheap to load in
tests that stub out cv2/numpy/paddleocr.
"""
import json
from pathlib import Path


def _jsonable(value):
    """Best-effort conversion of PaddleOCR values (numpy scalars/arrays) into
    plain Python types for the debug JSON. Unconvertible values become their
    string form rather than failing the dump."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return _jsonable(tolist())
        except Exception:
            pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def write_debug_artifact(preprocessed_path: str, debug: dict) -> None:
    """Save the extraction's intermediate data as outputs/debug/<stem>.json,
    matching the preprocessed image's stem so the pair is easy to correlate.
    Diagnostic only -- a failure here must never break the extraction itself."""
    try:
        debug_dir = Path(preprocessed_path).parent / "debug"
        debug_dir.mkdir(exist_ok=True)
        out_path = debug_dir / (Path(preprocessed_path).stem + ".json")
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(_jsonable(debug), f, indent=2, ensure_ascii=False)
    except Exception:
        pass
