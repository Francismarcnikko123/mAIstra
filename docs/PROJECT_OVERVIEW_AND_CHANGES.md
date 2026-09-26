# mAIstra Project Overview and Change Log

> **Ownership labels.** Each section below is tagged with its primary contributor(s): **Nikko** (mobile capture), **Jayrald** (web submissions/review UI, Judge0, Supabase), **Nombrado** (OCR pipeline & extraction). *Shared* marks cross-cutting sections. Labels reflect git authorship of the described work.

## Project purpose

mAIstra is a vision-based assessment system for handwritten C programming submissions. It captures student work, stores submission images, extracts C code through OCR, allows a teacher to verify the extracted code, executes it against question test cases with Judge0, and presents grading feedback.

## Main applications

### `maistra_mobile`

> **Owner:** Nikko

The Flutter mobile application captures handwritten submissions, runs the calibrated quality gate (blur, dark, bright and uneven-lighting checks with auto-correction), uploads images to Supabase Storage, and creates submission records. Since 2026-09-24 the student picks a validated question before capturing, and every page is uploaded with that `question_id` and the gate's verdict (`gate_result`).

### `maistra_web`

> **Owner:** Jayrald (submissions list, review UI, grading); Nombrado (OCR extraction + review highlighting); Nikko (question form, question bank, section folders)

The Angular teacher application manages questions and submissions. Teachers can review uploaded images, run OCR, correct extracted code, select the related question, execute code, and inspect test-case results.

### `ocr_feature`

> **Owner:** Nombrado

The Python FastAPI OCR service downloads or accepts submission images, preprocesses them, runs PaddleOCR, cleans recognized C tokens conservatively, and returns review suggestions and confidence information.

### `judge0_api`

> **Owner:** Jayrald

The Python FastAPI Judge0 wrapper submits C code to Judge0, polls for results, and decodes execution output for the Angular application.

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
   - Display output comparison and equal-weight test-case results.

### Review workflow fixes (September 26, 2026)

Both bugs were found by the new Playwright end-to-end tests.

- **Steps now advance after saving.** The Angular app runs without zone.js, so
  it only re-renders when told to. "Save and review code" and "Save and
  continue to grading" changed the step after the save's `await` without
  re-rendering, which left the dialog on the old step until the teacher
  clicked something else. Both now run change detection after the step
  changes.
- **New questions appear without a reload.** `SubmissionsListComponent` loaded
  questions only when the page opened, so a question saved in the question
  form was missing from the review dialog's question picker until the page was
  refreshed. The form now emits `questionSaved`, and `app.html` uses it to
  reload the list's questions. A question created in another tab or by
  another teacher still needs a page refresh.

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
- Program submissions receive each test case's `test_input` as stdin during
  grading and the first-test run preview. Function questions use assigned
  values in Test Code and always execute with empty stdin.
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

## Program tabs in Review Code (2026-09-24)

> **Owner:** Nombrado (review editor); schema needs Jayrald's approval

- One paper can hold several programs. Step 2 shows browser-style tabs above the editor. Program 1 is the existing editor, and its question comes from Details. **+** adds Programs 2..n. The teacher moves each program's code into its own tab and links it to a question from the bank through a question picker. The picker shows each question's name, a prompt preview and its test-case count.
- Each question can be linked to only one program. The picker greys out questions another tab holds ("In Program N"). Saving is blocked for a tab with code but no question, a tab with a question but no code, or a duplicate question. Fully empty tabs are ignored.
- Programs 2..n are saved as `{ code, question_id }` in the new `submissions.answers jsonb` column. They sit under the same submission ID and use the same guarded save as Program 1. `extracted_text` is never modified, and Re-extract replaces Program 1 only. There is no OCR change.
- Programs 2..n are saved but not graded yet. Grading them is a follow-up for Jayrald.
- **Grading hand-off (for Jayrald):** `programsForGrading(verified_text, question_id, answers)` in `submissions-list/extra-answers.ts` returns every gradable program on a paper as `{ program, code, question_id }`: Program 1 first, then each saved tab. Entries without code or without a question are skipped. Each `question_id` points at the `questions` row whose `model_answer` and `test_cases` that program should be graded against, so the grading step can loop over this list instead of reading `verified_text` alone. The review screen guarantees each question appears at most once per paper.
- The split is manual by design. OCR program-boundary detection exists, but its consistency is unmeasured.
- **Review aids (2026-09-24).** None of these read, move or check the student's code:
  - **OCR text beside the photo.** "Show OCR text" opens the saved OCR reading, read-only, next to the photo; the editor moves to full width below. It makes reading-order and continuation results checkable against the paper.
  - **Re-extract on a paper with tabs** only refreshes that panel and never overwrites a tab. The teacher copies what they need. Without tabs, Re-extract works as before.
  - **"View question"** shows the linked question's prompt and test cases, read-only, without the model answer.
  - **"Change"** on Program 1 goes back to Details.
  - **Unsaved dots** mark tabs changed since the last save. Closing the review with unsaved changes (✕, the dark overlay, Cancel or Finish) asks: Keep editing / Discard changes. (Until 2026-09-26 it also offered "Save and close"; saving now happens with the Save button next to the tabs. See "Save next to the program tabs" below.)
  - Tooltips on the tab marks, guide text in an empty tab, and ←/→ keys between tabs.
- Code: `submissions-list/extra-answers.ts` holds the pure parse, taken-question and save-rule helpers. `submissions-list/program-tabs.css` holds the tab styles, kept separate so the component stylesheet stays under its 12 kB build budget. `CodeEditorComponent.refresh()` re-measures a previously hidden tab.
- **Migration:** apply `supabase/migrations/20260923000000_add_submission_answers.sql` to enable saving Programs 2..n. It adds a column-level `UPDATE (answers)` grant for `anon` and `authenticated` so the review editor works after the public API lockdown migration. Only Jayrald applies it to the cloud project. Until it runs, the app still works. `getSubmissions()` retries without `answers` when Postgres reports the column missing (42703), Program 1 saves as before, and Step 2 marks extra tabs as preview-only. On save, Program 1 is saved, the extra tabs stay on screen unsaved, and a message says so ("Program 1 was saved. Programs 2 and up can't be saved yet…").
- **Code-review fixes (2026-09-24):**
  - A realtime reload no longer replaces unsaved Program 1 edits.
  - Removing a tab no longer hands its editor's undo history to the next tab.
  - The open review's `answers` update after a save.
  - OCR backend (`ocr_feature/`):
    - The cleanup no longer rewrites float literals like `1.1f` into `1.if`.
    - Each request works in a temporary folder that is deleted afterwards. Photos and debug dumps are no longer kept in `uploads/` / `outputs/`, and client file names never reach a path.
    - Downloads are capped at 25 MB and must be http(s).
    - Predictions are serialized with a lock.
    - The upload endpoint no longer blocks the server.
- Verification: 89/89 web tests (50 existing + 39 new); TypeScript check and `ng build` pass. Checked in the running app against the cloud database without the column: all 209 submissions load, the tabs and picker render, the Program 1 question is greyed as "In Program 1", the preview-only note shows, and clicking elsewhere cancels an armed "Remove?". Saving Programs 2..n end to end is untested until the migration is applied.

## Pre-extraction on arrival (2026-09-24, branch `feature/pre-extraction`)

> **Owner:** Nombrado (OCR server, review editor). The worker writes to the shared `submissions` table, so it's announced in `docs/TEAM_SYNC.md`.

- **Branch and handoff:** `feature/pre-extraction` is pushed and includes the pushed `feature/program-tabs` branch. Nikko owns mobile selection/sending of `question_id` for Program 1. Jayrald owns applying the `answers` migration and the remaining cloud schema for Nikko's complete question-linking flow. The worker and badge can be tested on new papers before that integration; neither branch is merged to `main` yet.

- **What it does:** when the OCR server runs with `AUTO_EXTRACT=true`, a background worker reads papers that arrived from the phone and saves `extracted_text`, so teachers open them already extracted. It's off by default.
- **Same results:** it uses the same extraction function as the Extract button (`extract_image_url` in `ocr_feature/main.py`) under the same lock. The pipeline is unchanged, so the recorded accuracy numbers still apply.
- **Never overwrites work:** the save only goes through if `extracted_text` and `verified_text` are still empty at that moment. It writes nothing else: not `verified_text`, `answers` or `status`.
- **Only new papers:** papers captured before the server started, or before `AUTO_EXTRACT_SINCE`, are never read. The existing backlog of test papers stays as it is.
- **Failures:** a paper that fails 3 times is left "Needs OCR" for the manual **Extract now**.
- **Web review:**
  - Opening a paper re-reads it (`getSubmission(id)` in `supabase.ts`), so text saved after the list loaded shows up.
  - The OCR server's `GET /` reports whether the worker is running, its start date and papers it has given up on. The web checks this on load, every 30 seconds and after list reloads; an unreachable server counts as off.
  - An unread paper captured after that start date shows **Extracting…** while the worker is running. It remains in the **Needs OCR** filter. Old papers, failed papers and papers seen while the server is off show **Needs OCR**.
  - The Supabase realtime UPDATE listener fills empty OCR and editor fields and changes the badge to **Needs review** when the worker saves. It preserves teacher edits, verified text and program tabs. Opening a paper uses the same guarded merge.
  - Re-extracting an untouched pre-extracted paper no longer asks to discard edits.
  - The empty state and button now say **Extract now**.
- **Key:** `ocr_feature/.env` holds `SUPABASE_URL` / `SUPABASE_KEY` (template: `.env.example`). The publishable key works while `submissions` has no RLS; switch to a secret key once RLS is on. Never put a secret key in the browser or mobile app.
- **Live check:** one new phone paper changed from **Extracting…** to **Needs review** without a reload. A second paper showed **Needs OCR** while the server was off, then changed to **Needs review** on the same open page after the server restarted with a temporary start date covering the offline capture.
- **Not yet:** provenance columns.
- **Verification:** OCR 231/231 tests and web 114/114 tests pass; TypeScript checks and Angular build pass with the existing CSS budget warning. The unchanged 20-sample evaluator still reports clean_ws CER **0.099**, clean WER **0.328**, and clean token accuracy **0.716**.

## Question sections and mobile question linking (2026-09-24)

> **Owner:** Nikko. Spec: `IMPLEMENTATION_SPEC_question_linking.md`. Change notes in [`docs/changes/`](changes/README.md).

- **Schema:** new tables `question_sections` and `question_section_items` give every question a section and a number (`Basic · Q2 · Sum of two numbers`). Nothing on `questions` changes. Migration `supabase/migrations/20260926000100_add_question_sections.sql` (renamed on 2026-09-26), not applied yet. [Note](changes/2026-09-24-question-sections-migration.md)
- **Mobile:** the student picks a validated, sectioned question before the camera opens; it stays in the app bar; Keep page is disabled on RETAKE; the review screen blocks Submit while any page is RETAKE; uploads send `question_id` and `gate_result`. The quality gate itself is unchanged. [Note](changes/2026-09-24-mobile-question-linking.md)
- **Web:** top bar with *Question bank* and *Submissions* pages (Nombrado's mock); the create form requires section and number, previews the label and saves only after validation passes; the bank groups by section with "No section yet" last; a question page shows the model answer, test cases and linked papers; submission folders come from the question's section and Details shows it read-only. [Note](changes/2026-09-24-web-question-bank-and-folders.md)
- **Database (done by Jayrald, 2026-09-26):** the sections migration is applied; `can_publish`, `gate_result`, UPDATE on `questions` and `batch_id` are live.
- **Verification:** mobile 53/53, web 128/128 at the time, both checked on device/browser against the live database (which lacks the new tables).

## `feature/question-linking-v2`: merges and follow-ups (2026-09-26)

> **Owner:** Nikko (merge). Review requested from Nombrado and Jayrald.

- The branch combines the quality gate, Nombrado's program tabs and pre-extraction, the question-linking work above, and Jayrald's `judge0-integration` (revision-guarded saves, per-row realtime refresh, persisted grades, Playwright tests). The judge0 merge had 17 conflicting files; every resolution keeps both sides' features and is listed in the [merge note](changes/2026-09-26-merge-pre-extraction-and-judge0.md) and the `ffcf908` commit message.
- **Please confirm (Nombrado, Jayrald):** `ocr_feature/main.py` CORS now uses Jayrald's localhost origins with `allow_credentials=False`.
- **Behaviour after the merge:** closing a review with unsaved programs asks Save / Discard / Keep editing, then restores the saved version; re-extracting over saved code asks first; Programs 2..n are saved inside Jayrald's revision-guarded update.
- **Follow-ups:** the sections migration was renamed because its version clashed with `20260924000000_save_grade_for_stored_code.sql` ([note](changes/2026-09-26-migration-rename.md)); the question page no longer shows marks, which `judge0-integration` removed from test cases ([note](changes/2026-09-26-question-page-drop-marks.md)).
- **Verification:** web 281/281, mobile 53/53, OCR tests pass; `ng build` passes with a stylesheet size warning. Checked in the browser: program tabs, question lock, remove arming and re-extract prompt. `judge0_api` tests not run locally.
- **Second pass (2026-09-26), after Nombrado's review:** merged his latest `feature/pre-extraction` (`0f87354`: Save next to the program tabs, handoff); restored `AGENTS.md` (deleted by `judge0-integration`); `ocr_feature/` is identical to his branch again (Jayrald's CORS change and `test_api.py` not included). His `saveStatusLabel()` now also shows Jayrald's save conflict, and `code-editor.ts` keeps Jayrald's `readOnly` input; both await his OK. Web 289/289, OCR tests pass. Not pushed: Nombrado asked to wait. [Note](changes/2026-09-26-merge-latest-pre-extraction.md)
- **Third pass (2026-09-26):** merged Jayrald's `judge0-integration` at `268eb54`, which already contained the pushed v2 and adds the live schema (`gate_result`, `can_publish`, question UPDATE, `batch_id`, `submission_programs`, per-program grading). v2 keeps Nombrado's Save layout with the conflict-aware label. Web 300/300. [Note](changes/2026-09-26-merge-judge0-schema.md)
- **Phone `batch_id` (2026-09-26):** every page of one submit carries the same `batch_id` (a version-4 UUID), so the pages of one answer can be grouped; each page stays its own row. Mobile 58/58. [Note](changes/2026-09-26-mobile-batch-id.md)
- **End-to-end test passed (2026-09-26)** against the live database: *Basic · Q1* created and validated on the web, picked and captured on the phone, submitted, filed in the **Basic** folder, linked on the question page; the row has `question_id`, `gate_result = PASS` and a `batch_id`. Not yet covered: a two-page submit, OCR on the new paper, editing older questions (Edit screen not built). [Note](changes/2026-09-26-end-to-end-test.md)

The Judge0 wrapper now converts outbound Judge0 connectivity failures into a
clear HTTP `502` response that identifies the configured `JUDGE0_BASE_URL`,
instead of surfacing an internal FastAPI stack trace. This now also covers a
connectivity failure during the result-polling loop, not just the initial
submission request. `JUDGE0_BASE_URL` is validated at startup — the service
now fails fast with a clear error instead of silently building `None`-based
request URLs when the environment variable is missing.

## Judge0 output validation (model answer vs. submitted code)

The Judge0 wrapper compiles and runs code for question validation and student
grading. Expected Output is authored by the teacher and is never replaced by
Judge0 output:

- **Question authoring (`question-form`):** clicking "Validate Test Cases"
  requires a manually entered Expected Output, compiles and runs the model
  answer through Judge0, and compares the normalized actual and expected
  values. The result shows both Expected and Got for diagnosis. A mismatch
  fails validation without changing the teacher's entry.
- **Saving a question:** the Save button is now disabled until every test
  case has been validated and passed (`canPublish`), so a question can no
  longer be persisted with an unverified `expected_output`.
- **Grading (`submissions-list`):** the submitted code's Judge0 output is
  compared against the same teacher-authored `expected_output`.

**Compile status handling:** "compiled successfully" is now determined solely
by Judge0's own `status.id === 3` ("Accepted"), across the question-form
validator, submission grading, and the manual "Run" preview panel
(`judge0.ts`). Previously, any non-empty `stderr`/`compile_output` was also
treated as a failure, which incorrectly rejected code that compiled with only
warnings (e.g. calling `printf` without `#include <stdio.h>`) but still ran
and produced correct output. A real compile error (`status.id === 6`) or
runtime crash (`status.id` 7-12) still fails, as expected.

### Question format and manual-output validation (updated September 8, 2026)

- **Write a Function:** Model Answer and Test Code reject `#include`, `main()`, and `scanf()` before execution. Inline messages and editor borders explain what to remove. Comments and quoted text do not trigger these checks. Model Answer contains the functions; Test Code assigns fixed values, calls the functions, and prints results. Standard Input is hidden, ignored during validation and grading, and cleared when a function question is saved.
- **Write a Program:** Model Answer defines `main()`. The shared execution wrapper supplies `#include <stdio.h>` for question validation, model-run helpers, submission grading, and the submission run preview. Programs with their own explicit header still work. The program template contains only `main()`.
- Write a Program retains Standard Input and may use `scanf()` when required.
- Expected Output is required and entered manually for both question types. An accepted execution passes only when its normalized stdout matches that value. Empty stdout gets a **No output** failure, and a mismatch gets **Wrong Answer**; neither case changes Expected Output. Compiler warnings do not fail an otherwise successful run with matching output.
- Execution status, compiler details, stderr, and service messages are displayed separately from actual output.
- At least one test case is required. Code/input edits and test-case changes invalidate pending results, and Save verifies that the current inputs match the successful validation. A partially completed run cannot display “Passed all tests.”

Design and implementation notes are in [the validation design](plans/2026-09-06-question-validation-design.md) and [the implementation plan](plans/2026-09-06-question-validation.md).
The September 8 manual-output and function-input update is documented in [its design](plans/2026-09-08-manual-expected-output-function-inputs-design.md) and [implementation plan](plans/2026-09-08-manual-expected-output-function-inputs.md).

### Equal-weight test scoring prototype (September 9, 2026)

- Each passed test case earns one point and each failed case earns zero.
- The displayed score is `(passed test cases / total test cases) * 100`, rounded to at most two decimal places.
- Submission results show the passed fraction, percentage, and `1/1 point` or `0/1 point` for every case.
- The question form no longer exposes or stores test-case marks. Older records containing `mark` remain readable, but scoring ignores the property and awards one point per passed case.
- Logic Analysis is isolated on `feature/logic-feature`; this branch scores only Judge0 test-case results.
- This is intentionally a partial implementation: score persistence, teacher overrides, and any larger rubric formula are pending adviser approval.

The review questions are tracked in [the adviser-review task](plans/2026-09-09-adviser-review-equal-weight-scoring.md). The supporting rationale and implementation scope are in [the scoring design](plans/2026-09-09-equal-weight-test-scoring-design.md) and [implementation plan](plans/2026-09-09-equal-weight-test-scoring.md).

## C structural analysis

- The Tree-sitter checker, logic comparison endpoint, frontend request/state, and Logic Analysis panel are owned by `feature/logic-feature`.
- `judge0-integration` intentionally contains no structural-analysis implementation and uses Judge0 test cases as its only automatic correctness mechanism.
- Additional parser-based scoring should be developed and reviewed on the feature branch before integration.

## Save next to the program tabs (2026-09-26, branch `feature/program-tabs-save`, merged into `feature/pre-extraction`)

> **Owner:** Nombrado (review editor). One label change in Jayrald's Step 2 footer, announced in `docs/TEAM_SYNC.md`.

**Why:** Step 2 had no plain Save. A teacher could only save by going to grading ("Save and continue to grading") or by leaving (✕ → "Save and close", which closed the paper, so reaching grading meant reopening it). Nikko's first review screen (`da00269`) had a plain Save; the 3-step redesign (`aca278e`) replaced it.

**What changed (teacher's view):**
- A **Save** button at the right end of the program tab bar saves **every tab of the paper** in one update and keeps the teacher on Step 2. The unsaved dots clear and "✓ All programs saved" shows next to it. While the cloud database has no `answers` column, only Program 1 is stored: the label then says "✓ Program 1 saved", the extra tabs keep their dots, and the existing message explains why (fixed the same day; the first version claimed "All programs saved"). **Cmd/Ctrl+S** does the same on Step 2 (and no longer opens the browser's "save page" dialog there).
- The footer button is now **"Continue to grading"**. Its logic is unchanged: it still saves first, and moves to Step 3 only when the save succeeds, so grading always runs on code that is in the database.
- The **✕ / overlay / Cancel / Finish** prompt for unsaved changes now offers **Keep editing** (primary) and **Discard changes**. "Save and close" is removed; saving lives next to the tabs.

**What did not change:**
- One save function for everything: the Save button, the shortcut and "Continue to grading" all call the existing `saveVerifiedText()`. The save rules (a tab with code needs a question, no duplicate questions), the save-generation/timer/destroy guards, and the columns written (`verified_text`, `answers`, `status = 'verified'`, `verified_at`) are unchanged. `extracted_text` is still only ever written with OCR output, never with the teacher's edits.
- Save stays clickable when nothing looks changed, because an untouched pre-extracted paper looks saved but is still `pending` with no `verified_text`; Save must still verify it. The shortcut does nothing on a paper with no extracted code yet (the button is hidden there too).
- No schema, OCR or grading change.

**Fix included:** the app is zoneless, so setting `reviewStep` after an `await` did not re-render. "Save and review code" and "Continue to grading" could leave the dialog on the old step until the next click. `continueFromDetails()` and `saveCodeAndContinue()` now call `detectChanges()` after the step changes, the same two-line fix Jayrald made on `judge0-integration` (`8e20fd5`).

**Code:** `submissions-list.html` (tab bar wrapper `program-tabs-bar` with the Save area outside `role="tablist"`; footer label; two-button prompt), `submissions-list.ts` (`onSaveShortcut()` `@HostListener`; `saveAndClose()` removed; the two `detectChanges()` calls), `program-tabs.css` (bar and Save styles), `submissions-list.css` (unused `.save-status` removed).

**Verification:** web 121/121 tests (7 new program-tab tests replace the one Save-and-close test; the continue-to-grading test now checks the step is rendered); application and spec TypeScript checks and `ng build` pass with the existing CSS budget warning. Viewed in the running app without saving: the Save button in the tab bar (pinned right while many tabs scroll), the "Continue to grading" label, and the two-button prompt.

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
- Added timeout and exception handling to question saving so a stalled Supabase
  request no longer leaves the assignment form stuck in the saving state.
- Question saving no longer requests the inserted row back from Supabase, keeping
  the insert request lighter because the UI does not use the returned row.
- Added a visible assignment-saved confirmation before the submission review
  workflow advances from Details to Review code.

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

## End-to-end tests (September 26, 2026)

Playwright tests in `maistra_web/tests/e2e` drive the real Angular app in
Chromium. Run them from `maistra_web`:

```bash
npm run e2e                 # headless, starts its own dev server on port 4300
npx playwright test --ui    # watch the browser step through each test
```

`teacher-workflow.spec.ts` follows one submission through the whole teacher
workflow without reloading the page:

1. Create a program question, validate its test cases against Judge0, and save it.
2. Receive a new upload over Supabase Realtime, as the mobile app would send
   it, and find it with the Needs OCR filter.
3. Assign the new question, extract the code with OCR, correct an OCR mistake,
   and save the verified code.
4. Run the sample, submit against every test case, and check that the grade,
   the OCR text and the verified text are stored separately.

`submission-grading.spec.ts` and the rest of `teacher-workflow.spec.ts` cover
the other paths: partial credit (1/2, 50%), a question whose expected output
disagrees with its model answer, an OCR failure, Judge0 being unavailable, and
a submission that changes while it is being graded.

**Faked services.** `environment.ts` points the web app at the hosted Supabase
project, and the teacher pages have no login, so a live run would write grades
into production rows. The tests therefore fake Supabase (REST, the
`save_submission_grade` RPC and Realtime), the Judge0 wrapper and the OCR
service inside the browser (`tests/e2e/support/fake-backend.ts`). The fake
grade save follows the same match rules as the real RPC, and any request the
fake does not recognise fails the test.

**Not covered:** the mobile capture app, real OCR accuracy, the real Judge0
instance, and the hosted database's RLS policies. The tests confirm the
workflow behaves correctly; they do not measure grading accuracy on real
handwriting.

## Database changes (September 26, 2026)

- `20260926000000_repair_realtime_publication.sql` adds `public.submissions`
  and `public.questions` to the `supabase_realtime` publication only when they
  are missing. A migration can stay marked as applied after the publication
  is changed by hand, which silently stops live updates; this repair is safe
  to run on a database that is already correct.
- `supabase/tests/database/security_contract.test.sql` now checks that both
  tables are published.
- `20260926000200_add_submission_gate_result.sql` adds `submissions.gate_result`
  (the phone's photo verdict: `PASS`, `FIXABLE`, `RETAKE` or NULL). The browser
  can set it only on insert, and the insert policy refuses `RETAKE` pages.
  [Note](changes/2026-09-26-gate-result-can-publish-and-cloud-migrations.md)
- `20260926000300_restore_question_can_publish.sql` brings back
  `questions.can_publish`, the "model answer validated" flag the phone's
  question picker filters on. Existing questions with test cases were marked
  validated.
- `20260926000400_allow_question_updates.sql` lets the question page edit a
  saved question (validated like a new one, no delete). Changing a question's
  test cases or type clears the grades of its linked papers and advances their
  `grading_revision`, so a grade computed against the old test cases can't be
  saved. [Note](changes/2026-09-26-question-updates.md)
- `20260926000500_add_submission_batch_id.sql` adds `submissions.batch_id`, set
  by the phone on every page of one answer (insert only).
  [Note](changes/2026-09-26-batch-id.md)
- `20260926000600_add_submission_programs.sql` stores every program on a paper
  as its own row, Program 1 included, with its own question and grade, and
  drops the empty `answers` column. See "Grading every program on a paper"
  below. [Note](changes/2026-09-26-submission-programs-and-per-program-grading.md)
- **Cloud project is at `20260926000600`.** Nombrado's `answers` migration and
  Nikko's sections migration were applied along with these.
- **Branches (decided in `TEAM_SYNC.md`):** everyone builds on
  `judge0-integration`, which now contains `feature/question-linking-v2` and
  `feature/pre-extraction` ([note](changes/2026-09-26-merges-into-judge0-integration.md)).
  `code-similarity/duplicate` is parked and will be rebuilt on top of
  `submission_programs`.

## Grading every program on a paper (2026-09-26, branch `judge0-integration`)

> **Owner:** Jayrald. Commits `f85d99e`, `f3138c6`, `96eda09`.

- **Storage:** `submission_programs` has one row per verified program (tab
  order = `position`), each linked to the question it answers and carrying its
  own grade and `grading_revision`. `submissions` stays the page: photo, raw
  OCR, status. Program 1 is also mirrored to `submissions.verified_text` /
  `question_id`.
- **Saving the review:** `supabase.ts` calls `save_submission_programs()`,
  which saves every tab in one step, guarded by the page's revision. The review
  screen still receives Programs 2..n as `answers`, so the program-tab code is
  unchanged.
- **Grading:** Step 3 shows a chip per program when a paper has more than one.
  Each program is graded against its own question's test cases and saved with
  `save_program_grade()`. A page is Graded only when every program is. Cards
  show `Q1 3/4 · Q2 not graded`; a single-program paper looks as before.
- **Stale grades:** editing a program's code or question clears that program's
  grade; editing a question's test cases or type clears the grades of every
  program linked to it.

## Setup documentation

> **Owner:** Jayrald

- `JUDGE0_UBUNTU_DOCKER_SETUP.md` explains how to deploy Judge0 CE on an Ubuntu VM with Docker, connect through SSH, configure cgroups, set `AUTHN_TOKEN` and `AUTHZ_TOKEN`, and connect mAIstra.
- `SUPABASE_LOCAL_SETUP.md` explains local Supabase development.
- `SUPABASE_CLOUD_LOCAL_SWITCHING.md` explains switching between local and hosted Supabase environments.

## Verification status

> **Owner:** Shared

- **2026-09-26 program-tabs Save checkpoint:** web 121/121; Angular application and spec TypeScript checks and `ng build` pass with the existing CSS budget warning. No OCR code changed, so the OCR suite was not re-run (last run 231/231 on 2026-09-24).
- **2026-09-24 pre-extraction checkpoint:** OCR 231/231, web 114/114; Angular application and spec TypeScript checks pass, and Angular build passes with the existing CSS budget warning. The live phone-photo, server-off and restart catch-up badge checks passed. See the pre-extraction section above for scope.
- **Earlier environment limitation (historical):** Vitest was blocked in WSL when `node_modules` held Windows-native Rollup/esbuild packages; this did not apply to the later macOS verification above.
- The earlier automatic Expected Output synchronization was verified live before being superseded by the September 8 manual-output workflow.
- The current `judge0_api` suite covers health/execution behavior and confirms the feature-only logic endpoint is unavailable on this branch.
- Question-validation follow-up (September 6): 71 focused Vitest tests pass across question-form, C structure checks, submissions-list, and Judge0 runner; `tsc --noEmit -p tsconfig.spec.json` and the Angular development build pass. Updated older fixtures to include real Judge0 status IDs and the test cases required by the existing submission workflow. Removed the redundant filesystem-based template string assertion; the changed UI was checked in the browser.
- Live browser/Judge0 checks confirmed immediate function-format errors, successful function output, successful programs both with and without an explicit stdio header using Standard Input, and an explicit No output failure with Save disabled. No test questions were saved to Supabase during verification.
- Manual-output and function-input update (September 8): 79 focused Vitest tests pass across question-form, C structure checks, submissions-list, and Judge0 runner; `tsc --noEmit -p tsconfig.spec.json` and the Angular development build pass. Live Judge0 verification was not run for this update.
- Equal-weight scoring prototype (September 9): all 85 frontend Vitest tests pass; `tsc --noEmit -p tsconfig.spec.json` and the Angular development build pass. Adviser approval and live Judge0 verification remain pending.
- End-to-end tests and review workflow fixes (September 26): all 7 Playwright tests pass, and they passed 35 of 35 runs with `--repeat-each=5`; all 164 frontend Vitest tests still pass. The tests run against faked services, so the real OCR, Judge0 and Supabase were not exercised.
- Database migrations (September 26): `supabase test db` passes 58/58 on local Supabase and the Python migration contract tests pass 18/18. After the cloud push, the new columns, grants, policies and trigger were checked by querying the cloud project directly. The phone and the question page were not tried against them yet.
- Per-program grading and the two merges (September 26, `judge0-integration`): `supabase test db` 80/80, `npx ng test` 299/299, both TypeScript checks, `npx ng build` (existing CSS budget warning), `npx playwright test` 8/8 run twice each. The save and grade functions were also called as the browser role through the local Supabase REST API. Not yet tried by a teacher on real papers.

## Important security work

> **Owner:** Shared

Before deploying mAIstra beyond a trusted development environment:

- ~~Rotate the Supabase `service_role` key exposed in Angular configuration.~~ **Done 2026-09-23 (`a448198`):** Supabase disabled the project's legacy keys on 2026-09-21. `maistra_web/src/environment.ts` now uses a publishable key. The legacy `service_role` JWT must stay disabled and must not be re-enabled.
- Never place a Supabase service-role key in browser or mobile code.
- Add complete Row Level Security policies for questions, submissions, and storage objects. RLS is enabled on `questions`, `submissions` and the section tables (`20260921000000_lock_down_public_api.sql`, confirmed in the cloud on 2026-09-26), with column-level grants. The policies still allow any caller with the publishable key because there are no logins yet.
- Restrict access to handwritten submission images or serve them with signed URLs.
- Authenticate and rate-limit the OCR and Judge0 wrapper APIs.
- Restrict the OCR URL downloader to trusted storage hosts and enforce download-size limits.
- Move hardcoded service URLs into Angular environment configuration.
- Add missing migrations for application columns such as `question_type`, `topic`, and `question_id`.

## Recommended next steps

> **Owner:** Shared

1. **OCR:** import the incoming bond paper and yellow pad datasets, which are the current blocker for OCR work. They should add new writers, give both paper types a writer-disjoint holdout, and support a retrain and re-evaluation on the same test set.
2. Tighten the RLS policies once teachers log in: they are enabled on every table but still allow any caller with the publishable key. (The frontend key was corrected in `a448198`.)
3. Keep the Angular dependency install matched to the operating system used for testing; the complete frontend suite passed at the 2026-09-24 checkpoint.
4. Add authentication and rate limiting to the OCR and Judge0 wrapper services.
5. Move API endpoints and mobile Supabase configuration into environment-specific configuration.
