from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from preprocess import preprocess_image
from c_code_cleanup import clean_c_code


# Models are pinned EXPLICITLY (both detection and recognition) so nothing is
# chosen silently. Note: when a model name is given, PaddleOCR ignores `lang`
# and `ocr_version`, so those are omitted here to avoid confusion -- the pinned
# names are the single source of truth.
#
# Detection: PP-OCRv5_mobile_det. Dropping the doc-orientation / unwarping /
# textline-orientation passes took extraction from ~81s to a few seconds per
# image on CPU. Our captures are quality-gated to be upright/flat, so the
# dropped passes aren't needed; revisit if that changes.
#
# Recognition: en_PP-OCRv5_mobile_rec (English-only). C source is ASCII, so an
# English recognizer is the natural fit and constrains output to the relevant
# character set -- it structurally cannot emit CJK characters. We measured the
# newer multilingual PP-OCRv6_medium_rec as slightly more accurate (~7.5% vs
# ~9.5% char error rate on our samples), but it occasionally emits Chinese
# characters where C symbols belong (e.g. 二 for '='). We chose the English
# model: the small accuracy difference is cushioned by the human verify step,
# and it avoids non-ASCII output entirely.
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


# Recognition-confidence floor. Detections below this are treated as noise
# (smudges, marks, texture) and dropped. Kept low so only near-certain false
# positives are removed -- real characters on our samples score well above this.
REC_SCORE_FLOOR = 0.3


def _filter_low_confidence(rec_texts, rec_scores, rec_boxes):
    """Drop detections whose recognition score is below REC_SCORE_FLOOR. Keeps
    the three parallel lists aligned. Missing scores are treated as passing so
    we never drop text just because a score was absent."""
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


def _group_into_reading_order(rec_texts, rec_scores, rec_boxes):
    """
    Group detected text into visual lines in natural reading order using each
    box's position: fragments whose vertical centers are close are treated as
    one line (top-to-bottom), ordered left-to-right within the line.

    Returns a list of lines, where each line is a list of (text, score) members
    sorted left-to-right. The caller joins each line's members with a space, so
    pieces of one handwritten row (e.g. "int result", "=", "add(3,4);") come out
    on the same output line instead of scattered, out-of-order lines.

    This only reorders/regroups whole detected pieces by position and joins them
    with whitespace -- it never changes any character, so graded content is
    untouched. rec_boxes entries are [x_min, y_min, x_max, y_max]; if box data is
    missing or misaligned, fall back to PaddleOCR's original order (one line per
    detection).
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
        except (TypeError, IndexError, ValueError):
            # Malformed box -> don't risk regrouping; keep original order.
            return [[(t, rec_scores[i] if i < len(rec_scores) else 0.0)]
                    for i, t in enumerate(rec_texts)]
        score = rec_scores[i] if i < len(rec_scores) else 0.0
        y_center = (y_min + y_max) / 2.0
        items.append({"text": rec_texts[i], "score": score,
                      "x": x_min, "y": y_center})
        heights.append(y_max - y_min)

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
        if lines and abs(it["y"] - lines[-1]["y_ref"]) <= line_tol:
            lines[-1]["members"].append(it)
            # Track the running vertical center so a line that drifts slightly
            # doesn't split; average keeps the reference stable.
            members = lines[-1]["members"]
            lines[-1]["y_ref"] = sum(m["y"] for m in members) / len(members)
        else:
            lines.append({"y_ref": it["y"], "members": [it]})

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

        # Drop very-low-confidence detections. These are usually false positives
        # where the detector fired on a smudge, stray mark, or paper texture and
        # the recognizer guessed a character it isn't sure about (e.g. a phantom
        # "2" scored ~0.13 while every real character scores 0.7+). The cutoff is
        # deliberately low so we only remove near-certain noise, never real but
        # hard-to-read characters.
        rec_texts, rec_scores, rec_boxes = _filter_low_confidence(
            rec_texts, rec_scores, rec_boxes)

        # Regroup detected text into natural reading order (top-to-bottom, then
        # left-to-right) using each box's position, and merge fragments on the
        # same handwritten row into one line. PaddleOCR's default order can
        # interleave/scatter pieces when handwriting spacing is irregular (e.g.
        # "int result = add(3,4);" arriving as separate, out-of-order fragments).
        # This only regroups whole detected pieces by position and joins them
        # with whitespace -- it never changes any character, so graded content
        # is untouched.
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