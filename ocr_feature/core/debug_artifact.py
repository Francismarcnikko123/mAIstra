"""Save each extraction's intermediate data (detections, dropped entries,
grouped lines) as JSON for debugging. It doesn't affect the OCR result.

Uses only the standard library, so tests can load it without OpenCV or
PaddleOCR.
"""
import json
from pathlib import Path


def _jsonable(value):
    """Convert PaddleOCR values (numpy numbers and arrays) to plain Python
    types for JSON. Anything else becomes a string."""
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
    """Save `debug` as debug/<image name>.json next to the preprocessed
    image. Errors are ignored, so this can never break an extraction."""
    try:
        debug_dir = Path(preprocessed_path).parent / "debug"
        debug_dir.mkdir(exist_ok=True)
        out_path = debug_dir / (Path(preprocessed_path).stem + ".json")
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(_jsonable(debug), f, indent=2, ensure_ascii=False)
    except Exception:
        pass
