import math
from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from core.preprocess import preprocess_image, PreprocessConfig, DEFAULT_CONFIG
from core.numeric import finite_float
from core.debug_artifact import write_debug_artifact
from core.c_code_cleanup import clean_c_code
from core.c_code_suggestions import suggest_c_code


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
# no regressions. This is the ONLY recognizer this pipeline runs -- no
# stock-model fallback -- so the result the thesis measured is always what's
# actually running, never silently swapped for something weaker. Weights
# aren't committed (see models/README.md -- ~76MB, distributed via a GitHub
# Release) and reproduced via docs/ocr/COLAB_SETUP_WORKING.md. A teammate who
# hasn't downloaded them yet gets a clear error below, not a silent
# degradation to stock.
_FINE_TUNED_REC_DIR = "models/fine_tuned_rec/inference"
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
    device="cpu"
)


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

# Same-row fragments are side by side; stacked rows overlap in x. Across the
# available cohort artifacts, the largest overlap retained on one row was 8%
# and the smallest confirmed stacked-row merge was 37%. Keep a margin on both
# sides of that measured gap.
MAX_SAME_LINE_X_OVERLAP = 0.3


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
                      "x": x_min, "x_max": x_max, "y": y_center,
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
            within_vertical_tolerance = (
                trend_delta <= line_tol
                and (center_delta <= line_tol
                     or trend_delta <= line_tol * 0.5)
            )
            if within_vertical_tolerance:
                overlap_fractions = (
                    max(
                        0.0,
                        min(member["x_max"], it["x_max"])
                        - max(member["x"], it["x"]),
                    ) / min(
                        member["x_max"] - member["x"],
                        it["x_max"] - it["x"],
                    )
                    for member in members
                )
                # Stacked rows overlap heavily in x; genuine fragments on one
                # row are side by side. Compare the candidate with each actual
                # member so an empty gap inside the line's span cannot veto a
                # merge merely because detections arrived out of x-order.
                if max(overlap_fractions) <= MAX_SAME_LINE_X_OVERLAP:
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


def line_member_bounds(members):
    """Union bounding box (x_min, y_min, x_max, y_max) in raw pixel space over
    a line's grouped members. Members must carry finite x/x_max/y_min/y_max --
    i.e. come from the geometry-safe path of _group_detection_records; callers
    guard for that before calling. Shared so the live pipeline and the offline
    crop builder compute a line's box the same way."""
    x_min = min(member["x"] for member in members)
    x_max = max(member["x_max"] for member in members)
    y_min = min(member["y_min"] for member in members)
    y_max = max(member["y_max"] for member in members)
    return x_min, y_min, x_max, y_max


def _group_structured_lines(rec_texts, rec_scores, rec_boxes, image_height):
    """Return nonempty OCR lines with confidence and normalized geometry."""
    grouped, geometry_safe = _group_detection_records(
        rec_texts, rec_scores, rec_boxes
    )
    normalized_height = finite_float(image_height)
    geometry_safe = (
        geometry_safe
        and normalized_height is not None
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
            score = finite_float(member["score"])
            if score is not None:
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
                _, raw_y_min, _, raw_y_max = line_member_bounds(members)
                y_min = raw_y_min / normalized_height
                y_max = raw_y_max / normalized_height
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
            numeric_score = finite_float(score)
            if numeric_score is not None:
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
    write_debug_artifact(preprocessed_path, debug)

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
