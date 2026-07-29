from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass(frozen=True)
class PreprocessConfig:
    """Tunable preprocessing knobs. The defaults reproduce the pipeline's
    long-standing behavior; change them only with a before/after CER
    comparison (evaluate_cer.py) to show the change actually helps."""

    # Cap resolution -- beyond this the OCR model downsamples internally
    # anyway, so paying denoise/detect cost for it is wasted.
    max_side: int = 1600

    # Non-local-means denoising (cv2.fastNlMeansDenoising).
    denoise: bool = True
    denoise_strength: int = 10
    denoise_template_window: int = 7
    denoise_search_window: int = 21

    # Adaptive Gaussian threshold to a black/white image.
    threshold: bool = True
    threshold_block_size: int = 31
    threshold_c: int = 15


DEFAULT_CONFIG = PreprocessConfig()


def preprocess_image(
    image_path: str,
    output_dir: str = "outputs",
    config: PreprocessConfig = DEFAULT_CONFIG,
) -> str:
    """Preprocess an image for OCR, writing the result to output_dir and
    returning its path."""

    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image file: {image_path}")

    height, width = img.shape[:2]
    longest_side = max(height, width)

    if longest_side > config.max_side:
        scale = config.max_side / longest_side
        img = cv2.resize(
            img,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    processed = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if config.denoise:
        processed = cv2.fastNlMeansDenoising(
            processed,
            None,
            config.denoise_strength,
            config.denoise_template_window,
            config.denoise_search_window,
        )
    if config.threshold:
        processed = cv2.adaptiveThreshold(
            processed,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            config.threshold_block_size,
            config.threshold_c,
        )

    output_path = output_dir / f"{image_path.stem}_preprocessed.jpg"

    cv2.imwrite(str(output_path), processed)

    return str(output_path)
