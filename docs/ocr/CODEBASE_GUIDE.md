# OCR Codebase Guide — How `ocr_feature/` Actually Works

> **Current-state pointer (2026-09-24):** This long guide includes dated
> quoted code and old 14-page `0.149` baseline notes. The current 20-page
> production result is clean_ws CER 0.099 / WER 0.328 / token accuracy 0.716.
> `main.py` now also starts the optional `core/auto_extract.py` worker and
> reports its state through `GET /`; see the pre-extraction note near the
> `main.py` section and [RUNNING_LOCALLY.md](../setup/RUNNING_LOCALLY.md).
> Treat older "current" statements below as historical to their dates.

## Continuation-association files — 2026-09-17

- `core/continuation.py`: live, records-only association rules used by the layout
  package after full or banded column ordering.
- `core/layout/__init__.py`: production coordinator and guarded finalizer; accepts
  only complete row-preserving permutations and retains baseline order otherwise.

- `evaluators/continuation_prototype.py`: frozen, records-only association rules;
  no production imports of this module.
- `evaluators/evaluate_continuation_development.py`: default baseline replay;
  `--prototype` adds association scoring against development labels.
- `evaluators/evaluate_continuation_reserved.py`: explicit reserved replay with
  rule/fixture hash checks.
- `tests/manual_continuation.py`: fresh single-photo CLI with lazy model loading,
  unique output folder and saved `comparison.json`. Not a discovered unit test.
- `tests/test_manual_continuation.py`: model-free runner checks.

The production derivative is therefore active in both FastAPI and the web app,
while the frozen evaluator remains offline. The shortened `ocr_pipeline.py` retains recognition/orchestration; spatial logic
was moved to the `layout/` package on September 13 and organized by responsibility on September 17, not deleted by the prototype. See [session handoff](../../ocr_feature/reports/2026-09-14-continuation-session-handoff.md).

> **Purpose of this doc.** Not an API reference. This walks through each file
> as actual code blocks — quoted in full, not paraphrased — with what each
> block does, why it's built that way, how it talks to the other files, and
> for every constant or function that actually matters, what breaks if you
> change it. Written for you (the author) to re-orient quickly after time
> away, not for a stranger seeing the code cold.
>
> **⚠️ 2026-08-30: the recognizer is now fine-tuned, required, and has no
> stock fallback** — `core/ocr_pipeline.py` raises `FileNotFoundError` if
> `models/fine_tuned_rec/` is missing rather than falling back to the named
> `PP-OCRv6_medium_rec` this doc still describes below. CER: 0.274 (stock) →
> 0.126 (fine-tuned), −54%, on a held-out 20-image test set — see
> `EVALUATION.md`'s top banner and `NEXT_STEPS.md`'s 2026-08-30 status block.
> The baseline-history paragraph immediately below is retained for mechanics
> context but its cited numbers are all superseded; don't cite them as current.
>
> Status context: models are `PP-OCRv6_medium`, preprocessing exhausted.
> **Baseline update 2026-08-04:** the original 13-page `0.148` is superseded (5
> non-representative `nikko` close-ups deleted); current reproducible baseline is
> `clean_ws 0.190` over 8 full-page `nombrado` captures (bond 0.165 / greenbook
> 0.231) — a cohort change, not a regression. **2026-08-05:** 5 gate-framed
> `submission_*` samples added (bond/greenbook/yellow_pad), baseline `0.128` over
> those 5 (not directly comparable — different writers/content). **2026-08-06:**
> binarization off by default (`threshold=False`, `0.149`), THEN the deciding
> raw-vs-gate experiment ran — 7 raw `nombrado_*` pages retaken through the
> gate, same page/writer, only crop/de-warp+JPEG differing: bond worse under
> gate, greenbook better. Raw versions replaced with gate versions; `samples/`
> is now 100% gate-framed, and two `writer1` pages were then added.
> **Current reproducible baseline: `clean_ws 0.149`** over 14 samples. All
> earlier figures (`0.148`/`0.190`/`0.128`/`0.151`) are superseded. See
> `EVALUATION.md` for the evidence; this doc is about mechanics, not evidence.
>
> **STRUCTURE NOTE (verify before trusting a path).** The OCR domain modules live
> in **`core/`** (`core/preprocess.py`, `core/ocr_pipeline.py`,
> `core/layout/`, `core/c_code_cleanup.py`, plus the shared leaf
> modules `core/c_literals.py`, `core/numeric.py`, and `core/debug_artifact.py`);
> the offline tools live
> in **`evaluators/`** (`evaluate_cer.py`, `evaluation.py`, `export_dataset.py`,
> `evaluate_robustness.py`, `robustness.py`). `main.py`, `try_config.py`, and
> `run_tests.py` stay at the `ocr_feature/` root. Imports are therefore
> `from core.ocr_pipeline import ...`, `from evaluators.evaluation import ...`.
> Some quoted blocks below were written before this refactor — if a quoted `import`
> shows a bare module name, the live code uses the `core.`/`evaluators.` form.

> **File purposes at a glance.** The distinction below is easy to lose track
> of since several files "run OCR" but for different reasons — this table is
> the quick answer to "which one do I run for X":
>
> | File | Runs the real model? | Needs `labels.csv`? | What it's for |
> |---|---|---|---|
> | `main.py` | Yes | No | The FastAPI server — what the mobile/web apps actually call. Needs the server running. |
> | `try_config.py` | Yes | No | **Single-image, no server.** Eyeball one image's extraction under a given `PreprocessConfig`. No accuracy number, just prints the text. |
> | `compare_config.py` | Yes (twice) | Optional | **Single-image, side by side.** Runs one image through grayscale+denoise (shipped default) *and* adaptive binarization (`threshold=True`), printing both texts/confidences. Prints CER too when the image is found in the project's ground truth (`samples/labels.csv` or `datasets/verified/labels.csv`, matched by image name — built from the verified `.txt` transcriptions); a loose `<image>.txt` beside the image is intentionally ignored (redundant with `labels.csv`, and outside the project root). `--show` also opens both preprocessed images as VS Code tabs (`code -r`). Built for demonstrating the binarization-vs-grayscale finding live, not for routine use — see `DEFENSE_PREP.md` §14. |
> | `evaluators/evaluate_cer.py` | Yes | **Yes** | Real accuracy measurement — CER/WER/token-accuracy against verified ground truth. This is where a percentage comes from. Fails closed if any row lacks `literal_verified` provenance. |
> | `evaluators/evaluate_robustness.py` | Yes | Yes | Same idea as `evaluate_cer.py`, but compares preprocessing variants against each other rather than reporting one number. |
> | `evaluators/build_recognition_dataset.py` | Yes | Yes | Converts whole-page labels into per-line crops for fine-tuning (`datasets/recognition/`). Not an accuracy tool. |
> | `evaluators/build_crosswriter_dataset.py` | Yes | Yes | Builds the writer-disjoint MEASUREMENT dataset (4 greenbook writers excluded) + test manifest, for the cross-writer generalization experiment. Not the shipped training path. See `EVALUATION.md`. |
> | `evaluators/crosswriter_eval.py` | Yes | **Yes** | Cross-writer (new-writer) CER/WER on the 15 held-out pages. Select the model via the `MAISTRA_REC_MODEL_DIR` env var (read by `core/ocr_pipeline.py`) — no source edits. Result: stock 0.296 → fine-tuned 0.123 (−58%). |
> | `tests/test_ocr_pipeline.py` | **No — stubbed out** | No | Unit tests for the grouping/geometry *logic only* (`_group_detection_records`, `_expected_line_y`), using fabricated fake boxes. `cv2`/`paddleocr`/`numpy` are all replaced with fakes (see §3.4) so it runs instantly without the real model installed. Never touches a real image. |
> | `tests/test_*.py` (others) | No | No | Same pattern as above — fast, offline, no real model, no real images. |
>
> Rule of thumb: if you want to *see what OCR reads on a photo*, that's
> `try_config.py` (one image) or `main.py` (via the app). If you want a
> *percentage*, that's `evaluate_cer.py`, and it requires verified labels. If
> you're just checking the grouping code didn't break, that's
> `test_ocr_pipeline.py`, and it proves nothing about real accuracy.
>
> **How to run each one** (all from the `ocr_feature/` directory, using the
> project's own venv):
> ```bash
> # try_config.py -- one real image, no server, no ground truth needed
> .venv/bin/python try_config.py path/to/image.jpg
> .venv/bin/python try_config.py path/to/image.jpg --adaptive-denoise
>
> # compare_config.py -- one image, grayscale+denoise vs binarization, side by side
> .venv/bin/python compare_config.py path/to/image.jpg
> .venv/bin/python compare_config.py path/to/image.jpg --show   # also opens both
>                                                                # preprocessed images
>                                                                # as VS Code tabs
>
> # evaluate_cer.py -- real accuracy (CER/WER/token-acc) against samples/labels.csv
> .venv/bin/python -m evaluators.evaluate_cer
>
> # evaluate_robustness.py -- compares preprocessing variants against each other
> .venv/bin/python -m evaluators.evaluate_robustness
>
> # build_recognition_dataset.py -- builds datasets/recognition/ line crops
> .venv/bin/python -m evaluators.build_recognition_dataset
>
> # one test file in isolation -- fake data, no model, instant
> .venv/bin/python -m tests.test_ocr_pipeline
>
> # the full test suite -- same fake-data nature, all files
> .venv/bin/python -m unittest discover -s tests -p "test_*.py"
> ```
> Module form (`-m evaluators.evaluate_cer`, `-m tests.test_ocr_pipeline`) is
> required, not the bare file path — these files use `from evaluators...`/
> `from core...` imports that only resolve as package imports. Running them
> as `python evaluators/evaluate_cer.py` fails with an import error.

---

## 1. The shape of the system in one picture

```
                         ┌─────────────┐
   mobile app  ────────▶ │  Supabase   │  (image_url stored on a
   (photo capture)       │  storage    │   submissions row)
                         └──────┬──────┘
                                │
                                ▼
                         ┌─────────────┐
   web "Extract" button ▶│  main.py    │  FastAPI: two endpoints,
                         │             │  download-or-receive an image
                         └──────┬──────┘
                                │ calls
                                ▼
                     ┌────────────────────┐
                     │ core/ocr_pipeline.py│  orchestrator — the one
                     │ extract_text_from_  │  function everything else
                     │ image()             │  in the package answers to
                     └──────┬─────────┬────┘
                            │         │
                core/preprocess.py    PaddleOCR
                    (image →          (`ocr.predict`)
                     cleaned bitmap)      │
                                          ▼
                              core/c_code_cleanup.py   (safe keyword fixes)
```

Offline tooling sits *beside* this runtime path, not inside it — all under
`evaluators/`:

- **`evaluators/evaluation.py`** (+ `evaluate_cer.py`, `evaluate_robustness.py`,
  `robustness.py`) — offline measurement tools. They call
  `core.ocr_pipeline.extract_text_from_image()` the same way `main.py` does, but
  score the result against `samples/labels.csv` instead of returning it to a
  client.
- **`evaluators/export_dataset.py`** — offline, pulls verified rows out of
  Supabase to build a labeled dataset for future fine-tuning. Never imported by
  the runtime path. **Since 2026-09-27** it reads `status` in (`verified`,
  `graded`), uses `SUPABASE_KEY` (the legacy `SUPABASE_ANON_KEY` is only a
  fallback), and takes each page's text from the `submission_programs` table
  (embedded in the same request). A page the teacher split into several
  programs is written with every program in the new `program_blocks` column
  (JSON list, tab order); its `verified_text` is the blocks joined by a blank
  line, for reading only, and its `correction_edit_distance` is blank (tab
  order is not reading order). `build_recognition_dataset._pair_lines()`
  matches each block to the page's detected lines on its own, and drops any
  line two blocks both claim; one-text pages pair exactly as before.
  `compare_config.py` and `select_holdout.py` skip split pages
  (`labels_schema.is_split_page`), so they can never become a whole-page CER
  reference or a test page. The export also warns when Program 1 in
  `submission_programs` differs from `submissions.verified_text` (a save that
  bypassed `save_submission_programs()`); the table wins.

**The one rule that shapes almost every design choice in this package:**
*this is a grading app.* The OCR text is read by a human teacher before it
ever affects a grade, and nothing in this codebase is allowed to silently
change what a student appears to have written. That single constraint is why
`c_code_cleanup.py` has a closed vocabulary instead of a general-purpose
autocorrect, and why `REC_SCORE_FLOOR` only removes near-certain noise
rather than "improving" readings.

---

## 2. `core/preprocess.py` — turning a photo into something PaddleOCR can read well

Four sequential stages, each optional via `PreprocessConfig`, always applied
in this order because each stage assumes the previous one already ran:
denoising works on grayscale, thresholding works on denoised input.

### 2.1 `PreprocessConfig` — the full dataclass

```python
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
    # [DEFAULT FLIPPED 2026-08-06: now False — see correction below this block]
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
    # [Comment ABBREVIATED here — the live core/preprocess.py comment is now
    #  much longer. See the 2026-08-06 correction summarized right below this
    #  code block, and read the source for the full measured history.]
    adaptive_denoise: bool = True
    textured_paper_threshold: float = 2.2
    textured_denoise_strength: int = 20


DEFAULT_CONFIG = PreprocessConfig()
```

> **Three current corrections the quoted block predates (all 2026-08-06 — the
> live `core/preprocess.py` carries the full versions):**
>
> 0. **`threshold` now defaults to `False`** — the pipeline feeds PaddleOCR the
>    denoised *grayscale* image. Full-cohort A/B: clean_ws `0.166 → 0.149`
>    overall, bond and greenbook both improved, pad noise-level worse at n=2;
>    same-cohort re-confirm on the current 14 samples (2026-08-07): grayscale
>    `0.149` vs binarized `0.201`. Mechanism (corrected 2026-08-07, see
>    EVALUATION.md top banner): grayscale wins by unlocking an effective
>    single-channel denoiser, NOT because "the model is trained on grayscale"
>    (that claim was unverifiable against primary sources). The threshold path
>    (and `_median_glyph_height`, which only
>    runs inside it) stays fully functional behind `threshold=True`. Note this
>    means the §2.4 walkthrough's "resize → grayscale → denoise → threshold →
>    write" description is now the *non-default* path — the default ends at
>    denoise.
>
> 1. **The "clean separation at 2.2" claim holds only for RAW captures.** Once
>    gate-framed samples were measured, the texture-score separation collapsed:
>    gate-greenbook reads 1.75–2.00 (below the 2.2 threshold — treated as smooth
>    paper, gets weak denoise) and overlaps gate yellow_pad (1.94–1.97). Lowering
>    the threshold to 1.7 to fix it was tested and *also* regressed (no single
>    threshold separates gate-greenbook from pad). So `textured_paper_threshold`
>    is a known-fragile proxy under gate-framed input — do not trust the "midpoint
>    of a clean gap" story for anything the mobile gate produced. See
>    `EVALUATION.md`'s 2026-08-06 update.
> 2. **A `remove_horizontal_lines` field briefly existed here and was REMOVED.**
>    A ruled-line remover (to erase printed greenbook/pad rules that survive into
>    the binary and crowd a row) was prototyped, measured in three variants, and
>    removed 2026-08-06 — no version was a net win (width alone can't separate a
>    printed rule from a long handwriting stroke). If you heard about it, its
>    absence from the config is correct. Finding preserved in `EVALUATION.md`.

**Why a `frozen=True` dataclass instead of module constants:** every
experiment (the sweeps referenced in the comments above) constructs a
*different* `PreprocessConfig(...)` and passes it through
`preprocess_image()` / `extract_text_from_image()` without touching global
state, so one experiment's tweak can never leak into another's run.
`frozen=True` means an instance can't be mutated mid-pipeline and silently
change behavior for a later call reusing the same object.

**If you add a new field:** it must default to reproducing *current* behavior
exactly (the class docstring says this explicitly) — importing this module
and calling `extract_text_from_image()` with no config argument must never
silently change production behavior. Concretely:

```python
# new field, correctly defaulted to a no-op
ruled_line_removal: bool = False   # off by default = identical to today's behavior
```

**Verify the "no silent change" guarantee directly:** call
`extract_text_from_image()` on a sample with no config argument (or
`PreprocessConfig()` with all defaults) before and after adding the field,
diff the two `cleaned_text` outputs, and confirm they're byte-identical —
that's the actual proof, not just reading the docstring rule. See §10 for
the general before/after/test pattern used throughout this file.

### 2.2 `_median_glyph_height()` — measuring how big the handwriting is

```python
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
```

Runs a throwaway threshold+connected-components pass just to *measure* the
page (this result is discarded — the real threshold later uses only the
derived block size). Components are filtered by shape to exclude:
- **speckle** (`area >= 12` — drops isolated noise pixels/dots),
- **page-sized blobs** (`h <= 300` — drops a whole shadowed region collapsing
  into one component),
- **long rules/edges** (`w <= 12 * h` — drops a horizontal margin line, which
  would otherwise report a misleading aspect-ratio outlier as a "glyph").

### 2.3 `_background_noise()` — measuring how textured the paper is

```python
def _background_noise(gray) -> float:
    """Mean absolute residual against a median blur, over background pixels
    only, as a proxy for how textured the paper is. Ink is excluded by the
    brightness mask so the measure reflects the page, not the writing."""
    residual = cv2.absdiff(gray, cv2.medianBlur(gray, 5)).astype(np.float32)
    background = gray > np.percentile(gray, 60)
    if not background.any():
        return 0.0
    return float(residual[background].mean())
```

Blur the image, subtract the blur from the original — what's left over (the
residual) is high-frequency detail: either paper texture or ink. The
`background` mask keeps only the brighter 40% of pixels (excludes dark ink
strokes), so the residual measured reflects paper texture specifically.
Result: roughly 0.5–2 for bond paper, 2.5+ for greenbook **in the raw-capture
samples** — clean separation, threshold set at the midpoint (2.2).

> **Correction (2026-08-06): that clean separation is a raw-capture property
> only.** On gate-framed captures (the mobile app's actual output) the scores
> compress and overlap — gate-greenbook 1.75–2.00, gate yellow_pad 1.94–1.97,
> gate bond ~1.50 — so `_background_noise` no longer cleanly maps to paper type,
> and the 2.2 threshold puts gate-greenbook on the wrong (weak-denoise) side.
> This is the single most important caveat on this function now: it was
> calibrated on raw photos, and the production pipeline sees gate-framed ones.
> See `EVALUATION.md`'s 2026-08-06 update and `core/preprocess.py`'s
> `adaptive_denoise` comment.

### 2.4 `preprocess_image()` — the full pipeline, in order

```python
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
```

Read this top to bottom as **resize → grayscale → (adaptive) denoise →
(glyph-adaptive) threshold → write**.

**The line that matters most in this whole file:** `glyph =
_median_glyph_height(processed)` is called on `processed` — the variable
that, by this point, already went through `cv2.fastNlMeansDenoising`. Glyph
height is measured **after** denoising, never before. This is not
incidental: measuring on raw (pre-denoise) grayscale lets paper-texture
speckle get counted as tiny "glyphs," dragging the median down and making
textured paper (greenbook) look like it has much smaller handwriting than it
actually does. Measuring post-denoise correctly reports greenbook's real
glyph size (14–16px, comparable to bond). **If this call is ever moved
earlier in the pipeline (before the denoise block), that exact bug comes
back.**

**If you change `max_side` (1600):** raising it costs more CPU (denoise and
threshold are per-pixel) for likely no gain, since PaddleOCR downsamples
internally past a point anyway. Lowering it risks shrinking fine strokes
below what denoising and recognition can resolve — expect CER to get worse.
See §10.10 for the exact before/after and test command.

**If you change `denoise_strength` / `textured_denoise_strength`:** this is
literally the accuracy/texture-removal tradeoff from the table in the
dataclass comment (bond gets *worse* at strength 20, greenbook gets *better*)
— any change must be re-measured **per paper-type subgroup**, not as one
overall average, or a regression on one paper type can hide behind an
improvement on the other.

**If you change `textured_paper_threshold` (2.2):** lowering it pulls more
images — including some bond pages — onto the stronger denoise that bond was
measured to do worse under. Raising it risks leaving some greenbook pages on
the weaker denoise that leaves texture behind. **Important (2026-08-06):** this
threshold was calibrated on RAW captures, where bond/greenbook separate cleanly.
On gate-framed captures the scores compress and overlap (gate-greenbook 1.75–2.00,
yellow_pad 1.94–1.97, gate bond ~1.50), so no single threshold classifies them
correctly — a 1.7 recalibration was tested and regressed. Yellow pad now has
measured gate-framed samples (it lands ~1.94–1.97, *above* 2.2 is false — it's
below, so it currently gets weak denoise); do not assume the raw-capture
separation transfers. Re-measure per paper type on gate-framed input before
touching this. See `EVALUATION.md`'s 2026-08-06 update.

**If you change `threshold_block_scale` (1.5):** `None` reverts every page to
the fixed `threshold_block_size` (31), which was measured worse (0.223 vs
0.198 CER) on this cohort. Any other multiplier needs re-validation across
every writer/paper subgroup, not just the average — that's the actual claim
the current value earned ("best on every subgroup").

**If you change `threshold_c` (15):** higher values classify more pixels as
paper (risk losing faint/thin strokes); lower values classify more as ink
(risk texture/shadow read as false ink). No sweep of this constant exists —
treat any change here as untested. See §10.11 for the exact before/after and
test command.

---

## 3. `core/ocr_pipeline.py` — the orchestrator (the file everything answers to)

> **STRUCTURE UPDATE (2026-09-13): reading-order geometry now lives in
> `core/layout/`.** `ocr_pipeline.py` had grown past 1,200 lines, so the pure
> reading-order / indentation geometry was extracted into a new sibling module
> along its natural dependency seam (commit `f99732c`, behavior-preserving —
> function bodies moved by exact line range, no logic changed; 148 tests pass
> and `evaluate_cer` reproduces the pins exactly). The split:
> - **`core/ocr_pipeline.py`** (~275 lines): recognition + orchestration —
>   model construction (§3.1), `warmup()`, `REC_SCORE_FLOOR`,
>   `_filter_low_confidence` (§3.2), `_recognize_preprocessed`,
>   `extract_text_from_image` (§3.6/§3.7). Imports `cv2`/`numpy`/`paddleocr`.
> - **`core/layout/`** (~960 lines): all the geometry the sections below
>   describe — `_group_detection_records` (§3.3), the column/banded/severance
>   detectors and brace-depth reassembly (§3.8), `_group_structured_lines`
>   (§3.5), `line_member_bounds`, and indentation/blank-line reconstruction.
>   Pure stdlib + `core.numeric`/`core.c_literals`; imports nothing heavy, so it
>   loads in tests without the recognizer.
>
> `ocr_pipeline.py` **re-exports** the two geometry names still imported from it
> (`_group_detection_records`, `line_member_bounds`), so
> `from core.ocr_pipeline import _group_detection_records`
> (`evaluators/build_recognition_dataset.py`) still works. (Update 2026-09-18: the
> other six geometry re-exports and the `core/layout/reorder.py` compatibility shim
> were removed as dead — no importer used them; import those helpers directly from
> `core.layout`.) Geometry unit tests,
> however, load `core.layout` directly (`load_layout()` in
> `tests/test_ocr_pipeline.py`) so `patch.object` targets the module where the
> functions call one another — patching a re-export would not intercept those
> internal calls. The function descriptions below are unchanged; only the file
> that physically holds them moved.

### 3.1 Model construction (module load time)

```python
from paddleocr import PaddleOCR

# Detection and recognition are pinned by name -- passing a model name makes
# PaddleOCR silently ignore lang/ocr_version, so setting those too would be misleading.

# no orientation/unwarp passes: ~81s -> a few seconds per image on CPU, since
# our captures are already gated upright/flat at the mobile app.

# Model pairing chosen by sweep over the 13 human-verified pages (2026-08-03),
# clean_ws CER, all four pairings scored on the same cohort:
#
#   v6_medium_det + v6_medium_rec      0.148   <- selected
#   v5_mobile_det + en_v5_mobile_rec   0.181   (previous default)
#   v5_server_det + en_v5_mobile_rec   0.187   at ~9x the runtime
#   v5_mobile_det + v5_server_rec      0.279
#
# v6 wins on 11 of 13 pages and improves every paper/writer subgroup. Bigger is
# not better here: v5_server_rec is multilingual and substitutes CJK for C
# symbols (二 for '='), which is why the older en_ recognizer was pinned -- that
# instinct is now confirmed numerically. Detection is not the bottleneck;
# v5_server_det cost 9x the time for a worse score, so detection stays small.
#
# Cost of this change: ~3s -> ~9s per page on CPU.
#
# v6_medium_rec also emits occasional CJK, but stripping non-ASCII moves CER by
# ~0.0001, so it is cosmetic rather than an accuracy problem.
#
# REC_SCORE_FLOOR below (0.3) was re-verified against the current v6 recognizer
# on the gate-framed test set: dropped items are empty-text phantoms (0.0) or
# junk (highest 0.291), lowest real kept detection 0.334 — the floor sits in
# the 0.291 -> 0.334 gap.

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_dir=_FINE_TUNED_REC_DIR,  # fine-tuned, required (see banner)
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_det_box_thresh=0.30,   # lowered from 0.60 default to recover braces
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
```

This runs **once, at import time**, not per request — constructing
`PaddleOCR(...)` loads model weights, which is slow, and that cost needs to
be paid once at server start (see `main.py`'s `lifespan`, §4), not on a
user's first request. `warmup()` runs one dummy prediction so any lazy
internal initialization inside PaddleOCR also happens before real traffic
arrives, wrapped in a bare `except` because a warm-up failure must never
block server startup.

**If you change the model names:** this is the single highest-leverage
accuracy lever in the file, and the riskiest to get wrong silently — a bad
pairing passes every unit test (none of them call the real model) and only
shows up as a worse `clean_ws` in `evaluate_cer.py`. Re-run the full sweep
(same 13 verified pages, all four CER variants, every subgroup) before
keeping a change — see `PIPELINE.md`'s "Model selection" table.

**If you flip a `use_*=False` flag to `True`:** latency jumps back toward
~81s/image. This is only safe to skip *because* captures are assumed
upright/flat from the mobile app — an assumption the quality gate is meant
to enforce but has not yet merged (see `NEXT_STEPS.md`). See §10.12 for the
exact before/after and test command.

**`text_det_box_thresh=0.30`** (added 2026-09-04): lowered from PaddleOCR's
`0.60` default. On the fine-tuned model, braces were being lost at the
*detection* stage — standalone braces on their own line scored below the 0.60
box cutoff, so the recognizer never saw them (recognition itself reads braces
fine, at 0.9–1.0 confidence). Measured A/B, 0.60→0.30: overall CER stays
`0.126` (no phantom regression), closing-brace recovery rises 82→87 of 89, and
the extra detections are all real content (braces + previously-missing code
lines), zero junk. Verified negligible runtime cost (~0.2s, detection count
barely changes). Full A/B: `EVALUATION.md`. `REC_SCORE_FLOOR` (§3.2) still
guards the recognition stage against genuine junk independently of this.

### 3.2 `REC_SCORE_FLOOR` and `_filter_low_confidence()`

```python
# Below this score a detection is almost always the detector firing on a
# smudge or stray mark rather than real writing -- a phantom "2" once scored
# 0.127 while every real character on the same page scored 0.7+. Kept low
# enough to only catch that kind of noise, not genuine hard-to-read characters.
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
```

Three parallel lists in (`rec_texts`/`rec_scores`/`rec_boxes` — one entry per
detected fragment from PaddleOCR), filtered together so they stay aligned.
Note the `except` branch: a missing/malformed score **passes through** rather
than being dropped (`passes = True`) — the filter only removes what it can
positively confirm is below the floor, never guesses a fragment away.

**If you change `REC_SCORE_FLOOR` (0.3):** raising it drops more fragments —
because some of those are real low-confidence (but correct) characters,
expect more *deletions*, which in a grading app means the teacher sees less
than the student wrote (worse than a wrong-but-visible character). Lowering
it lets more phantom noise survive. On the current v6 model, a sweep found
this constant currently inert (0.0–0.5 moves `clean_ws` by <0.001) — but
that's a property of *this* model's confidence distribution; recheck after
any model swap or fine-tuning run.

**Where the dropped list actually goes:** `dropped_low_confidence` (the
fourth return value) is written into the debug JSON (§3.6) but is **not**
part of what `extract_text_from_image()` returns to `main.py` or the
evaluators (see §3.6's dict comparison) — this asymmetry once caused a
floor-sweep script to read the wrong field and report zero drops at every
floor value tested.

### 3.3 Reading-order grouping — the core geometry logic

```python
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
                      "x": x_min, "y": y_center,
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
            if (trend_delta <= line_tol
                    and (center_delta <= line_tol
                         or trend_delta <= line_tol * 0.5)):
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
```

**The problem this solves (from the caller's docstring, quoted in §3.3
below):** PaddleOCR returns fragments in detection order, not reading order.
A real observed failure: `int result = add(3,4);` came back as three
disconnected fragments — `add (3,4);`, `int result`, `=` — each on its own
"line," out of order.

**How to read it, in three stages:**

1. **Geometry extraction, fail-safe by construction.** Every box is unpacked
   into `x_min, y_min, x_max, y_max`; any parse failure, non-finite value, or
   non-positive width/height causes an **immediate return to
   `_original_detection_records`** — one fragment per line, untouched order.
   This fallback fires three separate times in this function (malformed box,
   invalid geometry, non-finite center) — the function would rather do
   nothing risky than group on bad data.
2. **Per-page tolerance, not a fixed pixel number.** `line_tol = max(median_h
   * 0.6, 1.0)` — "same line" is judged relative to *this page's* typical
   detection height, so it scales with however large or small this
   particular student's handwriting is.
3. **Trend-fit sweep, not just banding.** `_expected_line_y()` fits a simple
   linear regression (slope of y vs x) through the current line's members,
   so a fragment that's drifted vertically but stays consistent with a
   slight slant can still join the line. The join condition
   (`trend_delta <= line_tol and (center_delta <= line_tol or trend_delta <=
   line_tol * 0.5)`) requires *either* fitting the simple mean-y band *or*
   fitting the trend within half tolerance — the half-tolerance restriction
   specifically exists to stop a slanted trend from swallowing a genuinely
   new indented row (e.g. a nested block's first line) that happens to
   continue the slope.

**What this never does:** it only reorders and merges whole recognized
fragments by position — it never edits a character inside a fragment. This
is why `PIPELINE.md` calls it "grade-safe": wrong about *sequence* is
possible, wrong about *content* is not, by construction.

**If you change the `0.6` multiplier:** raising it merges more aggressively
(risk: joining two genuinely separate rows); lowering it splits more (risk:
one visual line reported as several). No existing sweep of this constant —
any change needs testing against a deliberately slanted sample, not just
straight ones, since it interacts with the trend-fit logic non-linearly.

**If you change the `* 0.5` half-tolerance:** controls how far a slanted
trend can extend past the mean-y band before being rejected as a new line.
Loosening it risks following a slant into an actually-new indented row;
tightening it risks splitting a genuinely slanted line in two.

### 3.4 `_group_detection_records()` is the single grouping core — no separate wrapper

Earlier this codebase had a thin public wrapper, `_group_into_reading_order()`,
that just reshaped `_group_detection_records()`'s output into `(text, score)`
tuples. It had no production caller — `_group_structured_lines()` (§3.5) was
already the real production path, calling `_group_detection_records()`
directly — so the wrapper was dead code that only tests exercised. It was
deleted; `tests/test_ocr_pipeline.py`'s `GroupDetectionRecordsTests` (11 cases)
now calls `_group_detection_records()` directly and flattens the result
itself, so the same algorithm coverage remains with one less indirection.
**There is now exactly one function that implements the grouping algorithm:
`_group_detection_records()`**, described in §3.1–§3.3 above.

### 3.5 `_group_structured_lines()` — normalized geometry for cross-image comparison

```python
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
                y_min = min(member["y_min"] for member in members) / normalized_height
                y_max = max(member["y_max"] for member in members) / normalized_height
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
```

**Why `y_min`/`y_max` are divided by `image_height` here:** this normalizes
box positions to a 0.0–1.0 scale regardless of pixel resolution, so the
reading-order grouping (§3.3) behaves identically whether the preprocessed
image is 1600px tall or 800px. The line-assignment tolerances downstream are
expressed as fractions of page height, so they only make sense against
normalized coordinates — a fixed pixel tolerance would mean different things
on different-resolution captures.

### 3.6 Debug artifacts

> **MOVED (2026-08-08):** both functions below now live in
> **`core/debug_artifact.py`**, not `ocr_pipeline.py`. `_write_debug_artifact`
> was renamed to the module-public **`write_debug_artifact`** (`_jsonable`
> stays private to that module); `ocr_pipeline.py` does
> `from core.debug_artifact import write_debug_artifact`. Rationale: this is
> developer-facing diagnostic I/O, not recognition logic, so `ocr_pipeline.py`
> stays extraction-only — the same separation `preprocess.py` already has.
> Behavior-preserving: `clean_ws 0.149` unchanged (bond 0.133 / greenbook
> 0.159 / yellow_pad 0.171), 64/64 tests pass, artifacts still written to
> `outputs/debug/`. The module imports stdlib only (`json`, `pathlib`) so
> `tests/test_ocr_pipeline.py` loads the real module in its stub setup rather
> than faking it — see §3.4's isolation note.

```python
def _jsonable(value):
    """Best-effort conversion of PaddleOCR values (numpy scalars/arrays) into
    plain Python types for the debug JSON. Unconvertible values become their
    string form rather than failing the dump."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return _jsonable(tolist())
        except Exception:
            pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _write_debug_artifact(preprocessed_path: str, debug: dict) -> None:
    """Save the extraction's intermediate data as outputs/debug/<stem>.json,
    matching the preprocessed image's stem so the pair is easy to correlate.
    Diagnostic only -- a failure here must never break the extraction itself."""
    try:
        debug_dir = Path(preprocessed_path).parent / "debug"
        debug_dir.mkdir(exist_ok=True)
        out_path = debug_dir / (Path(preprocessed_path).stem + ".json")
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(_jsonable(debug), f, indent=2, ensure_ascii=False)
    except Exception:
        pass
```

`_jsonable()` recurses through PaddleOCR's return values (which include numpy
scalar/array types Python's `json` module can't serialize directly), calling
`.tolist()` on anything array-like, falling back to `float()`, and as a last
resort stringifying whatever it still can't convert — so the dump never
raises on an unexpected type. `write_debug_artifact()` wraps the entire
write in a bare `try/except: pass` because this is explicitly diagnostic —
a failed debug write (disk full, permissions) must never turn a *successful*
extraction into a failed API response.

**Where this is called from, and the asymmetry that matters** — inside
`extract_text_from_image()`:

```python
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
```

`debug` and `result` are **two separate dict literals** built from the same
underlying data — `dropped_low_confidence` is in `debug` but not `result`.
If a new field needs to reach the API/CLI caller, it has to be added to
*both* literals explicitly; adding it only to `debug` makes it invisible to
`main.py` and the evaluators. This exact gap is what caused an earlier
`REC_SCORE_FLOOR` sweep to read zero drops at every floor value tested.

### 3.7 The consensus branch — REMOVED 2026-08-04

There used to be a `recognition_config.mode == "consensus"` branch here that ran
recognition three times per image (baseline + two `±0.5°` rotations) and let a
selector override the baseline line-by-line. **It was deleted on 2026-08-04**
along with `recognition_consensus.py` and its evaluator/tests. `extract_text_from_image()`
is now baseline-only — one recognition pass, no `recognition_config` parameter.

**Why it was removed:** consensus across rotations of the *same image* scored by
the *same model* behaves like correlated readers, not independent evidence — it
improved some lines and corrupted others (including turning correct C keywords
wrong) roughly 50/50, for a net CER change indistinguishable from noise and ~2×
the runtime. It never ran in production (the default was always baseline), and its
evaluator had already been deleted, so it was a dead, unmeasurable path. The full
rejected-experiment record — numbers, root-cause analysis, and the "correlated
views aren't evidence" argument — is preserved in
[`RAW_OCR_CONSENSUS_HANDOFF.md`](RAW_OCR_CONSENSUS_HANDOFF.md). If a genuinely
independent second opinion (a different model, or a language prior) is ever worth
trying, it would be new work, not a revival of this code.

### 3.8 Reading-order handling — `feature/reading-order-reassembly` branch (updated 2026-09-11, not yet merged)

**Where this lives.** Feature branch off `ocr_feature`, 16 commits (`74ebace` →
`82a47bc`). NOT yet on `ocr_feature`, not yet pushed. This subsection documents
what the branch adds, so the code doesn't come as a surprise on review.

**What actually works vs. what is recognition-gated — read this first.** The
branch contains *two independent mechanisms* that are easy to conflate:

1. **Two-column split** (`_detect_two_columns` + `_order_column_items`) — the
   real, demonstrable win. Detects a page written as two side-by-side columns
   of *independent* programs and reads the whole left column top-to-bottom, then
   the whole right column, instead of zig-zagging across the gap and fusing
   unrelated lines. **This fires on real handwriting and measurably improves
   accuracy** (see "Baseline" below). It is pure geometry — it does NOT need to
   understand whether the right column is a new program or a continuation of the
   left; it just reads each column in order.
2. **Brace-depth continuation reassembly** (`_reassemble_displaced_regions`) —
   the fragile, recognition-gated mechanism for a *single* program whose tail was
   displaced into the margin. **It has never fired on a real photo.** It works
   only on synthetic fixtures because it needs nearly every `{`/`}` in the block
   recognized correctly, and real brace recall is far too low for that. Present
   it honestly at defense as a designed-and-tested-but-not-demonstrable path with
   a known recognition dependency, never as a shipped result.

Do not let the branch name ("reassembly") imply the reassembly is what works —
the *split* is.

**Problem it solves.** A student writes a `switch`-case body (or similar
mid-structure fragment) into unused margin space, because the space directly
below is filled with the rest of the function. Today's `_group_detection_records`
would either fuse the same-height fragments into one garbled line (no
horizontal-gap check exists, only x-overlap) or, if vertical tolerance is
exceeded, insert the fragment as its own line at the wrong position in the
sequence. Either way the extracted text doesn't represent the student's
intended program. This exact scenario is what the thesis adviser raised as a
real, expected case — see `docs/ocr/DEFENSE_PREP.md` §11 for the defense
framing.

**Two-phase design.**

*Phase 1 — gap severance.* Inside `_group_detection_records`, after a
candidate passes the existing vertical-tolerance and x-overlap gates, one
check: if the horizontal gap from the candidate's leftmost x to the current
line's rightmost x exceeds `REGION_GAP_MULTIPLIER * median_box_width`, sever the
candidate into its own line tagged `severed_by_gap=True` instead of merging it
in. `REGION_GAP_MULTIPLIER` is now **`0.75`** (recalibrated from the original
provisional `6.0` after measuring real gaps on calibration photos: confirmed
same-line gaps 48–81px vs. confirmed cross-region gaps 151–391px, a clean
separation). The original `6.0` is retained as `BASELINE_REGION_GAP_MULTIPLIER`
for the conservative baseline comparison. This alone stops the "fusion into one
garbled line" failure mode, even without Phase 2.

*Dynamic gutter trace.* `_trace_displaced_region` walks the boxes by top,
narrowing `left_max`/`right_min` as it goes, and closes the region on a genuine
straddle or at page-end. It is capped at `MAX_DISPLACED_REGION_LINES = 12` lines
and `MAX_DISPLACED_REGION_SPAN = 300.0`px so a runaway trace can't swallow a
whole column, and it discards a region that never closes (that shape is a
two-column page, handled by the split below, not a margin displacement).

*Two-column split.* `_detect_two_columns` finds the widest persistent,
uncrossed vertical coverage gap and takes its midpoint as `best_x`. It requires
both sides to be substantial — at least `MIN_COLUMN_LINES = 4` detections and at
least `MIN_COLUMN_VSPAN_FRACTION = 0.5` of page height each — before declaring a
genuine two-column page. When it fires, `_group_detection_records` partitions by
`best_x` and runs `_order_column_items` on each side, reading the left column
fully, then the right. On `green_writer10_B2_1.jpg` this splits at `x=321` into
24 left detections then 23 right, with no mixed lines. This is the mechanism
that produces the measured accuracy win.

*Banded column split (2026-09-13).* `_detect_banded_column` generalizes the
full-height split to a **partial-height** right block — a two-page /
side-by-side capture whose continuation fills only the top-right quadrant. It
runs **only when `_detect_two_columns` returns None**, so green_writer10 still
takes the full-height path (banded never runs on it). The full-page projection
fails on these pages because a stray wide line elsewhere (e.g. a left `printf`
that reaches far right at a height where the right block no longer exists)
bridges the x-projection, reporting gutter 0. Banded instead: (1) builds a
right cluster by x0 — it tries each item as a seed in **descending-x0 order** and
keeps the first whose greedy median-aligned group (admit items within
`BAND_X_ALIGN_MULTIPLIER=2.0 × median_width` of the running median x0) forms a
persistent column; any higher-x0 strays above the chosen seed are folded into the
right cluster, so a lone far-right detection (a page-edge mark) can't seed a
one-row cluster and hide a real column (hardening, commit `c8cc502`); (2) requires
the cluster to occupy ≥ `MIN_BAND_ROWS=3` distinct visual rows; (3) within the
cluster's y-band, requires a clean gutter `right_min − left_max ≥ BAND_GUTTER_MIN`
(`max(1.5 × median_width, 60px)`) — the midpoint gutter this defines leaves no
band item straddling it by construction (an explicit straddle re-check was
removed as dead code, same commit). If all hold it reads left-fully-then-right-fully like the
full-height split; any degenerate/ambiguous geometry returns None (today's
behavior). Pure geometry, grade-safe: whole pieces move by position, no
character is added/edited/split/dropped. **Measured win:** `green_writer18_B2_2`
clean_ws CER **0.147 → 0.042** (ordering only; the 0.042 residual is recognition
error). No held-out `samples/` page has this layout, so the `evaluate_cer`
headline stays **0.099** (WER 0.328, token acc 0.716). See
`docs/superpowers/specs/2026-09-12-banded-column-detection-design.md`.

*Banded vs. severance — complementary, both kept.* A 162-artifact corpus scan
(`outputs/debug/*_preprocessed.json`) confirmed banded fires on exactly the one
genuine banded page (both copies of green_writer18) with **zero false
positives** on the ~145 clean single-column pages. It **grade-safely declines**
the 7 `reassemble_example*` structural-reassembly pages: on each the banded
gutter is negative (a left box's right edge overlaps the right cluster within
the band — no clean spatial gutter), so those remain handled by
`_sever_displaced_regions` + `_reassemble_displaced_regions`. The two mechanisms
target different shapes (spatial column vs. margin-overlap structural block), so
severance is **retained as a documented fallback**, not retired.

*Phase 2 — brace-depth reassembly.* A new module-level function
`_reassemble_displaced_regions(lines)` runs right before the final sort.
It scans for `severed_by_gap` lines and computes the C brace-depth
trajectory (via `_brace_delta`, which shields braces inside string/char literals
**and comments** before counting — `core/c_literals.C_LITERAL` plus `//` and
`/* */` masking, matching `core.continuation._scope` so the two brace guards never
disagree on the same text; comment masking added 2026-09-18). Then it walks every possible block
length starting at the first severed line, computes the reordering `normal
+ block`, and keeps only reorderings where cumulative depth never goes
negative *and* ends at 0. If exactly one block length yields a well-formed
reordering, apply it. Zero or multiple valid lengths → return the input
unchanged. This is the design's core invariant: **no confident guessing —
either uniqueness proves the reordering, or the algorithm stays silent**.

**Post-selection semantic guard.** After the search finds a unique winning
block length, one more check: if the winning candidate's non-severed
partition contains a line with negative brace delta (a real closer), veto
the reordering and return the input unchanged. Justification: end-of-sequence
displacement, by definition, means main-column text left scopes dangling
and the block closes them. If the main-column text contains its own
closers, the displaced block belongs *mid-sequence*, and brace math alone
cannot semantically distinguish "correct mid-insertion" from "wrong
end-append" (both can produce identical depth trajectories, verified by
hand-trace). Failing safely to no-op is strictly better than producing a
wrong reordering that looks structurally clean.

**Definition-close exemption to the guard** (`_is_definition_close`). The guard
above wrongly rejected any real program containing a multi-line `struct`/`union`/
`enum`, because its `};` reads as a negative-delta closer in the "normal"
partition. `_is_definition_close(text)` returns True when *every* `}` on a line
is immediately followed by `;` (a type-definition close), and such lines are
exempted from the veto — a displaced executable block can never legitimately
belong inside a type definition, so its `};` is not the kind of closer the guard
is meant to catch. This fix unblocked the multi-line-struct case; it does not
make the reassembly fire on real photos (recognition is still the ceiling).

**What's out of scope, honestly.** Not general non-linear layout. Not
mid-sequence reassembly. Not PP-StructureV3 (evaluated, deprioritized —
printed-doc multi-column tool, no C-syntax awareness). Not indentation
(that stays the teacher-triggered Format button). Full non-goals list:
`docs/superpowers/specs/2026-09-07-reading-order-reassembly-design.md`.

**Test coverage: 148/148 passing** (full Python suite as of the banded
hardening, incl. `BandedColumnDetectionTests`; historically 126 at the
reassembly phase). RBNode
`rotate_rb` and Compressor `pack_flags` — both adviser-raised structural
examples — uniquely reassemble at `block_len=9` and `block_len=7`. Ambiguous
fixtures (two valid block lengths) and unbalanced fixtures (no valid block
length) both correctly return unchanged. A counter-example test locks in the
guard's rejection of Codex's post-selection edge case;
`test_relocates_past_a_multiline_struct_in_the_main_flow` and
`test_refuses_when_normal_contains_a_closer` lock in the definition-close
exemption. `TwoColumnDetectionTests` /
`test_full_height_two_column_page_is_split_into_sequential_columns` and
`DynamicGutterGroupingTests` cover the split and the gutter trace.
For a visible synthetic reassembly demo, run
`.venv/bin/python -m tests.test_ocr_pipeline --demo-reassembly rbnode`,
`compressor`, `small`, or `all` from `ocr_feature/`; this prints before/after
ordering from the same synthetic fixtures without invoking live OCR.

**Baseline — this is the measured win.** `evaluate_cer` on `samples/` (20
samples; re-verified after the banded work with the full 148-test Python suite
green): **clean_ws CER 0.099, clean WER 0.328, clean token accuracy 0.716**. The two-column split is what moved it: only
`green_writer10_B2_1.jpg` changed (its own CER 0.606 → 0.061), taking the
overall from the pre-split 0.126 down to 0.099. All 19 other samples stayed
single-column and unchanged. **This is a reading-order improvement, not a
recognition improvement** — the same characters, read in the right order. Keep
that distinction crisp at defense: 0.126 is the recognition-only fine-tune
number; 0.099 is end-to-end after reading-order handling.

**Real-photo findings (2026-09-10).** Real handwriting photos *were* tested this
session (`reassemble_example*`, `isolate` through `isolate_6`, plus the 20
`samples/`). Outcome: the **two-column split fires and helps** on genuinely
two-column pages; the **brace-depth reassembly never fired on any real photo** —
misread braces break the block's depth math, exactly the risk the older draft of
this section flagged as unknown. So the reassembly stays in as a designed,
synthetic-tested, fail-safe path, but the demonstrable capability is the split.
Fuller trace: `docs/superpowers/specs/2026-09-10-displaced-region-tracking-design.md`
and `docs/ocr/READING_ORDER_REVIEW_VERIFICATION_2026-09-10.md`.

---

## 4. `main.py` — the FastAPI surface, in full

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the OCR models on startup so the first real request is fast.
    warmup()
    yield


app = FastAPI(title="MaestrAI OCR Backend", lifespan=lifespan)
```

`lifespan` runs once when the server process starts, before any request is
accepted — this is where `warmup()` (§3.1) gets called, so the first real
user never pays that latency.

> **Added 2026-09-24 (pre-extraction):** `main.py` now has `extract_image_url()`: download, then OCR in a temporary folder. The endpoint and the auto-extract worker share it, so both produce identical text. The `lifespan` hook starts `core/auto_extract.py`'s worker when `AUTO_EXTRACT=true` and stops it on shutdown. The worker's pure logic (`run_once`) takes a store and an extract function, so it is tested with fakes (`tests/test_auto_extract.py`). `SupabaseStore` only reads unread papers captured since a start date and saves with a PATCH filtered on `extracted_text`/`verified_text` still empty.
>
> **Changed 2026-09-24 (code review):** the snippets in this section are the pre-review `main.py`. Each endpoint now works in a `tempfile.TemporaryDirectory` that is deleted afterwards, so there's no `UPLOAD_DIR`, client file names and `submission_id` never become paths, and photos and debug JSON aren't kept. `download_image` requires http(s) and caps the body at 25 MB (`DOWNLOAD_MAX_BYTES`). `extract_from_upload` is a plain `def`, so it runs in the threadpool. CORS no longer allows credentials. In `ocr_pipeline.py`, `_ocr_lock` serializes `ocr.predict`. In `c_code_cleanup.py`, fixes whose misread starts with a digit (`1f`, `1nt`, `1nclude`) only apply after whitespace, `{`, `}`, `;`, `(` or `,`, so float literals like `1.1f` are left alone.


```python
@app.post("/api/ocr/extract-upload")
async def extract_from_upload(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    file_path = UPLOAD_DIR / file.filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = extract_text_from_image(str(file_path))

    return {
        "raw_text": result["raw_text"],
        "cleaned_text": result["cleaned_text"],
        "average_confidence": result["average_confidence"],
    }
```

Direct file-upload endpoint. Note the return dict is hand-picked from
`result` — internal/debug fields (like anything only present in the `debug`
dict from §3.6) never cross this boundary even if present on `result`.

```python
DOWNLOAD_CONNECT_TIMEOUT = 15   # seconds to establish the connection
DOWNLOAD_READ_TIMEOUT = 120     # seconds to finish reading the body
DOWNLOAD_RETRIES = 3


def download_image(url: str, dest: Path) -> None:
    """Download an image to `dest`, retrying on network errors. Raises
    HTTPException(400) if all attempts fail."""
    last_error = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            with requests.get(
                url,
                timeout=(DOWNLOAD_CONNECT_TIMEOUT, DOWNLOAD_READ_TIMEOUT),
                stream=True,
            ) as response:
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to download image URL (HTTP {response.status_code}).",
                    )
                with dest.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            return
        except HTTPException:
            # A non-200 status is not a transient error; don't retry it.
            raise
        except requests.RequestException as exc:
            # Network/timeout error: worth retrying.
            last_error = exc

    raise HTTPException(
        status_code=400,
        detail=f"Failed to download image after {DOWNLOAD_RETRIES} attempts: {last_error}",
    )


@app.post("/api/ocr/extract-from-url")
def extract_from_url(request: ImageUrlRequest):

    image_path = UPLOAD_DIR / f"{request.submission_id}.jpg"

    download_image(request.image_url, image_path)

    result = extract_text_from_image(str(image_path))

    return {
        "submission_id": request.submission_id,
        "raw_text": result["raw_text"],
        "cleaned_text": result["cleaned_text"],
        "average_confidence": result["average_confidence"],
        "saved_to_db": False,
    }
```

This is the endpoint the web app actually calls (images live in Supabase
storage, referenced by URL, not uploaded directly). **Why timeout is split
into connect (15s) vs read (120s), and why retries are conditional:** mobile
captures run 3–5MB; a single flat timeout can fail purely from slow transfer
of a legitimately large file, not because anything's wrong. Splitting the
timeout means a slow *connection* still fails fast, while a slow *transfer*
gets real room. The `except HTTPException: raise` before the
`except requests.RequestException` branch is deliberate ordering — a non-200
status is re-raised immediately without consuming a retry, since retrying a
genuine 404 three times just delays telling the caller it's broken; only
actual network-level exceptions get retried.

**`saved_to_db: False`, always:** this backend never writes to Supabase.
Extraction ends at "here's the text" — the web app is what writes the
teacher's *verified* text after human review. This is a structural
enforcement of "OCR is an assistant, never the authority," not just a
convention — this service simply has no write path to grading data.

---

## 5. `core/c_code_cleanup.py` — closed-vocabulary keyword fixes

### 5.1 `core/c_code_cleanup.py` — the full file, annotated in place

```python
import re

# Known OCR misread -> correct C token. Whole-token, case-sensitive. Keep this
# list small and obvious -- every entry should be defensible on its own.
FIXES = {

    # types
    "1nt": "int",
    "vo1d": "void",
    "cnar": "char",
    "f1oat": "float",
    "doub1e": "double",

    # keywords / control flow
    "1f": "if",
    "e1se": "else",
    "wh1le": "while",
    "f0r": "for",
    "retvrn": "return",
    "s1zeof": "sizeof",
    "swltch": "switch",
    "struc t": "struct",
    "cont1nue": "continue",

    # functions / headers
    "ma1n": "main",
    "pr1ntf": "printf",
    "1nclude": "include",
    "#inc1ude": "#include",
    "std1o": "stdio",
    "stdlo": "stdio",
    "std1ib": "stdlib",
}

# C_LITERAL (imported from core/c_literals.py) matches a full string literal
# "..." or char literal '...' so we can shield their contents from replacement.

# Standard headers are a small closed set, so an #include line is safe to
# normalize even when OCR mangles the extension ('.h' -> '.n') or the closing
# '>' (often read as '7') -- only a line that already looks like an #include
# with a known header gets touched. A stray '7' or '>' elsewhere is left
# alone since it could be real content.
_KNOWN_HEADERS = ("stdio", "stdlib", "stddef", "string", "math", "ctype", "time")
# '#' is optional in the pattern: OCR sometimes drops it, but "include
# <stdio.h>" is still unambiguous, so it gets added back.
_INCLUDE_LINE = re.compile(
    r"^\s*#?\s*[Ii]nclude\s*<\s*(" + "|".join(_KNOWN_HEADERS) + r")\b.*$"
)


def _fix_include_line(line: str) -> str:
    """Snap a recognizable but garbled #include line to its canonical form."""
    match = _INCLUDE_LINE.match(line)
    if match:
        return f"#include <{match.group(1)}.h>"
    return line


def _fix_segment(segment: str) -> str:
    """Apply whole-token keyword fixes to a chunk that has no string literals."""
    for wrong, right in FIXES.items():
        # \b won't help around '#', so match the token bounded by non-word chars.
        pattern = r"(?<![\w#])" + re.escape(wrong) + r"(?![\w])"
        segment = re.sub(pattern, right, segment)
    return segment


def clean_c_code(text: str) -> str:
    """
    Return a lightly cleaned copy of `text`: known #include lines are snapped to
    canonical form and garbled C keywords are corrected. String/char literals
    are left exactly as extracted.
    """
    if not text:
        return text

    # 1) Keyword pass, shielding string/char literals from replacement.
    out = []
    last = 0
    for match in C_LITERAL.finditer(text):
        # Fix the code between literals, then re-attach the literal untouched.
        out.append(_fix_segment(text[last:match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(_fix_segment(text[last:]))
    fixed = "".join(out)

    # 2) Then normalize #include lines. Running this after the keyword pass means
    # a header already corrected to a known name (e.g. std1o -> stdio) is now
    # recognized and snapped to its canonical "#include <stdio.h>" form.
    return "\n".join(_fix_include_line(line) for line in fixed.split("\n"))
```

**Step 1 — literal shielding is the safety-critical piece.** `clean_c_code()`
splits the text on `C_LITERAL` matches and only runs `_fix_segment()` on the
code *between* literals — literal contents are re-attached verbatim, never
passed through the fixer. This means a keyword lookalike written *inside* a
string (say a student's `printf("f0r loop")`) is never touched, because
`f0r`→`for` never even sees inside the quotes.

**Step 2 — whole-token matching, not substring matching.**
`r"(?<![\w#])" + re.escape(wrong) + r"(?![\w])"` bounds each fix on both
sides by non-word characters — a plain `\b` doesn't correctly bound around
`#`, hence the explicit negative lookbehind covering it too. This is what
stops `wh1le` from matching inside a longer identifier like
`mywh1lecounter`.

**Step 3 — `#include` normalization runs *after* the keyword pass, on
purpose.** A header typo the keyword pass just fixed (`std1o`→`stdio`) is
then recognized by `_INCLUDE_LINE` and snapped to the fully canonical
`#include <stdio.h>` — including fixing a mangled extension or a mangled
closing `>` (often misread as `7`). This only fires on a line that already
matches the include-statement shape referencing one of `_KNOWN_HEADERS`; a
stray `7` or `>` anywhere else in the code is left alone.

**If you add an entry to `FIXES`:** it must be independently defensible as
*unambiguous* — could this string plausibly be a variable name or literal
content a student actually typed? If there's any doubt, leave it uncorrected
rather than adding it — `FIXES` only takes fixes safe to auto-apply
unconditionally.

**If you remove the literal-shielding step:** immediate correctness bug — any
`FIXES`-dict lookalike inside a string/char literal gets silently rewritten,
so the "cleaned" text stops matching what the student actually wrote inside
their own string constants. This kind of regression can pass casual testing
(most test inputs don't happen to put `1nt` inside a string) and only
surface later as a real grading error. See §10.13 for the exact before/after
and test command.

---

## 6. `recognition_consensus.py` — REMOVED 2026-08-04

This file (and its evaluator `evaluators/evaluate_raw_consensus.py` and tests)
**no longer exists.** It implemented the rejected raw-OCR consensus experiment:
generate two `±0.5°` rotated views of the preprocessed image, run the same model
over each, and select whole lines where the rotations agreed. It was deleted
because it never ran in production, could not be re-measured (its evaluator was
already gone), and its net effect on CER was noise while it sometimes corrupted
correct C keywords.

**The finding is preserved, not lost.** The full record — measured numbers,
the decision, and the root-cause analysis (rotations of the *same* image scored
by the *same* model are correlated readers, so their agreement is not independent
evidence) — lives in [`RAW_OCR_CONSENSUS_HANDOFF.md`](RAW_OCR_CONSENSUS_HANDOFF.md).
Any future second-opinion idea would need a genuinely independent source (a
different model or a language prior), which would be new code, not a revival.

---

## 7. `evaluators/evaluation.py` — how accuracy claims are actually produced

### 7.1 The provenance gate — the actual code enforcing "never trust an unverified label"

```python
LITERAL_VERIFICATION_VALUE = "true"
LITERAL_PROVENANCE_FIELDS = (
    "literal_verified_by",
    "literal_verified_at",
)


def literal_provenance_issues(rows: list[dict]) -> list[str]:
    """Return failures in human source-paper transcription provenance."""
    issues = []
    for row_number, row in enumerate(rows, 2):
        filename = str(row.get("filename") or "").strip()
        row_name = filename or f"row {row_number}"
        literal_verified = str(row.get("literal_verified") or "").strip()
        if literal_verified.casefold() != LITERAL_VERIFICATION_VALUE:
            issues.append(
                f"{row_name}: literal_verified must be true; this confirms "
                "a human transcription from the source paper"
            )
        for field in LITERAL_PROVENANCE_FIELDS:
            if not str(row.get(field) or "").strip():
                issues.append(
                    f"{row_name}: {field} is required for auditable human "
                    "source-paper transcription"
                )
    return issues
```

And how `evaluators/evaluate_cer.py` uses it — **before** importing
`ocr_pipeline` at all:

```python
def _load_extractor():
    """Import the model-owning OCR pipeline only after label preflight."""
    from core.ocr_pipeline import extract_text_from_image
    return extract_text_from_image


def main() -> int:
    ...
    with LABELS_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ...
    provenance_issues = literal_provenance_issues(rows)
    if provenance_issues:
        print("Ground-truth provenance is incomplete:")
        for issue in provenance_issues:
            print(f"  {issue}")
        return 1

    extract = _load_extractor()   # model load only happens here, after the gate passes
```

A `labels.csv` row without `literal_verified == "true"` plus non-empty
`literal_verified_by` and `literal_verified_at` fails the run **before the
slow model even loads** (`_load_extractor()` is only called after the gate
passes — note the model import is deferred *inside* that function
specifically so it can't happen earlier). This is the concrete enforcement
mechanism behind the project's hard rule against citing unverified labels —
this exact function is what forced the labels.csv provenance backfill this
session (all 13 rows carrying `John Cale Nombrado` / `2026-08-03`) before any
CER number could be called citable again.

**If you weaken this check:** directly reopens the failure this project
already lived through once — citing a CER number against labels that turned
out unverified (the retracted `.181`-era claims in `PIPELINE.md`). Treat this
as a hard gate, not a warning to be relaxed for convenience. See §10.14 for
the exact before/after and how to see the failure this guards against.

### 7.2 CER math

```python
def edit_distance(a: str, b: str) -> int:
    """Return the Levenshtein edit distance between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for row_number, left_char in enumerate(a, 1):
        current = [row_number]
        for column_number, right_char in enumerate(b, 1):
            current.append(min(
                previous[column_number] + 1,
                current[column_number - 1] + 1,
                previous[column_number - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def cer(prediction: str, reference: str) -> float:
    """Return character error rate relative to the reference length."""
    if not reference:
        return 0.0 if not prediction else 1.0
    return edit_distance(prediction, reference) / len(reference)


def normalize_ws(text: str) -> str:
    """Collapse whitespace so recognition can be scored without formatting."""
    return " ".join(text.split())


def evaluate_text_pair(
    raw: str,
    cleaned: str,
    reference: str,
) -> dict[str, float]:
    """Return the four CER metrics used by the project."""
    normalized_reference = normalize_ws(reference)
    return {
        "raw": cer(raw, reference),
        "clean": cer(cleaned, reference),
        "raw_ws": cer(normalize_ws(raw), normalized_reference),
        "clean_ws": cer(normalize_ws(cleaned), normalized_reference),
    }
```

Standard O(n·m) Levenshtein DP for `edit_distance()`. `cer()` divides by
reference length with explicit zero-reference handling (empty reference +
empty prediction = 0.0; empty reference + nonempty prediction = 1.0,
avoiding a `ZeroDivisionError` while still scoring it maximally wrong).
`normalize_ws()` is what separates `raw`/`clean` from `raw_ws`/`clean_ws` —
whitespace-normalized scoring isolates *recognition* errors from
*formatting* differences, on the reasoning that the teacher reformats text
anyway before grading. **This is why `clean_ws` — not `raw` or `clean` — is
the number cited everywhere as "the baseline":** it most directly answers
"how often does the recognizer get characters wrong," without a formatting
confound that isn't the OCR's fault.

`edit_operations()` (not reproduced in full here — same DP table, but
backtracked to classify each edit as insertion/deletion/substitution rather
than just counted) is what produced the finding recorded in project memory
that braces (`{`, `}`) account for a disproportionate share of deletions —
only visible because errors are classified by *type*, not just totaled.

### 7.3 The "perfect score is suspicious" warning

From `evaluators/evaluate_cer.py`:

```python
        if raw == truth:
            exact_matches.append(f"{fname} (raw)")
        if clean == truth:
            exact_matches.append(f"{fname} (cleaned)")
    ...
    if exact_matches:
        print("\nWARNING: exact prediction/reference matches require "
              "ground-truth revalidation:")
        for match in exact_matches:
            print(f"  {match}")
```

An exact match between OCR output and ground truth triggers a *warning*, not
celebration. **Why a good result is treated with suspicion:** an exact match
is statistically the signature of the exact contamination bug this project
already hit once — Supabase `verified_text` that turned out to be unedited
OCR output saved back unchanged, producing a meaningless "0 CER" that
measured nothing real. A perfect match on a row independently, physically
verified is fine; but the script can't distinguish that from the
contamination pattern automatically, so it flags every instance and leaves
the judgment to a human rather than silently trusting a suspiciously perfect
number.

### 7.4 `run_tests.py` — why not plain `unittest discover`

```python
def main() -> int:
    verbosity = 2 if "-v" in sys.argv else 1
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", top_level_dir=".")
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1
```

Tests in `tests/` import project modules through their packages (`from
core.ocr_pipeline import ...`, `from evaluators.evaluation import ...`), which
only resolves if Python's notion of "top level" is `ocr_feature/` itself —
so the `core` and `evaluators` packages are importable. `top_level_dir="."` is
what makes `discover()` add `ocr_feature/` — not `ocr_feature/tests/` — to the
import path. Running plain `python -m unittest discover -s tests` from
`ocr_feature/` finds the test files but fails to import the `core.*` modules
correctly without this explicit argument. (The test that loads the pipeline
without models stubs `core`, `core.preprocess`, etc. into `sys.modules` — so if
you rename the package, that stub map has to move with it.)

---

## 8. `evaluators/export_dataset.py` — the contamination guard, in full

> **2026-09-27:** the guard still compares the exported text with
> `extracted_text`; for a split page that is the programs joined by a blank
> line, so a page split without any correction is set aside like any other
> unedited page. Where the text comes from (`submission_programs`, split pages,
> `program_blocks`) is summarized in section 1.

```python
def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace so formatting-only edits compare equally."""
    return " ".join(text.split())


def is_suspected_unedited(row: dict) -> bool:
    """Return whether verified text appears to be saved OCR output."""
    verified = normalize_whitespace(row.get("verified_text") or "")
    extracted = normalize_whitespace(row.get("extracted_text") or "")
    if not verified or not extracted:
        return False

    # This heuristic cannot catch every contamination case (for example, a
    # wrong-program label). It only catches the "saved without editing" pattern,
    # which accounted for the majority of the known contaminated rows.
    return verified == extracted
```

And how it's used during export:

```python
    for row in rows:
        text = (row.get("verified_text") or "").strip()
        image_url = row.get("image_url") or ""
        if not text or not image_url:
            print(f"  skip {row.get('id')}: missing verified_text or image_url")
            skipped += 1
            continue
        if is_suspected_unedited(row):
            suspected_unedited_ids.append(str(row.get("id")))
            skipped += 1
            continue
        dest = IMAGES_DIR / f"{row['id']}.jpg"
        if not download_image(image_url, dest):
            print(f"  skip {row.get('id')}: image download failed")
            skipped += 1
            continue
        exported.append(row)
```

If a submission's `verified_text` (what the teacher supposedly confirmed) is
whitespace-identical to `extracted_text` (the OCR's own raw output), the row
is quarantined — skipped, its ID collected into a warning list — because a
teacher clicking "save" without editing anything is, from stored data alone,
indistinguishable between "the OCR was perfect" and "the teacher didn't
actually check it." This exact pattern is what contaminated the project's
Supabase data once already; this function is the permanent fix.

**Explicitly stated limitation, in the module docstring:** this only catches
the "saved unedited" pattern — not a *wrong-program* label (edited, but to
describe a different submission), and not a case where `extracted_text`
itself was already overwritten by a since-fixed save-path bug (nothing left
to compare against). This is exactly why exported pairs still need an
explicit human review/provenance signal before being trusted at volume,
rather than treating this guard as sufficient on its own.

```python
    duplicates = Counter(
        normalize_whitespace(row["verified_text"]) for row in exported)
    duplicate_groups = {t: n for t, n in duplicates.items() if n > 1}
    ...
    if duplicate_groups:
        print(f"WARNING: {len(duplicate_groups)} verified text(s) appear on "
              f"multiple submissions (likely re-captures of the same page). "
              f"Keep such groups on the same side of any train/test split.")
```

Flags submissions whose verified text matches another's — likely re-captures
of the same physical page. Matters for a future train/test split: if the
same page's two photos land on opposite sides of a split, the model would
effectively be evaluated on data resembling what it trained on, inflating
apparent accuracy. The script only *flags* this — the actual split decision
is deliberately left to training time, not export time.

**Update (2026-09-06): the write is now merge-preserving, and two provenance
columns exist.** Before this date, `export_dataset.py` and
`import_verified_batch.py` both opened `labels.csv` in truncating write
mode — each wrote *only its own rows*, so running one after the other
silently destroyed whichever rows the other script had written (discovered
while designing this fix, not by a reported bug). Both scripts now go
through a shared `evaluators/labels_schema.py`:

```python
_WRITER_BATCH_ID = re.compile(r"^(bond|green|yellow)_writer\d+")

def is_writer_batch_id(submission_id: str) -> bool:
    return bool(_WRITER_BATCH_ID.match(submission_id))
```

`export_dataset.py` loads whatever's currently on disk, keeps every
writer-batch-shaped row untouched, and only rebuilds its own Supabase-UUID
rows:

```python
    existing = load_existing_rows(LABELS_CSV)
    preserved = {
        sid: row for sid, row in existing.items() if is_writer_batch_id(sid)
    }
    own_new = {...}  # built from `exported`, keyed by Supabase id
    merged = {**preserved, **own_new}
    write_labels_csv(LABELS_CSV, merged)
```

`import_verified_batch.py` does the mirror image — preserves every
non-writer-batch (Supabase) row, rebuilds only its own writer-batch rows.

Regarding the "still needs an explicit human review/provenance signal"
limitation named just above: the signal now exists as three new columns —
`literal_verified`, `literal_verified_by`, `literal_verified_at` — populated
by `import_verified_batch.py`'s new required `--verified-by` flag for
physically-verified rows, left blank for Supabase-sourced rows (no per-row
physical check exists in that path). **This is deliberately informational,
not a new gate:** `is_suspected_unedited()` above is still the only thing
that blocks a row from export. Requiring the new signal during export was
considered and rejected while designing this — it would conflict with the
project's active push to bloat the bond/yellow dataset, where blocking on
provenance would throttle collection rather than measure it. A fourth
column, `correction_edit_distance` (character-level edit distance between
`extracted_text` and `verified_text` after whitespace normalization, via
the same `edit_distance()` used for CER), is computed for every exported
Supabase-sourced row, giving per-row visibility into how much a
"not flagged by the equality guard" row was actually edited — a one-character
fix and a full rewrite no longer look identical downstream. Design doc:
`docs/superpowers/specs/2026-09-06-training-data-provenance-design.md`.
Real numbers from the first run under this code: `ocr/DEFENSE_PREP.md` §7
appendix (2026-09-06).

---

## 9. Cross-cutting patterns worth naming explicitly

**"Fail closed to the untouched input, not to an error."** Reading-order
grouping falls back to original order on bad geometry (§3.3);
debug-artifact writing is wrapped in a silent `try/except` (§3.6). In every
case the failure mode is "do less, using data already trusted," never
"guess" or "crash" — appropriate for a grading tool, where a missed fix is
recoverable (human sees raw text) but a wrong "fix" silently misrepresents
the student.

**"Measure per-subgroup, not just overall."** `summarize_metrics()` grouping
by `paper_type` and `writer` (§7.4); the `adaptive_denoise`/
`threshold_block_scale` tuning both validated "best on every subgroup," not
just on average. This repeats because an average can hide one subgroup
getting much better while another gets worse, and a 2-writer/2-paper-type
cohort is small enough that a subgroup regression would otherwise be
invisible.

**"Everything expensive is parameterized, but defaults never silently
change."** `PreprocessConfig`, `RecognitionConfig` — both frozen dataclasses
whose defaults reproduce known-good current behavior. This is what let this
project run so many sweeps (model pairing, denoise strength, threshold
scale, floor value) safely — each experiment constructs its own config
object instead of mutating shared state.

**"Never let recognized/graded content be silently rewritten."** The
literal-shielding regex lives once as `C_LITERAL` in `core/c_literals.py`,
imported by `c_code_cleanup.py` so the auto-fixer never touches string/char
literal contents. Reading-order grouping never touches characters. This is
the "grading app" constraint from §1, showing up as a structural pattern
across files rather than a single rule stated once.

---

## 10. If you're about to change something — exact before/after code, and how to test it

Each entry below names the **exact file and line**, shows the **literal
current code**, shows what an **actual edit** looks like, gives the **exact
command** to run afterward, and says what the **output tells you**. Copy the
"after" block over the "before" block — nothing here is abbreviated with
`...`.

**One command, three metrics.** `python -m evaluators.evaluate_cer` prints
CER, WER, and token-level recognition accuracy together in a single run
(§6/§10's evaluate_cer entries) — it's one command, not three. When an entry
below says to "check CER" or "compare the baseline," read the whole printed
table: WER and token accuracy are scored differently (WER fails a whole word
on one wrong character; token accuracy is scored on C-lexical tokens, not
characters) and can move even when CER doesn't. Always check all three
columns before deciding a change is safe, not just `clean_ws`.

### 10.1 Swap the OCR model

**File:** `ocr_feature/core/ocr_pipeline.py`, the `ocr = PaddleOCR(...)`
constructor near the top of the file (below the `_FINE_TUNED_REC_DIR` setup;
line numbers shift as comments are edited, so match on the call, not a line).

**Before (current):**

```python
ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_dir=_FINE_TUNED_REC_DIR,  # fine-tuned, required
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_det_box_thresh=0.30,   # lowered from 0.60 to recover braces (§3.1)
    device="cpu"
)
```

Note two things that changed since this section was first written: (1) the
**recognizer is now the fine-tuned model**, pointed at by
`text_recognition_model_dir=_FINE_TUNED_REC_DIR` (a local inference dir),
**not** a stock `text_recognition_model_name`. To swap the *recognizer*, point
that dir elsewhere — or, for a throwaway experiment, set the
`MAISTRA_REC_MODEL_DIR` env var (read at the top of the file) instead of
editing source. (2) `text_det_box_thresh=0.30` was added (detection
sensitivity; see the box_thresh note in §3). The detector is still swapped by
name, as the example below shows.

**After — example: reverting to the stock v5 pair** (detector *and* a stock
recognizer name — this exact pairing was already tried and scored 0.279,
*worse*; shown to demonstrate the name-based swap mechanics, not as a
recommendation, and note it also throws away the fine-tuned recognizer):

```python
ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_server_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    device="cpu"
)
```

**Yes — it really is just changing the two string values.** `PaddleOCR`
resolves both `text_detection_model_name` and `text_recognition_model_name`
independently by name, so you can mix and match detector/recognizer pairs
freely (that's exactly how the four-way sweep in the comment above this
block was produced — same detector, different recognizer, and vice versa).
The valid names for this project's testing so far: `PP-OCRv6_medium_det`,
`PP-OCRv6_medium_rec`, `PP-OCRv5_mobile_det`, `en_PP-OCRv5_mobile_rec`,
`PP-OCRv5_server_det`, `PP-OCRv5_server_rec`.

**One thing you must NOT do — pass only a detector name and expect a
sensible default recognizer:**

```python
# WRONG — do not do this:
ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    lang="en",              # <- silently ignored once a model name is set
    device="cpu"
)
```

The comment at the top of the file states why: passing a model name makes
PaddleOCR silently ignore `lang`/`ocr_version`, so you'd get whatever
recognizer PaddleOCR defaults to internally — not necessarily the one you
think `lang="en"` implies. Always pin **both** names explicitly.

**After editing, restart anything holding the old model in memory** — the
`ocr = PaddleOCR(...)` call runs once at **import time** (§3.1), so a running
`uvicorn`/FastAPI process or an already-imported Python session will keep
using the old model until restarted.

**Test it — run the CER sweep, not just "does it start":**

```bash
cd ocr_feature
python -m evaluators.evaluate_cer
```

Expect output shaped like this (column meanings are printed at the bottom of
the real output too):

```
Evaluating 13 sample(s)...

file                       raw   clean  raw_ws  clean_ws
--------------------------------------------------------------
nikko_001_array_loop.jpeg 0.185   0.171   0.162     0.148
...
--------------------------------------------------------------
AVERAGE CER               0.201   0.189   0.176     0.148

BY PAPER TYPE
group                          raw   clean  raw_ws  clean_ws
--------------------------------------------------------------
bond                          0.190   0.178   0.165     0.140
greenbook                     0.230   0.215   0.201     0.181

BY WRITER
group                          raw   clean  raw_ws  clean_ws
--------------------------------------------------------------
nikko                         0.195   0.183   0.170     0.145
nombrado                      0.207   0.195   0.182     0.151
```

(Numbers above are illustrative of the *shape* of real output, not a live
result of the example swap — run it yourself to get real numbers.) **The
number that matters is `AVERAGE CER` → `clean_ws` column, plus every row
under `BY PAPER TYPE` and `BY WRITER`.** Compare all of them — not just the
overall average — against the current baseline (`clean_ws 0.149` over 14
gate-framed samples, 2026-08-06 — see EVALUATION.md's top banner; the quoted
sample output above is illustrative only, from before this baseline existed)
before deciding to keep a model swap. If the script instead prints:

```
Ground-truth provenance is incomplete:
  ...
```

that means `samples/labels.csv` failed the provenance gate (§7.1) — this is
unrelated to the model change itself and must be fixed first (every row
needs `literal_verified=true` plus both provenance fields).

**If you want to also update the pinning comment** (recommended, so a future
reader doesn't trust a stale sweep table), edit the block of comments
directly above the `ocr = PaddleOCR(...)` call — replace the four-row sweep
table and the "Cost of this change" line with your new sweep's numbers.

---

### 10.2 Change the confidence floor (`REC_SCORE_FLOOR`)

**File:** `ocr_feature/core/ocr_pipeline.py`, line 132 (match on the
`REC_SCORE_FLOOR =` assignment, not the exact line — it shifts as comments change).

**Before:**

```python
REC_SCORE_FLOOR = 0.3
```

**After — example, raising it to be stricter:**

```python
REC_SCORE_FLOOR = 0.45
```

That is the entire code change — `_filter_low_confidence()` (§3.2) reads
this module-level constant at call time, so nothing else needs editing.

**Test it — before/after CER, and inspect what got dropped:**

```bash
cd ocr_feature
python -m evaluators.evaluate_cer
```

Then look at what the floor actually removed on one specific page, by
opening its debug artifact (regenerated on every extraction call the
evaluator makes):

```bash
cat outputs/debug/nikko_001_array_loop_preprocessed.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for d in data['dropped_low_confidence']:
    print(d['score'], repr(d['text']))
"
```

Example output:

```
0.127 '2'
0.294 '↓'
```

If `clean_ws` gets **worse** after raising the floor, check whether real
characters (not just noise) started appearing in `dropped_low_confidence` —
that's the deletion failure mode described in §3.2 (missing text is worse
than a wrong-but-visible character in a grading app).

---

### 10.3 Change denoise strength for textured paper

**File:** `ocr_feature/core/preprocess.py`, lines 61–63, inside `PreprocessConfig`.

**Before:**

```python
    adaptive_denoise: bool = True
    textured_paper_threshold: float = 2.2
    textured_denoise_strength: int = 20
```

**After — example, trying a gentler strength on textured paper:**

```python
    adaptive_denoise: bool = True
    textured_paper_threshold: float = 2.2
    textured_denoise_strength: int = 15
```

**Test it — must be checked per paper-type subgroup, not the overall
average**, because bond and greenbook were measured to respond in *opposite*
directions to this knob:

```bash
cd ocr_feature
python -m evaluators.evaluate_cer
```

Look specifically at the `BY PAPER TYPE` block in the output — compare the
`greenbook` row and the `bond` row separately against the current baseline
(`bond` should stay essentially unaffected since it's below
`textured_paper_threshold` and never uses this constant; `greenbook` is the
one this constant actually controls).

**If you want to test the threshold itself** (which images get the stronger
strength at all) instead of the strength value:

**Before:**

```python
    textured_paper_threshold: float = 2.2
```

**After — example, lowering it so more borderline pages qualify:**

```python
    textured_paper_threshold: float = 1.8
```

Same test command; same requirement to check both subgroups, because
lowering this threshold pulls some bond pages onto the stronger denoise too.

---

### 10.4 Change how the threshold block adapts to handwriting size

**File:** `ocr_feature/core/preprocess.py`, line 40, inside `PreprocessConfig`.

**Before:**

```python
    threshold_block_scale: float | None = 1.5
```

**After — example, trying a larger multiplier:**

```python
    threshold_block_scale: float | None = 2.0
```

**After — example, turning it off entirely (back to a fixed block size):**

```python
    threshold_block_scale: float | None = None
```

When set to `None`, `preprocess_image()`'s branch
(`if config.threshold_block_scale is not None:`) is skipped entirely, and
`block_size` stays at whatever `threshold_block_size` is set to (default
`31`) for every page — this was the pre-2026-08-02 behavior, measured worse
(0.223 vs 0.198 CER on this cohort).

**Test it:**

```bash
cd ocr_feature
python -m evaluators.evaluate_cer
```

Check `BY WRITER` and `BY PAPER TYPE` both — the original tuning's claim was
specifically "best on every subgroup," which is a stronger bar than "better
on average." Also re-confirm `_median_glyph_height()` is still being called
on `processed` (the post-denoise variable) in `preprocess_image()` — this
change doesn't touch that call, but if you're editing nearby code, don't
accidentally move it earlier:

```python
    processed = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if config.denoise:
        ...
        processed = cv2.fastNlMeansDenoising(...)   # <- denoise happens first
    if config.threshold:
        block_size = config.threshold_block_size
        if config.threshold_block_scale is not None:
            glyph = _median_glyph_height(processed)  # <- measured on denoised `processed`, correctly
```

---

### 10.5 Add a "safe to auto-fix" keyword

**File:** `ocr_feature/core/c_code_cleanup.py`, lines 5–33, the `FIXES` dict.

**Before (excerpt):**

```python
FIXES = {

    # types
    "1nt": "int",
    "vo1d": "void",
    "cnar": "char",
    "f1oat": "float",
    "doub1e": "double",

    # keywords / control flow
    "1f": "if",
    "e1se": "else",
    "wh1le": "while",
    "f0r": "for",
    "retvrn": "return",
    "s1zeof": "sizeof",
    "swltch": "switch",
    "struc t": "struct",
    "cont1nue": "continue",

    # functions / headers
    "ma1n": "main",
    "pr1ntf": "printf",
    "1nclude": "include",
    "#inc1ude": "#include",
    "std1o": "stdio",
    "stdlo": "stdio",
    "std1ib": "stdlib",
}
```

**After — example, adding a new observed misread (`brea k` → `break`):**

```python
FIXES = {

    # types
    "1nt": "int",
    "vo1d": "void",
    "cnar": "char",
    "f1oat": "float",
    "doub1e": "double",

    # keywords / control flow
    "1f": "if",
    "e1se": "else",
    "wh1le": "while",
    "f0r": "for",
    "retvrn": "return",
    "s1zeof": "sizeof",
    "swltch": "switch",
    "struc t": "struct",
    "cont1nue": "continue",
    "brea k": "break",

    # functions / headers
    "ma1n": "main",
    "pr1ntf": "printf",
    "1nclude": "include",
    "#inc1ude": "#include",
    "std1o": "stdio",
    "stdlo": "stdio",
    "std1ib": "stdlib",
}
```

That's it — one new key/value pair. `_fix_segment()` (§5.1) iterates
`FIXES.items()` and builds the bounded regex automatically for every entry,
so nothing else in the file needs to change.

**Before adding an entry, ask the safety question explicitly:** could
`"brea k"` (the wrong-side string) plausibly appear as legitimate content a
student typed — inside a string literal, as part of a variable name, etc.?
If there's real doubt, it does **not** belong here, and there is no
lower-stakes "suggestion" table to fall back to on this branch — if a fix
is too risky for `FIXES`, the correct answer is to leave it un-corrected.

**Test it:**

```bash
cd ocr_feature
python run_tests.py -v
```

specifically look for `tests/test_c_code_cleanup.py` in the output — add a
test case there too if you're adding a new fix permanently:

```python
# in tests/test_c_code_cleanup.py, alongside the existing cases
def test_fixes_brea_k_to_break(self):
    self.assertEqual(clean_c_code("brea k;"), "break;")
```

Then re-run the full CER sweep to make sure the new fix doesn't collide with
real content anywhere in the labeled samples:

```bash
python -m evaluators.evaluate_cer
```

---

### 10.7 Change line-grouping tolerance (reading-order)

**File:** `ocr_feature/core/layout/` (the reading-order geometry moved here
from `ocr_pipeline.py` in the 2026-09-13 split — see §3). Match on the code:
the line-height tolerance is in `_group_detection_records` (`heights.sort()` /
`median_h` / `line_tol`, ~line 734), and the same-line overlap gate is
`MAX_SAME_LINE_X_OVERLAP` used in `_sweep_detection_records`.

**Before (the tolerance calculation):**

```python
    heights.sort()
    median_h = heights[len(heights) // 2] if heights else 0.0
    line_tol = max(median_h * 0.6, 1.0)
```

**After — example, making line-membership more permissive (more merging):**

```python
    heights.sort()
    median_h = heights[len(heights) // 2] if heights else 0.0
    line_tol = max(median_h * 0.9, 1.0)
```

**Before (the join condition using that tolerance):**

```python
            if (trend_delta <= line_tol
                    and (center_delta <= line_tol
                         or trend_delta <= line_tol * 0.5)):
                members.append(it)
                continue
```

**After — example, tightening how far a slanted trend can extend past the
mean-y band:**

```python
            if (trend_delta <= line_tol
                    and (center_delta <= line_tol
                         or trend_delta <= line_tol * 0.3)):
                members.append(it)
                continue
```

**Test it — there's no existing sweep script for this constant, so you have
to build the check yourself.** The most direct method: pick a page with
noticeably slanted handwriting, run extraction, and read the debug artifact's
grouped lines directly:

```bash
cd ocr_feature
PYTHONPATH=. python3 -c "
from core.ocr_pipeline import extract_text_from_image
result = extract_text_from_image('samples/nombrado_s02_two_numbers_raw.jpeg')
print(result['raw_text'])
"
```

Compare the printed `raw_text` line-by-line against what you can see in the
actual photo (`samples/nombrado_s02_two_numbers_raw.jpeg`) — specifically
check whether a genuinely separate row got merged into its neighbor (over-
merging, more likely if you raised `0.6`), or a single visual row got split
across two output lines (under-merging, more likely if you lowered it). Then
confirm the change didn't regress overall CER:

```bash
python -m evaluators.evaluate_cer
```

---

### 10.8 Add or verify a new dataset row

**File:** `ocr_feature/samples/labels.csv`. Header row (already present,
don't change it):

```
filename,ground_truth_text,writer,paper_type,capture_condition,literal_verified,literal_verified_by,literal_verified_at
```

**Before — adding a new row is invalid until every field is filled:**

```
newwriter_s09_swap_bond_raw.jpeg,"int main() {
	int a = 5;
	int b = 10;
	swap(&a, &b);
	return 0;
}",newwriter,bond,raw,,,
```

Running the evaluator against this incomplete row fails immediately:

```bash
cd ocr_feature
python -m evaluators.evaluate_cer
```

```
Ground-truth provenance is incomplete:
  newwriter_s09_swap_bond_raw.jpeg: literal_verified must be true; this confirms a human transcription from the source paper
  newwriter_s09_swap_bond_raw.jpeg: literal_verified_by is required for auditable human source-paper transcription
  newwriter_s09_swap_bond_raw.jpeg: literal_verified_at is required for auditable human source-paper transcription
```

**After — filled in only once a human has read the physical paper and typed
the text character-for-character** (never generated or verified by an AI
image read — see `[[ai-photo-reads-are-not-label-evidence]]` in project
memory):

```
newwriter_s09_swap_bond_raw.jpeg,"int main() {
	int a = 5;
	int b = 10;
	swap(&a, &b);
	return 0;
}",newwriter,bond,raw,true,John Cale Nombrado,2026-08-04
```

Now the same command passes the gate and actually runs extraction on the new
row alongside the existing 13.

---

### 10.9 Export more training data from Supabase

**File:** you don't edit `export_dataset.py` itself for a normal run — you
just run it. The command:

```bash
cd ocr_feature
python -m evaluators.export_dataset
```

Expected output shape (updated 2026-09-06 — now includes the merge summary
and provenance/correction-distance lines added alongside the overwrite fix;
see §8's update note and `ocr/DEFENSE_PREP.md` §7 appendix for real numbers):

```
Found 42 verified submission(s).
  skip a1b2c3d4: missing verified_text or image_url
Exported 38 pair(s) to datasets/verified/labels.csv (4 skipped).
labels.csv now contains 206 total row(s) (168 preserved, 38 from this run).
Provenance: 0/206 fully verified (literal_verified=true with verifier and date recorded).
Correction edit-distance (OCR-sourced rows only, n=38): mean 18.4, median 9.0, min 1, max 340.
WARNING: skipped submission(s) whose verified_text matches extracted_text after whitespace normalization: e5f6a7b8, c9d0e1f2
WARNING: 3 verified text(s) appear on multiple submissions (likely re-captures of the same page). Keep such groups on the same side of any train/test split.
```

The "preserved" count is the writer-batch rows already in `labels.csv` from
`import_verified_batch.py` — a re-run of `export_dataset.py` no longer wipes
them. The correction-distance line only appears when at least one
Supabase-sourced row survives this run's filters.

**If you need to change *which* rows are considered "verified" and
exportable** — for example, to also require a minimum text length before
export — that's a change to `fetch_verified_submissions()`'s query filter,
`ocr_feature/evaluators/export_dataset.py` lines 64–71:

**Before:**

```python
            params={
                "status": "eq.verified",
                "select": "id,image_url,extracted_text,verified_text,"
                          "verified_at,topic,student_name",
                "order": "verified_at.asc",
                "limit": str(PAGE_SIZE),
                "offset": str(offset),
            },
```

The Supabase REST filter syntax (`"status": "eq.verified"`) only supports
adding more `column: "op.value"` pairs here — there is no length filter
available server-side for `verified_text` through this simple params dict,
so a minimum-length rule has to be applied client-side instead, inside the
`main()` loop:

**Before (`main()`, the per-row export decision):**

```python
    for row in rows:
        text = (row.get("verified_text") or "").strip()
        image_url = row.get("image_url") or ""
        if not text or not image_url:
            print(f"  skip {row.get('id')}: missing verified_text or image_url")
            skipped += 1
            continue
        if is_suspected_unedited(row):
            suspected_unedited_ids.append(str(row.get("id")))
            skipped += 1
            continue
```

**After — example, also skipping suspiciously short verified text (under 20
characters, likely a partial/incomplete capture):**

```python
    for row in rows:
        text = (row.get("verified_text") or "").strip()
        image_url = row.get("image_url") or ""
        if not text or not image_url:
            print(f"  skip {row.get('id')}: missing verified_text or image_url")
            skipped += 1
            continue
        if len(text) < 20:
            print(f"  skip {row.get('id')}: verified_text too short ({len(text)} chars)")
            skipped += 1
            continue
        if is_suspected_unedited(row):
            suspected_unedited_ids.append(str(row.get("id")))
            skipped += 1
            continue
```

**Test it:**

```bash
python -m evaluators.export_dataset
```

Check the printed skip count and reasons match what you expect, then
manually spot-check a few rows in the resulting
`datasets/verified/labels.csv` against `datasets/verified/images/` before
trusting the export at volume — this script's contamination guard (§8)
catches one specific failure pattern, not every possible one.

---

### 10.10 Change the resize cap (`max_side`)

**File:** `ocr_feature/core/preprocess.py`, inside `PreprocessConfig`.

**Before:**

```python
    max_side: int = 1600
```

**After — example, lowering it:**

```python
    max_side: int = 1000
```

**Test it, and the actual confirmed result (2026-09-06):** `run_tests.py`
first (81/81 passes either way, confirmed — no dedicated unit test for this
constant), then the full sweep:

```bash
cd ocr_feature
python run_tests.py
python -m evaluators.evaluate_cer
```

**Measured:** lowering to `1000` genuinely worsens accuracy — `clean_ws`
`0.126` → `0.128` overall, and notably **bond nearly doubled**, `0.005` →
`0.010`, with yellow_pad also worse (`0.070` → `0.079`). This confirms the
prose warning above with a real number, not just a plausible-sounding
prediction — fine strokes on the smoothest paper type are exactly what
degrades first when resolution drops. Revert, re-run `run_tests.py`.

### 10.11 Change `threshold_c`

**File:** `ocr_feature/core/preprocess.py`, inside `PreprocessConfig`.

**Before:**

```python
    threshold_c: int = 15
```

**After — example, raising it:**

```python
    threshold_c: int = 25
```

**Same critical caveat as §10.7's Otsu comparison, verified by actually
running it there: `threshold_c` sits inside the same `if config.threshold:`
block, and `threshold` defaults to `False`.** Running `evaluate_cer` with
this changed and the rest of the config untouched produces a byte-identical
`clean_ws` — confirmed by the §10.7 test, since it's structurally the same
dead branch. Don't run the default `evaluate_cer` sweep expecting to see
anything; force `threshold=True` first, the same way §10.7 does, then
compare on a real image with `extract_text_from_image(path,
preprocess_config=PreprocessConfig(threshold=True, threshold_c=25))`.

**Test it:** `run_tests.py` first as a baseline — this constant has no
dedicated unit test (confirmed: it still passes 81/81 regardless of the
value), which is itself worth noting as a coverage gap. Then look at the
actual preprocessed image (not a metric number, which won't move under the
default config) for a page with faint handwriting or heavy shadow, and check
whether thin strokes vanished (raised value) or shadow/texture got misread
as ink (lowered value). Revert, re-run `run_tests.py` to confirm baseline.

### 10.12 Flip a `use_*` orientation/unwarp flag on

**File:** `ocr_feature/core/ocr_pipeline.py`, the `ocr = PaddleOCR(...)`
constructor (§10.1).

**Before:**

```python
ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_dir=_FINE_TUNED_REC_DIR,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_det_box_thresh=0.30,
    device="cpu"
)
```

**After — example, turning orientation classification back on:**

```python
ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_dir=_FINE_TUNED_REC_DIR,
    use_doc_orientation_classify=True,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_det_box_thresh=0.30,
    device="cpu"
)
```

**Test it, and an important discrepancy found by actually running it
(2026-09-06):**

```bash
cd ocr_feature
python run_tests.py
time python3 -c "
from core.ocr_pipeline import extract_text_from_image
extract_text_from_image('samples/bond/bond_writer1_1.jpg')
"
```
(note: `samples/nombrado_s02_two_numbers_raw.jpeg`, this doc's older example
path, no longer exists — samples are now organized under
`samples/<paper_type>/`, use a real path like the one above.)

**Measured result, does not match the ~81s-vs-a-few-seconds claim cited
elsewhere in this codebase (§3.1):** with all three flags flipped to `True`,
wall-clock time was `10.19s`, essentially identical to the baseline
`10.12s` with them `False` — re-run twice to rule out a one-time
model-download cost, same result both times (`10.16s`, `10.46s`). This is a
genuinely unresolved discrepancy, not a confirmed re-measurement of the old
number: it may reflect a different image, a different PaddleOCR version, or
different hardware at the time the ~81s figure was originally measured. Say
so honestly if asked live — "I measured no significant difference on this
machine just now, which doesn't match the ~81s figure cited elsewhere; that
gap is unresolved" is a stronger, more defensible answer than repeating an
unverified historical number. `run_tests.py` passes 81/81 regardless of the
flags. Also run `evaluate_cer` — this flag is off specifically because
captures are assumed already upright/flat (the quality gate's job), so an
accuracy check matters independent of the timing question. Revert, re-run
`run_tests.py`.

### 10.13 Remove the literal-shielding step (to see why it must stay)

**File:** `ocr_feature/core/c_code_cleanup.py`, `clean_c_code()`.

**Before:**

```python
    out = []
    last = 0
    for match in C_LITERAL.finditer(text):
        out.append(_fix_segment(text[last:match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(_fix_segment(text[last:]))
    fixed = "".join(out)
```

**After — unshielded (do not ship this):**

```python
    fixed = _fix_segment(text)
```

**Test it:** `run_tests.py` first — `test_c_code_cleanup.py` has a case
asserting `printf("1nt is a typo")` keeps its string literal untouched; the
unshielded version fails it immediately. Then confirm visually:

```bash
cd ocr_feature
PYTHONPATH=. python3 -c "
from core.c_code_cleanup import clean_c_code
print(clean_c_code('printf(\"1nt is a typo\");'))
"
```

Current code prints the string unchanged; the unshielded version prints
`printf("int is a typo");` — the exact grading-integrity violation the
shielding exists to prevent. Then run the full sweep for completeness:

```bash
python -m evaluators.evaluate_cer
```

Any sample whose ground truth has a `FIXES`-lookalike inside a string
literal would show up as a real CER regression here, not just in the
crafted one-liner above. Revert immediately after seeing it, re-run
`run_tests.py` to confirm baseline.

### 10.14 Weaken the literal-verification provenance gate (to see the failure it prevents)

**File:** `ocr_feature/evaluators/evaluation.py`, `literal_provenance_issues()`.

**Before:**

```python
        literal_verified = str(row.get("literal_verified") or "").strip()
        if literal_verified.casefold() != LITERAL_VERIFICATION_VALUE:
            issues.append(
                f"{row_name}: literal_verified must be true; this confirms "
                "a human transcription from the source paper"
            )
```

**After — weakened (do not ship this):**

```python
        # gate removed: any row is now accepted regardless of verification
        pass
```

**Test it, and the actual confirmed result (2026-09-06) — more robustly
covered than expected:** `run_tests.py` first — **4 tests fail, not just
one**: `test_literal_provenance_rejects_non_true_and_blank_audit_fields` in
`test_evaluation.py`, plus **three** dedicated tests in `test_evaluate_cer.py`
(`test_missing_literal_verification_rejects_before_ocr_import`,
`test_blank_literal_verification_rejects_before_ocr_import`,
`test_false_literal_verification_rejects_before_ocr_import`). This gate has
real, layered test coverage across two files — no `labels.csv` edit needed to
prove that. Then see the real-world consequence anyway, for the full
picture: temporarily set one `labels.csv` row's `literal_verified` to
`false` or blank, then run:

```bash
cd ocr_feature
python run_tests.py
python -m evaluators.evaluate_cer
```

With the gate intact, this refuses to run and prints the row as a
provenance issue. With it weakened, the evaluator proceeds and reports a CER
(and WER/token-accuracy) number computed against a reference nobody
confirmed matches the actual paper — which is exactly the failure mode that
produced the retracted `.181`-era claims. Revert the `labels.csv` edit and
the code change immediately after confirming the refusal, re-run
`run_tests.py`.

### 10.15 Revert the merge-preserving write (to see the overwrite bug it fixed)

**File:** `ocr_feature/evaluators/export_dataset.py`, `main()`'s CSV-writing
section. This is `datasets/verified/labels.csv` — the training set's
overwrite bug, not the evaluation-set provenance gate in 10.14 above (a
different file, a different problem).

**Before (current, merge-preserving):**

```python
    existing = load_existing_rows(LABELS_CSV)
    preserved = {
        sid: row for sid, row in existing.items() if is_writer_batch_id(sid)
    }
    own_new = {...}
    merged = {**preserved, **own_new}
    write_labels_csv(LABELS_CSV, merged)
```

**After — reverted to the pre-2026-09-06 truncating write (do not ship
this):**

```python
    with LABELS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "submission_id", "image_path", "verified_text",
            "extracted_text", "verified_at", "topic", "student_name",
        ])
        for row in exported:
            writer.writerow([...])
```

**Test it:** `run_tests.py` first —
`ExportDatasetPreservesOtherSourceRowsTests.test_preserves_writer_batch_rows_already_in_file`
in `tests/test_export_dataset.py` fails immediately: it seeds `labels.csv`
with one writer-batch row, runs `export_dataset.main()` against a single new
Supabase row, and asserts both survive. The reverted code only ever writes
`exported`, so the pre-existing writer-batch row vanishes from the output
file. Then see it against real shape (do NOT point this at the real
`datasets/verified/labels.csv` — use a scratch copy):

```bash
cd ocr_feature
cp datasets/verified/labels.csv /tmp/labels_scratch.csv
python -c "
from pathlib import Path
from evaluators import export_dataset
export_dataset.LABELS_CSV = Path('/tmp/labels_scratch.csv')
"
```

With the fix intact, running `export_dataset.main()` against
`/tmp/labels_scratch.csv` preserves all 168 existing writer-batch rows
alongside whatever Supabase rows this run finds (confirmed live, 2026-09-06:
168 preserved, 0 lost). With it reverted, every one of those 168 rows is
gone the moment the script writes its output — silently, no warning, no
error, just fewer rows than before. This is the exact bug that motivated
`evaluators/labels_schema.py`, discovered by reading both scripts and
noticing they shared a truncating write target, not by a reported data-loss
incident. Revert the code change immediately after confirming, re-run
`run_tests.py`.

---

If a change doesn't show up above, it's either purely mechanical (logging,
formatting, file paths) or genuinely new territory — in which case the two
questions worth asking before touching it are still the ones this whole
codebase is organized around: **does this ever risk misrepresenting what a
student actually wrote, and can I prove any accuracy claim about it against
a physically verified label?**
