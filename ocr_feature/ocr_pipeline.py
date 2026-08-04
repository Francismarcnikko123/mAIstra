import math
from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from preprocess import preprocess_image
from c_code_cleanup import clean_c_code


# Detection and recognition are pinned by name -- passing a model name makes
# PaddleOCR silently ignore lang/ocr_version, so setting those too would be misleading.

# mobile_det + no orientation/unwarp passes: ~81s -> a few seconds per image
# on CPU, since our captures are already gated upright/flat at the mobile app.

# en_PP-OCRv5_mobile_rec over the multilingual PP-OCRv6_medium_rec: the
# multilingual model measured ~2pts better CER (0.075 vs 0.095) but
# occasionally recognizes a CJK character instead of a C symbol (二 for '=').
# English-only can't do that, and the accuracy gap is small enough to eat
# given the teacher verifies everything anyway.

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="en_PP-OCRv5_mobile_rec",
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
    A missing score passes through rather than getting dropped."""
    if not rec_scores or len(rec_scores) != len(rec_texts):
        return rec_texts, rec_scores, rec_boxes
    keep_texts, keep_scores, keep_boxes = [], [], []
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
    return keep_texts, keep_scores, keep_boxes


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
    if not rec_boxes or len(rec_boxes) != len(rec_texts):
        return [[(t, rec_scores[i] if i < len(rec_scores) else 0.0)]
                for i, t in enumerate(rec_texts)]

    items = []
    heights = []
    for i, box in enumerate(rec_boxes):
        try:
            x_min, y_min, x_max, y_max = (float(box[0]), float(box[1]),
                                          float(box[2]), float(box[3]))
        except (TypeError, IndexError, ValueError, OverflowError):
            # Malformed box -> don't risk regrouping; keep original order.
            return [[(t, rec_scores[i] if i < len(rec_scores) else 0.0)]
                    for i, t in enumerate(rec_texts)]
        width = x_max - x_min
        height = y_max - y_min
        if (not all(math.isfinite(value)
                    for value in (x_min, y_min, x_max, y_max, width, height))
                or width <= 0 or height <= 0):
            # Invalid geometry -> don't risk regrouping; keep original order.
            return [[(t, rec_scores[i] if i < len(rec_scores) else 0.0)]
                    for i, t in enumerate(rec_texts)]
        y_center = y_min + height / 2.0
        if not math.isfinite(y_center):
            # Invalid geometry -> don't risk regrouping; keep original order.
            return [[(t, rec_scores[i] if i < len(rec_scores) else 0.0)]
                    for i, t in enumerate(rec_texts)]
        score = rec_scores[i] if i < len(rec_scores) else 0.0
        items.append({"text": rec_texts[i], "score": score,
                      "x": x_min, "y": y_center})
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
                return [[(t, rec_scores[i] if i < len(rec_scores) else 0.0)]
                        for i, t in enumerate(rec_texts)]
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

    ordered_lines = []
    for line in lines:
        members = sorted(line["members"], key=lambda m: m["x"])
        ordered_lines.append([(m["text"], m["score"]) for m in members])
    return ordered_lines


def extract_text_from_image(image_path: str) -> dict:
    Path("outputs").mkdir(exist_ok=True)

    preprocessed_path = preprocess_image(
        image_path=image_path,
        output_dir="outputs"
    )

    results = ocr.predict(preprocessed_path)

    extracted_lines = []
    confidence_scores = []

    for page in results:
        data = page.json
        result_data = data.get("res", {})

        rec_texts = result_data.get("rec_texts", [])
        rec_scores = result_data.get("rec_scores", [])
        rec_boxes = result_data.get("rec_boxes", [])

        rec_texts, rec_scores, rec_boxes = _filter_low_confidence(
            rec_texts, rec_scores, rec_boxes)
        ordered_lines = _group_into_reading_order(rec_texts, rec_scores, rec_boxes)

        for line_members in ordered_lines:
            parts = [t.strip() for t, _ in line_members if t and t.strip()]
            if parts:
                extracted_lines.append(" ".join(parts))
            for _, score in line_members:
                try:
                    confidence_scores.append(float(score))
                except Exception:
                    pass

    raw_text = "\n".join(extracted_lines)

    # Light keyword-only tidy so the teacher has fewer edits. The raw text is
    # kept separately; cleaning never touches string literals or arbitrary
    # content. See c_code_cleanup.py.
    cleaned_text = clean_c_code(raw_text)

    average_confidence = None
    if confidence_scores:
        average_confidence = sum(confidence_scores) / len(confidence_scores)

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "average_confidence": average_confidence,
        "preprocessed_image": preprocessed_path
    }
