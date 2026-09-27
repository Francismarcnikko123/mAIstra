"""Prepare a photo for OCR: resize, convert to grayscale and denoise."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class PreprocessConfig:
    """Preprocessing settings. The defaults are the measured, shipped setup;
    change one only with a before/after CER comparison
    (evaluators/evaluate_cer.py)."""

    # The longer side is scaled down to this; the model downsamples larger
    # images anyway.
    max_side: int = 1600

    # Non-local-means denoising (cv2.fastNlMeansDenoising).
    denoise: bool = True
    denoise_strength: int = 10
    denoise_template_window: int = 7
    denoise_search_window: int = 21

    # Black-and-white thresholding. Off: it made CER worse (0.149 grayscale vs
    # 0.201 thresholded on the same 14 samples), because it hardens pen strokes
    # and turns ruled lines into solid black. Kept for compare_config.py,
    # which demonstrates the difference.
    threshold: bool = False
    threshold_block_size: int = 31
    threshold_c: int = 15

    # When thresholding, size the block from the handwriting (1.5 x median
    # glyph height, rounded to odd) instead of a fixed size. None uses
    # threshold_block_size.
    threshold_block_scale: float | None = 1.5

    # Stronger denoising for textured paper. Greenbook and yellow pad keep
    # speckle the default misses, while smooth bond paper loses thin strokes
    # if denoised harder, so it's chosen per page from the background texture
    # (_background_noise): 2.2 or more gets strength 20. Measured on the test
    # set: no real overall difference (CER 0.126 on vs 0.123 off, within
    # noise for 20 pages), slightly better on yellow pad.
    adaptive_denoise: bool = True
    textured_paper_threshold: float = 2.2
    textured_denoise_strength: int = 20

    # No ruled-line removal: width alone can't tell a printed rule from a pen
    # stroke, and every setting tried fixed one page but broke another.


DEFAULT_CONFIG = PreprocessConfig()


def _median_glyph_height(gray) -> float:
    """Estimate the handwriting size: the median height of letter-sized ink
    blobs. 0.0 if none are found."""
    # Adaptive, not one global threshold: a large blank area would throw a
    # global threshold off.
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


def _background_noise(gray) -> float:
    """How textured the paper is: the mean difference from a median-blurred
    copy, over the brightest 40% of pixels, so the ink doesn't count."""
    residual = cv2.absdiff(gray, cv2.medianBlur(gray, 5)).astype(np.float32)
    background = gray > np.percentile(gray, 60)
    if not background.any():
        return 0.0
    return float(residual[background].mean())


def preprocess_image(
    image_path: str,
    output_dir: str = "outputs",
    config: PreprocessConfig = DEFAULT_CONFIG,
) -> str:
    """Resize, convert to grayscale and denoise the image (and threshold it
    if enabled). Saves it to output_dir as <name>_preprocessed.jpg and
    returns that path."""

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
        strength = config.denoise_strength
        if config.adaptive_denoise:
            if _background_noise(processed) >= config.textured_paper_threshold:
                strength = config.textured_denoise_strength
        processed = cv2.fastNlMeansDenoising(
            processed,
            None,
            strength,
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
