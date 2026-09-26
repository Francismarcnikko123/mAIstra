# Handoff — read this if you're picking up cold

## Current state — 2026-09-26, evening (supersedes the blocks below)

- **Working branch for everyone: `judge0-integration`** (Jayrald's). It contains Nombrado's `feature/pre-extraction` (merged in `046b88c`) and Nikko's `feature/question-linking-v2` (`138ef02`). `feature/pre-extraction` is retired: don't build on it. Start new work on a branch made from `judge0-integration` and merge it back there; everything goes to `main` later in one merge.
- **Multi-program papers use the `submission_programs` table** (Nombrado's proposal, accepted and built by Jayrald: `20260926000600_add_submission_programs.sql`, applied to the cloud). One row per program on a page, Program 1 = position 1, each with `verified_text`, `question_id` and its own grade. `submissions.answers` is **dropped**. Program 1 is still mirrored to `submissions.verified_text` / `question_id` for the list and the OCR export.
  - The review code still works with `answers` **in memory** (`extraAnswers`, `{ code, question_id }`): Jayrald's `supabase.ts` maps table rows to that shape and `updateSubmissionText()` calls the `save_submission_programs()` database function. `answersColumnAvailable` now means "the programs table exists".
  - **Never save by writing `submissions.verified_text` directly** (e.g. from an old branch): the cloud still allows it, but Program 1 in `submission_programs` would not follow. Always save through `updateSubmissionText()`.
- **Saves are guarded by `grading_revision`** (Jayrald): if someone else changed the paper since it was opened, the save is refused, `saveStatus[id] = 'conflict'`, and the paper reloads.
- **Nombrado tasks:** (1) Save-label follow-ups: **done**, merged into `judge0-integration` (`4bf44f6`). (2) OCR training export reading every program from `submission_programs`: **done 2026-09-27** on `feature/ocr-export-programs` (`labels.csv` gained `program_blocks`; `build_recognition_dataset._pair_lines()` aligns each block separately; split pages are skipped by `compare_config.py` / `select_holdout.py`; OCR 250/250). Next OCR step: the bond / yellow pad datasets.
  - **Follow-up completed on `feature/review-save-followups` (`a2d39a3`):** one label beside Save now covers conflict and unsaved-after-save states; the old paragraph is removed and the missing-table warning is corrected. Web 306/306, program tabs 47/47, app/spec TypeScript and build pass (existing list CSS warning only); Chrome layout fixture 15/15. Playwright could not start because the local test package and bundled browsers are missing. This branch is awaiting review, not pushed or merged; the OCR export remains next.
- **Ownership:** `ocr_feature/`, `code-editor/`, the program tabs (`extra-answers.ts`, `program-tabs.css`, the tab/picker/Save-bar parts of `submissions-list.*`) are Nombrado's. `supabase.ts`, migrations, the save/conflict logic, grading and Judge0 are Jayrald's. Mobile and the question bank are Nikko's. Keep `code-editor.ts`'s `readOnly` input (Jayrald's Step 3 uses it).
- **Checks on `judge0-integration` (2026-09-26):** OCR 231/231, web 299/299, TypeScript clean, `ng build` passes (CSS budget warning on `submissions-list.list.css`, Jayrald's).

## Current state — 2026-09-24 (supersedes everything below)

- **Web, 2026-09-26:** `feature/program-tabs-save` (merged into `feature/pre-extraction`) adds a Save button next to the program tabs plus Cmd/Ctrl+S, removes "Save and close" from the unsaved prompt, and renames the footer to "Continue to grading" (logic unchanged, still saves first). Also `detectChanges()` after step changes (zoneless app; mirrors Jayrald's `8e20fd5`). Web tests 121/121. Commit messages must follow "Commit messages" in the repo-root `AGENTS.md`.
- **OCR:** continuation association has been **live** since 2026-09-17 (`core/continuation.py`). Pre-extraction on arrival is implemented on pushed `feature/pre-extraction`, off by default, with the same OCR pipeline and unchanged clean_ws CER 0.099 / WER 0.328 / token accuracy 0.716. New bond and yellow pad datasets remain the next accuracy evidence step.
- **Web:** pushed `feature/pre-extraction` includes pushed `feature/program-tabs` and the realtime **Extracting… → Needs review** list badge. The live phone-photo, server-off and restart catch-up checks passed. See `web/WEB_CODEBASE_GUIDE.md`, `setup/RUNNING_LOCALLY.md`, and the pre-extraction plan. At that checkpoint OCR tests passed 231/231 and web tests 114/114.
- **Integration:** Nikko owns the mobile `question_id` selection/sending (Program 1). Jayrald owns applying the `answers` migration and the cloud schema required by Nikko's complete question-linking flow. OCR worker behavior can be tested with new papers before that integration. See `TEAM_SYNC.md`.
- **Team coordination:** `docs/TEAM_SYNC.md` (tracked). Only edit the Nombrado section. Others don't touch `ocr_feature/`.

## Continuation handoff — 2026-09-14 (historical)

Start with [session handoff](../ocr_feature/reports/2026-09-14-continuation-session-handoff.md). The older August handoff below is historical. Current
association work is an offline prototype plus a manual terminal photo tester;
production OCR/web behavior is unchanged. Do not treat correct flattened order as
proof of answer membership. All 11 supplied photos were included; the skipped
Example 7 ID is unresolved bookkeeping. The report records the frozen evaluation,
known association gaps and concrete next steps for this branch.

> **⚠️ Dated 2026-08-06 — significantly stale as of 2026-08-30.** The
> "Colab fine-tuning dry run" line below ("not run end-to-end yet,
> pipeline-mechanics proof only") is no longer true: a real fine-tune has
> since run and shipped as the pipeline's default recognizer. See
> `NEXT_STEPS.md`'s 2026-08-30 status block for the actual current state
> (fine-tune result, model distribution, the three separate dataset
> batches in flight) before trusting anything below.

**Written:** 2026-08-06, by Claude, for whichever AI tool (Codex or otherwise)
picks this project up if this session runs out of usage. Written to be
self-contained — but "self-contained" is a trap if you trust every number in
here forever. **This file will go stale.** Verify anything load-bearing
against the live sources listed in each section before acting on it. The
project's own history includes deleting two earlier handoff docs
(`CHECKPOINT.md`, an older `CODEX_HANDOFF.md`) specifically because they
calcified and started contradicting the code. Don't let this one do that —
if you update project state, update this file's "Current state" section too,
or delete it rather than let it drift.

## What this project is

**mAIstra** — a vision-based handwritten C-code grading app; a thesis project.
Three people, three components:
- **John Cale Nombrado** (the user in this session) owns **OCR**
  (`ocr_feature/` — Python/FastAPI + PaddleOCR).
- **Nikko** owns the mobile **capture/quality-gate** (`maistra_mobile/`,
  Flutter, branch `feature/document-scanner`).
- A third teammate (Jayrald, per earlier project memory) owns another part —
  not touched in this session.

## Hard rules — do not violate these regardless of what else changes

1. **Never let AI-derived text become ground truth.** An AI (including you)
   may show extracted/transcribed text as a *reference*, but a human must
   independently verify it against the **physical paper** — not just the
   photo — before it goes into `samples/labels.csv`. Never edit
   `ground_truth_text` content yourself. See `docs/ocr/EVALUATION.md`'s
   "Adding a new sample" section.
2. **`samples/` = test set, `datasets/verified/` = train set. Never overlap.**
   An image verified via the web app's "Save Verified Text" button
   auto-becomes train-eligible (`export_dataset.py` pulls `status='verified'`
   from Supabase). Images destined for `samples/` must be verified by hand
   (chat → physical paper → paste back), never via that button.
3. **OCR cleanup only fixes closed C vocabulary** (keywords, standard
   headers) — never touch content that's actually being graded. This is a
   grading app; inventing/correcting a student's code is a rule violation, not
   a bug fix.
4. **Never reconstruct braces from indentation/layout.** A missing `{`/`}` may
   be the student's real mistake. Synthesizing one inflates the grade.
5. **No AI attribution in commits/PRs** (no `Co-Authored-By: Claude`,
   Codex, ChatGPT etc.) — standing instruction from the user across this
   whole project. **Every commit also needs a body** (what changed, why,
   checks run), docs and merge commits included. Full format and an example:
   "Commit messages" in the repo-root `AGENTS.md`.
6. **Read Nikko's branch read-only.** `git fetch` + `git show
   origin/feature/document-scanner:<path>` only. Never check out or merge it
   into `ocr_feature` — that's the team's own merge schedule.
7. **Never cite a CER baseline without checking which one is current.**
   `0.148` (the original 13-page cohort) is superseded and no longer
   reproducible. Baselines drift — see "Current state" below, but re-verify
   against `docs/ocr/EVALUATION.md`'s top banner before citing a number.
8. **Nikko's branch moves.** It was force-pushed once already during this
   project (commit hashes changed, content didn't). Always `git fetch` and
   re-read before trusting any doc's claim about his code — including this
   one.

## Where the real, current state lives (check these, not memory)

- **`docs/NEXT_STEPS.md`** — the actual "current state" doc (the de-facto
  checkpoint; there is no separate `CHECKPOINT.md`, it was deleted as
  redundant). Has a dated status block at the top — read that first.
- **`docs/ocr/EVALUATION.md`** — CER methodology, baseline history, what's
  superseded vs. current, symbol-level error profile.
- **`docs/ocr/QUALITY_GATE_REVIEW.md`** — Nikko's gate: what it does, what's
  been fixed, what's still open. Has a superseding banner at the top for
  anything below it that describes removed code.
- **`docs/ocr/PIPELINE.md`, `LIMITATIONS.md`, `FINE_TUNING_READINESS.md`** —
  how the pipeline works, what's fixable by engineering vs. needs fine-tuning,
  the fine-tuning readiness chain.
- **`docs/ocr/LINE_MERGE_INVESTIGATION.md`** — two handwritten rows fusing
  into one line (Mode 2 grouping). Diagnosis + fix (horizontal-overlap guard).
  Implemented + verified 2026-08-08, committed + pushed 2026-08-09 (`afd2ef2`).
- **`docs/ocr/PHANTOM_DETECTION_INVESTIGATION.md`** — detector inventing a line
  where there's no writing (the phantom `0`). Measured evidence + a candidate
  height-outlier filter, but deliberately BLOCKED on clean images: re-measure
  once the quality gate delivers clean captures before deciding a code filter
  is even needed. Do not implement preemptively.
- **`docs/ocr/COLAB_FINE_TUNING_GUIDE.md`** — 14-step verified procedure for
  the Colab fine-tuning dry run (build crops → Colab → PaddleX train/export →
  swap into `ocr_pipeline.py` → re-measure). Not run end-to-end yet; steps
  marked `[verified]` were checked directly against this repo's `.venv`.
  Pipeline-mechanics proof only at current volume, not a real fine-tune.
- **`ocr_feature/core/preprocess.py`** — inline comments carry the measured
  history of every preprocessing decision (why each default is what it is,
  what was tried and rejected). Trust this over any doc if they conflict —
  it's closest to the code.
- **`docs/web/VERIFICATION_UI.md`** — the `maistra_web` side (out of scope for
  everything else in this file, which is `ocr_feature` only). Bug-fix log for
  the verification widget plus the 2026-08-10 "Format" button feature
  (brace-depth indentation in `code-editor.ts`) — committed `9c719f3`
  (2026-08-11); stale "NOT committed" note removed 2026-09-02. See
  **`docs/web/WEB_CODEBASE_GUIDE.md`** for the current, code-level
  walkthrough of `code-editor.ts` (§2), including a 2026-08-18 styling
  change (`5ccd5e9`, a teammate's commit, layout-only — no behavior change)
  that made the component reusable outside `submissions-list`.

## Snapshot as of 2026-08-06 (verify before relying on any of this)

- **Test set:** `samples/labels.csv`, 14 usable rows, **all gate-framed** —
  7 `nombrado_*_gate.jpeg` pages (bond/greenbook, retaken through Nikko's
  gate 2026-08-06, replacing the old raw versions) + 5 `submission_*`
  pages (bond/greenbook/yellow_pad, writer1 + nikko) + 2 `writer1_*` pages
  (greenbook + bond). No raw pages remain in `samples/`. 5 dead `nikko_00N`
  pointers remain in the CSV (images deleted) and are skipped at eval time.
- **Baselines (all `clean_ws` CER):** current **`0.149`** over 14 samples, all
  gate-framed (bond 0.133 / greenbook 0.159 / yellow_pad 0.171). Historical
  figures `0.148`, `0.190`, `0.128`, and the transient `0.151` (the 12-sample
  figure from before the two `writer1` pages were added) are **superseded** —
  do not cite them as current.
- **Binarization off by default (2026-08-06):** `PreprocessConfig.threshold`
  flipped to `False` after a full-cohort A/B (`0.166 → 0.149`; PaddleOCR wants
  grayscale stroke gradients, not hard binary). The threshold code stays behind
  `threshold=True`. `REC_SCORE_FLOOR` re-verified safe under grayscale input.
- **THE DECIDING RAW-VS-GATE EXPERIMENT (2026-08-06):** 7 raw `nombrado_*`
  pages retaken through Nikko's gate, same writer/handwriting/content, only
  scanner crop/de-warp+JPEG differing. Result: bond worse under gate (+0.015
  avg, every page), greenbook better (−0.012 avg, 2/3 pages) — a real,
  paper-type-dependent effect, not a wash. Raw versions replaced with gate
  versions in `samples/labels.csv`; test set now 100% gate-framed. Full table:
  `docs/ocr/EVALUATION.md` top banner.
- **Training set:** `datasets/verified/`, 7 pairs exported via
  `export_dataset.py` (bond array/sum/add-function, greenbook array, + writer1
  three-snippets/star-loop/even-numbers added 2026-08-06). The greenbook pointer
  page `826cc0e5` was SKIPPED by the contamination guard (its verified_text ==
  extracted_text — saved unedited, not a real human correction). Never overlaps
  the test set — verified by content + count reconciliation.
- **Quality gate (Nikko, branch tip `d57a1bc`/`b404c8b` as of this writing —
  re-fetch to confirm):** ships **raw-only upload**. `processDocument`
  (illumination normalization) removed entirely. Scanner forked to
  `SCANNER_MODE_BASE`, removing the Enhance filter. Gate itself is read-only —
  four whole-frame checks (blur via top-third crop, dark/bright via
  clip-fraction), no photometric processing. See his own
  `QUALITY_GATE_STATUS.md` (he sent this directly, not in the repo) for his
  measured thresholds.
- **Open question RESOLVED 2026-08-06.** The deciding same-page raw-vs-gate
  experiment ran (see above) — the gate's effect is real and paper-type
  dependent (bond worse, greenbook better), not a texture-score artifact to
  chase further. *Why* bond and greenbook diverge is still unexplained
  (plausibly de-warp resampling costs sharpness on clean bond but helps a
  harder greenbook capture) but is not blocking — the net effect is measured.
- **Ruled-line removal in preprocessing:** built, measured (three variants:
  blunt width filter, smarter near-full-width filter, denoise-threshold
  lowering), and **removed** 2026-08-06 — none was a net win at any setting.
  Width alone can't separate a printed rule from a handwriting stroke. Full
  numbers in `EVALUATION.md`. If ever revisited, the direction is a
  straightness/periodic-spacing (Hough-based) detector, not morphological
  width filtering.
- **Consensus OCR mode:** evaluated, rejected, code fully removed (this was
  from an earlier phase of the project, well before this session).
- **Shared leaf modules (added 2026-08-07 in a dedup pass):**
  `core/c_literals.py` holds `C_LITERAL` (the string/char-literal regex, at the
  time shared by `c_code_cleanup.py` and `c_code_suggestions.py`); `core/numeric.py`
  holds `finite_float` (the "coerce to a finite float or None" guard used by
  `ocr_pipeline.py`, and at the time also by `c_code_suggestions.py`). Both are
  read-only leaves with no heavy deps — import them rather than re-declaring the
  pattern. Same pass deleted the unused `_group_into_reading_order` wrapper.
  Behavior-preserving: baseline still `0.149`. Full session summary:
  `NEXT_STEPS.md` top block. **(`c_code_suggestions.py` itself was later
  removed 2026-09-12 from `feature/reading-order-reassembly` as unused on that
  branch — see `docs/ocr/OCR_REVIEW_SUGGESTION_AB.md`'s banner.)**
- **Tests:** 78/78 passing as of last run (`python run_tests.py` from
  `ocr_feature/`); was 64/64 before the 2026-08-08 line-grouping fix (+3
  geometry tests), 67/67 before the 2026-08-09 code-review pass (+1
  end-to-end coverage test), and 68/68 before the 2026-08-10 WER/token-
  accuracy addition (+10 tests). Each `tests/test_*.py` also runs standalone
  via `.venv/bin/python -m tests.test_<name>`.
- **WER + token-level recognition accuracy (2026-08-10, NOT COMMITTED)** —
  `evaluate_cer.py` now also reports WER and a C-lexical-token accuracy
  metric, matching the thesis's objective 7 wording exactly. First measured:
  WER clean `0.656`, token accuracy clean `0.729`; CER baseline `0.149`
  unaffected. Full detail: `NEXT_STEPS.md` top block, `ocr/EVALUATION.md` top
  banner.

## Immediate next step

The raw-vs-gate experiment is **DONE** (2026-08-06) — the retakes came back,
the same-page comparison ran, and `samples/` is now 100% gate-framed at
`clean_ws 0.149` (14 samples). The engineering/pipeline side is stable; the
2026-08-07 code-quality pass (dedup + dead-code + measured comments) is the
most recent work (see `NEXT_STEPS.md` top block). What remains is **data
volume** plus **one scoped code task**:

0. ~~**Line-merge in grouping (Mode 2) — diagnosed, ready to implement.**~~
   **DONE — committed `afd2ef2` (2026-08-09), see `NEXT_STEPS.md`'s
   2026-08-09 status block.** (Left the original diagnosis text below for
   history/context only — do not re-implement this.) Two physically separate
   handwritten rows sometimes fused into one extracted line (e.g.
   `int main C){ int result = add (3, 4);`). Root cause and the fix (a
   horizontal-overlap guard in `_group_detection_records`, now in
   `core/layout/` since the 2026-09-13 split) are written up in
   **`ocr/LINE_MERGE_INVESTIGATION.md`**. Two things noted there at the time:
   (a) this did NOT move `clean_ws 0.149` because `normalize_ws` collapses
   newlines — it was measured against `build_recognition_dataset.py`'s
   skip-rate instead; (b) the fix deliberately did NOT lower the vertical
   `0.6` tolerance — the doc explains why distance-based levers can't
   separate these rows.

1. Keep collecting papers — more writers, longer/brace-heavy programs, and
   especially raw pad coverage (still thin). Current dataset is nowhere near
   the 1,000–2,000+ line minimum a real fine-tuning attempt needs (see
   `FINE_TUNING_READINESS.md`).
2. For each new paper, same workflow as always: extract as reference → user
   verifies against the physical paper → paste back → file into
   `samples/labels.csv` (test) or app-verify + `export_dataset.py` (train).
   Never let extracted text become ground truth without physical-paper review.
3. Once volume is usable, build the fine-tuning dataset and re-measure CER
   against the current `0.149` baseline.
4. **As of 2026-08-28:** the transcription/verification pass described above
   is live in `~/Desktop/image_to_transcribe/` (outside this repo) — bond
   22/22, greenbook 145/145, yellow_pad 22/22 all 1:1 image-to-`.txt`, all
   Claude-vs-photo checked. A teammate is now running the physical-paper pass
   per `image_to_transcribe/VERIFICATION_INSTRUCTIONS.md`; his edits get
   diffed against Claude's pre-verification versions once he reports a folder
   done (`dual-verification-then-diff` project memory). `labels.csv` rebuild
   stays blocked until that reconciliation finishes for all three folders.
   Full detail: `NEXT_STEPS.md`'s 2026-08-28 status block.

## Useful commands

```bash
# Run tests
cd ocr_feature && python run_tests.py

# Run CER evaluation (loads real OCR models, takes a minute+)
cd ocr_feature && .venv/bin/python -m evaluators.evaluate_cer

# Export newly-verified Supabase submissions into training data
cd ocr_feature && .venv/bin/python -m evaluators.export_dataset

# Check Nikko's branch (READ-ONLY — never merge/checkout)
git fetch origin
git log origin/feature/document-scanner --oneline -10
git show origin/feature/document-scanner:<path>
```

## If you're an AI reading this to continue the work

Don't skip the hard rules section. The single most-repeated correction across
this project's history has been AI tools (including earlier sessions of
Claude) overstepping on ground-truth provenance or citing a stale baseline —
both are cheap mistakes to avoid by just re-reading the current docs before
acting, rather than trusting a summary (including this one).
