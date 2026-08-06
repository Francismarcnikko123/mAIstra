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
    #
    # DEFAULT FLIPPED TO False 2026-08-06, by measurement. PaddleOCR's
    # recognizer is trained on natural grayscale images and uses the
    # anti-aliased gradients on stroke edges; hard-binarizing before
    # recognition throws that information away. A/B on the full 13-sample
    # cohort (bond + greenbook + yellow_pad, raw + gate-framed, 3 writers):
    #
    #                clean_ws   binary (old)   grayscale (new)   delta
    #   bond (6)                   0.142          0.125          -0.017
    #   greenbook (5)              0.196          0.168          -0.028
    #   yellow_pad (2)             0.161          0.171          +0.010 (n=2, noise-level)
    #   overall (13)               0.166          0.149          -0.017
    #
    # 9 of 13 pages improved, several strongly. This is NOT the same as the
    # misleading 2026-07-30 "grayscale-only best" result (5 clean bond pages,
    # single writer, which inverted once greenbook arrived) -- this run spans
    # every paper type and both capture paths, and the win holds on 2 of 3
    # subgroups. Caveats, honestly: pad is n=2 and slightly negative (revisit
    # when more pad samples land -- if pad genuinely prefers binary, the fix is
    # a conditional like adaptive_denoise, not a global revert); and
    # REC_SCORE_FLOOR was rechecked under grayscale input the same day --
    # clean gap (dropped junk <=0.25, real text >=0.36, p5 0.82), floor
    # behavior unchanged.
    #
    # The threshold code below stays fully functional -- pass threshold=True
    # to reproduce the old pipeline (evaluators, future paper types, or a
    # conditional branch if pad diverges). Denoise still runs either way.
    threshold: bool = False
    threshold_block_size: int = 31
    threshold_c: int = 15

    # A fixed block size is implicitly tuned for one handwriting size: too
    # large a block spans several characters when the writing is small, and
    # thresholding degrades. Setting threshold_block_scale derives the block
    # from the measured glyph height instead (block = scale x glyph, rounded
    # to odd), so the pipeline copes with whatever size the student wrote.
    #
    # Measured on 13 labelled samples (2 writers, bond + greenbook paper):
    # fixed 31 -> 0.223 CER; scale 1.5 -> 0.198. Best on every subgroup, and
    # it removes the penalty from show-through when both sides of a sheet are
    # written on (0.370 -> 0.229 with, 0.242 -> 0.226 without).
    # Set to None to go back to the fixed threshold_block_size.
    threshold_block_scale: float | None = 1.5

    # Paper type changes what denoising should do. Recycled stock (greenbook)
    # carries speckle that survives the default strength and gets thresholded
    # as ink; smooth bond paper is damaged by stronger denoising, which erodes
    # thin strokes. Measured on 13 samples:
    #
    #                        greenbook   bond
    #   denoise 10 (default)     0.354  0.151
    #   denoise 20               0.290  0.209
    #
    # No single strength serves both, so pick per page from the paper's own
    # background texture. Measured separation was clean: bond 0.47-1.89,
    # greenbook 2.53-2.62, threshold set at the midpoint.
    #
    # Enabled by default 2026-08-02: safe on bond paper (every bond sample
    # measures below the threshold, so behavior there is unchanged) and
    # measurably better on greenbook. Yellow pad is still unmeasured -- if
    # it lands above the threshold and the stronger denoise doesn't suit it,
    # re-check against a labelled batch and adjust textured_paper_threshold
    # or add a third profile rather than assuming this setting is final.
    #
    # BROKEN under gate-processed images as of 2026-08-05 -- the clean
    # bond/greenbook separation above was measured on RAW captures only. Once
    # gate-processed samples were measured, the separation collapsed:
    #
    #                          texture score
    #   raw bond                0.49-0.94
    #   gate bond (1 sample)     1.50
    #   gate greenbook           1.75-2.00   <- WRONG SIDE of 2.2, should be high
    #   gate yellow_pad          1.94-1.97
    #   raw greenbook            2.53-2.62
    #
    # Something about the gate path drags gate-greenbook's score below the
    # threshold -- it gets treated as smooth paper and receives weak denoise,
    # letting its ruling lines survive into the binary image, which can crowd a
    # row enough that the detector skips a whole line (see the removed-feature
    # note near DEFAULT_CONFIG for the line-removal experiments this prompted).
    # NOTE (2026-08-06, verified against scanner branch tip d57a1bc): the gate
    # no longer does ANY photometric processing -- Nikko shipped raw-only upload
    # (processDocument removed) and removed the Enhance filter (scanner in
    # SCANNER_MODE_BASE). The only pixel ops on a DB image are edge-detect +
    # perspective de-warp + JPEG. So the texture drop, IF caused by the gate, can
    # only be de-warp resampling smoothing the paper speckle -- not photometric
    # hardening (that hypothesis is dead). Still confounded with the raw cohort
    # being a different writer/paper/capture; the same-page s06/s07/s08 retake
    # isolates de-warp+JPEG.
    # Tried lowering textured_paper_threshold to 1.7 to force gate-greenbook
    # into strong denoise: A/B result was NOT a fix -- recovered the dropped
    # line on 1 of 2 gate-greenbook samples (-0.022 better) but regressed the
    # other gate-greenbook sample (+0.049) and badly regressed BOTH
    # yellow_pad samples (+0.058, +0.104), because gate-greenbook and
    # yellow_pad now occupy the same 1.7-2.0 texture band -- no single
    # threshold can move one without sweeping in the other. Left at 2.2;
    # lowering it is a net loss, not a fix.
    #
    # IMPORTANT CAVEAT (2026-08-06): whether this is actually caused by the
    # gate, or by an uncontrolled difference between the raw-cohort writer's
    # paper/pen/lighting and the gate-cohort writer's, is UNCONFIRMED -- every
    # comparison so far changes gate-status AND writer AND physical paper AND
    # capture conditions simultaneously (classic confound). The gate-processed
    # greenbook and pad samples are also few (2 each) and were NOT measured
    # to be individually inconsistent from each other's readability -- one of
    # the two gate-greenbook pages scored well (0.123) even at the default
    # threshold, the other did not (0.167), which points at per-page condition
    # (line darkness, row spacing, capture shadow) rather than paper type or
    # gate-vs-raw as the operative variable. The one experiment that can
    # actually isolate the gate's effect is a same-page raw-vs-gate pair
    # (planned: retaking nombrado's raw greenbook s06/s07/s08 through the
    # gate) -- do not treat "the gate causes this" as established until that
    # runs. See `quality-gate-should-not-binarize` memory and
    # `docs/ocr/QUALITY_GATE_REVIEW.md` §7-8.
    adaptive_denoise: bool = True
    textured_paper_threshold: float = 2.2
    textured_denoise_strength: int = 20

    # NOTE: horizontal ruled-line removal was prototyped here and REMOVED
    # 2026-08-06 after measurement. Ruled/pad stock (mtcc pad, gate-framed
    # greenbook) can leave printed rules in the binary that crowd a row and make
    # the detector skip a whole line. Two preprocessing removers were built and
    # measured against the 5 gate-framed samples -- a blunt "erase any long
    # horizontal run" (regressed clean_ws 0.128->0.144) and a sharper
    # "near-full-width runs only" (0.128->0.135). Neither was a net win at any
    # setting: a width-fraction sweep found no value that recovers a dropped line
    # without regressing a page that has a genuinely full-width handwriting
    # element, and the crowded rows that most need removal are where the rule is
    # least detectable (its middle is occluded by the writing). Conclusion: width
    # alone cannot separate printed rules from handwriting, and preprocessing
    # line-removal is the wrong tool -- the robust fix for lined paper is
    # fine-tuning on real ruled-paper samples, not editing pixels before OCR. If
    # revisited, a straightness/periodic-spacing detector (Hough-based), not
    # morphological width, is the direction. Full measurement history:
    # `quality-gate-should-not-binarize` memory and `docs/ocr/EVALUATION.md`.


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
