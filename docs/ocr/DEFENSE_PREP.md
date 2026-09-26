# Code Walkthrough & Defense Prep — OCR Component

> **Current figures (2026-09-24):** clean_ws CER 0.099, clean WER 0.328,
> clean token accuracy 0.716 on the 20-page production evaluator. The
> 14-page `0.149` numbers and "current" wording later in this dated study
> guide are historical. Pre-extraction uses the same model and settings;
> it changes arrival timing, not recognition accuracy. See
> [EVALUATION.md](EVALUATION.md) and [RUNNING_LOCALLY.md](../setup/RUNNING_LOCALLY.md).

## Continuation experiment framing — 2026-09-14

Safe description: “We tested local code-block association offline. It improved
reading order on our small same-writer pilot while preserving recognized text,
but explicit membership/continuation decisions still have gaps and can abstain.”
Do not present 8/8 development or 3/3 reserved ordering as general recognition or
program-membership accuracy. The web app has not adopted the prototype. Demonstrate
it with `tests/manual_continuation.py`; recognize that missing/misread OCR symbols
are not corrected. Current evidence and concrete limitations: [session handoff](../../ocr_feature/reports/2026-09-14-continuation-session-handoff.md).

Study document for a live code test. Covers every file in the extract →
display → save pipeline (John Cale Nombrado's scope), what each piece
does, **why it is built that way**, and the questions a panel is likely
to ask — with the strong answers.

> **Defense framing (2026-09-05):** the OCR-review highlighting described
> below is **outside the defended scope** (extract → save raw/verified text
> → display for teacher editing in the Ace editor) and lives only on the
> `confidence-flagging-experiment` branches, unmerged. Don't lead with it or
> volunteer it in the main walkthrough. If a panelist asks something like
> "how does the teacher know where to look" or "did you consider confidence
> scoring," it's a legitimate, well-tested answer to have ready — but present
> it as an explored prototype with a known, understood limit (see the
> low-recall finding just below), correctly scoped as future work pending
> more training data, not as a finished or shipped feature.
>
> **OCR review update (2026-09-12):** the OCR-review suggestions backend
> described here was removed from `feature/reading-order-reassembly`
> (commit `43addce`) as unused on this branch. See
> [`OCR_REVIEW_SUGGESTION_AB.md`](OCR_REVIEW_SUGGESTION_AB.md) for history.

## Quick numbers & one-line answers (memorize these)

**CER milestones** — all `clean_ws` on the 20-image held-out `samples/`. Note
`0.126` and `0.099` are **both end-to-end** on the same set; the difference is
the reading-order feature, not the model (same fine-tuned recognizer in both).

| Configuration | CER | What it isolates |
|---|---|---|
| Stock recognizer | **0.274** | before fine-tuning |
| Fine-tuned recognizer (pre-two-column) | **0.126** | the −54% recognition gain |
| **Current end-to-end** (fine-tuned + two-column reading order) | **0.099** | today's pipeline |
| Fine-tuned + binarization ON | 0.218 | ablation — worse |
| Fine-tuned + all orientation/unwarp passes ON | 0.177 | ablation — worse |

**One-line answers:**
- *"Which is your accuracy number?"* → **0.099 end-to-end.** `0.126` is the earlier
  checkpoint that isolates the recognition fine-tune; the two-column reading order
  then took it to `0.099`. Layout features (indentation, blank-line spacing) are
  whitespace-neutral to `clean_ws`, so they don't change `0.099`.
- *"What does the banded column split buy you if the headline stays 0.099?"* →
  It is a **real-submission-fidelity** win, not a headline mover: no held-out
  `samples/` page has the two-page/side-by-side layout, so `evaluate_cer` is
  unchanged, but on the real page `green_writer18_B2_2.jpg` it takes clean_ws CER
  **0.147 → 0.042** (ordering only). Same shape of result as the local-gutter
  feature — it fixes pages real students actually submit.
- *"Why grayscale, not binarize?"* → Measured on the **deployed** model:
  binarization raises CER **0.126 → 0.218** (+73% relative), worse on every paper
  type (worst on greenbook). Grayscale + denoise measured best, so `threshold=False`
  ships. (`EVALUATION.md`)
- *"Why no orientation/unwarp correction?"* → The mobile **quality gate** rejects
  bad geometry/illumination/blur *before* OCR, so the pipeline doesn't repeat it.
  Measured: the two **page-level** passes (`doc_orientation_classify` +
  `doc_unwarping`) hurt (0.126 → 0.177, bond ~91× worse) by mis-warping
  already-flat pages; `textline_orientation` alone was **neutral** (not isolated
  flag-by-flag beyond that). (`§14.1`)
- Preprocessing pipeline (current): **raw/gate image → downscale → grayscale →
  adaptive denoise → PaddleOCR detection/recognition.** Binarization is OFF by
  default.

> **⚠️ STATUS UPDATE (2026-08-30) — the "Results level" Q&A below is
> outdated and would undersell what's actually true now.** The answer to
> *"Your baseline is only 13 samples, 2 writers"* (in the Results level
> section) still says the correct response is "not a valid baseline...
> not defending a percentage." That was correct in 2026-08-03; it is not
> the current situation. There is now a **real fine-tune**, trained on
> 2,491 physically-verified line crops across multiple writers and all
> three paper types, measured on a genuinely held-out 20-image test set:
> **CER 0.274 (stock) → 0.126 (fine-tuned), −54%, every sample improved,
> zero regressions.** If a panelist raises the small-sample-size question
> now, the answer is the result above, not the old deflection — see
> `EVALUATION.md`'s top banner and `NEXT_STEPS.md`'s 2026-08-30 status
> block for the full, current, defensible numbers and methodology.
>
> **⚠️ ADD (2026-09-01) — the three strongest defense points, all in
> `EVALUATION.md`:**
> - **WER (objective 7):** stock → fine-tuned **0.726 → 0.359 (−51%)**;
>   token-accuracy 0.487 → 0.701. Improved on every paper type. (WER always
>   reads higher than CER on handwriting — one wrong char fails the whole word
>   — so the absolute value is expected; the ~50% *relative* drop is the point.)
> - **Greenbook is writer-disjoint** (writer id = number + **batch**; numbering
>   resets per batch). 13 of 20 test images are from writers never seen in
>   training, so **0.126 is largely a genuine unseen-writer result** — not
>   same-writer. Bond/yellow stay same-writer only because they have too few
>   writers to hold out.
> - **Cross-writer experiment (the clincher for "does it work on new
>   students?"):** a separate model retrained with 4 greenbook writers excluded
>   entirely, tested on their never-seen pages: **stock 0.296 → fine-tuned 0.123
>   CER (−58%)**. Proves the improvement transfers to writers with zero training
>   exposure — it's generalization, not memorization of known handwriting. The
>   quiz-grading scenario (fixed questions, varied handwriting) makes repeated
>   code content the *right* distribution; the writer-disjoint test is what
>   proves it reads a *new student's* answer. Reproducible via
>   `evaluators/build_crosswriter_dataset.py` + `evaluators/crosswriter_eval.py`.
>
> **STATUS UPDATE (2026-08-03) — supersedes the 2026-08-02 retraction below.**
> All 13 labels were physically verified by John Cale Nombrado and found literal
> and correct; each row now carries `literal_verified` provenance. The evaluators
> run. **⚠️ Baseline update 2026-08-04:** the original 13-page `0.148` is
> superseded — the 5 non-representative `nikko` close-ups were deleted, so the
> baseline then became `clean_ws 0.190` over 8 full-page `nombrado` pages —
> superseded 2026-08-06 by **`clean_ws 0.149`** under the grayscale default
> (binarization off; see §6) — measured over 8 full-page `nombrado`
> captures (**bond 0.165 / greenbook 0.231**). This is a cohort-composition change,
> **not** a regression; per-paper-type figures are the stable citable metric (see
> `EVALUATION.md`). The v6 model selection still beats v5, using
> **`PP-OCRv6_medium_det` + `PP-OCRv6_medium_rec`** (`0.148` vs v5 `0.181` on the
> original cohort). Consensus was evaluated, rejected, and its code removed
> 2026-08-04 (pipeline is baseline-only). So the v6 model selection and the
> per-paper-type baseline ARE
> defensible now; the older `.181`/`.186` numbers are the v5 baseline, and the
> pre-verification "canonical/not literal" caveat no longer applies.
>
> _Superseded 2026-08-02 retraction (kept for history): it held that `.181`/`.186`
> and all model/preprocessing/subgroup rankings were unciteable because the 13
> labels were unverified. The verification on 2026-08-03 resolved that._
> Evaluators still fail closed unless **every** `labels.csv` row has
> `literal_verified=true` plus nonblank `literal_verified_by` and
> `literal_verified_at` — which the current cohort satisfies. Authoritative
> model/eval status: [`PIPELINE.md`](PIPELINE.md) and [`EVALUATION.md`](EVALUATION.md).

How to study this: read a section, then open the actual file beside it
and trace the code line by line until you could re-explain it with the
file closed. The "likely questions" at the end are for self-testing.

---

## 0. The one-paragraph system summary (memorize this)

> Students hand-write C code on paper. The mobile app captures a photo
> (to be quality-gated by a teammate's component — in progress, not yet
> merged) and stores it in Supabase.
> My pipeline takes that image, preprocesses it (resize → grayscale →
> denoise → adaptive threshold), runs PaddleOCR detection + recognition,
> filters phantom detections by confidence, reassembles fragments into
> reading order using bounding-box geometry, applies a closed-vocabulary
> C keyword cleanup, and returns the text to the web app, where the
> teacher reviews it in an Ace code editor and saves a verified version
> to the database. The teacher's saved text is the grading input; the OCR is
> an assistant, never the authority. A `verified` status alone is **not**
> evaluation ground truth: literal transcription and recorded provenance are
> required before using any saved text for OCR-accuracy claims.

Scope boundary (say this if asked about anything upstream/downstream):
capture quality gate = teammate's component (mobile); grading logic =
downstream. My component: image in → verified text in DB.

---

## 1. Data flow (draw this if given a whiteboard)

```
photo (mobile, quality-gated)
   └─> Supabase storage (image_url on a submissions row)
        └─> web "Extract" button
             └─> POST /api/ocr/extract-from-url        [main.py]
                  ├─ download_image()  (retry, split timeout)
                  ├─ preprocess_image()                [preprocess.py]
                  │    resize ≤1600 → gray → denoise (threshold off by default)
                  ├─ ocr.predict()  (PaddleOCR: detect + recognize)
                  ├─ _filter_low_confidence()  (drop score < 0.3)
                  ├─ _group_detection_records()  (geometry sort/merge)
                  ├─ clean_c_code()                    [c_code_cleanup.py]
                  ├─ debug JSON → outputs/debug/       (diagnostics)
                  └─ return {raw_text, cleaned_text, average_confidence}
                       └─> Ace editor (teacher edits)
                            └─> saveVerifiedText()
                                 verified_text  = teacher's text
                                 extracted_text = OCR's own output only
```

---

## 2. `main.py` — the FastAPI backend

**What it is:** a small FastAPI app with two endpoints:
- `POST /api/ocr/extract-upload` — direct file upload (dev/testing).
- `POST /api/ocr/extract-from-url` — production path: takes
  `submission_id` + `image_url`, downloads from Supabase, extracts.

**Design points you must be able to explain:**

- **`lifespan` + `warmup()`**: models are loaded at startup and warmed
  with a tiny synthetic "int main" image so the *first real request*
  doesn't pay model-initialization cost. Warmup failure is swallowed
  deliberately (`except Exception: pass`) — a warmup problem must never
  prevent the server from starting; the first real request would just be
  slower.
- **`download_image()` resilience**: mobile captures are 3–5 MB. A flat
  30s timeout failed on slow networks. Fix: split timeout (15s to
  connect, 120s to read), streamed download in 8 KB chunks, up to 3
  retries — but **only network errors are retried**. A non-200 HTTP
  status raises immediately: it is not transient (the URL is wrong or
  access is denied; retrying can't fix that).
- **CORS `allow_origins=["*"]`**: development convenience. If asked:
  "in production this would be restricted to the web app's origin."

**Likely question:** *"Why does the endpoint return `saved_to_db:
false`?"* → The backend does not write results to the database; the web
app owns the save, because saving is coupled to teacher verification.
One writer per column keeps ownership clear.

---

## 3. `preprocess.py` — image preparation

**Pipeline:** resize (cap longest side at 1600 px) → grayscale →
`fastNlMeansDenoising` → `adaptiveThreshold` (Gaussian, block 31, C 15).

**Why each step:**

- **Resize cap 1600**: beyond this the OCR model downsamples internally
  anyway, so denoising a 4000-px image is paying cost for pixels the
  model never sees. `INTER_AREA` interpolation because it's the correct
  choice for shrinking (averages source pixels; no aliasing).
- **Grayscale**: ink-on-paper carries no useful color information;
  every later step operates on intensity.
- **Denoise (non-local means)**: removes sensor noise / paper texture
  while preserving edges better than a blur. Parameters (strength 10,
  template window 7, search window 21) are the OpenCV-recommended
  defaults for this function.
- **Adaptive threshold**: binarizes to black text / white background.
  *Adaptive* (per-31×31-block, minus constant 15) rather than global
  (Otsu) because phone captures have uneven lighting — one global
  threshold would push a shadowed corner to solid black. Gaussian
  weighting = nearer pixels count more within each block.

**`PreprocessConfig` (dataclass, frozen):** all knobs in one place;
defaults reproduce the long-standing behavior exactly. `frozen=True`
makes configs immutable — an experiment can't accidentally mutate the
shared default. `extract_text_from_image` takes an optional config, so
experiments never touch production behavior.

**The ablation (know this history — a panelist may probe whether you
actually understand it, not just recite a number):**

An early version of this ablation claimed denoise+threshold beat no
preprocessing by a wide margin on "7 real captures" (0.095 dev vs 0.153
real, with/without dropping to 0.234). **That specific comparison was
retracted** — the "real captures" reference text was mostly the OCR's own
unedited output, not independent transcription, so the 0.153-family
numbers are invalid. Full story if asked: `CAPTURE_GATE_FINDINGS_3_CORRECTION.md` §8.

**Correction:** The following table is preserved as the historical ablation,
but the claim that it was solid or validated on 13 individually verified
samples is retracted. Its labels need literal human revalidation; all values
are canonical-reference diagnostics, not OCR accuracy or proof of ranking:

| Historical change | Canonical-reference diagnostic | Intended rationale (not validated effect) |
|---|---|---|
| baseline (fixed 31px threshold block, fixed denoise) | 0.223 | — |
| + `threshold_block_scale` (block sized to measured handwriting) | 0.198 | small/large handwriting, not just one tuned size |
| + `adaptive_denoise` (denoise strength sized to measured paper texture) | **0.181** (retracted diagnostic) | historical greenbook diagnostic 0.354 → 0.282; not validated accuracy |

**Likely question:** *"Why does one denoise/threshold setting not work
for every capture?"* → Handwriting size and paper texture both vary, and
each has a fixed pixel-scale parameter (threshold block size, denoise
strength) tuned for one scale. Measuring the page's own properties
(glyph height via connected components, background noise via median-blur
residual) and deriving the parameter from that, instead of hardcoding it,
is the engineering rationale for both features. The old ranking appeared in
canonical-reference tests, but it is not confirmed accuracy; several
alternatives that used one *global* setting for all paper types (stronger
denoise, Sauvola binarization, CLAHE) produced different historical
diagnostics by paper. Retest the hypothesis only after valid literal labels
exist; do not claim per-page adaptation measured best on current evidence.

**Second likely question, and the one to volunteer proactively:** *"Has
a wrong measurement bitten this project before?"* → Yes, and it's worth
raising yourself rather than waiting to be asked — see §8 of the correction
doc referenced above and the "ground-truth discipline" callout further
down this file. The short version: an exact match between OCR output and
a reference is a red flag, not a success, and that lesson now gates every
measurement made since.

---

## 4. `ocr_pipeline.py` — the core (know this file best)

> **Structure note (2026-09-13):** `ocr_pipeline.py` was split. It now holds
> recognition + orchestration only (~275 lines): model construction, `warmup`,
> `REC_SCORE_FLOOR`, `_filter_low_confidence`, `_recognize_preprocessed`,
> `extract_text_from_image`. The reading-order / indentation **geometry**
> (`_group_detection_records`, the column/banded/severance detectors,
> brace-depth reassembly, indentation reconstruction) moved to **`core/layout/`**
> — pure stdlib, imports no recognizer. Behavior-preserving move (byte-identical
> functions; `evaluate_cer` unchanged). `ocr_pipeline.py` re-exports the two geometry
> names still imported from it (`_group_detection_records`, `line_member_bounds`); the
> other re-exports and the `core/layout/reorder.py` shim were removed as dead on
> 2026-09-18 (import the rest directly from `core.layout`). Anchors below that point
> into the geometry now cite `core/layout/`.

### 4.1 Model selection (detector by name; recognizer now fine-tuned)

```python
ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_dir=_FINE_TUNED_REC_DIR,   # fine-tuned (was v6_medium_rec by name)
    text_det_box_thresh=0.30,                         # lowered from 0.60 to recover braces
    ...)
```

> **Currency note:** the snapshot above is the *current* code. The detector is
> still the stock `PP-OCRv6_medium_det` pinned by name, but the **recognizer is
> now the fine-tuned model** (dir-based, required — see §0/§4 banners), and
> `text_det_box_thresh=0.30` was added (brace recovery, EVALUATION.md
> 2026-09-04). The v6_medium *recognizer* selection below is the historical
> starting point the fine-tune was trained on.

- **Why v6_medium (2026-08-03):** a sweep over the 13 verified labels picked this
  pair at `clean_ws 0.148`, beating the previous v5 mobile pair (`0.181`) on
  11/13 pages and every subgroup. Defensible talking point: it was a *model
  selection* on verified data, not fine-tuning and not a preprocessing tweak.
- **Why still pinned explicitly:** passing only a detector name makes PaddleOCR
  silently ignore `lang`/`ocr_version` and pick a default recognizer.
- **Why not the bigger v5 server recognizer:** it is multilingual and substitutes
  CJK for C symbols (二 for `=`), scoring 0.279 — much worse. The win came from a
  newer architecture generation, not more capacity.
- **On CJK from v6:** v6_medium also emits occasional CJK, but stripping non-ASCII
  changes CER by ~0.0001, so no filter was added. In a grading app a visible `二`
  is a self-announcing error a teacher fixes on sight; a silent deletion would
  look like a student's own mistake. (Earlier the English-only v5 model was pinned
  precisely to guarantee ASCII — that decision was made on unverified labels and
  is now reversed with the CJK cost measured.)
- **Why lightweight detection:** disabling orientation/unwarp passes took
  extraction from ~81s to a few seconds on CPU; the verified sweep also showed the
  heavy `PP-OCRv5_server_det` is *worse* at ~9x runtime, so detection is not the
  bottleneck. Captures are gated upright/flat by the mobile app; if that gate
  disappears, revisit. (Current v6 cost is ~9s/page vs the old ~3s.)
  **Flagged, unresolved (2026-09-06):** re-flipping all three `use_*` flags to
  `True` on the current setup and timing it directly did **not** reproduce
  this ~81s figure — measured `10.19s` vs a `10.12s` baseline, essentially no
  difference, repeated twice. Don't cite ~81s as freshly re-confirmed; it may
  be stale (different detector, image, or hardware from whenever it was
  originally measured). See `CODEBASE_GUIDE.md` §10.12 for the full
  measurement. If asked live, say the discrepancy exists rather than
  asserting either number confidently.
- **History — the English-only pin, now reversed:** v5's English recognizer was
  originally pinned to guarantee ASCII output, even though a multilingual model
  measured ~2 pts *better* on early dev samples (0.075 vs 0.095). At the time
  those labels were unverified, so the gap was treated as uncitable and the ASCII
  guarantee won. The 2026-08-03 verified sweep resolved it the other way: v6
  measurably wins (`0.148` vs `0.181`) and the CJK cost is ~0.0001, so v6 was
  adopted without an ASCII filter. Defensible framing: "we pinned English-only
  while we couldn't trust the labels; once we verified them, the newer model won
  cleanly and the CJK concern proved negligible." The retracted 2026-08-02
  "server 64% worse / current model won / no accuracy left" claims stay retracted
  — they were superseded by the verified sweep, not revived.

### 4.2 Confidence filter — `_filter_low_confidence`

`REC_SCORE_FLOOR = 0.3`. Detections scoring below it are dropped
before text assembly — they are near-certain false positives (detector
fired on a smudge). Evidence: a phantom "2" scored **0.127** while
every real character on the same page scored 0.7+. Validated on 12
real uploads: caught 2 genuine phantoms ('2' @0.127, '↓' @0.294),
dropped zero real characters.

Code details to be ready for:
- If `rec_scores` is missing or misaligned with `rec_texts`, the
  filter passes everything through — **when metadata is unreliable,
  do nothing rather than guess** (a recurring principle in this file).
- A score that can't be parsed as float passes through (same reason).
- Since 2026-07-29 it also returns what it dropped, so the debug
  artifact can show discarded content.
- **Known limitation (volunteer it before they find it):** the floor
  only catches *low-confidence* phantoms. A stray line from outside
  the answer area can be read confidently (observed: `return o` at
  high confidence) — that's a capture-framing problem; the fix
  belongs in the capture gate, not in a threshold.

### 4.3 Reading order — `_group_detection_records` (the algorithm)

**Problem:** PaddleOCR's output order can scatter one handwritten row
into out-of-order fragments. Observed live: `int result = add(3,4);`
came back as three disconnected pieces in the wrong sequence.

**Algorithm** (trace this on paper until you can do it from memory):
1. For each detection take its box `[x_min, y_min, x_max, y_max]`;
   compute vertical center `y` and left edge `x`.
2. `line_tol = max(0.6 × median box height, 1.0)` — two fragments
   belong to the same visual line if their vertical centers are within
   ~60% of a typical line height. **Median** height (not mean) so one
   unusually tall detection doesn't skew the tolerance.
3. Sort all fragments by `y` (top to bottom); sweep once.
4. For each fragment, try to join the *current* line: predict where
   this line's centerline should be at the fragment's `x` using a
   least-squares slope through the line's existing members
   (`_expected_line_y`) — this follows handwriting that drifts
   upward/downward across the page. Join if the fragment is within
   tolerance of the trend (and within the center band, or within half
   tolerance of a tight trend — the half-tolerance rule stops a
   *slightly indented next row* from being absorbed into a sloped
   line). Otherwise start a new line.
5. Within each line, sort members left → right; join with spaces.

**Fail-safe:** any malformed box, non-finite value, or overflow makes
the function fall back to original order, one fragment per line —
**never let geometry errors corrupt text content**. This is why the
code checks `isfinite` obsessively.

**Grade-safety property (say it verbatim if scope is questioned):**
this function reorders and joins whole recognized fragments; it
**never edits a character**.

**Likely questions:**
- *"Why 0.6 of median height?"* → Tuned against real handwriting
  samples: large enough to absorb fragments of the same wavy row,
  small enough not to swallow the next row; validated by the unit
  tests that encode observed failure cases (drift, slope, indent).
- *"Why least-squares instead of just comparing y-centers?"* →
  Handwritten lines slope. A fixed y-band splits a sloped row into
  two lines; following the fitted trend keeps it together. There is a
  test for exactly this (`test_keeps_a_sloped_handwritten_line_together`).

### 4.4 `extract_text_from_image` — orchestration

Order of operations: preprocess → predict → per page: filter → group →
assemble lines + collect scores → join to `raw_text` → `clean_c_code`
→ average confidence → write debug artifact → return dict with
`raw_text`, `cleaned_text`, `average_confidence`, `preprocessed_image`.

- `average_confidence` is the mean of kept detection scores — this is
  the number the quality-gate calibration uses (healthy captures
  0.87–0.93; degraded 0.77–0.80).
- Raw and cleaned text are both returned/stored — cleanup is
  transparent and reversible, never a black box.

### 4.5 Debug artifacts (added 2026-07-29)

Every extraction writes `outputs/debug/<stem>_preprocessed.json`: raw +
cleaned text, average confidence, every detection (text, score, box),
dropped detections, grouped lines. Purpose: diagnose *which stage*
failed; supply confidence data for gate calibration; boxes will later
cut line-level crops for fine-tuning.

Both helpers live in `core/debug_artifact.py` (moved out of
`ocr_pipeline.py` on 2026-08-08 so the pipeline module holds recognition
logic only — behavior-preserving, `clean_ws 0.149` unchanged):

- `write_debug_artifact` is wrapped in try/except — **diagnostics
  must never break extraction**.
- `_jsonable` converts numpy scalars/arrays to plain Python for JSON
  (`tolist()` if available, else float, else string) — PaddleOCR
  returns numpy types that `json.dump` rejects.

---

## 5. `c_code_cleanup.py` — closed-vocabulary cleanup

**The hard rule (the most important sentence in your defense):** this
app grades student work, so nothing may auto-"correct" content that
could misrepresent what the student wrote. Therefore cleanup fixes
**only a closed vocabulary** — a small dictionary of known OCR
misreads of C keywords (`1nt`→`int`, `pr1ntf`→`printf`, ~20 entries)
plus `#include` line normalization. Never variable names, numbers,
literals, or ambiguous symbols.

**Mechanics you must be able to walk through:**

1. **Literal shielding:** a regex finds every string/char literal;
   keyword fixes are applied only to the segments *between* literals,
   and literals are re-attached untouched. A student writing
   `printf("1nt")` keeps `"1nt"` in the string.
2. **Whole-token matching:** `(?<![\w#])token(?![\w])` — custom
   boundaries because `\b` misbehaves around `#`. So `1nt` fixes but
   `x1nt` doesn't.
3. **`#include` normalization:** a line already recognizable as
   `#include <knownheader...>` is snapped to canonical form
   (`#include <stdio.h>`), because standard headers are a closed set —
   OCR often mangles `.h` → `.n` or `>` → `7`, and only a line already
   matching the pattern is touched; a stray `7` elsewhere is left
   alone. The `#` is optional in the pattern (OCR drops it sometimes;
   `include <stdio` is still unambiguous).
4. **Pass order:** keywords first, then includes — so `std1o` is first
   fixed to `stdio` by the keyword pass, which lets the include pass
   recognize and snap the line.

**Historical diagnostic:** cleanup changed canonical-reference strict CER from
0.148 → 0.137 and did not regress a row in that set. This is not validated OCR
accuracy. Defend the cleanup from its closed-vocabulary, non-mutating scope and
unit tests—not from the withdrawn labels.

**Likely question:** *"Why not use a C parser / LLM to fix the code?"*
→ Because anything that could invent or alter student content is
disqualified by the grading-integrity rule. The dictionary is small,
auditable, and every entry defensible on its own; a parser or LLM is
neither.

---

## 6. `evaluators/evaluate_cer.py` — current baseline `0.149` (14 samples, all gate-framed)

> **Runs on the verified cohort.** Labels have literal human provenance, so the
> script runs and its output is citable. Current reproducible baseline:
> `clean_ws 0.149` over 14 samples, all gate-framed — the deconfounded
> raw-vs-gate experiment ran 2026-08-06 (bond worse under the gate, greenbook
> better; see EVALUATION.md's top banner) and two `writer1` pages were then
> added; `samples/` no longer has any raw pages. Older figures
> `0.148`/`0.190`/`0.128`/`0.151` are **superseded**. Run
> it as a module from `ocr_feature/`:
> `python -m evaluators.evaluate_cer`.

The provenance preflight runs before OCR models load. Every `labels.csv` row
must have `literal_verified=true` and nonblank `literal_verified_by` and
`literal_verified_at`; any missing, false, or blank value aborts evaluation.
The current cohort satisfies this.

**CER** = Levenshtein edit distance(prediction, reference) ÷
len(reference). 0.0 = perfect; can exceed 1.0 if the prediction is
much longer than the reference.

**Levenshtein (be ready to explain the DP on a whiteboard):** minimum
number of single-character insertions, deletions, substitutions to
turn string A into string B. The implementation is the classic
dynamic-programming row-by-row version: `prev` holds the previous
row of the edit-distance matrix; each cell is
`min(deletion, insertion, substitution-or-match)`. O(len(a)·len(b))
time, O(len(b)) memory because only one previous row is kept.

**Why four variants (raw/clean × strict/ws):**
- raw vs clean isolates the cleanup layer's contribution.
- strict vs whitespace-normalized: `normalize_ws` collapses all
  whitespace runs to single spaces — layout/indentation differences
  are not character-recognition errors, and the teacher reformats
  anyway. `clean_ws` was the old headline metric variant, but there is no
  current headline OCR-accuracy number because the references are invalid.

**Edge case:** empty reference → CER defined as 0.0 if prediction
also empty, else 1.0 (avoids division by zero).

**Ground-truth discipline:** The earlier claim that `labels.csv` was a
character-faithful transcription is retracted. Direct paper inspection found
canonical/intended content that differs from what was physically written.
Every row must be human-revalidated literally—including student bugs, spelling,
punctuation, case, and numbers—with provenance. Copying OCR output or the
intended prompt as ground truth makes CER meaningless.

**Defensible baseline (updated 2026-08-06):** **`clean_ws 0.149`** over 14
samples, all gate-framed (bond 0.133 / greenbook 0.159 / yellow_pad 0.171) —
the deconfounded raw-vs-gate experiment ran this day and two `writer1` pages
were added, `samples/` no longer has any raw pages. Earlier figures `0.190`
(8 raw nombrado pages), `0.151` (the 12-sample figure before the `writer1`
pages), and `0.148` (original 13-page cohort, superseded when
the 5 non-representative nikko close-ups were deleted) are all superseded —
v6 still beat v5 `0.181` on that original cohort. Prefer the per-paper-type
figures as the stable citable metric. These are citable — the labels
were verified, and the earlier "not literal" claim was an AI photo-read error
that was withdrawn. Present it as a small-sample baseline (12 hard, varied
pages, 3 writers), not a production accuracy figure, and report per-subgroup
with the writer/paper confound named. The Supabase `0.153` figure stays
retracted on its own (self-comparison contamination). Consensus was
evaluated, rejected, and its code **removed 2026-08-04** (pipeline is now
baseline-only); see `RAW_OCR_CONSENSUS_HANDOFF.md` for the retained record.

**WER + token-level recognition accuracy (added 2026-08-10, thesis objective
7 says "CER, WER, and token-level recognition accuracy" — this exists
specifically to satisfy that line).**

- **WER** = edit distance over `str.split()` word tokens ÷ reference token
  count. Lower is better. Reuses the exact same `edit_distance()` function as
  CER — it already compares list elements with `!=`, not just characters, so
  no new algorithm was needed, just a different input (a token list instead
  of a character string). No separate `_ws` variant: `split()` already
  ignores whitespace runs, so a raw split and a `normalize_ws()`'d split
  produce identical tokens — there's nothing left for whitespace-normalization
  to change.
- **Token-level recognition accuracy** = `1 - (edit distance over C-lexical
  tokens ÷ reference token count)`, floored at 0. HIGHER is better (accuracy,
  not error rate — matches the paper's exact wording). Tokens come from a
  small regex lexer (`tokenize_c` in `evaluation.py`): multi-char operators
  first (longest-match, so `<<=` isn't cut into `<<` + `=`), then numbers,
  identifiers, and single characters; string/char literals stay atomic by
  reusing the same `C_LITERAL` pattern the cleanup layer uses to shield them.
  **Why this exists as a separate metric from WER, not just "WER but for
  code":** whitespace-split words treat `x=5` and `x = 5` as different token
  counts (1 vs 3) purely from spacing style, which has nothing to do with
  recognition accuracy — C isn't whitespace-sensitive, so scoring by
  whitespace would inject noise unrelated to what OCR actually got right.
  Token boundaries follow C grammar instead, so operator spacing never counts
  as an error.
- **Not a full C tokenizer** — no hex/octal/suffixed number literals, no
  wide/prefixed strings (`L"..."`, `u8"..."`). Good enough for scoring
  handwritten intro-level C; would need extending for a general-purpose
  lexer.
- **First measured values (14 samples): WER raw 0.699 / clean 0.656; token
  accuracy raw 0.715 / clean 0.729.** CER `clean_ws 0.149` is completely
  unaffected — verified the CER table prints byte-identical numbers before
  and after this change; the additions are purely additive.
- **Be ready to explain why WER looks so much worse than CER — this will get
  asked.** A single misread character fails the *entire* word under WER
  (`factonial` vs `factorial` = 1 full error) but only ~1/9 under CER (one
  wrong character out of nine). So a large WER-vs-CER gap on handwriting is
  expected and correct, not a sign of a worse result — the three metrics are
  measuring different granularities of the same output on purpose, per the
  paper's own objective. Cleaned beats raw on all three metrics, which is a
  good internal-consistency signal.
- Implementation: `evaluation.py` (`wer`, `tokenize_c`, `token_accuracy`,
  `evaluate_word_token_pair`); printed as a second table in `evaluate_cer.py`
  (kept separate from the CER table because CER's "good direction" is lower
  and WER/token-accuracy's is mixed — lower for WER, higher for accuracy).
  10 new unit tests in `test_evaluation.py`; full suite **78/78**.

---

## 7. `export_dataset.py` — the fine-tuning data pipeline

**Purpose:** teacher verification produces (image, corrected text)
pairs as a byproduct of normal grading — exactly what fine-tuning
needs. This script pulls all `status='verified'` submissions from
Supabase REST into `datasets/verified/` (images named
`<submission_id>.jpg` + `labels.csv`).

**Details to be able to explain:**
- Pages through results 100 at a time (`limit`/`offset`) until a
  short page — no assumption the table stays small.
- Downloads skip already-present files → re-running is cheap and
  idempotent; the CSV is rewritten from current DB state each run.
- Rows missing text/image or failing download are *skipped with a
  warning*, not fatal — a partial export is more useful than none.
- **Duplicate warning:** identical (whitespace-normalized) verified
  text on multiple submissions = re-captures of one page; they must
  end up on the same side of any train/test split or the evaluation
  leaks. The script detects and warns at export time.
- Auth: same `SUPABASE_URL` / `SUPABASE_KEY` the OCR server uses, from
  `.env` (`SUPABASE_ANON_KEY` was the legacy name; Supabase disabled that key
  on 2026-09-21).
- **Update 2026-09-27:** pages with several programs come from the
  `submission_programs` table; each program is kept as its own block and
  matched to the photo's lines separately, and such pages are never used as
  whole-page CER references or test pages.

**Current state:** 7 pairs exported, but only 1 (`d8cb2ec1`) is a
genuine human correction — 4 are the OCR's own output saved unedited, 1
has a label for a different program than its image. **Be ready for
this if asked:** `status='verified'` currently means "a teacher saved
this," not "a teacher corrected this," and the gap between those two
was discovered by treating the labels as ground truth and getting an
invalid measurement as a result. An export guard requiring an explicit
human-review signal is a known, still-open task — naming it
proactively is stronger than waiting to be asked why the data looked
wrong.

**Update (2026-09-06): the verification gap above is now measured, not just
anecdotal, and a related bug was fixed.** `export_dataset.py` and
`import_verified_batch.py` previously overwrote each other's rows in
`labels.csv` instead of merging — running one after the other silently
destroyed whichever rows the other had written. Fixed via a shared
`evaluators/labels_schema.py` module that partitions rows by ID shape
(writer-batch IDs vs. Supabase UUIDs) so each script only ever rewrites its
own namespace. Two new signals now ship with every export: `literal_verified`
(populated by `import_verified_batch.py` for physically-verified rows, blank
for Supabase-sourced rows with no per-row physical check) and
`correction_edit_distance` (character-level edit distance between OCR output
and the teacher's saved text, for OCR-sourced rows only). Real measured
output from the current dataset:

```
Found 2 verified submission(s).
Exported 0 pair(s) to datasets/verified/labels.csv (2 skipped).
labels.csv now contains 168 total row(s) (168 preserved, 0 from this run).
Provenance: 0/168 fully verified (literal_verified=true with verifier and date recorded).
```

The 0/168 provenance count is expected: all 168 rows were imported before the
provenance columns existed. The next `import_verified_batch.py --verified-by`
run will populate them. The 2 skipped Supabase submissions break down as: 1
missing `verified_text` or `image_url`, 1 caught by the `is_suspected_unedited()`
guard (verified text matched extracted text after whitespace normalization).
No correction edit-distance stats are printed because no OCR-sourced rows were
exported this run — the stat line appears only when at least one Supabase row
survives the filters.

This does not retroactively verify any row — it only makes it visible, per
row and in aggregate, which rows have a real provenance trail and how much
correction actually happened on the ones that don't. No row is rejected or
skipped based on either signal; both are informational, consistent with the
project's decision not to block data collection while it's still being
deliberately grown.

---

## 8. The web slice — extract, display, save

(`submissions-list.ts` + `services/supabase.ts`; the Ace editor is
`code-editor/`.)

- **`extractText()`**: POSTs the submission's `image_url` to the
  backend; puts `cleaned_text` into `extractedText[id]` (the OCR's
  record) and `editableText[id]` (what the teacher edits). On failure
  it sets a separate `extractionError` — **the error string is never
  placed in the editable field**, so a teacher can't accidentally
  save an error message as a verified answer.
- **`saveVerifiedText()`**: teacher's `editableText` → `verified_text`
  column; the OCR's own `extractedText[id]` (if extraction ran this
  session) → `extracted_text` column. Save-status feedback uses a
  per-submission generation counter so an older in-flight save or its
  3-second clear timer can never overwrite a newer save's status
  (race-condition fix, has tests).
- **`updateSubmissionText(id, verifiedText, extractedText?)`**: writes
  `verified_text`, `status='verified'`, `verified_at`; includes
  `extracted_text` **only when provided**. Throws Supabase errors so a
  failed save can't display as success.

**The Bug 5 story (tell it proactively — it's a strength):** while
computing CER on exported pairs, every submission scored an impossible
0.000 — the save path was writing the teacher's text into *both*
columns, erasing the OCR's output. Fixed so teacher edits only ever
touch `verified_text`, and `extracted_text` is never fabricated (left
untouched in the DB when no extraction ran). Moral: the evaluation
tooling caught a data-integrity bug the UI never would have shown.

---

## 9. `tests/test_ocr_pipeline.py` — what's tested and how

11 unit tests, all on `_group_detection_records` — the highest-risk
pure logic (it rearranges text content). Cases encode *observed*
failure modes: sloped lines held together, indented next row not
absorbed, running-mean drift, malformed/non-finite boxes falling back
to original order, left-to-right sorting.

**The stubbing trick (be ready to explain):** the module is loaded
with `importlib` under fake `cv2`/`numpy`/`paddleocr`/`preprocess`
modules patched into `sys.modules` — so the geometry logic is testable
without installing or loading any OCR runtime (tests run in
milliseconds, no models needed). The stub only needs the names the
module imports (`preprocess_image`, `PreprocessConfig`,
`DEFAULT_CONFIG`, `PaddleOCR`, `clean_c_code`).

**If asked "why no tests for X":** honest answer — the grouping logic has unit
tests because it is pure logic with observed failure cases. End-to-end accuracy
is established separately by `python -m evaluators.evaluate_cer` on the verified
cohort (`clean_ws 0.149` over 14 gate-framed samples, 2026-08-06), not by unit assertions — OCR
quality belongs in a versioned offline evaluation, which is what the evaluators are.
Fine-tuning will re-baseline against the current cohort and a fresh held-out test set.

---

## 10. Every magic number and its defense (rapid-fire table)

| Number | Where | Defense |
|---|---|---|
| 1600 px resize cap (`max_side`) | preprocess | model downsamples internally beyond this; cost without benefit. The old claim that raising it hurt accuracy is a retracted canonical-reference diagnostic |
| 10 / 7 / 21 denoise params (bond default) | preprocess | OpenCV-recommended defaults for fastNlMeansDenoising; strength rises to 20 on textured paper via `adaptive_denoise` |
| 31px threshold block (bond default) / 15 constant | preprocess | pre-adaptive default; on textured/small-handwriting pages, `threshold_block_scale` derives it from measured glyph height instead |
| **1.5** — `threshold_block_scale` | preprocess | Shipping historical choice; 0.223 → 0.198 and "best subgroup" claims are retracted canonical-reference diagnostics |
| **2.2** — `textured_paper_threshold` | preprocess | midpoint between measured bond background noise (0.47–1.89) and greenbook (2.53–2.62); calibrated on only 3 greenbook pages, flagged as needing more data |
| 0.3 `REC_SCORE_FLOOR` | ocr_pipeline | re-verified against v6 on the gate-framed set: dropped items are empty-text phantoms (0.0) or junk (highest 0.291), lowest real kept 0.334 — floor sits in the 0.291→0.334 gap, 0 real chars lost |
| **0.30** — `text_det_box_thresh` | ocr_pipeline | lowered from PaddleOCR's 0.60 default (measured 2026-09-04). Standalone braces + some faint whole code lines were lost at DETECTION (box score < 0.60), not recognition. Sweep 0.60/0.40/0.30: overall CER stays 0.126 at every value (no phantom regression), closing-brace recovery 82→86→87 of 89. Sharper 0.40-vs-0.30 diff: every extra box at 0.30 is real content (1 brace + 4 missing code lines), zero junk. "Misread beats missing" for a grading app. Full A/B: EVALUATION.md |
| 0.6 × median height | grouping | line tolerance tuned on real handwriting; encoded in unit tests |
| 0.5 × tolerance (trend rule) | grouping | lets a tight sloped fit continue without absorbing indented rows |
| 15s / 120s / 3 retries | main.py | 3–5 MB captures on slow networks; non-200 not retried (not transient) |
| **0.149 (current) / 0.151 / 0.190 / 0.148 / 0.181 (v5)** | evaluation | current reproducible baseline `0.149` on 14 gate-framed samples (bond 0.133 / greenbook 0.159 / yellow_pad 0.171); `0.151` was the 12-sample figure before the two `writer1` pages; `0.190` was the interim binary-default figure on 8 raw nombrado pages; `0.148` was the original 13-page cohort, superseded 2026-08-04 (nikko close-ups deleted); `0.181` is the v5 predecessor |
| ~81s → few s; v6 ~9s/page | model choice | dropped unwarp passes for speed; verified sweep showed heavy server detector is worse, so detection stays light |
| 0.075 vs 0.095 → v6 wins | model choice | early v6-favoring dev diagnostic; confirmed by the 2026-08-03 verified sweep (v6 `0.148` vs v5 `0.181`) |

---

## 11. Likely panel questions — with strong answers

**Fine-tuning specifics (2026-09-01 — moved here from the training notebook,
so it lives with the rest of defense prep instead of inside a Colab cell).**
The CER/WER numbers are computed **locally** by `evaluators/evaluate_cer` on
the held-out `samples/` set (Colab never sees the test set — it only trains).

- *Is the test set writer-disjoint from training?* **Greenbook yes; bond/yellow
  no.** Writer identity includes the BATCH: numbering resets per batch, so
  `green_writer19_B1` and `green_writer19_B2` are different students. Under
  that identity, **8 of 9 greenbook test writers (13 of 14 greenbook images)
  never appear in training** — so the greenbook result (CER 0.159, the bulk of
  the test set) is effectively a **new-writer** number. Only bond (2 writers)
  and yellow (4 writers) are same-writer, because those types have too few
  writers to hold one out without gutting training. Net: **13 of 20 test
  images are from unseen writers**, so 0.126 is largely a genuine new-writer
  result — with bond/yellow as the same-writer exceptions, and more writers
  there is planned.
  **Independent confirmation (cross-writer experiment):** a separate model was
  retrained with 4 greenbook writers excluded ENTIRELY, then tested on those
  never-seen writers: stock 0.296 → fine-tuned **0.123 CER (−58%)**. The
  improvement transfers to writers with zero training exposure — generalization,
  not memorization of known writers. (Measurement model only; the shipped
  model trains on all writers. Reproducible via
  `evaluators/build_crosswriter_dataset.py` + `evaluators/crosswriter_eval.py`.)
- *Only 20 test images — real improvement or small-sample noise?* Every one of
  the 20 files improved; zero regressions, consistent across all three paper
  types: bond 0.089 → 0.005, yellow_pad 0.175 → 0.071, greenbook 0.328 → 0.159.
  A uniform per-sample improvement is much stronger evidence than a single
  averaged number.
- *What about WER (thesis objective 7)?* Measured on the same 20-image set
  (2026-09-01): **WER (clean) 0.726 → 0.359 (−51%)** and **C-token accuracy
  48.7% → 70.1% (+21.4 pts)**, alongside CER 0.274 → 0.126. WER always reads
  higher than CER on handwriting (one wrong character fails the whole word —
  `factonial` vs `factorial` = full WER error but ~1/9 CER), so the absolute
  WER being higher is expected, not a regression; the ~50% *relative* drop
  tracks CER, and it improved on every paper type.
- *How did you choose the hyperparameters?* PaddleOCR's **published
  PP-OCRv6_medium_rec recipe, unchanged** (Adam, Cosine LR 5e-4, 5-epoch
  warmup, L2 3e-5, batch size 64) — only `epoch_num=40` was set. The training
  curve shows validation accuracy **still rising at epoch 39 with no
  overfitting divergence**, so this was not over-trained; a longer run
  (60–80 epochs) is a natural future-work lever, not a fix for a defect.
- *Why does most of the dataset repeat the same code?* Deployment is quiz
  grading — a teacher gives a fixed set of questions, so all students produce
  similar code; the only real variable is handwriting. The dataset mirrors
  that (same programs, many writers), and the writer-disjoint greenbook result
  is exactly what proves the model reads a **new student's** handwriting on a
  known quiz, not memorized code. Scope honestly: this doesn't yet prove
  performance on unfamiliar C constructs (structs, pointers, switch, arrays) —
  collecting that content diversity is planned.

**Concept level**

- *"Why not train your own model from scratch?"* → Handwriting
  recognition needs data volume we don't have; fine-tuning a strong
  pretrained model on domain data is the standard, resource-realistic
  approach. The pipeline is built so fine-tuning slots in later.
- *"80% accuracy — usable?"* → Don't answer in "% accuracy"; the metric is CER.
  Current defensible figure: `clean_ws 0.149` over 14 gate-framed samples
  (2026-08-06; bond 0.133 / greenbook 0.159 / yellow_pad 0.171) — i.e. ~15%
  character error on a small, multi-writer, multi-paper-type cohort. Frame it
  honestly as a small-sample baseline, not a production accuracy claim. The
  system-level safeguard still stands: OCR drafts, a teacher reviews, and only the
  saved teacher text is used for grading.
- *"Why is fine-tuning not done?"* → Dataset doesn't exist yet at
  volume (13 verified images exist; 200–500 is a minimum for a first attempt).
  We built the collection pipeline
  instead: dictated-snippet sessions produced the current set, and submissions
  are meant to add more automatically — though that automatic path
  currently has a data-quality gap being fixed (see the
  `export_dataset.py` section). Evidence fine-tuning is *needed*, not
  optional: systematic misreads (`printf`→`printe`, `}`→`3`, `0`→`o`) at
  0.85+ confidence — confidently wrong, so unfixable by thresholds;
  only the model itself can improve.
- *"How do you know teacher-verified text is correct?"* → You do not know from
  `status='verified'` alone. A valid evaluation row requires a human to view the
  physical paper, transcribe it literally, and record
  `literal_verified=true`, nonblank `literal_verified_by`, and nonblank
  `literal_verified_at`. The evaluator checks all three before models load.

**Code level**

- *"Walk me through the line grouping."* → Section 4.3; practice
  aloud with the `int result = add(3,4);` example.
- *"What happens if PaddleOCR returns a malformed box?"* → Grouping
  falls back to original order, one fragment per line — geometry
  errors must never corrupt text content.
- *"Why does the cleanup skip string literals?"* → Grading integrity:
  a literal is student content, verbatim; `printf("1nt")` must stay
  `"1nt"`.
- *"Explain Levenshtein distance."* → Section 6; be able to fill a
  small DP table by hand (e.g. "cat" → "cut").
- *"Why is `extractedText` optional in the save?"* → Never fabricate:
  if no extraction ran this session, we have no OCR output to store,
  so the DB column is left untouched rather than guessed at.

**Results level**

- *"Your baseline is only 13 samples, 2 writers."* → Correct, and it's
  not a valid baseline at all. Both the earlier 0.153 claim and the later
  0.181/0.186 claims are retracted because their references were not proven
  literal ground truth. The correct next step is human revalidation of all 13
  pages plus a fresh untouched, multi-writer, multi-paper cohort—not defending
  a percentage from the current set.
- *"Why does CER vary by paper type?"* → Do not claim a validated difference
  from this cohort. The historical greenbook-versus-bond values (including
  ~2.3× and 0.354 → 0.282) are canonical-reference diagnostics. Paper texture
  provides a plausible engineering mechanism and motivates diverse collection,
  but the effect and any preprocessing ranking must be remeasured against
  literal labels.
- *"Could preprocessing be improved further?"* → It's now fully
  configurable (`PreprocessConfig`), two dimensions are adaptive
  (handwriting size, paper texture) rather than fixed, and half a dozen
  further techniques were tried (CLAHE, Sauvola, ruled-line removal, stronger
  fixed denoise, higher-resolution recognition). Their old ranking is
  retracted; valid literal references are required before claiming diminishing
  returns or locating the remaining error in preprocessing versus the model.

**Scope level**

- *"What if a bad photo gets through?"* → My pipeline still runs,
  flags low average confidence (measured degraded band 0.77–0.80),
  and the teacher sees and corrects the output. Prevention is the
  capture gate's job (teammate's scope); detection and graceful
  degradation are mine.
- *"Who wrote what?"* → Answer honestly per your team's norms. What
  you must be able to do regardless: explain every line in your
  component. That ability — not authorship claims — is what a code
  test measures.

- *"What happens if a student writes their code non-linearly — puts a
  case body in the margin because the space directly below is filled
  with the rest of the function?"* → The exact scenario the adviser
  raised. The branch `feature/reading-order-reassembly` (branched off
  `ocr_feature`; 16 commits `74ebace` → `82a47bc`; not yet merged) holds
  **two distinct mechanisms — do not conflate them**:

  - **Two-column split** (`_detect_two_columns` + `_order_column_items`) —
    the mechanism that actually **fires on real handwriting and improves
    accuracy**. It detects a page written as two side-by-side columns of
    independent programs and reads the left column fully, then the right,
    instead of fusing across the gap. It is pure geometry (a persistent,
    uncrossed vertical gutter with both sides substantial: ≥4 detections and
    ≥half the page height each). On the real sample `green_writer10_B2_1.jpg`
    it splits at `x=321` (24 left, 23 right) and takes that page's CER from
    0.606 to 0.061.
  - **Banded column split** (`_detect_banded_column`, 2026-09-13) — the same
    left-fully-then-right-fully rule generalized to a **partial-height** right
    block (a two-page / side-by-side capture whose continuation fills only the
    top-right quadrant). It runs only when the full-height split declines, so
    green_writer10 is unaffected. The full-page projection fails on these pages
    because a stray wide line bridges it (gutter reported as 0); banded instead
    finds a persistent right cluster with a clean, uncrossed gutter *within its
    own y-band* and reads it in order. Pure geometry, grade-safe (whole pieces
    move by position; any ambiguous geometry declines). On the real sample
    `green_writer18_B2_2.jpg` it takes that page's clean_ws CER from **0.147 to
    0.042** (ordering only; the residual is recognition error). No held-out
    `samples/` page has this layout, so the `evaluate_cer` **headline is
    unchanged at 0.099** — a real-submission-fidelity win, not a headline mover
    (exactly like the local-gutter feature). A 162-artifact corpus scan: banded
    fires on green_writer18 only (zero false positives), and grade-safely
    declines the 7 `reassemble_example*` structural pages (negative spatial
    gutter), so severance is **kept as a complementary fallback**, not retired.
  - **Brace-depth reassembly** (`_reassemble_displaced_regions`) — for a
    *single* program whose tail was displaced into the margin. It walks the C
    brace-depth trajectory of every possible block length from the severed
    line, keeps only reorderings whose cumulative depth never goes negative and
    ends at 0, and applies iff exactly one length is valid; a post-selection
    guard vetoes any winner whose non-severed partition contains a real closer.
    **Be honest here: this has never fired on a real photo.** It is verified on
    synthetic fixtures (RBNode `rotate_rb`, Compressor `pack_flags`), but real
    handwriting includes misread braces that break the depth math, so on
    genuine OCR output it safely no-ops. Present it as a designed, tested,
    fail-safe path gated on brace-recognition quality — not a demonstrated
    result.

  **Why this works when general reading-order research doesn't.** The
  2022 *Neural Computing and Applications* survey on handwritten-doc
  reading-order and PaddleOCR's own PP-StructureV3 both treat reading
  order as a *purely geometric* problem (X-Y cut variants, GNN sorts of
  bounding boxes) — they have no signal beyond position, and print-doc
  layout literature explicitly notes "geometry alone is
  underdetermined" for parallel columns / marginalia / interlinear
  content. This project has a signal they don't: **C is formally
  bracket-delimited**, so brace-depth continuity across regions is a
  domain-specific structural check that geometric methods can't apply.
  That's the honest defense line — "we didn't solve general non-linear
  reading order; we used a signal specific to the language being
  transcribed, which is what *lets* a bounded heuristic attempt this
  narrow case where general methods can't. In practice the geometric
  two-column split is what pays off on our real photos; the brace-depth
  reassembly is the same idea pushed further, and it's gated on brace
  recognition we don't yet have at the block level."

  **Honest limits, name them proactively.** Not general non-linear
  layout (only end-of-sequence displacement where the block's closing
  braces balance the main text's still-open scopes). Not mid-sequence
  insertion (brace math can't discriminate two reorderings whose depth
  trajectories match — Codex's post-selection edge case, documented in
  the design spec's non-goals). The guard trades some legitimate
  multi-scope pages (e.g., a completed for-loop *before* a displaced
  switch case) for safety against confidently wrong reorderings —
  those pages fall back to human verification, same as any unresolved
  case. This is a *deliberate* conservatism: a wrong-but-plausible
  reordering is harder for a teacher to catch than a no-op that leaves
  the raw geometric order intact.

  **Test coverage: 148/148 Python tests** (was 126 at the reassembly phase;
  the banded column detector and its hardening added the rest), including both
  motivating reassembly examples, ambiguity/unbalanced fallback cases, the
  Codex counter-example the guard rejects, the definition-close exemption, and
  the two-column split / dynamic-gutter tests. **`evaluate_cer` = clean_ws CER
  0.099, clean WER 0.328, clean token accuracy 0.716** (verified 2026-09-10,
  20 samples). The two-column split drove the gain: only `green_writer10_B2_1.jpg`
  changed, taking the overall from the pre-split 0.126 to 0.099 — a
  *reading-order* improvement (same characters, right order), NOT a recognition
  gain. Keep 0.126 (recognition-only fine-tune) and 0.099 (end-to-end after
  reading-order) distinct. Full design + non-goals + real-photo findings:
  `docs/superpowers/specs/2026-09-10-displaced-region-tracking-design.md`,
  `docs/ocr/READING_ORDER_REVIEW_VERIFICATION_2026-09-10.md`, and the older
  `docs/superpowers/specs/2026-09-07-reading-order-reassembly-design.md`.
  To show the synthetic brace-depth path live without relying on PaddleOCR
  symbol recognition, run
  `.venv/bin/python -m tests.test_ocr_pipeline --demo-reassembly rbnode`,
  `compressor`, `small`, or `all` from `ocr_feature/`; it prints the synthetic
  detected order and the reassembled continuation.

- **Q: How does the teacher fix formatting — and can it corrupt the graded code?**
  The **Format button** (`CodeEditorComponent.reindent()`, `maistra_web`) is a
  one-click **C indentation normalizer** the teacher runs on demand. It covers
  all of C's indentation — brace nesting, `switch`/`case`, line continuation,
  `goto` labels, preprocessor at column 0 — but it is **whitespace-only and
  grade-safe by construction**: it strips ONLY leading whitespace and emits every
  other character verbatim, so it can never change a code character. It re-derives
  indentation purely from the **braces already in the buffer** (like an IDE — by
  the editor stage the box geometry is gone, only text remains), and it edits the
  editable working copy, never the stored original extraction (one undoable edit).
  Two honest points to volunteer: (1) it is a *reindenter, not a beautifier* — no
  line reflow, brace insertion, or intra-line spacing changes (those would touch
  code characters); (2) it is **brace-gated** — a misread `}` still misindents, so
  the intended order is *fix braces first, then Format*, and the teacher's edit
  pass remains the correctness guarantee. It is a teacher-readability aid, and
  because it is whitespace-only it is **invisible to the `clean_ws` CER (0.099
  unchanged)** — not an accuracy claim. Note the two layers: *extraction*
  reconstructs the student's own handwritten indentation from box geometry
  (recognition-independent); *Format* is the on-demand override to canonical C
  structure on the text. 13 unit tests in `code-editor.spec.ts` (each rule,
  brace-depth regression, grade-safety, idempotency); web suite 50/50.

---

## 12. Counterfactuals — "what happens if you change this?"

Panels love this question form. For each critical block: the current
code, the change they might propose, and the concrete consequence —
using real observed data where possible. Practice answering these
*before* reading the consequence.

**One command, three metrics — read every "run `evaluate_cer`" step below
this way.** `python -m evaluators.evaluate_cer` always prints CER, WER, *and*
token-level recognition accuracy together in one table (§6) — it is not
three separate commands. Wherever a "What's next" step below says to check
"the CER" after a change, that's shorthand for reading the whole printed
table: WER can move without CER moving (WER fails an *entire* word on one
wrong character, so it's more sensitive to certain kinds of errors), and
token accuracy is scored on C-lexical tokens rather than characters, so it
can disagree with both. Judging a change on CER alone can miss a real
regression the other two would have caught — always glance at all three
columns, not just `clean_ws`.

**If asked to actually make a change live (skill test), don't just cite the
consequence below from memory -- demonstrate it, in this order, fastest check
first:**

1. **Unit tests** — `.venv/bin/python run_tests.py` (or `-v`). Catches a
   change that breaks an assumption another part of the pipeline relies on
   (e.g. a grouping test, a cleanup boundary test). Seconds to run; do this
   first, always.
2. **Single-image visual check** — `.venv/bin/python try_config.py <image path>`
   (add `--adaptive-denoise` to toggle that pass). Prints the average
   confidence and the exact cleaned text for one image, so you can see *what
   changed in the actual output*, not just a number, before committing to a
   full run. Use one of the `samples/<paper_type>/` images so there's ground
   truth to eyeball against.
3. **Full metric check** — `.venv/bin/python -m evaluators.evaluate_cer`.
   Reports CER, WER, and token accuracy on all 20 held-out `samples/` images
   against their physically-verified ground truth, broken down **by paper
   type and by writer**, not just an overall average. Always check the
   per-group breakdown, not only the headline number: a change can improve
   the average while quietly hurting one paper type (see §12.7/12.8's
   retracted-ablation note on exactly this mistake) — that's specifically
   why per-group rows exist.
4. **The web app itself, against the physical paper** — since the actual
   product surface is "extract text, teacher checks it against the paper
   they're holding," the ultimate check is running the real app end-to-end
   on a captured image and reading the result next to the physical sheet, the
   same way a teacher would. This catches things the automated metrics can't
   — e.g. a change that scores fine on `clean_ws` CER but produces text a
   human would immediately flag as wrong (a plausible-looking but incorrect
   substitution), or a paper type/lighting condition not well represented in
   the 20-image `samples/` set.

A change is only "verified," not just "theorized," once you've done at least
steps 1 and 3 and can quote the actual before/after numbers — not the
consequence described qualitatively below, which is illustrative, not a
substitute for re-measuring after a real edit.

### 12.0 Worked example — a live preprocessing change (skill-test walkthrough)

Preprocessing has **no simple global setting** the way `REC_SCORE_FLOOR` does,
and that's the point to make first, not apologise for. Denoise strength is
chosen *per page* from measured paper texture (greenbook speckle vs. smooth
bond need different treatment; a single value damages one of them), and
binarization — when on — is computed *per 31×31 neighborhood*, not once
globally, precisely because a global threshold turns a shadowed corner solid
black and destroys the characters in it. So lead with **why it's adaptive**,
then demonstrate a change on the one number that still touches every image.

**The data-backed insight to open with (measured 2026-09-02 on the current
`samples/` set):** the adaptive denoise branch (`adaptive_denoise`,
`textured_paper_threshold=2.2`) **is genuinely active** — it fires on **15 of
20** images. Measured background-noise (`_background_noise`) split, exactly as
the design intends by paper texture:

| paper type | noise range | strength applied |
|---|---|---|
| bond (smooth) | 0.49 – 0.54 | 10 (base) |
| greenbook (textured) | 0.78 – 3.53 | mostly 20; 3 low-noise pages stay at 10 |
| yellow_pad (textured) | 3.17 – 4.52 | 20 (all) |

So you can *show* the adaptive logic working, not just describe it: smooth
bond stays gentle, textured greenbook/yellow gets the stronger treatment,
decided per-image from the page's own measured noise.

> **Note — code comment is now current (fixed 2026-09-04):** an older
> `preprocess.py` comment claimed "every current gate sample scores below the
> trigger (0.50-2.07), branch inert." That was an *older* `samples/` set; the
> current one fires on 15/20, and the comment has been corrected to carry the
> real re-measured A/B numbers (below). Nothing stale left to flag here.

**Say this to open (~30s):** *"Preprocessing is adaptive by design, not global
— denoise strength is chosen per page from measured paper texture, because
smooth bond and textured greenbook need different treatment and one global
value hurts one of them. And it's genuinely working: on our 20 test images, 15
trigger the stronger denoise and 5 don't, split exactly by paper texture. Let
me show what that adaptation actually buys by turning it off."*

**Then run the loop live, narrating each step:**

1. Baseline tests — `.venv/bin/python run_tests.py` — "confirms nothing is
   already broken before I touch anything."
2. Make the edit: in `core/preprocess.py`, `adaptive_denoise: bool = True` →
   `False`. This forces the 15 textured images back to the base strength 10,
   so we can measure what the per-paper adaptation contributes.
3. Single-image visual check, so they see the *actual extracted text* change,
   not just a number. Use one image that fires the branch and one that doesn't:
   `.venv/bin/python try_config.py samples/greenbook/green_writer10_B2_1.jpg`
   (noise 3.19 — was getting 20, now 10) and
   `.venv/bin/python try_config.py samples/bond/bond_writer1_1.jpg`
   (noise 0.49 — was 10, unchanged, a control). Read the printed `cleaned_text`
   aloud — does greenbook get noisier/worse with the weaker denoise?
4. Full metric check — `.venv/bin/python -m evaluators.evaluate_cer` — and
   compare the **by-paper-type** rows to the recognition-only fine-tuned baseline
   this A/B was measured against (overall `0.126`; bond `0.005`, yellow_pad
   `0.071`, greenbook `0.159`) — a *preprocessing* experiment predating the
   two-column split, so its overall reference is 0.126, not the current
   end-to-end 0.099.
   You're testing a *preprocessing* change on top of the same fine-tuned model,
   and you expect bond (a control, unaffected) to stay flat while
   greenbook/yellow may change.
5. **State the real result.** This A/B has now been run for real (2026-09-04,
   fine-tuned model + current 20-image set), so you can present the answer with
   confidence instead of hoping the live run comes out clean. The measured
   result (`clean_ws` CER, ON = shipped vs OFF):

   | group | ON | OFF | Δ |
   |---|---|---|---|
   | **overall** | **0.126** | 0.123 | +0.003 (within noise, n=20) |
   | bond (control) | 0.005 | 0.005 | +0.000 (never fires) |
   | yellow_pad | 0.071 | 0.077 | −0.006 (ON helps) |
   | greenbook | 0.159 | 0.153 | +0.006 (ON slightly worse) |

   **The honest reading:** adaptive_denoise is **~neutral** on gate-framed
   input — it does not degrade accuracy (the +0.003 overall is noise at this
   sample size), it *helps* the worst-textured paper (yellow), and the bond
   control stays flat exactly as predicted (branch never fires there). This is
   the strong, defensible finding: you verified the step rather than asserting
   it, and you can state plainly that it's neutral-to-helpful and kept on
   because 0.126 is the validated/released number the fine-tuned model trained
   through. Reading a neutral result honestly beats a scripted "it improved."
6. Revert: `adaptive_denoise` back to `True`, re-run `run_tests.py` to confirm
   you're at baseline, leave the repo clean.

The panel is grading whether you understand the architecture (why adaptive, not
global), can verify a claim instead of asserting it (the loop above), and can
reason about a real result — not whether a number moved the "right" way on cue.

### 12.1 The confidence floor

`core/ocr_pipeline.py:132`

```python
# current
REC_SCORE_FLOOR = 0.3
```

**Try it (pick one, edit the line, then run the 4-step loop from §12.0):**

```python
# new — filter off
REC_SCORE_FLOOR = 0.0

# new — raised
REC_SCORE_FLOOR = 0.6   # or 0.9
```

**What's next after editing, and the actual confirmed result (2026-09-06):**
`run_tests.py` first — **correction: this constant does have a direct test**,
found by actually running it rather than assuming: lowering to `0.0` fails
`test_recognize_preprocessed_preserves_page_order_and_debug_data`, which
plants a fake phantom fragment `"dust"` at score `0.2` and asserts it's
dropped. With the floor at `0.0` it survives and the assertion fails —
concrete, executed proof of the "phantom returns" claim below, not just a
prediction. Then `evaluate_cer`: confirmed the sweep's existing "inert
0.0–0.5" claim — clean_ws moved from `0.126` to `0.127`, i.e. materially
unchanged. Revert, re-run `run_tests.py` to confirm 81/81 again.

**If lowered to 0.0 (filter off):** the two observed phantoms come
back — a stray `'2'` (score 0.127) appears inside a student's code,
and a `'↓'` arrow mark (0.294) becomes a character in the output.
Content that isn't writing gets graded as writing.

**If raised to 0.6:** now it deletes real student writing — observed
detections like `'N'` at 0.387 (real content in sample 005) would be
silently discarded. In a grading app, silently deleting student work
is *strictly worse* than showing a phantom the teacher can delete.
That asymmetry (deletion worse than noise) is why the floor sits low,
just above the phantom band (≤0.294 observed) and far below real
writing (0.7+ typical, 0.387 worst observed).

**If raised to 0.9:** whole correct lines vanish — `int main ()`
scored 0.846 on a *clean* sample.

### 12.2 Median vs mean line height (grouping)

`core/layout/__init__.py` (in `_group_detection_records`; moved from
`ocr_pipeline.py` in the 2026-09-13 split)

```python
# current
heights.sort()
median_h = heights[len(heights) // 2] if heights else 0.0
line_tol = max(median_h * 0.6, 1.0)
```

**Try it:**

```python
# new — median -> mean
heights.sort()
mean_h = sum(heights) / len(heights) if heights else 0.0
line_tol = max(mean_h * 0.6, 1.0)

# new — tolerance widened
line_tol = max(median_h * 1.2, 1.0)

# new — tolerance narrowed
line_tol = max(median_h * 0.2, 1.0)
```

**What's next, and the actual confirmed result (2026-09-06) — a genuine
surprise:** `run_tests.py` on the mean-vs-median swap **passed 81/81,
unchanged.** No existing fixture happens to contain the outlier-height case
this design choice defends against, so the theoretical risk (one tall box
poisoning the tolerance) doesn't manifest in current test data — a real,
worth-naming coverage gap, not proof the swap is safe in general. More
surprising: `evaluate_cer` showed a slight *improvement*, not a regression —
clean_ws `0.126` → `0.123`, driven mostly by greenbook `0.159` → `0.155`.
**Read this carefully before citing it:** this does not mean mean is better
than median — it means the current 20-image cohort has no case where an
outlier detection height actually occurs, so this specific run can't
distinguish the two approaches on robustness; the median's defensive
rationale (resistant to one bad box) stands on the code's own logic
regardless of what this one sample set shows. State the measured result
honestly (no regression, mild improvement, no test broken) rather than
either the original "should break a test" prediction or an overclaimed "mean
is better." Revert, confirm `run_tests.py` passes.

**Decision (2026-09-06): do not actually ship this swap, and here's the
reasoning to give if a panelist suggests it live.** Three reasons, not one:
(1) `0.003` on `n=20` is within-noise by this project's own established
standard — the exact same magnitude on `adaptive_denoise` was explicitly
labeled "within noise... NOT a real regression" elsewhere in this doc, so
treating an equally small median→mean delta as a real win would be
inconsistent with that standard. (2) Median's defensive value (resisting one
outlier-height box) is a property of the *code's logic*, not something this
test set can confirm or rule out — "no counter-example exists yet" isn't
evidence the guard is unnecessary, only that this sample can't exercise it.
(3) The citable `0.126` figure was measured, and the fine-tuned recognizer
was trained, against the pipeline exactly as it stands with median grouping
— changing this now would detach the number you'd defend from the code that
actually produced it, for a change whose benefit is statistically
indistinguishable from zero. If asked "did you consider this," the strong
answer is exactly this three-part reasoning, not silence and not the
raw 0.126→0.123 number alone.

**If `median` → `mean`:** one outlier detection poisons the
tolerance. Real case: a large curly brace or a tall smudge detection
(observed boxes: most ~35 px tall, one `'3'`-for-`}` box 50 px). With
a mean, that one tall box inflates `line_tol`, and two *separate*
handwritten rows start merging into one line. Median ignores the
outlier entirely.

**If `0.6` → `1.2`:** adjacent rows whose centers sit within one line
height merge — on sample 002, `int result = add (3,4);` (center
y≈288) and `printf(...)` (center y≈334) are ~46 px apart with ~40 px
median height: at tolerance 1.2×40=48 they'd merge into one garbled
line. At 0.6×40=24 they stay separate. **This is a real example you
can cite from the debug JSON.**

**If `0.6` → 0.2:** a single wavy row fragments — the sloped-line
tests (`test_keeps_a_sloped_handwritten_line_together`) fail, and the
original scattered-fragments bug returns.

**Why `max(..., 1.0)`:** if all boxes were degenerate (tiny heights),
tolerance 0 would put every fragment on its own line; the 1.0 floor
keeps the comparison meaningful.

### 12.3 The malformed-box fallback

`core/layout/__init__.py` (in `_group_detection_records`; moved from
`ocr_pipeline.py` in the 2026-09-13 split)

```python
# current
except (TypeError, IndexError, ValueError, OverflowError):
    # Malformed box -> don't risk regrouping; keep original order.
    return _original_detection_records(rec_texts, rec_scores), False
```

**Try it:**

```python
# new — let it raise (remove the except)
# (delete the try/except wrapper entirely so the exception propagates)

# new — skip the bad box instead of falling back whole
except (TypeError, IndexError, ValueError, OverflowError):
    continue  # drops this fragment's text instead of preserving it
```

**What's next:** `run_tests.py` — the malformed-box unit test
(`test_ocr_pipeline.py`) feeds a deliberately bad box and asserts every
fragment's *text* still comes back; the "skip" variant should fail that
assertion immediately (content silently disappears), which is the concrete
proof of why "do nothing clever" beats "try to be helpful." The "let it
raise" variant needs no test to see the problem — call the function directly
with a malformed box and watch it crash instead of degrading gracefully.
Malformed boxes are rare in real PaddleOCR output, so `evaluate_cer` on the
20-image set likely won't move either way — that null result is itself worth
stating out loud rather than skipping the check. Revert before moving on,
re-run `run_tests.py` to confirm baseline.

**If removed (let it raise):** one bad box from PaddleOCR crashes the
whole extraction — teacher gets an error instead of text.

**If replaced with "skip the bad box":** worse — the fragment's *text*
silently disappears from the output (student content deleted).

**Current behavior:** give up on *reordering only*, keep every
fragment in original order. Degrades layout, never content. This
"when metadata is unreliable, do nothing clever" pattern repeats
through the whole file — same reason the score filter passes
unparseable scores through.

### 12.4 Literal shielding in cleanup

`core/c_code_cleanup.py:79-82`

```python
# current
for match in C_LITERAL.finditer(text):
    out.append(_fix_segment(text[last:match.start()]))  # fix between
    out.append(match.group(0))                          # literal untouched
    last = match.end()
out.append(_fix_segment(text[last:]))
fixed = "".join(out)
```

**Try it:**

```python
# new — run fixes on the whole text, no shielding
fixed = _fix_segment(text)
```

**What's next, and the actual confirmed result (2026-09-06):** `run_tests.py`
first — confirmed `test_preserves_string_and_character_literals` fails
immediately, exactly as expected. The one-liner also confirmed exactly:
`clean_c_code('printf("1nt is a typo");')` returns
`printf("int is a typo");` under the unshielded version — the concrete
grading-integrity violation, not just an abstract risk. Then `evaluate_cer`:
**measured no CER movement at all** (`0.126` unchanged) — none of the 20
held-out samples happen to contain a `FIXES`-lookalike inside a string
literal, so this is a genuine null result on the current cohort, not
evidence the change is safe in general (a single crafted example already
proved the bug; the full sweep just confirms this particular test set
doesn't happen to contain a real-world instance of it). Revert, re-run
`run_tests.py`.

**If removed (run fixes on the whole text):** a student who wrote
`printf("1nt is a typo")` gets their string silently changed to
`"int is a typo"` — the app has now altered graded content inside a
string literal, violating the project's hard rule. The shielding is
what makes the cleanup defensible at all.

### 12.5 Whole-token boundaries in cleanup

`core/c_code_cleanup.py:62`

```python
# current
pattern = r"(?<![\w#])" + re.escape(wrong) + r"(?![\w])"
```

**Try it:**

```python
# new — plain substring replace, no boundaries
segment = segment.replace(wrong, right)

# new — \b instead of the custom lookaround
pattern = r"\b" + re.escape(wrong) + r"\b"
```

**What's next, and the actual confirmed result (2026-09-06):** `run_tests.py`
on the plain-replace variant — **correction: the real failing tests use
`my1nt`, `ma1n_value`, and `pr1ntf_count`, not `po1nt`** (that name doesn't
appear anywhere in `test_c_code_cleanup.py` — checked directly rather than
assumed). `test_preserves_ordinary_identifiers` and
`test_corrects_only_known_whole_tokens` both fail immediately; a one-liner
confirms the mangling concretely: `int po1nt = 5;` → `int point = 5;`. For
the `\b` variant, a one-off call pinpoints the *actual* failure mode more
precisely than "misbehaves": `\b` requires a transition between a word and
non-word character, and at the very start of a string, both "before the
string" and `#` count as non-word — so `\b` never matches there at all.
Confirmed: `#inc1ude <std1o.h>` under `\b` leaves `#inc1ude` completely
unfixed (the fix silently fails to fire), rather than firing somewhere
incorrect. Revert both, confirm `run_tests.py` passes.

### 12.6 Cleanup pass order

`core/c_code_cleanup.py:76-90` (`clean_c_code`)

```python
# current
# 1) Keyword pass, shielding string/char literals from replacement.
out = []
last = 0
for match in C_LITERAL.finditer(text):
    out.append(_fix_segment(text[last:match.start()]))
    out.append(match.group(0))
    last = match.end()
out.append(_fix_segment(text[last:]))
fixed = "".join(out)

# 2) Then normalize #include lines.
return "\n".join(_fix_include_line(line) for line in fixed.split("\n"))
```

**Try it:**

```python
# new — reversed order: includes first, then keywords
fixed = "\n".join(_fix_include_line(line) for line in text.split("\n"))
out = []
last = 0
for match in C_LITERAL.finditer(fixed):
    out.append(_fix_segment(fixed[last:match.start()]))
    out.append(match.group(0))
    last = match.end()
out.append(_fix_segment(fixed[last:]))
return "".join(out)
```

**What's next, and the actual confirmed result (2026-09-06):** `run_tests.py`
first — **correction: two tests DO catch this**, found by running it rather
than assuming: `test_normalizes_known_headers` and `test_cleanup_is_idempotent`
both fail under the reversed order. The visual confirmation matches the
predicted mechanism exactly: `clean_c_code('#include < std1o.h')` under the
reversed order returns `'#include < stdio.h'` — `std1o` gets fixed by the
(now-second) keyword pass, but the include line was already checked and
rejected by the (now-first) include pass while it still read `std1o`, so the
line never gets snapped to the canonical `#include <stdio.h>` form. Both
pieces of evidence (test failure and one-liner) agree, so `evaluate_cer` on
the full set wasn't run for this one — the unit test already gives a
concrete, sufficient proof. Revert, confirm `run_tests.py` passes again.

### 12.7 Adaptive vs global threshold

`core/preprocess.py:190-196`

```python
# current
processed = cv2.adaptiveThreshold(
    processed,
    255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,
    block_size,
    config.threshold_c,
)
```

**Try it:**

```python
# new — global Otsu threshold instead of adaptive
_, processed = cv2.threshold(
    processed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
)
```

**Critical caveat found by actually running this (2026-09-06): this whole
block is dead code under the shipped default.** `PreprocessConfig.threshold`
defaults to `False` (binarization is off by default, per the
`binarization-off-by-default` finding), and this `cv2.adaptiveThreshold` call
sits inside `if config.threshold:` — confirmed empirically: making this exact
edit and running `evaluate_cer` (which uses `DEFAULT_CONFIG`) produced a
byte-identical `clean_ws 0.126`, because the branch never executed either
way. **If you only run `run_tests.py` and `evaluate_cer` as usual, you will
see nothing, and wrongly conclude the change is safe or a no-op** — the real
test requires forcing `threshold=True` explicitly, the way `compare_config.py`
does.

**What's next, correctly this time:** `run_tests.py` first as a baseline (no
pixel-level test exists for this branch — a real coverage gap). Then force
the comparison directly, since the default config can't see it:
```python
from core.preprocess import PreprocessConfig
from core.ocr_pipeline import extract_text_from_image
cfg = PreprocessConfig(threshold=True)
extract_text_from_image('samples/greenbook/green_writer10_B2_1.jpg', preprocess_config=cfg)
```
**Actual measured result on that sample:** adaptive gave confidence `0.916`
and read `#include <stdio.h>` cleanly; Otsu gave confidence `0.914` (close)
but produced visibly more garbled text on the same page (`#include stdio.
n> x %. 2 = 00;` vs adaptive's correct line) — confirming adaptive is the
better choice when binarization is actually on, even though this doesn't
affect the shipped pipeline's headline `0.126` number at all today, since
binarization is off. Revert, re-run `run_tests.py`.

**If replaced with a global threshold (e.g. Otsu):** works on evenly
lit captures, but a phone capture with a shadow gradient (observed on
the real uploads — the uneven-lighting cases at 0.77–0.80 confidence)
pushes the shadowed region below one global cutoff: that corner turns
solid black and every character in it is destroyed before the OCR
ever sees it. Adaptive computes the cutoff per 31×31 neighborhood, so
a shadow only shifts the local baseline.

**If threshold removed entirely, or denoise removed entirely:** the
specific percentages once cited here (+39%, +34%, from a "7 real
captures" comparison) were part of the retracted ablation — see §3's
note. The later 2026-08-02 paper-type ablation is also retracted as accuracy
evidence. It remains reasonable to hypothesize that global settings interact
with paper texture, but the claim that every tested method helped one paper
type while hurting another must be remeasured against literal labels. The
standing methodological rule survives: never tune against one convenient set;
use valid, provenance-backed per-paper and per-difficulty evaluation.

### 12.8 Denoise strength, made paper-adaptive

`core/preprocess.py:171-172` (branch) and `:90-92` (config)

```python
# current
if config.adaptive_denoise:
    if _background_noise(processed) >= config.textured_paper_threshold:
        strength = config.textured_denoise_strength   # 20
```

**Try it:**

```python
# new — turn adaptation off (force base strength everywhere)
# in PreprocessConfig:
adaptive_denoise: bool = False

# new — lower the trigger threshold so it fires on smoother pages too
textured_paper_threshold: float = 1.0
```

**What's next:** `run_tests.py` first, as always, even though this constant
has no dedicated unit test. This is the one entry with a real, already-run
A/B in §12.0 — `adaptive_denoise=False` measured `clean_ws` overall
0.126→0.123 (within noise), bond flat (control, never fires), yellow_pad
worse (0.071→0.077), greenbook slightly better (0.159→0.153). Reproduce that
exact result yourself: flip the flag, run `evaluate_cer` (check the WER/token
accuracy columns too, not just `clean_ws`), compare your per-paper-type
numbers to those four values before touching anything else.
For the lowered-threshold variant, first print `_background_noise()` for a
few bond samples (§12.0's table: bond sits 0.49–0.54) to see which ones
would newly cross a 1.0 trigger, then re-run `evaluate_cer` and check
whether bond (previously a flat control) moves. Revert both, confirm
`run_tests.py` passes.

### 12.9 Download retry policy

`main.py:97-103` (`download_image`)

```python
# current
except HTTPException:
    # A non-200 status is not a transient error; don't retry it.
    raise
except requests.RequestException as exc:
    # Network/timeout error: worth retrying.
    last_error = exc
```

**Try it:**

```python
# new — retry everything, including HTTP errors
except (HTTPException, requests.RequestException) as exc:
    last_error = exc
    continue

# new — retry nothing
except (HTTPException, requests.RequestException) as exc:
    raise
```

**What's next:** `run_tests.py` first, always, even here — this touches
error-handling logic that other code may assume behaves a certain way, so
confirm nothing existing breaks before reasoning about the new behavior.
Then point `image_url` at a URL that returns a real 403/404 (a Supabase path
with a bad token works) and time the request. "Retry everything" should
visibly take ~3x as long to fail (3 attempts against a non-transient error)
— a stopwatch is the real test here, since this changes *timing/behavior*,
not recognized text, so `evaluate_cer` has nothing to say about it and isn't
part of this one's verify loop. "Retry nothing" needs a flaky-network
simulation to observe (harder to force locally); the code-reading argument
(one dropped packet fails the whole extraction) is the practical way to
defend it live. Revert, re-run `run_tests.py`.

**If everything were retried:** a 403 (bad/expired URL) or 404 gets
hammered 3 times, tripling the teacher's wait for an error that was
never going to succeed.

**If nothing were retried:** one Wi-Fi hiccup on a 5 MB download
fails the whole extraction. The split — retry what time can fix,
fail fast on what it can't — is the entire design.

### 12.10 Warmup exception swallowing

`core/ocr_pipeline.py:108` (`warmup`)

```python
# current
try:
    ocr.predict(dummy)
except Exception:
    # Warm-up is best-effort; a failure here must never block startup.
    pass
```

**Try it:**

```python
# new — let it raise
ocr.predict(dummy)   # no try/except at all
```

**What's next, and the actual confirmed result (2026-09-06):** `run_tests.py`
first — confirmed 81/81 pass regardless, genuinely no dedicated test for
this one (unlike the surprise in 12.1). Then force a failure to make the
consequence real rather than theoretical — swap `ocr` for a stub object
whose `.predict()` raises, then call `warmup()` directly:
```python
import core.ocr_pipeline as m
class Boom:
    def predict(self, x): raise RuntimeError("simulated model load glitch")
m.ocr = Boom()
m.warmup()
```
**Confirmed:** with the `except` in place, this returns normally (the
failure is swallowed, exactly as designed). Removing the `except` and
re-running the same stub call: **confirmed** it raises
`RuntimeError: simulated model load glitch` straight out of `warmup()` —
which `main.py`'s `lifespan` hook calls at startup, so this would crash
server boot. This one has no `evaluate_cer` step: it changes nothing about
recognition, only startup robustness, so CER/WER/token accuracy have
nothing to say about it (don't conflate this with the separate
first-extraction-after-restart timing question — that was live-tested this
session and traced to page content length, not warmup state). Revert, re-run
`run_tests.py`.

**If the except were removed:** any transient warmup failure (model
download glitch, first-run cache issue) crashes the server at
startup. Current behavior: server always starts; worst case the first
real request pays the initialization cost. A panel may flag bare
`except Exception` as a smell — the answer is that it's deliberate
and scoped: *this* failure class must never block startup, and the
comment says so.

### 12.11 The save-path fix (web)

`maistra_web/src/app/services/supabase.ts:80-82` (`updateSubmissionText`)

```typescript
// current
const update: Record<string, unknown> = {
  verified_text: verifiedText,
  status: 'verified',
  verified_at: new Date().toISOString(),
};
if (extractedText !== undefined) {
  update['extracted_text'] = extractedText;
}
```

**Try it:**

```typescript
// new — always write (Bug 5's original shape)
const update: Record<string, unknown> = {
  verified_text: verifiedText,
  extracted_text: extractedText,   // undefined when no extraction ran
  status: 'verified',
  verified_at: new Date().toISOString(),
};
```

**What's next:** `ng test` first — the web equivalent of `run_tests.py`,
run before touching anything, to confirm the baseline suite is green. Then
make the edit and run it again: it will very likely **still pass**, and
that's the actual finding to state out loud, not a reason to skip the rest
of the loop — grepping `submissions-list.spec.ts` confirms no existing test
asserts on the `extracted_text` column's value after a save, so this is a
real, currently-open test-coverage gap, exactly the kind this doc's own
philosophy says to name rather than let hide. Because the unit suite can't
catch it, the real verification is manual: save a submission through the UI
*without* clicking Extract first (open one already sitting in "verified" or
"ready to grade" and just re-save). Under the new code, watch the
`extracted_text` column in Supabase get overwritten with `null`/`undefined`,
erasing whatever OCR output was stored there — confirm either directly in
Supabase's table editor, or by re-running `export_dataset.py` afterward and
seeing `extracted_text` come back empty for that row. This is also citable
directly: Bug 5 already happened for real (7 rows before the fix are
unrecoverable), so you can narrate it as history, not hypothesis, before
reverting. No `evaluate_cer` step applies here — this is a database write
path, not recognition, so CER/WER/token accuracy can't see it either.

**If the `if` were removed (always write):** `extracted_text` gets
`undefined`/null on every save where extraction didn't run this
session — wiping stored OCR output with nothing.

**If it reverted to the old `updateSubmissionText(id, text, text)`:**
Bug 5 returns — every verification overwrites the OCR's output with
the teacher's text, all real-world CER measurements read a false
0.000, and the fine-tuning error analysis loses its "what did the
model actually say" column. (This actually happened; the 7 pre-fix
rows are unrecoverable.)

### 12.12 Whitespace normalization in CER

`evaluators/evaluation.py:121-123`

```python
# current
def normalize_ws(text: str) -> str:
    """Collapse whitespace so recognition can be scored without formatting."""
    return " ".join(text.split())
```

**Try it:**

```python
# new — no-op (strict-only scoring, no normalization)
def normalize_ws(text: str) -> str:
    return text
```

**What's next, and the actual confirmed result (2026-09-06):** `run_tests.py`
first — `test_evaluation.py` has a direct unit test on `normalize_ws()`, and
it fails immediately as expected. **Bonus finding from actually running
it, not in the original prediction:** a *second*, different test also
breaks — `test_skips_normalized_matches_and_lists_ids_in_warning` in
`test_export_dataset.py` — because the dataset-export contamination guard
also calls `normalize_ws()` to detect re-captures of the same page. This
function has two independent consumers, not one; both would need re-checking
after a real change here. Then `python -m evaluators.evaluate_cer`: measured
exactly as predicted — `clean_ws` became byte-identical to `clean_strict`
(`0.272` both), while `AVERAGE WER/TOKEN-ACC` stayed completely unchanged
(`0.354`/`0.696`, identical to baseline) — confirming `tokenize_c`'s tokens
already ignore whitespace by construction (§6), so this really is a
CER-specific concern, not a general one. Look specifically at a sample where the
teacher's saved formatting differs in indentation/line breaks from a literal
transcription; that row's strict CER should jump while its actual
character-recognition correctness hasn't changed at all — the concrete
demonstration of why counting whitespace as an error would be measuring
formatting, not recognition. Revert, re-run `run_tests.py`, and confirm the
printed table matches the known baseline again.

**If dropped (strict only):** the metric punishes indentation and
line-break differences as if they were misread characters. The historical
sample-001 0.195 strict vs 0.149 normalized values are canonical-reference
diagnostics, not accuracy, but they illustrate what the two formulas count.
Do not use that row for tuning until its literal reference is revalidated.

**If applied to grading (not just measurement):** different story —
never alter the stored text; normalization exists only inside the
metric computation.

---

## 13. Glossary (terms you should use correctly without hesitation)

- **CER** — character error rate; edit distance ÷ reference length.
- **Levenshtein distance** — min single-char edits between strings.
- **Detection vs recognition** — finding text boxes vs reading their
  contents; separate models in PaddleOCR.
- **Adaptive thresholding** — per-neighborhood binarization threshold;
  robust to uneven lighting, unlike a global (Otsu) threshold.
- **Non-local means denoising** — averages similar patches across the
  image; preserves edges better than local blurs.
- **Confidence score** — recognizer's probability-like score per
  detection; used for the phantom floor and quality calibration.
- **Phantom detection** — detector firing on a smudge/mark that isn't
  writing.
- **Ablation** — removing one component at a time to measure its
  contribution.
- **Ground truth** — a literal character-for-character human transcription of
  the source paper with provenance. An intended prompt, canonical solution, or
  `status='verified'` value is not sufficient by itself.
- **Fine-tuning** — continuing training of a pretrained model on
  domain data (handwritten C) to specialize it.

---

## 14. Binarization rescue attempts (2026-08-25 investigation)

> **Re-measured on the FINE-TUNED model 2026-09-04:** the numbers in this
> section are the *stock* model. On the shipped fine-tuned recognizer + current
> 20-image test set, binarization is a *stronger* no-go: `clean_ws` **0.126
> (grayscale) → 0.218 (binarized), +0.092 worse**, hitting 19/20 files
> (greenbook worst, +0.124). Larger penalty than stock (+0.052) because the
> model was trained on grayscale crops, making binary input out-of-distribution.
> Full table: EVALUATION.md top banner. So the "why not binarize?" answer is now
> backed by a measurement on the *actual deployed model*, not just the stock one.

Prompted by an advisor question ("why not binarize?"), this investigation
tried to find *any* way to make binarization competitive with the shipped
grayscale + denoise default, before concluding it's structurally unfixable
for this dataset. All tests below ran against real images with real
PaddleOCR output (scratchpad-only scripts, not committed to the repo —
none of these changed `core/preprocess.py`). Use this section as the
answer to "did you just assume binarization was worse, or test it?"

**Baseline restated:** grayscale + denoise (shipped default) beats plain
adaptive-threshold binarization on CER; see §6 and §12.7. Six follow-up
attempts tried to close that gap:

1. **Denoise before binarizing** (grayscale → denoise → adaptive
   threshold, instead of binarizing raw grayscale). Visually cleaner —
   less speckle — but OCR accuracy still lands worse than grayscale +
   denoise alone. The threshold step itself is what destroys thin-stroke
   and anti-aliasing information; a cleaner starting point doesn't change
   what happens at the moment of thresholding. This is why the codebase's
   binarized path exists only as a comparison/demo artifact, not
   something that reaches the shipped OCR call.

2. **Morphological opening** on the binarized output (small-kernel erode
   → dilate, meant to knock out isolated speckle pixels while leaving
   connected strokes intact). Failed: thin handwritten strokes are close
   enough to speckle-scale that opening erodes real ink along with noise.

3. **Connected-component filtering, with background** (`cv2.connected
   ComponentsWithStats`, filtering components by pixel-area to drop
   "noise-sized" blobs). Failed: wood-grain texture and shadow artifacts
   produce components in the *same* size class as real strokes and
   character fragments, so no area threshold separates them cleanly.

4. **Connected-component filtering, background-free control** (same
   method, re-run on a genuinely clean background image, to rule out
   "maybe it only fails because of texture"). Still lost to grayscale +
   denoise — confirms the failure is inherent to CC-filtering thin
   handwritten strokes, not just a texture-interaction artifact.

5. **Hough-line ruled-line suppression** (`cv2.HoughLinesP`, strict
   length + near-horizontal angle filter, targeting only long
   page-spanning segments — i.e., printed ruling, not glyph strokes —
   painted out of the grayscale image before thresholding). Failed:
   handwriting that crosses a ruled line breaks the line into short
   segments indistinguishable from real strokes, so the length filter
   either misses the ruling or clips through real ink.

6. **Adaptive threshold itself** — already the shipped implementation
   (`ADAPTIVE_THRESH_GAUSSIAN_C`, dynamic block size via
   `threshold_block_scale`; §12.7–12.8). Confirms the codebase isn't
   comparing against a strawman global/Otsu threshold — the adaptive
   version is what loses to grayscale + denoise.

**Conclusion:** the noise (wood grain, shadow, ruled lines) and the
signal (thin handwritten strokes) occupy the same pixel-size and
intensity range on this dataset. Every rescue attempt that tried to
separate them post-hoc — by size, by shape, by line geometry — removed
real ink along with noise, because there's no threshold-independent
feature that cleanly distinguishes the two. This is a structural property
of the dataset (handwriting on textured/lined paper, phone-photographed
under variable lighting), not a tuning gap. See also §6 and §12.7 for the
domain distinction (printed docs: uniform stroke width, high ink/paper
contrast, no meaningful anti-aliasing signal to protect — binarization is
safe there; handwritten, photographed pages: none of those hold).

**Fine-tuning does not change this recommendation.** Fine-tuning improves
the *model's* contextual judgment (e.g. resolving an ambiguous glyph from
surrounding context); it cannot recover pixel information binarization
already deleted before the model sees it. Grayscale + denoise remains the
shipped preprocessing regardless of whether the model is fine-tuned.

### 14.1 Deskew / orientation — three distinct questions, closed separately

The word "deskew" was disambiguated into three different corrections
during this investigation, each tested on its own merits:

- **Whole-page geometric skew** (the page photographed at an angle) —
  out of scope for OCR preprocessing; this is the capture/quality gate's
  job (angle check before a page is accepted), not something to correct
  post-hoc in `preprocess.py`.
- **Gross per-image rotation** — tested with a synthetic known-tilt image
  (Postl projection-profile method, rotate a binarized ink mask across an
  angle range, maximize row-sum variance) and confirmed a working
  estimate/correct round-trip *in principle*. Note: the scratch test's
  final correction step had a sign bug (double-negated the estimated
  angle, producing a more-tilted result) that was never fixed or re-run —
  flagged here so it isn't mistaken for a validated negative result. This
  line of testing was deprioritized because whole-page skew is already
  the gate's responsibility, not because the correction was proven
  ineffective.
- **Per-line baseline slant** (each detected line's own small internal
  tilt, independent of whole-page angle) — measured directly on real
  detected-line crops from production images using the same
  projection-profile method scoped to a small angle range. Result:
  negligible on real data (mean/max slant near zero across sampled
  lines) — nothing to correct, so no per-line slant-correction step was
  added.
- **`use_textline_orientation`** (PaddleOCR's built-in per-crop
  orientation classifier, off in production — see `ocr_pipeline.py`
  module-level `PaddleOCR(...)` construction) — tested on/off head-to-head
  through the real `extract_text_from_image` pipeline on multiple images
  including a synthetically tilted one. Produced no change in output text
  or confidence on the tested images; left off, consistent with the
  existing comment that captures are already gated upright/flat by the
  mobile app.
- **All three flags ON together — full-test-set CER measurement
  (2026-09-02).** The earlier test above was `use_textline_orientation`
  *alone*, qualitative, on a few images. This one enabled **all three**
  (`use_doc_orientation_classify`, `use_doc_unwarping`,
  `use_textline_orientation`) and ran the full `evaluate_cer` on the 20-image
  `samples/` set against the fine-tuned recognizer. Result — a clear
  **regression**, not just wasted compute:

  | group | flags OFF (shipped) | all-three ON | change |
  |---|---|---|---|
  | overall | 0.126 | **0.177** | +40% worse |
  | **bond** | 0.005 | **0.455** | **~91× worse** |
  | greenbook | 0.159 | 0.167 | +5% |
  | yellow_pad | 0.071 | 0.074 | ~same |

  Bond (smooth, plain white, few layout cues) is destroyed: the
  page-orientation / de-warp models (`PP-LCNet_x1_0_doc_ori`, `UVDoc`)
  mis-correct an already-upright, already-flat page — rotating or warping it —
  and scramble the text the recognizer then reads. Since `textline_orientation`
  alone was separately shown neutral (bullet above), the regression is
  attributable to the two **page-level** passes, not the per-line one. This
  is the *quantitative* confirmation the earlier qualitative test lacked: on
  gate-validated input these passes cost ~80s/image **and** actively hurt
  accuracy, which is why all three stay off. (Not isolated flag-by-flag —
  the aggregate all-three-ON result was enough to settle the design question.)

### 14.2 Shadow removal and bleed-through suppression — 0-for-2

Two enhancement ideas raised from a specific bad-capture example (a photo
with a visible hand/phone shadow) were tested more broadly, not just on
the triggering image:

- **Shadow removal** (illumination normalization to flatten uneven
  lighting before grayscale/denoise) — tested on the shadowed image it
  was proposed for (improvement plausible there) but also on a
  *non-shadowed* clean image, where it altered brightness/contrast
  without any shadow present to remove, changing OCR output for the
  worse. No case found where it reliably helps and no clear trigger
  condition (e.g. "shadow area > X% of frame") to gate it safely. Not
  adopted.
- **Bleed-through suppression** (attenuating ink showing through from the
  reverse side of thin paper) — tested on a bleed-through sample; result
  inconclusive/not a clear win. Flagged as needing a real A/B cohort
  once transcribed label volume exists, rather than a one-image verdict
  — deferred, not adopted or rejected outright.

**Net effect on the shipped pipeline:** none of the six binarization
rescue attempts, the three deskew variants, or the two enhancement ideas
changed `core/preprocess.py` or `core/ocr_pipeline.py`. Grayscale +
denoise, adaptive threshold available-but-off, and all three PaddleOCR
orientation flags off remain exactly as documented in §3–§4. This section
exists to show the negative results were earned empirically, not assumed.

### 14.3 External literature reviewed (2026-08-25) — how to cite each one correctly

Two outside sources were pulled in during this investigation, specifically
to answer "is this a known, documented tradeoff, or just something we
happened to measure once?" Neither replaces this project's own CER
measurements (§6, §12.7, §14) — both are framing/corroboration, cited here
with the precision needed to not overclaim them to a panel.

**Villegas, Romero, Sánchez (2015), "On the Modification of Binarization
Algorithms to Retain Grayscale Information for Handwritten Text
Recognition"** (Springer, `10.1007/978-3-319-19390-8_24`). Full text is
paywalled/blocked everywhere it was checked (scispace, academia.edu,
Springer itself) — **only the abstract is confirmed**, not the paper's
results or numbers. The confirmed abstract's premise: standard binarization
loses information handwritten-text recognizers need, motivating the paper's
own proposed fix (modifying binarization algorithms to retain some
grayscale signal for the recognizer). **Correct citation:** the paper's
existence and framing corroborate that binarization's information loss for
handwritten recognition is a recognized problem in the literature, not a
project-specific quirk. **Incorrect citation:** quoting any specific
accuracy number or result from it — those were never verified.

**Ayush Luhar, "Why Traditional Metrics Fail in Image Binarization"**
(Medium, full text obtained via user-provided screenshots, not WebFetch —
the URL 403s). Compares 8 binarization algorithms (Otsu, Niblack, Sauvola,
Wolf, NICK, T.R. Singh, ISauvola, WAN) against a printed-text ground-truth
image using four **pixel-level** metrics (DRD, PBC, NRM, MPM) — it never
runs OCR. Its argument: these metrics don't reliably predict real
downstream usefulness (Otsu wins on every metric while, by the article's
own account, WAN's worse scores reflect it trying harder on fine detail,
not actually performing worse). **Correct citation:** supports the general
claim that pixel-level "looks clean" and actual OCR usefulness are known
to be decoupled — a parallel to, not a duplicate of, this project's own
binarized-but-worse-CER finding. **Incorrect citation:** claiming this
article measured OCR accuracy on handwritten text, or that it's about
grayscale vs. binarization specifically — it's binarization algorithms
compared to each other, on printed text, using non-OCR metrics.

**The load-bearing evidence for this thesis remains this project's own
measured CER** (grayscale+denoise 0.149 vs. binarized 0.201, §6/§12.7) and
the six rescue attempts in §14. Both external sources are corroboration —
useful for "is this a recognized issue in the field," not for "here are the
numbers."
