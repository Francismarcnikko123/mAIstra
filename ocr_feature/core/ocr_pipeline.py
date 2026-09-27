import math
import os
import threading
from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from core.preprocess import preprocess_image, PreprocessConfig, DEFAULT_CONFIG
from core.debug_artifact import write_debug_artifact
from core.c_code_cleanup import clean_c_code
from core.layout import (
    _group_structured_lines,
    _join_lines_with_vertical_gaps,
    # Not used here: evaluators/build_recognition_dataset.py imports them
    # from this module.
    _group_detection_records,
    line_member_bounds,
)


# Models: PP-OCRv6_medium for text detection, and our fine-tuned PP-OCRv6
# recognizer for reading the text. The fine-tuned recognizer is required;
# there is no fallback to the stock one.
#
# The recognizer is loaded from models/fine_tuned_rec/inference (download it
# as described in models/README.md). MAISTRA_REC_MODEL_DIR overrides the
# folder, for evaluation experiments only.
_FINE_TUNED_REC_DIR = os.environ.get(
    "MAISTRA_REC_MODEL_DIR",
    str(Path(__file__).resolve().parent.parent / "models/fine_tuned_rec/inference"),
)
if not Path(_FINE_TUNED_REC_DIR).exists():
    raise FileNotFoundError(
        f"Fine-tuned recognizer not found at '{_FINE_TUNED_REC_DIR}'. "
        "Download it from the GitHub Release and unzip it there -- see "
        "models/README.md for instructions."
    )
print(f"[ocr_pipeline] recognizer: fine-tuned ({_FINE_TUNED_REC_DIR})")

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_dir=_FINE_TUNED_REC_DIR,
    # Off: the phone app only accepts upright, flat photos, and these passes
    # are slow on CPU.
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    # 0.30 instead of the default 0.60: at 0.60 some braces and faint code
    # lines were never detected. At 0.30 they are (closing braces 82 -> 87 of
    # 89) with no extra junk and no change in CER.
    text_det_box_thresh=0.30,
    device="cpu"
)

# All requests share one PaddleOCR model, so predictions run one at a time.
_ocr_lock = threading.Lock()


def warmup() -> None:
    """Load the models at server start with one small prediction, so the
    first real request isn't slow."""
    dummy = np.full((80, 240, 3), 255, dtype=np.uint8)
    cv2.putText(
        dummy, "int main", (5, 55),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2
    )
    try:
        with _ocr_lock:
            ocr.predict(dummy)
    except Exception:
        # A failed warm-up must not stop the server from starting.
        pass


# Recognized text scoring below 0.3 is dropped as noise (smudges, stray
# marks). On the test set, the highest dropped score was 0.291 (junk such as
# "2222") and the lowest real text kept was 0.334.
REC_SCORE_FLOOR = 0.3


def _filter_low_confidence(rec_texts, rec_scores, rec_boxes):
    """Drop detections scoring below REC_SCORE_FLOOR. Returns the kept texts,
    scores and boxes, plus the dropped ones for the debug file. A detection
    without a score is kept."""
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


def _recognize_preprocessed(preprocessed_path: str) -> dict:
    """Run OCR on one preprocessed image and group the detections into lines
    in reading order. Returns the text, the lines with their positions, the
    average confidence and debug data."""
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

    try:
        with _ocr_lock:
            # predict() can return its results lazily: read them all while
            # holding the lock.
            results = list(ocr.predict(preprocessed_path))
    except Exception as exc:
        # Name the image that failed instead of showing only PaddleOCR's error.
        raise RuntimeError(
            f"OCR prediction failed for {preprocessed_path}"
        ) from exc
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
        "raw_text": _join_lines_with_vertical_gaps(structured_lines),
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
    """The whole OCR pipeline for one photo: preprocess it, read the text,
    put the lines in reading order, and fix misread C keywords. Returns the
    raw text, the cleaned text, the average confidence and the preprocessed
    image's path, and writes a debug JSON file next to that image."""
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

    # Fix misread C keywords and #include lines only; string literals are
    # left as read. raw_text stays unchanged.
    cleaned_text = clean_c_code(raw_text)
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
    }
    write_debug_artifact(preprocessed_path, debug)

    result = {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "average_confidence": average_confidence,
        "preprocessed_image": preprocessed_path,
    }
    return result
