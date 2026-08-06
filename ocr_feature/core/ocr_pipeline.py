import json
import math
from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from core.preprocess import preprocess_image, PreprocessConfig, DEFAULT_CONFIG
from core.c_code_cleanup import clean_c_code
from core.c_code_suggestions import suggest_c_code


# Detection and recognition are pinned by name -- passing a model name makes
# PaddleOCR silently ignore lang/ocr_version, so setting those too would be misleading.

# no orientation/unwarp passes: ~81s -> a few seconds per image on CPU, since
# our captures are already gated upright/flat at the mobile app.

# Model pairing chosen by sweep over the 13 human-verified pages (2026-08-03),
# clean_ws CER, all four pairings scored on the same cohort:
#
#   v6_medium_det + v6_medium_rec      0.148   <- selected
#   v5_mobile_det + en_v5_mobile_rec   0.181   (previous default)
#   v5_server_det + en_v5_mobile_rec   0.187   at ~9x the runtime
#   v5_mobile_det + v5_server_rec      0.279
#
# v6 wins on 11 of 13 pages and improves every paper/writer subgroup. Bigger is
# not better here: v5_server_rec is multilingual and substitutes CJK for C
# symbols (二 for '='), which is why the older en_ recognizer was pinned -- that
# instinct is now confirmed numerically. Detection is not the bottleneck;
# v5_server_det cost 9x the time for a worse score, so detection stays small.
#
# Cost of this change: ~3s -> ~9s per page on CPU.
#
# v6_medium_rec also emits occasional CJK, but stripping non-ASCII moves CER by
# ~0.0001, so it is cosmetic rather than an accuracy problem.
#
# REC_SCORE_FLOOR below was calibrated against v5-mobile's confidence
# distribution and has NOT been recalibrated for v6.

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_name="PP-OCRv6_medium_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    device="cpu"
)


def warmup() -> None:
   
    dummy = np.full((80, 240, 3), 255, dtype=np.uint8)
    cv2.putText(
        dummy, "int main", (5, 55),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2
    )
    try:
        ocr.predict(dummy)
    except Exception:
        # Warm-up is best-effort; a failure here must never block startup.
        pass


# Below this score a detection is almost always the detector firing on a
# smudge or stray mark rather than real writing -- a phantom "2" once scored
# 0.127 while every real character on the same page scored 0.7+. Kept low
# enough to only catch that kind of noise, not genuine hard-to-read characters.
REC_SCORE_FLOOR = 0.3


def _filter_low_confidence(rec_texts, rec_scores, rec_boxes):
    """Drop entries below REC_SCORE_FLOOR, keeping the three lists aligned.
    A missing score passes through rather than getting dropped. Also returns
    the dropped entries so the debug artifact can show what was discarded."""
    if not rec_scores or len(rec_scores) != len(rec_texts):
        return rec_texts, rec_scores, rec_boxes, []
    keep_texts, keep_scores, keep_boxes = [], [], []
    dropped = []
    for i, text in enumerate(rec_texts):
        score = rec_scores[i]
        try:
            passes = float(score) >= REC_SCORE_FLOOR
        except (TypeError, ValueError):
            passes = True
        if passes:
            keep_texts.append(text)
            keep_scores.append(score)
            if i < len(rec_boxes):
                keep_boxes.append(rec_boxes[i])
        else:
            dropped.append({
                "text": text,
                "score": score,
                "box": rec_boxes[i] if i < len(rec_boxes) else None,
            })
    return keep_texts, keep_scores, keep_boxes, dropped


def _expected_line_y(members, candidate_x):
    """Predict a candidate's vertical center from the current line members."""
    if len(members) == 1:
        return members[0]["y"]

    try:
        x_mean = sum(member["x"] for member in members) / len(members)
        y_mean = sum(member["y"] for member in members) / len(members)
        if not all(math.isfinite(value) for value in (x_mean, y_mean)):
            return None

        denominator = sum((member["x"] - x_mean) ** 2 for member in members)
        if not math.isfinite(denominator):
            return None
        if denominator == 0:
            return members[0]["y"]

        covariance = sum(
            (member["x"] - x_mean) * (member["y"] - y_mean)
            for member in members
        )
        if not math.isfinite(covariance):
            return None
        slope = covariance / denominator
        if not math.isfinite(slope):
            return None
        predicted_y = y_mean + slope * (candidate_x - x_mean)
        return predicted_y if math.isfinite(predicted_y) else None
    except OverflowError:
        return None


def _original_detection_records(rec_texts, rec_scores):
    """Return one geometry-free record per detection in original order."""
    return [[{
        "text": text,
        "score": rec_scores[i] if i < len(rec_scores) else 0.0,
        "x": None,
        "y": None,
        "y_min": None,
        "y_max": None,
    }] for i, text in enumerate(rec_texts)]


def _group_detection_records(rec_texts, rec_scores, rec_boxes):
    """Group detections and retain the box geometry used for ordering.

    The boolean return value indicates whether every detection had safe,
    finite geometry. Unsafe geometry falls back to one detection per line in
    original order so callers never infer coordinates that Paddle did not
    provide reliably.
    """
    if not rec_boxes or len(rec_boxes) != len(rec_texts):
        return _original_detection_records(rec_texts, rec_scores), False

    items = []
    heights = []
    for i, box in enumerate(rec_boxes):
        try:
            x_min, y_min, x_max, y_max = (float(box[0]), float(box[1]),
                                          float(box[2]), float(box[3]))
        except (TypeError, IndexError, ValueError, OverflowError):
            # Malformed box -> don't risk regrouping; keep original order.
            return _original_detection_records(rec_texts, rec_scores), False
        width = x_max - x_min
        height = y_max - y_min
        if (not all(math.isfinite(value)
                    for value in (x_min, y_min, x_max, y_max, width, height))
                or width <= 0 or height <= 0):
            # Invalid geometry -> don't risk regrouping; keep original order.
            return _original_detection_records(rec_texts, rec_scores), False
        y_center = y_min + height / 2.0
        if not math.isfinite(y_center):
            # Invalid geometry -> don't risk regrouping; keep original order.
            return _original_detection_records(rec_texts, rec_scores), False
        score = rec_scores[i] if i < len(rec_scores) else 0.0
        items.append({"text": rec_texts[i], "score": score,
                      "x": x_min, "y": y_center,
                      "y_min": y_min, "y_max": y_max})
        heights.append(height)

    # Two boxes belong to the same visual line if their vertical centers are
    # within ~60% of a typical line height. Using the median height keeps this
    # robust to one unusually tall/short detection.
    heights.sort()
    median_h = heights[len(heights) // 2] if heights else 0.0
    line_tol = max(median_h * 0.6, 1.0)

    # Sort by vertical position first so we can sweep top-to-bottom.
    items.sort(key=lambda it: it["y"])

    lines = []
    for it in items:
        if lines:
            members = lines[-1]["members"]
            expected_y = _expected_line_y(members, it["x"])
            if expected_y is None:
                return _original_detection_records(rec_texts, rec_scores), False
            mean_y = sum(member["y"] for member in members) / len(members)
            trend_delta = abs(it["y"] - expected_y)
            center_delta = abs(it["y"] - mean_y)
            # A tightly fitted trend can continue beyond the center band, but
            # only within half tolerance to avoid absorbing an indented row.
            if (trend_delta <= line_tol
                    and (center_delta <= line_tol
                         or trend_delta <= line_tol * 0.5)):
                members.append(it)
                continue
        else:
            lines.append({"members": [it]})
            continue

        lines.append({"members": [it]})

    ordered_lines = [
        sorted(line["members"], key=lambda member: member["x"])
        for line in lines
    ]
    return ordered_lines, True


def _group_into_reading_order(rec_texts, rec_scores, rec_boxes):
    """
    Group detections into lines by position (top-to-bottom, then left-to-right
    within a line) instead of trusting PaddleOCR's raw order, which can scatter
    a single handwritten row into separate out-of-order pieces -- e.g.
    "int result", "=", "add(3,4);" coming back as three disconnected lines.

    Returns a list of lines, each a list of (text, score) tuples in reading
    order; the caller joins a line's members with a space. rec_boxes entries
    are [x_min, y_min, x_max, y_max]. Falls back to one line per detection if
    box data is missing or malformed. Grouping may reorder whole recognized
    fragments and the caller may insert whitespace when joining them, but this
    helper never edits recognized characters.
    """
    grouped, _geometry_safe = _group_detection_records(
        rec_texts, rec_scores, rec_boxes
    )
    return [
        [(member["text"], member["score"]) for member in members]
        for members in grouped
    ]


def _group_structured_lines(rec_texts, rec_scores, rec_boxes, image_height):
    """Return nonempty OCR lines with confidence and normalized geometry."""
    grouped, geometry_safe = _group_detection_records(
        rec_texts, rec_scores, rec_boxes
    )
    try:
        normalized_height = float(image_height)
    except (TypeError, ValueError, OverflowError):
        normalized_height = 0.0
    geometry_safe = (
        geometry_safe
        and math.isfinite(normalized_height)
        and normalized_height > 0
    )

    structured = []
    for members in grouped:
        parts = [
            member["text"].strip()
            for member in members
            if member["text"] and member["text"].strip()
        ]
        if not parts:
            continue

        scores = []
        for member in members:
            try:
                score = float(member["score"])
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(score):
                scores.append(score)

        mean_confidence = None
        if scores:
            try:
                candidate_mean = math.fsum(
                    score / len(scores) for score in scores
                )
            except OverflowError:
                candidate_mean = None
            if candidate_mean is not None and math.isfinite(candidate_mean):
                mean_confidence = candidate_mean

        y_min = None
        y_max = None
        if geometry_safe:
            try:
                y_min = min(member["y_min"] for member in members) / normalized_height
                y_max = max(member["y_max"] for member in members) / normalized_height
            except (TypeError, ValueError, OverflowError, ZeroDivisionError):
                y_min = None
                y_max = None
            if (y_min is None or y_max is None
                    or not all(math.isfinite(value) for value in (y_min, y_max))):
                y_min = None
                y_max = None

        structured.append({
            "text": " ".join(parts),
            "members": [
                (member["text"], member["score"]) for member in members
            ],
            "scores": scores,
            "mean_confidence": mean_confidence,
            "y_min": y_min,
            "y_max": y_max,
        })
    return structured


def _build_line_details(grouped_lines):
    """Build additive per-line review data without judging correctness."""
    details = []
    for members in grouped_lines:
        parts = [text.strip() for text, _ in members if text and text.strip()]
        if not parts:
            continue

        scores = []
        for _, score in members:
            try:
                numeric_score = float(score)
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(numeric_score):
                scores.append(numeric_score)

        details.append({
            "line": len(details) + 1,
            "text": " ".join(parts),
            "scores": scores,
            "min_confidence": min(scores) if scores else None,
            "mean_confidence": (
                sum(scores) / len(scores) if scores else None
            ),
            "review_reasons": [],
        })
    return details


def _attach_suggestion_reasons(line_details, suggestions) -> None:
    """Attach rule identifiers to line details for teacher navigation."""
    details_by_line = {detail["line"]: detail for detail in line_details}
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue
        try:
            line_number = int(suggestion.get("line"))
        except (TypeError, ValueError, OverflowError):
            continue
        rule_id = suggestion.get("rule_id")
        detail = details_by_line.get(line_number)
        if not detail or not isinstance(rule_id, str) or not rule_id:
            continue
        if rule_id not in detail["review_reasons"]:
            detail["review_reasons"].append(rule_id)


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


def _write_debug_artifact(preprocessed_path: str, debug: dict) -> None:
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


def _recognize_preprocessed(preprocessed_path: str) -> dict:
    """Recognize one preprocessed image and preserve per-line geometry."""
    try:
        image = cv2.imread(preprocessed_path, cv2.IMREAD_GRAYSCALE)
        image_height = image.shape[0] if image is not None else None
        numeric_height = float(image_height)
    except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
        numeric_height = 0.0
    if not math.isfinite(numeric_height) or numeric_height <= 0:
        raise ValueError(
            f"could not read preprocessed image: {preprocessed_path}"
        )

    results = ocr.predict(preprocessed_path)
    structured_lines = []
    confidence_scores = []
    debug_detections = []
    debug_dropped = []

    for page in results:
        data = page.json
        result_data = data.get("res", {})

        rec_texts = result_data.get("rec_texts", [])
        rec_scores = result_data.get("rec_scores", [])
        rec_boxes = result_data.get("rec_boxes", [])

        rec_texts, rec_scores, rec_boxes, dropped = _filter_low_confidence(
            rec_texts, rec_scores, rec_boxes
        )
        debug_dropped.extend(dropped)
        for i, text in enumerate(rec_texts):
            debug_detections.append({
                "text": text,
                "score": rec_scores[i] if i < len(rec_scores) else None,
                "box": rec_boxes[i] if i < len(rec_boxes) else None,
            })
            score = rec_scores[i] if i < len(rec_scores) else 0.0
            try:
                confidence_scores.append(float(score))
            except Exception:
                pass

        structured_lines.extend(_group_structured_lines(
            rec_texts, rec_scores, rec_boxes, numeric_height
        ))

    average_confidence = None
    if confidence_scores:
        average_confidence = sum(confidence_scores) / len(confidence_scores)

    return {
        "raw_text": "\n".join(line["text"] for line in structured_lines),
        "lines": structured_lines,
        "grouped_lines": [line["members"] for line in structured_lines],
        "average_confidence": average_confidence,
        "detections": debug_detections,
        "dropped_low_confidence": debug_dropped,
        "debug_lines": [
            [
                {"text": text, "score": score}
                for text, score in line["members"]
            ]
            for line in structured_lines
        ],
    }


def extract_text_from_image(
    image_path: str,
    preprocess_config: PreprocessConfig = DEFAULT_CONFIG,
    output_dir: str = "outputs",
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    preprocessed_path = preprocess_image(
        image_path=image_path,
        output_dir=str(output_path),
        config=preprocess_config,
    )

    selected_attempt = _recognize_preprocessed(preprocessed_path)

    raw_text = selected_attempt["raw_text"]
    grouped_lines = selected_attempt["grouped_lines"]

    # Light keyword-only tidy so the teacher has fewer edits. The raw text is
    # kept separately; cleaning never touches string literals or arbitrary
    # content. See c_code_cleanup.py.
    cleaned_text = clean_c_code(raw_text)
    line_details = _build_line_details(grouped_lines)

    # Suggestions are teacher-review hints only. They never modify either OCR
    # text field, and a failure here must not turn a successful extraction into
    # an API error.
    try:
        review_suggestions = suggest_c_code(raw_text, line_details)
        review_diagnostics = []
    except Exception as exc:
        review_suggestions = []
        review_diagnostics = [
            f"suggestion engine failed: {type(exc).__name__}"
        ]
    _attach_suggestion_reasons(line_details, review_suggestions)

    average_confidence = selected_attempt["average_confidence"]

    debug = {
        "source_image": image_path,
        "preprocessed_image": preprocessed_path,
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "average_confidence": average_confidence,
        "rec_score_floor": REC_SCORE_FLOOR,
        "detections": selected_attempt["detections"],
        "dropped_low_confidence": selected_attempt["dropped_low_confidence"],
        "grouped_lines": selected_attempt["debug_lines"],
        "line_details": line_details,
        "review_suggestions": review_suggestions,
        "review_diagnostics": review_diagnostics,
    }
    _write_debug_artifact(preprocessed_path, debug)

    result = {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "average_confidence": average_confidence,
        "preprocessed_image": preprocessed_path,
        "line_details": line_details,
        "review_suggestions": review_suggestions,
        "review_diagnostics": review_diagnostics,
    }
    return result
