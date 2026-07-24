from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from preprocess import preprocess_image


ocr = PaddleOCR(
    lang="en",
    ocr_version="PP-OCRv5",
    use_doc_orientation_classify=True,
    use_doc_unwarping=True,
    use_textline_orientation=True,
    device="cpu"
)


def warmup() -> None:
    """
    Run one throwaway prediction so PaddleOCR loads all of its models at
    startup instead of during the first real request. This keeps the first
    live extraction (e.g. during a demo) from stalling on model loading.
    """
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

    average_confidence = None
    if confidence_scores:
        average_confidence = sum(confidence_scores) / len(confidence_scores)

    return {
        "raw_text": raw_text,
        "average_confidence": average_confidence,
        "preprocessed_image": preprocessed_path
    }