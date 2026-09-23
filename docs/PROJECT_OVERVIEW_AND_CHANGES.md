# mAIstra Project Overview and Change Log

> **Ownership labels.** Each section below is tagged with its primary contributor(s): **Nikko** (mobile capture), **Jayrald** (web submissions/review UI, Judge0, Supabase), **Nombrado** (OCR pipeline & extraction). *Shared* marks cross-cutting sections. Labels reflect git authorship of the described work.

## Project purpose

mAIstra is a vision-based assessment system for handwritten C programming submissions. It captures student work, stores submission images, extracts C code through OCR, allows a teacher to verify the extracted code, executes it against question test cases with Judge0, and presents grading feedback.

## Main applications

### `maistra_mobile`

> **Owner:** Nikko

The Flutter mobile application captures handwritten submissions, performs a basic image-quality check, uploads images to Supabase Storage, and creates submission records.

### `maistra_web`

> **Owner:** Jayrald (submissions list, review UI, grading); Nombrado (OCR extraction + review highlighting)

The Angular teacher application manages questions and submissions. Teachers can review uploaded images, run OCR, correct extracted code, select the related question, execute code, and inspect test-case and logic results.

### `ocr_feature`

> **Owner:** Nombrado

The Python FastAPI OCR service downloads or accepts submission images, preprocesses them, runs PaddleOCR, cleans recognized C tokens conservatively, and returns review suggestions and confidence information.

### `judge0_api`

> **Owner:** Jayrald

The Python FastAPI Judge0 wrapper submits C code to Judge0, polls for results, decodes output, and provides the grading endpoint consumed by the Angular application.

### `supabase`

> **Owner:** Jayrald

This directory contains local Supabase configuration, schema migrations, seed data, and database exports. Supabase provides PostgreSQL storage, realtime submission notifications, and submission image storage.

## Submission review workflow

> **Owner:** Jayrald (review workflow + **Re-extract** control); Nombrado (OCR extraction backend + the guard stopping Re-extract from overwriting teacher edits, `144f340`)

The Angular submission review uses one existing `SubmissionsListComponent`; no additional visual components were introduced.

1. **Details**
   - Assign a topic or folder.
   - Select the related question.
   - The question is required before continuing.
   - Topic and `question_id` are persisted together.

2. **Review code**
   - Display the original submission image beside the editor.
   - Extract code with the OCR service.
   - Preserve the original OCR result separately from teacher edits.
   - Allow manual correction and formatting.
   - Save verified code before grading.

3. **Run and grade**
   - Execute the verified code through the Judge0 wrapper.
   - For function questions, generate a temporary `main()` test harness.
   - Run all configured test cases.
   - Display output comparison and logic-analysis results.

### Re-extraction: detailed ownership split

The "Re-extract code" flow was built in two clearly separated parts. All paths
below are in `maistra_web/src/app/components/submissions-list/`, verified against
`git blame`.

**Jayrald — the re-extraction capability** (`0133859`, "feat(web): Implement
submissions list and multi-stage review logic"):

- The extract control that doubles as **Re-extract** once text already exists:
  the button label switches between `Extract code`, `Extracting…`, and
  `Re-extract code` based on `hasExtractedText(...)` — `submissions-list.html:204`.
- `performExtract(id)` — the actual OCR call that re-runs extraction and
  overwrites the editor with the fresh result: `POST /api/ocr/extract-from-url`,
  then sets `extractedText[id]` / `editableText[id]` — `submissions-list.ts:320–340`.
  (The `performExtract` wrapper was factored out by Nombrado to insert the guard;
  the HTTP extraction call inside it is Jayrald's.)

**Nombrado — the guardrail** (`144f340`, "Guard Re-extract against silently
overwriting teacher's edits"):

- `extractText()` now checks for unsaved work before re-running: it compares the
  current editor text (`editableText[id]`) against the last extraction
  (`extractedText[id]`); if they differ (`hasEdits`), it opens the confirmation
  dialog instead of extracting, and only a first extraction or an edit-free
  re-extract runs straight through — `submissions-list.ts:289–306`.
- The confirmation dialog itself — *"Re-extract and discard edits? … Your current
  corrections will be lost."* — with `confirmReextract()` / `cancelReextract()`
  handlers and the `reextractConfirmId` state — `submissions-list.ts:308–318`,
  `submissions-list.html:328–348`, styling in `submissions-list.css` (destructive
  confirm button + dialog).
- Effect: re-extraction can no longer silently destroy a teacher's corrections;
  progress loss now requires an explicit confirm. Cancel keeps the edits intact.

**Boundary in one line:** Jayrald made extraction *re-runnable*; Nombrado made a
re-run that would discard edits *ask first*.

## Submission interface changes

> **Owner:** Jayrald

The submission interface was redesigned to make its workflow easier to discover and navigate:

- Added search by student, topic, or question.
- Added filters for Needs OCR, Needs review, Ready to grade, and Graded.
- Replaced image-only thumbnails with cards containing student, question, date, and status information.
- Replaced the overloaded review modal with a larger three-stage workspace.
- Added a visible step indicator and persistent navigation footer.
- Moved question selection into the Details stage.
- Made question selection mandatory before code review.
- Added immediate saving feedback and loading indicators.
- Kept later stages visible but disabled until their requirements are satisfied.
- Made the interface responsive for desktop, tablet, narrow panels, mobile, and short landscape screens.
- Corrected portrait-image sizing so previews use the available width without cropping or distortion.
- Made the Ace editor fill the complete review panel while retaining its default height elsewhere.

## State and reliability decisions

> **Owner:** Shared — Jayrald (Judge0 result maps, execution-source harness, question linking); Nombrado (save-race/destruction guards, OCR-text separation)

The following state is intentionally retained in `SubmissionsListComponent`:

- Save generations prevent an older request from overwriting the result of a newer save.
- Per-save timers prevent stale confirmation timers from clearing current errors or messages.
- Destruction guards prevent asynchronous callbacks from updating a destroyed component.
- Original OCR text remains separate from editable and verified text so teacher corrections do not overwrite the OCR baseline.
- Judge0 result maps keep execution results associated with the correct submission.
- Execution-source helpers remain responsible for building function-question test harnesses.
- Linked Supabase questions are accepted in either object or array form.

## OCR reading-order review fixes (2026-09-10)

> **Owner:** Nombrado

- Both OCR demo scripts default to the existing `samples/greenbook/green_writer10_B2_1.jpg`, resolved relative to each script. Explicit image arguments remain relative to the caller.
- `compare_config.py` resolves CSV ground truth relative to its script directory, by image basename. (The loose-`.txt`-beside-the-image fallback was later removed — commit `d1a4a06` — so `labels.csv` is now the single ground-truth source.) The default recognizer directory is resolved relative to the pipeline file so demos can also run from the repository root; `MAISTRA_REC_MODEL_DIR` overrides are preserved.
- Removed the redundant crossing check in `_detect_two_columns`: the widest coverage-gap midpoint already guarantees no crossing. Detection-count and vertical-span gates remain unchanged.
- The tail-extension search remains intact for the legacy single-line-flag pattern covered by synthetic RBNode/Compressor fixtures. The current gutter trace flags the whole displaced block.
- Historical recognition-only fine-tuning improved samples/ CER from 0.274 to 0.126 (WER 0.359). Current end-to-end results after two-column reading-order handling are clean_ws CER 0.099, clean WER 0.328, and clean token accuracy 0.716. Historical threshold/denoise ablation numbers refer to the earlier reading-order pipeline.
- Demo commands, including the synthetic reassembly before/after selector, are documented in `docs/setup/RUNNING_LOCALLY.md`. These notes remain local and ignored by Git.

## OCR layout reconstruction & suggestions cleanup (2026-09-11/12)

> **Owner:** Nombrado

- **Handwritten indentation reconstruction** (`_assign_indent_levels`): each detected line's box left-edge is turned into leading whitespace, quantized per column in `INDENT_STEP_CHARS` character-widths (character-scale, because a detection box spans a whole word and is ~10× too coarse). Recognition-independent; `clean_ws` CER stays 0.099 (whitespace-normalized), while the whitespace-sensitive raw CER improved 0.257 → 0.176 against the indentation-preserving ground truth.
- **Vertical spacing reconstruction** (`_join_lines_with_vertical_gaps`): blank lines are reinserted where the vertical gap between consecutive lines exceeds the normal line pitch (quantized, capped at `MAX_BLANK_LINES`), so the extraction reproduces the student's blank-line layout. Also whitespace-neutral to `clean_ws`. Two-column pages are handled for free (the left→right seam is a negative gap → no blank lines).
- **Removed the unused OCR-review suggestions backend** (commit `43addce`): `c_code_suggestions.py`, `_build_line_details`, `_attach_suggestion_reasons`, the `line_details`/`review_suggestions`/`review_diagnostics` API fields, the `evaluate_cer` suggestion report, and `suggestion_improves_reference`. The flagging UI it fed lives only on the unmerged experiment branch, so it was dead weight on this branch. Extraction output and CER are unchanged.
- Full end-to-end held-out CER remains **clean_ws 0.099** through all of the above (verified via `evaluate_cer`).

## OCR local-gutter continuations (2026-09-12)

> **Owner:** Nombrado

- `_sever_displaced_regions` runs only when `_detect_two_columns` does not find a column split. The existing two-column path, including the green_writer10 24-left / 23-right split, is retained.
- A continuation requires at least three consecutive visual rows with aligned right fragments and a positive, uncrossed local gutter. The calibrated gap and alignment multipliers remain 0.8 and 1.2; two-row blocks remain unchanged.
- The real pipeline already separates some distant pieces before this pass. Candidate visual rows are therefore reconstructed from detection geometry; only confirmed right pieces move, and the other original rows retain their order. Text and detection objects are preserved, and unsafe geometry produces no change.
- The user approved this extension after fresh real-pipeline A/B extraction against `datasets/verified/labels.csv`: green_writer18_B2_2 clean_ws CER improved **0.515044 → 0.146903**, while green_writer27_B1_3 remained **0.342105 → 0.342105**, with identical cleaned text. These replace the simplified-row-grouper A/B numbers for claims about the live pipeline; the original spec numbers remain historical evidence.
- A preserved 161-artifact replay of the final implementation changed nine pages, all within the independently reproduced candidate set, and preserved every detection. The historical scan's 16/145 classification could not be reproduced: its stated two-row criterion produced 20/141. The held-out 20-artifact replay was unchanged.
- Final real extractions matched the measured prototype exactly, with identical before/after recognition payloads on both spot-check pages. The full Python suite passes 139 tests, including the two real-sample column tests. The legacy tracing test helper bypasses both downstream ordering passes to preserve its tracing-only scope.
- Final live `evaluate_cer` retains clean_ws CER **0.099**, clean WER **0.328**, and clean token accuracy **0.716**. No constant calibration was required.

## OCR banded column detection (2026-09-13)

> **Owner:** Nombrado

- `_detect_banded_column` generalizes the two-column split to a **partial-height** right block — a two-page / side-by-side capture whose continuation fills only the top-right quadrant, where a stray wide line bridges the full-page x-projection so `_detect_two_columns` reports no gutter. It runs **only when `_detect_two_columns` returns None**, so green_writer10 keeps the full-height path (24-left / 23-right, unchanged) and banded never runs on it.
- Pure geometry and grade-safe: it builds a right cluster by x0 (running-median membership, `BAND_X_ALIGN_MULTIPLIER = 2.0` × median width), requires ≥ `MIN_BAND_ROWS = 3` distinct visual rows, and requires a clean, uncrossed gutter within the cluster's own y-band (`BAND_GUTTER_MIN = max(1.5 × median width, 60px)`). If all hold it reads left column fully, then right column fully. Only whole detected pieces move by position — no character is added, edited, split, or dropped — and any degenerate/ambiguous geometry (missing boxes, no clean band, a crossed/negative gutter) returns None, i.e. today's behavior.
- Measured on the real pipeline against `datasets/verified/labels.csv`: `green_writer18_B2_2` clean_ws CER improved **0.147 → 0.042** (ordering only; the residual is recognition error), while `green_writer27_B1_3` stayed **0.342 → 0.342** (its right cluster is short of the row/gutter thresholds). Live `evaluate_cer` is unchanged at clean_ws **0.099**, clean WER **0.328**, clean token accuracy **0.716** — no held-out `samples/` page has this layout, so this is a real-submission-fidelity win, not a headline mover.
- **Severance retirement gate — not retired.** A fresh 162-artifact corpus scan (`outputs/debug/*_preprocessed.json`, replaying grouping with banded disabled vs. enabled) showed banded fires on exactly the one genuine banded page (both copies of green_writer18) with **zero false positives** on the ~145 clean single-column pages, but grade-safely **declines** the 7 `reassemble_example*` structural-reassembly pages (on each the banded gutter is negative — the displaced block overlaps the main text in x, so no clean spatial gutter exists). Because those 7 pages are still moved by `_sever_displaced_regions`, removing severance would change their output, so `_sever_displaced_regions` (and `SEVER_GAP_MULTIPLIER` / `SEVER_X_ALIGN_MULTIPLIER` / `MIN_SEVER_ROWS` / `DisplacedSeveranceTests`) is **retained as a documented, complementary fallback**. The two mechanisms target different shapes: banded = clean spatial column; severance/reassembly = margin-overlap structural block.
- Tests: the full Python suite passes **147** (139 baseline + 9 new `BandedColumnDetectionTests` − 1 obsolete writer18 severance end-to-end test now covered by banded). A trace-cap regression test's fixture gutter was narrowed (300→225px) so it stays a single-column margin-fragment case that banded correctly declines, keeping the `_trace_displaced_region` line-count cap under test.

## Format button: complete C indentation (2026-09-13)

> **Owner:** Nombrado

- The teacher's Format button (`CodeEditorComponent.reindent()` in `maistra_web`) was extended from brace-depth-only to **all of C's indentation rules**: (1) brace nesting, (2) `switch`/`case` — labels at the switch's content level, bodies one deeper (tracked as a per-switch case-body level; handles nesting and Allman brace placement), (3) line continuation — a line reached with unbalanced `(`/`[` indents one deeper, (4) `goto` labels — one level out, (5) preprocessor (`#…`) — column 0.
- **Whitespace-only and grade-safe by construction.** It strips ONLY leading whitespace; trailing and every other character are emitted verbatim, so Format re-derives indentation purely from the braces already in the buffer and can never change the student's code content. The original extraction (`extractedText`) is untouched — Format edits only the editable working copy (`editableText`) as one undoable edit. It is a predictable reindenter, not a beautifier: no line reflow, brace insertion, or intra-line spacing changes (that would alter code characters, which a grading app must not do).
- Extraction is now paper-faithful (it reconstructs the student's handwritten indentation/spacing), so Format is the on-demand "make it IDE-structured" normalization on top of that — and it is only as correct as the braces in the buffer, so the teacher's edit pass remains the correctness guarantee.
- Tests: 13 new `code-editor.spec.ts` unit tests (each rule, brace-depth regression, grade-safety = only leading whitespace changes, idempotency, blank-line/robustness). Web suite 49/50 — the one red is a pre-existing, unrelated `submissions-list` OCR-error test. Whitespace-only, so invisible to the OCR `clean_ws` CER (0.099 unchanged); this is a teacher-readability change, not an accuracy metric mover.

## OCR reading-order layout package (2026-09-13, reorganized 2026-09-17)

> **Owner:** Nombrado

- `core/ocr_pipeline.py` keeps recognition and orchestration: model construction, `warmup`, `REC_SCORE_FLOOR`, `_filter_low_confidence`, `_recognize_preprocessed`, and `extract_text_from_image`. It is the only side that imports `cv2`, `numpy`, or `paddleocr`.
- Pure reading-order and presentation geometry lives in `core/layout/`: `__init__.py` coordinates grouping and remains the stable import surface; `columns.py` detects full-height and banded columns; `displacement.py` supplies sweep, trace, and brace-reassembly primitives; `braces.py` provides literal-safe brace-depth helpers; and `format.py` reconstructs indentation and blank lines. `reorder.py` is a legacy compatibility re-export.
- The split is behavior-preserving: original layout functions were moved without changing executable bodies. The package-level coordinator deliberately resolves mock-sensitive calls in its own namespace so tests patch the real live call path. `ocr_pipeline.py` continues to re-export layout helpers for existing callers.
- Fresh sanity check after the 2026-09-17 organization: all **18** original layout functions are present with no executable-body mismatches; the full Python suite reports **187 passed** with **5 documented expected planning failures**; the package and legacy `core.layout.reorder` import surfaces resolve to the same grouping functions. The evaluator started normally and printed the expected `green_writer10` clean_ws CER **0.061**, but the terminal detached before the aggregate table, so this change records no new aggregate CER claim.

## OCR real handwriting margin calibration (2026-09-13)

> **Owner:** Nombrado

- Validated three original 1536×2048 handwriting photos through the live fine-tuned pipeline, preserving unedited detections as `writerX_marginA/B/C_detections.json`. A already reads left-then-margin via two-column detection; B/C now do so through banded detection.
- Changed only `BAND_GUTTER_MIN_MULTIPLIER` **1.5 → 0.5**, retaining its 60px floor, three-row persistence, x-alignment and uncrossed-band guards. B/C's confirmed band gutters are **108px / 189px = 0.571** and **171px / 138px = 1.239** median widths. Full-page gutters are A/B/C **157/67/48 processed px**; these must not be confused with band gutters.
- Kept `REGION_GAP_MULTIPLIER=0.75`, the historical 6.0 merge threshold, and every severance constant. Lowering the region seed did not fix these captures. All handwritten rows are single OCR boxes, so the confirmed within-line gap distribution is empty and provides no new seed calibration evidence.
- **16/16 braces survived OCR**, including B's initializer pair, but brace reassembly still made no move. The old B trace missed the final margin close; C's left-drifting closers collapsed its trace gutter. Recognition is necessary but not sufficient for this path.
- Old/new grouping is identical across **315 historical artifacts / 262 distinct detection payloads**; live detections on the three new photos also match exactly before/after. Fabric false positives and OCR spelling errors remain untouched for teacher verification.
- Full Python suite **157 passed** (148 + 9). The trace-only test helper now disables banded interception; the original 12/13-line cap inputs and assertions are unchanged. Live 20-sample evaluator retains clean_ws CER **0.099**, clean WER **0.328**, clean token accuracy **0.716**, green_writer10 clean_ws **0.061**, with identical printed per-file tables.
- Complete boxes, raw/cleaned extractions, mechanism traces, brace audit, gap measurements and reproduction steps: [real margin validation](../ocr_feature/reports/2026-09-13-real-margin-validation.md).

## OCR brace-assisted margin fallback (2026-09-13)

> **Owner:** Nombrado

- Added `_reassemble_margin_candidates` as a conservative fallback after full-column, banded-column, trace, and severance ordering have failed to change a single-column page. It proposes only whole-line, visibly right-shifted, x-aligned margin clusters with a positive local gutter, then reuses `_reassemble_displaced_regions` as the final gate.
- The fallback is still grade-safe: it never edits OCR text, never inserts a missing brace, and never splits a detection. A readable `}` can prove that a right-margin block is a continuation; a misread `)` remains a `)` and the candidate stays in visual order.
- Acceptance requires exactly one brace-balanced move that preserves the line multiset. Ambiguous tail placement, missing geometry, crossed gutters, no closing-brace signal, or multiple possible candidate clusters all leave the original order unchanged.
- The A/B/C real handwriting photos still use geometric ordering (A full two-column, B/C banded). This fallback covers the adjacent failure class learned from that validation: OCR may read the braces correctly while strict geometry still fails to mark the exact displaced block.
- Tests add the fallback's two critical cases: readable braces can prove a missed right-margin candidate, while the same layout with a misread brace stays unchanged. Full OCR unit suite: **159 passed**. Live `evaluate_cer` remains clean_ws CER **0.099**, clean WER **0.328**, clean token accuracy **0.716**, green_writer10 clean_ws **0.061**. Disabling/enabling the fallback changes **zero** groupings across the existing **315 debug artifacts / 262 distinct detection payloads**.

## OCR continuation association planning (2026-09-14)

> **Owner:** Nombrado

- Planning and tests only; production behavior remains unchanged. The exact live
  detections from the two-question margin screenshot are preserved as
  `writerX_two_question_margin_detections.json` (20 unedited detections).
- Reproduced wrong ordering: the upper-right continuation follows the lower-left
  question. Full two-column ordering returns before the brace candidate fallback.
  Correcting only the misread `{else {` in a counterfactual replay does not fix order.
- Clarification of the earlier brace wording: balanced braces support a hypothesis;
  they do not prove intended continuation or answer membership. The A/B/C ordering
  successes do not establish continuation-versus-independent-program classification.
- Two desired-order tests were run red and are marked expected failures during
  planning; preservation and early-return characterization tests pass. These markers
  must be removed when the production fix is implemented, not treated as successes.
- The proposed next step compares local continuation and independent-answer
  hypotheses, preserving recognized characters and abstaining on ambiguity. Real
  independent-answer controls and held-out writers are required before integration.
- Research sources, exact detection order, test matrix and implementation gates:
  [continuation association plan](../ocr_feature/reports/2026-09-14-continuation-association-plan.md).
- Fresh verification: 163 tests executed, 161 passed and 2 expected failures.
  Live evaluator retains clean_ws CER 0.099, clean WER 0.328, clean token accuracy
  0.716 and green_writer10 clean_ws CER 0.061.

## OCR development-photo annotation and baseline (2026-09-14)

> **Owner:** Nombrado

- Completed live extraction and manual block/detection annotation for writerX
  Examples 1, 2, 4, 5, 6, 8, 9 and 11. Reserved Examples 3, 10 and 12 were not
  extracted or used for tuning at this baseline stage. The intake called ID 7
  missing; subsequent user clarification makes it unresolved numbering, not a
  confirmed missing photo. All 11 supplied photographs were included.
- Saved eight unedited detection fixtures and a sidecar with answer membership,
  continuation edges, intended order, photo regions and recognition-loss notes.
  Writer intent and image-only ambiguity are distinguished for unnumbered answers.
- Current retained-detection order matches 5/8 pages. Examples 5, 6 and 8 reproduce
  the full-column early-return failure, placing an upper continuation after the
  next answer's left block. All 90 retained detections survive grouping unchanged.
- Example 4's left closing brace was recognized as empty text and filtered before
  grouping. Correct order on retained text does not imply complete transcription.
- Example 11 is a confirmed real-photo activation of the brace-assisted fallback
  with correct ordering. Its comment delimiters are misrecognized; this does not
  prove general code understanding or reliable answer association.
- Added a development-only offline evaluator with explicit reserved-example
  rejection, pairwise order measurement and multiplicity checks. Association
  accuracy remains unavailable because the production pipeline emits no membership
  decisions. Three newly reproduced desired-order failures are marked expected
  failures during planning, pending implementation. No production changes.
- Full evidence and reproduction: [development baseline](../ocr_feature/reports/2026-09-14-development-baseline.md).
- Verification: 171 tests executed, 166 passed and 5 expected failures; live
  clean_ws CER 0.099, clean WER 0.328, clean token accuracy 0.716 and
  green_writer10 clean_ws CER 0.061. Offline replay matches live extraction rows.

## Offline continuation prototype (2026-09-14)

> **Owner:** Nombrado

- Added an experimental records-only module under `ocr_feature/evaluators/`, not
  `core/`. Neither the OCR backend nor web app imports it. Original recognition,
  cleanup, production grouping and thresholds remain unchanged.
- It discovers spatial bands, evaluates local gutter and recognized C-scope
  evidence, and emits continuation/independent/ambiguous relationships with reasons.
  Accepted links move retained detection IDs; no recognized character is edited,
  inserted or removed. An abstention preserves baseline order, which can be wrong.
- Development retained-detection order improves from 5/8 to 8/8. Six exact
  continuation links are correct; another targets a region containing both a helper
  function and the main start. That block-boundary error stays within one answer.
  No predicted continuation crosses annotated answers. Two cases are ambiguous.
- A SHA-256 freeze precedes reserved evaluation. Reserved results cannot be used
  to tune this version; Example 7 is intentionally out of scope, and all supplied
  pages use one writer. The historical frozen manifests are retained unchanged.
  The five known production-order expected failures remain unresolved by design.
- Frozen reserved order matches 3/3 available pages (baseline 2/3). Example 10's
  left→right→left ordering improves, but its final return association edge is not
  predicted. Examples 3 and 12 abstain. This is not three correct membership
  classifications. All 28 retained records survive; two braces were lost upstream.
- Verification: 185 tests, 180 passing and 5 expected failures; live baseline
  clean_ws CER 0.099, clean WER 0.328, clean token accuracy 0.716 and
  green_writer10 clean_ws CER 0.061. Further offline evaluation is required before
  live integration; this prototype has not changed teacher-visible output.
- Results, limitations, frozen evaluation and reproduction:
  [offline association experiment](../ocr_feature/reports/2026-09-14-offline-association.md).

## Manual continuation tester and session handoff (2026-09-14)

> **Owner:** Nombrado

- Added `ocr_feature/tests/manual_continuation.py` with a runnable module docstring.
  It takes a local image, runs fresh fine-tuned OCR, compares the frozen prototype,
  prints raw/proposed text and association reasons, and saves `comparison.json`
  in a unique output folder. It never writes fixtures or enables web behavior.
- `--help`, invalid-file handling and normal unit discovery do not load OCR models.
  The manual display uses one retained record per line rather than final production
  indentation. An ambiguous result is not evidence of correct fallback order.
- A real development page05 run recovered both local continuations, matched the
  annotated order and preserved all 15 retained records. The frozen rule file was
  unchanged. Focused runner tests cover lazy imports and duplicate preservation.
- Clarified this session: all 11 supplied photos were processed. Example 7 is
  intentionally skipped for this run; no rewrite is requested. Additional writers are future evaluation data, not a
  prerequisite to use the tester; testing photos does not train the OCR model.
- Updated local OCR guides, command reference, setup and maintainer entry points.
  Most are gitignored; the committed source of truth is the
  [session handoff](../ocr_feature/reports/2026-09-14-continuation-session-handoff.md),
  including current findings, terminal commands, limitations and next work.
- Verification: 187 tests executed, 182 passed and the same 5 expected failures.
  Fresh live evaluation retained clean_ws CER 0.099, clean WER 0.328, clean token
  accuracy 0.716 and green_writer10 clean_ws CER 0.061. No production changes.

## OCR continuation association live integration (2026-09-17)

> **Owner:** Nombrado

- Added `core/continuation.py`, a pure records-only decision layer derived from the
  frozen experiment. It receives recognized text, scores, boxes and the existing
  layout order; it returns a proposed detection-ID permutation plus inspectable
  continuation, independent or ambiguous evidence. It never changes OCR text,
  inserts symbols, compiles code or grades an answer.
- Full and banded column paths now pass their completed rows through one package-level
  finalizer before returning. The finalizer accepts only a complete permutation that
  keeps every existing visual row contiguous. Invalid, duplicate, missing or
  row-splitting proposals retain the current layout order. Existing single-column
  brace/severance mechanisms remain authoritative so association cannot undo their
  higher-confidence reassembly.
- A continuation requires a unique clean gutter and one local left target. Recognized
  scope closure supplies the normal content signal. The original two-question photo
  also uses a local `if`/`else` link before a recognized next-question boundary, so
  its order is recovered despite the unedited OCR strings `{else {` and
  `printf("a uns\');`. This is supporting evidence, not character correction.
- The five former expected failures are now ordinary passing acceptance tests: the
  original and counterfactual two-question fixtures, plus development Examples 5,
  6 and 8. All eight development pages match their annotated retained-detection
  order; Examples 1, 2, 4, 9 and 11 remain unchanged, and every detection survives.
  The A/B/C real-margin fixtures, `green_writer10`, per-column indentation and the
  existing brace-assisted single-column cases also retain their expected behavior.
- The frozen prototype and reserved manifests remain unchanged. Reserved Example 10
  still demonstrates a layout outside the live column gate; Examples 3 and 12 retain
  their existing order. All supplied evaluation photos are from one writer, so this
  release does not establish general continuation-classification accuracy. Additional
  writers remain the next evaluation step.
- Fresh verification: **204 tests pass with zero expected failures**. The 20-image
  live evaluator remains at clean_ws CER **0.099**, clean WER **0.328**, clean token
  accuracy **0.716**, and `green_writer10` clean_ws CER **0.061**.

## OCR heading recognition + code-review fixes (2026-09-18)

> **Owner:** Nombrado

- Widened heading recognition (`core/continuation.py` `QUESTION`) beyond `Question N:`
  to every format present in `datasets/verified/labels.csv`: `QUESTION NO. N`,
  `test Case N` / `Test case N:`, and bare numbered headings (`1.`, `2)`, `3.)`). The
  prefix is conditional, so a bare digit or `digit;` fragment (`5`, `0;`, `1;`) is NOT
  misread as a heading. Closed-vocabulary by design; an unrecognized style falls back
  to geometry/brace evidence and only loses a shortcut, never causes a wrong reorder.
- Synced `evaluators/continuation_prototype.py`'s `QUESTION` to the same pattern so the
  offline/manual tester (`tests/manual_continuation.py`) mirrors live heading
  recognition; behaviour-neutral on the recorded association cohort (all continuation
  tests unchanged).
- Code-review fixes (medium-depth review of the OCR feature): `_brace_delta` and
  `_is_definition_close` now mask `//` and `/* */` comments as well as literals, so the
  single-column brace guard matches `core.continuation._scope`; `#include`
  normalization no longer truncates a fused OCR line's trailing student content;
  `ocr.predict` failures now raise a `RuntimeError` carrying the image path instead of a
  bare traceback; `try_config.py` guards a `None` average confidence before formatting.
- Removed six dead "backward compatibility" re-exports from `ocr_pipeline.py` (only
  `_group_detection_records` and `line_member_bounds` are still imported from it) and
  deleted the unused `core/layout/reorder.py` shim — no importer used either.
- One review finding (adding `left_safe` to the if/else continuation branch) was
  intentionally NOT applied: `_code_rows` already blanks unsafe rows, so the `if`
  evidence can only come from a safe row, and requiring `left_safe` regresses a real
  annotated two-question fixture. The omission is now documented in-code and locked by
  `test_if_else_continuation_survives_unsafe_unrelated_left_row`.
- Verification: **207 tests pass**. Live evaluator unchanged: clean_ws CER **0.099**,
  WER **0.328**, token accuracy **0.716**, `green_writer10` clean_ws CER **0.061**.

## Current OCR state: waiting on new datasets (2026-09-23)

> **Owner:** Nombrado

- No OCR code work is pending. 207 tests pass with zero expected failures, and the live evaluator remains at clean_ws CER **0.099**, clean WER **0.328** and clean token accuracy **0.716**.
- The next step is data. New **bond paper** and **yellow pad** datasets are expected. These paper types have the thinnest evidence: training has 131 greenbook, 20 bond and 17 yellow pages. The 20-page held-out set has 14 greenbook, 2 bond and 4 yellow pages. The bond and yellow test pages share writers with training, so new-writer accuracy on those types is unmeasured.
- Planned at import: record `literal_verified*` provenance through `import_verified_batch.py --verified-by`, and add the deferred `writer_id` column to both `labels.csv` files. Hold out whole new bond/yellow writers for testing; `select_holdout.py` currently selects pages for these types and needs updating first. Then rebuild crops, retrain, and compare on the same test set.

## Code cleanup completed

> **Owner:** Shared (Jayrald + Nombrado)

- Removed the unused Supabase realtime callback parameter.
- Replaced `questions: any[]` with a typed question collection.
- Replaced the untyped realtime subscription with its inferred Supabase return type.
- Renamed `saveTopic()` to `saveSubmissionDetails()` to match its actual behavior.
- Replaced deprecated Angular/RxJS `.toPromise()` usage with `firstValueFrom()`.
- Added a typed OCR response instead of using `any`.
- Made workflow status detection respect persisted `extracted`, `verified`, and `graded` statuses.
- Added a method-level guard so grading cannot be opened without both student code and a question.

## Submission tests

> **Owner:** Jayrald (submissions workflow tests); Nombrado (OCR-failure / extraction test cases)

Focused tests now cover:

- Repeated saves and confirmation timer isolation.
- Out-of-order save completion.
- Component destruction during an active save.
- Multiple Judge0 test cases.
- Edited code taking precedence over stale verified code.
- Wrong-answer handling.
- Clearing execution results after a question change.
- Blocking Details when no question is selected.
- Saving topic and question assignment together.
- Linked questions returned as either an object or array.
- Requiring both code and a question before grading.
- Mapping persisted workflow statuses.
- Remaining in Review Code after an OCR failure.
- Advancing after a successful verified-code save.
- Remaining in Review Code after a failed save.

## Setup documentation

> **Owner:** Jayrald

- `JUDGE0_UBUNTU_DOCKER_SETUP.md` explains how to deploy Judge0 CE on an Ubuntu VM with Docker, connect through SSH, configure cgroups, set `AUTHN_TOKEN` and `AUTHZ_TOKEN`, and connect mAIstra.
- `SUPABASE_LOCAL_SETUP.md` explains local Supabase development.
- `SUPABASE_CLOUD_LOCAL_SWITCHING.md` explains switching between local and hosted Supabase environments.

## Verification status

> **Owner:** Shared

- Angular application TypeScript compilation passes.
- The focused submission-list test file passes isolated TypeScript validation.
- Angular template compilation passed after the submission workflow changes.
- Running Vitest from the current WSL environment is blocked because `node_modules` contains Windows-native Rollup/esbuild packages. Run `npm ci` and the tests in the same operating system environment, or run them directly from Windows where the dependencies were installed.
- Repository-wide spec type-checking currently also reports an unrelated missing Node `fs` type used by `question-form.spec.ts`.

## Important security work

> **Owner:** Shared

Before deploying mAIstra beyond a trusted development environment:

- ~~Rotate the Supabase `service_role` key exposed in Angular configuration.~~ **Done 2026-09-23 (`a448198`):** Supabase disabled the project's legacy keys on 2026-09-21. `maistra_web/src/environment.ts` now uses a publishable key. The legacy `service_role` JWT must stay disabled and must not be re-enabled.
- Never place a Supabase service-role key in browser or mobile code.
- Add complete Row Level Security policies for questions, submissions, and storage objects. RLS is currently enabled on `questions` only. `submissions` has a permissive policy but RLS is **not enabled**, so the publishable key does not restrict access to it.
- Restrict access to handwritten submission images or serve them with signed URLs.
- Authenticate and rate-limit the OCR and Judge0 wrapper APIs.
- Restrict the OCR URL downloader to trusted storage hosts and enforce download-size limits.
- Move hardcoded service URLs into Angular environment configuration.
- Add missing migrations for application columns such as `question_type`, `topic`, and `question_id`.

## Recommended next steps

> **Owner:** Shared

1. **OCR:** import the incoming bond paper and yellow pad datasets, which are the current blocker for OCR work. They should add new writers, give both paper types a writer-disjoint holdout, and support a retrain and re-evaluation on the same test set.
2. Add and verify Supabase migrations and RLS policies, starting with enabling RLS on `submissions`. (The frontend key was corrected in `a448198`.)
3. Reinstall Angular dependencies on the operating system used for testing, then run the complete frontend suite.
4. Add authentication and rate limiting to the OCR and Judge0 wrapper services.
5. Move API endpoints and mobile Supabase configuration into environment-specific configuration.
