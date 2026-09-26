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
    # Runtime: recognition hands its detections to the reading-order geometry.
    _group_structured_lines,
    _join_lines_with_vertical_gaps,
    # Re-exported for backward compatibility. The reading-order / indentation
    # geometry moved to core.layout (2026-09-13, behavior-preserving split);
    # evaluators/build_recognition_dataset imports these two names from
    # core.ocr_pipeline, so keep that import surface stable here. (The other
    # split-out geometry helpers are imported directly from core.layout by
    # their callers, so they are not re-exported here.)
    _group_detection_records,
    line_member_bounds,
)


# Detection is pinned by name -- passing a model name makes PaddleOCR
# silently ignore lang/ocr_version, so setting those too would be misleading.
# Recognition is pinned by directory instead (see the fine-tuned recognizer
# block below), since the fine-tuned weights are the only recognizer this
# pipeline runs -- there is no stock-model fallback.
#
# No orientation/unwarp passes: captures are already gated upright/flat by
# the mobile app, so these passes only add cost (~80s -> a few seconds/image
# on CPU) with nothing to correct.
#
# v6_medium (det+rec) is the selected pairing over the v5 alternatives: it
# won on CER across every paper/writer subgroup tested, and bigger isn't
# better here -- the v5 server recognizer is multilingual and substitutes
# CJK characters for C symbols (e.g. '二' for '='), which is why an English-
# only recognizer is pinned rather than the largest available one. v6_medium
# still emits occasional CJK, but rare enough to be cosmetic, not an accuracy
# problem. Full sweep numbers: docs/ocr/EVALUATION.md.

# Fine-tuned recognizer (2026-08-30): trained on 2,491 handwritten C-code
# line crops, cut recognition CER on the held-out samples/ set from 0.274
# (stock PP-OCRv6_medium_rec) to 0.126 (-54%), improving every sample with
# no regressions. That 0.274 -> 0.126 is the historical recognition-only
# fine-tune comparison, before the two-column reading-order split. Current
# samples/ end-to-end metrics after that split are clean_ws CER 0.099,
# clean WER 0.328, and clean token accuracy 0.716 (evaluate_cer).
# This is the ONLY recognizer this pipeline runs -- no
# stock-model fallback -- so the result the thesis measured is always what's
# actually running, never silently swapped for something weaker. Weights
# aren't committed (see models/README.md -- ~76MB, distributed via a GitHub
# Release) and reproduced via docs/ocr/COLAB_SETUP_WORKING.md. A teammate who
# hasn't downloaded them yet gets a clear error below, not a silent
# degradation to stock.
# Default is the shipped fine-tuned recognizer. An offline eval experiment can
# point the pipeline at a DIFFERENT recognizer (e.g. the cross-writer
# measurement model in models/fine_tuned_rec_crosswriter/) by setting
# MAISTRA_REC_MODEL_DIR, without editing this file -- see
# evaluators/crosswriter_eval.py. The default is resolved from this file so
# demo tools can also run from the repository root; explicit overrides retain
# their caller-supplied path semantics.
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
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    # Lowered from PaddleOCR's default 0.60 to 0.30, decided by measurement
    # (2026-09-04). The fine-tuned recognizer reads braces well (0.9-1.0 conf),
    # but standalone braces and some faint code lines were being LOST AT
    # DETECTION -- their box score fell below the 0.60 cutoff, so the recognizer
    # never saw them. A/B on the 20-image gate set, sweeping 0.60/0.40/0.30:
    # historical recognition-only clean_ws CER stayed 0.126 at every value
    # (no phantom-detection regression), while closing-brace recovery rose
    # 82 -> 86 -> 87 of 89. This sweep preceded the two-column split; current
    # end-to-end samples/ clean_ws CER is 0.099 with the shipped setting.
    # A sharper 0.40-vs-0.30 diff confirmed every extra box at 0.30 is REAL
    # content (1 brace + 4 whole code lines that were missing), zero junk. For a
    # grading app "misread beats missing" -- a recovered line is teacher-fixable
    # in the widget, a dropped line may never be noticed. REC_SCORE_FLOOR (0.3)
    # still guards the recognition stage against genuine junk. Full A/B:
    # docs/ocr/EVALUATION.md, docs/ocr/DEFENSE_PREP.md.
    text_det_box_thresh=0.30,
    device="cpu"
)

# FastAPI runs requests in a threadpool, but the one PaddleOCR predictor isn't
# documented as thread-safe. Serialize predictions: on CPU they can't usefully
# overlap anyway.
_ocr_lock = threading.Lock()


def warmup() -> None:
    """Run one throwaway prediction so PaddleOCR loads its models now, at
    startup, instead of on the first real request. Called from main.py's
    lifespan hook."""
    dummy = np.full((80, 240, 3), 255, dtype=np.uint8)
    cv2.putText(
        dummy, "int main", (5, 55),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2
    )
    try:
        with _ocr_lock:
            ocr.predict(dummy)
    except Exception:
        # Warm-up is best-effort; a failure here must never block startup.
        pass


# Below this score a detection is almost always the detector firing on a
# smudge or stray mark rather than real writing, not a genuine hard-to-read
# character. Re-verified against the current v6 recognizer on the gate-framed
# test set: everything dropped is either an empty-text phantom (score 0.0) or
# obvious junk (highest dropped 0.291: 's', '>', 'a', '2222'), while the
# lowest real kept detection is 0.334 and the median kept score is 0.936.
# 0.3 sits cleanly in the 0.291 -> 0.334 gap, so it removes noise without
# touching real text.
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

    try:
        with _ocr_lock:
            # PaddleOCR 3.x may yield results lazily; materialize them while
            # the lock is still held.
            results = list(ocr.predict(preprocessed_path))
    except Exception as exc:
        # A single bad image (corrupt/degenerate data, an internal model error,
        # or OOM) must fail with context rather than a bare PaddleOCR traceback
        # -- the preprocessed path is the one thing that pins down which image.
        # (warmup() swallows the same call because it's best-effort at startup;
        # a real request cannot silently continue, so this re-raises.)
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
