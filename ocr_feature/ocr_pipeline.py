from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from preprocess import preprocess_image
from c_code_cleanup import clean_c_code


# Config tuned for speed AND accuracy on our handwritten C samples (measured
# via A/B tests on the sample set):
#   - PP-OCRv5_mobile_det instead of the default server detector, and dropping
#     the doc-orientation / unwarping / textline-orientation passes, took
#     extraction from ~81s to ~2.3s per image (~35x) on CPU.
#   - Accuracy did NOT drop -- it slightly improved. The heavy server_det +
#     unwarping passes were over-processing our already-flat, upright captures
#     and degrading recognition (e.g. "printt"/"Hello work" -> "printf"/"Hello
#     world"). The mobile detector leaves the handwriting cleaner.
# Trade-off: the dropped passes helped with rotated/warped pages; our captures
# are gated to be upright/flat, so this is safe. Revisit if that changes.
ocr = PaddleOCR(
    lang="en",
    ocr_version="PP-OCRv5",
    text_detection_model_name="PP-OCRv5_mobile_det",
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

        for text, score in zip(rec_texts, rec_scores):
            if text and text.strip():
                extracted_lines.append(text.strip())
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