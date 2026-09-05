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

    # Adaptive Gaussian threshold to a black/white image. Off by default,
    # decided by measurement (same-cohort A/B on the 14 black-pen samples,
    # 2026-08-07): grayscale clean_ws 0.149 vs binarized 0.201 (+0.052 worse;
    # bond +0.026, greenbook +0.098). Binarization hardens the anti-aliased
    # edges of pen strokes and turns greenbook ruled lines into solid black
    # runs the detector then skips. NOTE: this is NOT "PaddleOCR is trained on
    # grayscale" -- that claim was checked against the PP-OCRv6 paper and a
    # maintainer comment and could not be confirmed (the recognizer takes a
    # 3-channel 3x48xW input, RGB reportedly preferred). The real win is that
    # grayscale unlocks an effective single-channel denoiser; with denoise off,
    # color slightly beats grayscale. The threshold code stays functional
    # behind threshold=True for compare_config.py (the binarization-vs-
    # grayscale demo tool -- see docs/ocr/DEFENSE_PREP.md section 14) and any
    # future evaluator that wants it; denoise runs either way. Full numbers +
    # 4-way color A/B: docs/ocr/EVALUATION.md.
    threshold: bool = False
    threshold_block_size: int = 31
    threshold_c: int = 15

    # A fixed block size is implicitly tuned for one handwriting size: too
    # large a block spans several characters when the writing is small, and
    # thresholding degrades. threshold_block_scale derives the block from the
    # measured glyph height instead (block = scale x glyph, rounded to odd),
    # so the pipeline copes with whatever size the student wrote. Also removes
    # the penalty from show-through when both sides of a sheet are written on.
    # Set to None to go back to the fixed threshold_block_size.
    threshold_block_scale: float | None = 1.5

    # Paper type changes what denoising should do. Raw recycled stock
    # (greenbook) carries speckle that survives the default strength and gets
    # thresholded as ink; smooth bond paper is damaged by stronger denoising,
    # which erodes thin strokes. No single strength serves both, so pick per
    # page from the paper's own measured background texture (_background_noise
    # below): at/above textured_paper_threshold the page gets the stronger
    # textured_denoise_strength, otherwise the default.
    #
    # The 2.2 trigger is calibrated for RAW captures, where it cleanly
    # separates bond (0.47-0.94) from recycled greenbook (2.53-2.62). It stays
    # relevant because the gallery-upload path bypasses the scanner and delivers
    # genuinely raw pages.
    #
    # UPDATE 2026-09-02: on the CURRENT gate test set the branch is NOT inert.
    # It fires on 15 of 20 samples (measured background noise 0.49-4.52). The
    # quality gate CROPS/frames the raw photo (capture_condition=gate_raw) but
    # does not smooth the paper's inherent texture, so greenbook speckle (mostly
    # 2.6-3.5) and yellow-pad grain (3.2-4.5) survive and correctly trigger the
    # stronger denoise; smooth bond (0.49-0.54) stays at the default. This
    # SUPERSEDES the earlier claim that gate input measured 0.50-2.07 and the
    # branch was "deliberately inert on gate" -- that was an older, smoother
    # cohort; the current select_holdout.py test set is textured enough to
    # engage the branch, which is the design working as intended.
    #
    # RE-MEASURED 2026-09-04 (ON vs OFF, fine-tuned recognizer, current 20-image
    # gate test set): overall clean_ws CER 0.126 (ON, shipped) vs 0.123 (OFF) --
    # a +0.003 difference that is within noise at n=20, NOT a real regression.
    # Per paper type: bond 0.005/0.005 (branch never fires, noise ~0.46), yellow
    # 0.071/0.077 (ON HELPS -0.006), greenbook 0.159/0.153 (ON worse +0.006,
    # driven mostly by one file swinging). Net: adaptive_denoise is ~NEUTRAL on
    # gate-framed input -- it does not degrade accuracy. Kept ON because (1) it's
    # neutral-to-helpful, not harmful; (2) 0.126 is the released/validated number
    # and the fine-tuned model was trained through this same config; (3) it helps
    # the worst-textured pages (yellow). This SUPERSEDES the earlier "byte-
    # identical 0.149 either way" claim, which was the stock model on an older,
    # smoother cohort. The 2.2 trigger and bond-vs-greenbook rationale still hold.
    # See docs/ocr/EVALUATION.md, docs/ocr/QUALITY_GATE_REVIEW.md, and the
    # `quality-gate-should-not-binarize` memory.
    adaptive_denoise: bool = True
    textured_paper_threshold: float = 2.2
    textured_denoise_strength: int = 20

    # Horizontal ruled-line removal (erasing printed rules that survive
    # denoise on lined paper) was prototyped and removed: width alone can't
    # distinguish a printed rule from a handwriting stroke, and every setting
    # tested traded a fix on one page for a regression on another. The robust
    # fix for lined paper is fine-tuning on real ruled-paper samples, not
    # pixel editing. If revisited, a straightness/periodic-spacing detector
    # (Hough-based) is the right direction, not morphological width filtering.
    # Full history: docs/ocr/EVALUATION.md, `quality-gate-should-not-binarize`
    # memory.


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


def _background_noise(gray) -> float:
    """Mean absolute residual against a median blur, over background pixels
    only, as a proxy for how textured the paper is. Ink is excluded by the
    brightness mask so the measure reflects the page, not the writing."""
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
