from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


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

    # A fixed block size is implicitly tuned for one handwriting size: too
    # large a block spans several characters when the writing is small, and
    # thresholding degrades. Setting threshold_block_scale derives the block
    # from the measured glyph height instead (block = scale x glyph, rounded
    # to odd), so the pipeline copes with whatever size the student wrote.
    #
    # Measured on 7 labelled samples (2 writers): fixed 31 -> 0.160 CER;
    # scale 1.5 -> 0.128. Largest gain on the smallest handwriting
    # (0.370 -> 0.229). None = keep the fixed size.
    threshold_block_scale: float | None = None


DEFAULT_CONFIG = PreprocessConfig()


def _median_glyph_height(gray) -> float:
    """Median height of glyph-sized connected components, as a cheap proxy
    for how large the handwriting is in this image. Returns 0.0 when nothing
    plausible is found, so callers can fall back."""
    # Adaptive rather than Otsu: a global threshold is thrown off by any
    # large uniform region (a wide margin, a blown-out area), which can
    # collapse the whole page into a single component.
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 15)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    heights = []
    for i in range(1, count):
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        # Skip speckles, page-sized blobs, and long rules/edges.
        if 4 <= h <= 300 and area >= 12 and w <= 12 * h:
            heights.append(h)
    return float(np.median(heights)) if heights else 0.0


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
        block_size = config.threshold_block_size
        if config.threshold_block_scale is not None:
            glyph = _median_glyph_height(processed)
            if glyph > 0:
                # adaptiveThreshold requires an odd block of at least 3.
                block_size = max(3, int(round(config.threshold_block_scale * glyph)))
                if block_size % 2 == 0:
                    block_size += 1
        processed = cv2.adaptiveThreshold(
            processed,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size,
            config.threshold_c,
        )

    output_path = output_dir / f"{image_path.stem}_preprocessed.jpg"

    cv2.imwrite(str(output_path), processed)

    return str(output_path)
