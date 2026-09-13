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

## OCR pipeline split into `core/layout.py` (2026-09-13)

> **Owner:** Nombrado

- `core/ocr_pipeline.py` had grown past **1,200 lines**, so the pure reading-order / indentation geometry was extracted into a new sibling module `core/layout.py` along the file's natural dependency seam (commit `f99732c`). **`ocr_pipeline.py`** (~275 lines) keeps recognition + orchestration (model construction, `warmup`, `REC_SCORE_FLOOR`, `_filter_low_confidence`, `_recognize_preprocessed`, `extract_text_from_image`) and is the only half that imports `cv2`/`numpy`/`paddleocr`. **`core/layout.py`** (~960 lines) holds all the geometry: `_group_detection_records`, the two-column / banded / severance detectors, brace-depth reassembly, `_group_structured_lines`, `line_member_bounds`, and indentation/blank-line reconstruction — pure stdlib + `core.numeric`/`core.c_literals`, so it loads in tests without the recognizer.
- **Behavior-preserving, not a rewrite:** function bodies were moved by exact line range, never retyped; no logic changed. `ocr_pipeline.py` re-exports the geometry names, so `from core.ocr_pipeline import _group_detection_records` (tests, `evaluators/build_recognition_dataset.py`) still works. Geometry unit tests load `core.layout` directly (`load_layout()`) so `patch.object` targets the module where the functions call one another — patching a re-export would not intercept those internal calls.
- Verified four ways: (1) an AST check confirms all **41** top-level definitions are byte-for-byte identical between the pre-split file and the post-split `ocr_pipeline.py` + `layout.py`; (2) running the real fine-tuned OCR on the gate set with the pre-split vs post-split code produced **byte-for-byte identical** `evaluate_cer` output (every per-file row and aggregate — clean_ws CER **0.099**, clean WER **0.328**, clean token accuracy **0.716**, green_writer10 clean_ws **0.061**); (3) full Python suite **148/148**; (4) all pipeline callers (`main`, `try_config`, `compare_config`, the three evaluators, `build_recognition_dataset`) import cleanly and the re-exports are the same objects as `layout`'s definitions.

## OCR real handwriting margin calibration (2026-09-13)

> **Owner:** Nombrado

- Validated three original 1536×2048 handwriting photos through the live fine-tuned pipeline, preserving unedited detections as `writerX_marginA/B/C_detections.json`. A already reads left-then-margin via two-column detection; B/C now do so through banded detection.
- Changed only `BAND_GUTTER_MIN_MULTIPLIER` **1.5 → 0.5**, retaining its 60px floor, three-row persistence, x-alignment and uncrossed-band guards. B/C's confirmed band gutters are **108px / 189px = 0.571** and **171px / 138px = 1.239** median widths. Full-page gutters are A/B/C **157/67/48 processed px**; these must not be confused with band gutters.
- Kept `REGION_GAP_MULTIPLIER=0.75`, the historical 6.0 merge threshold, and every severance constant. Lowering the region seed did not fix these captures. All handwritten rows are single OCR boxes, so the confirmed within-line gap distribution is empty and provides no new seed calibration evidence.
- **16/16 braces survived OCR**, including B's initializer pair, but brace reassembly still made no move. The old B trace missed the final margin close; C's left-drifting closers collapsed its trace gutter. Recognition is necessary but not sufficient for this path.
- Old/new grouping is identical across **315 historical artifacts / 262 distinct detection payloads**; live detections on the three new photos also match exactly before/after. Fabric false positives and OCR spelling errors remain untouched for teacher verification.
- Full Python suite **157 passed** (148 + 9). The trace-only test helper now disables banded interception; the original 12/13-line cap inputs and assertions are unchanged. Live 20-sample evaluator retains clean_ws CER **0.099**, clean WER **0.328**, clean token accuracy **0.716**, green_writer10 clean_ws **0.061**, with identical printed per-file tables.
- Complete boxes, raw/cleaned extractions, mechanism traces, brace audit, gap measurements and reproduction steps: [real margin validation](../ocr_feature/reports/2026-09-13-real-margin-validation.md).

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

- Rotate the Supabase `service_role` key currently exposed in Angular configuration and replace it with an anon or publishable key.
- Never place a Supabase service-role key in browser or mobile code.
- Add complete Row Level Security policies for questions, submissions, and storage objects.
- Restrict access to handwritten submission images or serve them with signed URLs.
- Authenticate and rate-limit the OCR and Judge0 wrapper APIs.
- Restrict the OCR URL downloader to trusted storage hosts and enforce download-size limits.
- Move hardcoded service URLs into Angular environment configuration.
- Add missing migrations for application columns such as `question_type`, `topic`, and `question_id`.

## Recommended next steps

> **Owner:** Shared

1. Rotate the exposed Supabase service-role key and correct the frontend key.
2. Add and verify Supabase migrations and RLS policies.
3. Reinstall Angular dependencies on the operating system used for testing, then run the complete frontend suite.
4. Add authentication and rate limiting to the OCR and Judge0 wrapper services.
5. Move API endpoints and mobile Supabase configuration into environment-specific configuration.
