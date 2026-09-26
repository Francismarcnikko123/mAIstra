# Claude Handoff: Handwritten C-Code Dataset

> **Commits:** always a subject *and* a body (what changed, why, checks run),
> and never any AI attribution (`Co-Authored-By` Claude/Codex, "Generated with").
> Full rule and example: "Commit messages" in the repo-root `AGENTS.md`.

## Current integration state — 2026-09-24

**Update 2026-09-26:** Review Code now has a Save button next to the program
tabs (every tab, stays on Step 2, Cmd/Ctrl+S); the unsaved prompt is Keep
editing / Discard changes; the footer reads "Continue to grading". Branch
`feature/program-tabs-save`, merged into `feature/pre-extraction`; web tests
120/120. See TEAM_SYNC for the handoff.

The pushed `feature/pre-extraction` branch includes the pushed
`feature/program-tabs` work. Auto-extraction is off by default. When enabled,
the worker fills `extracted_text` for eligible new papers, and the web badge
changes **Extracting… → Needs review** through a realtime UPDATE. The user
live-tested that transition, the server-off **Needs OCR** state, and restart
catch-up with a recent `AUTO_EXTRACT_SINCE`. At this checkpoint OCR tests were
231/231 and web tests 114/114; the measured OCR accuracy was unchanged.

Nikko owns choosing/sending the mobile paper's `question_id` (Program 1);
Jayrald owns applying the `answers` migration and the remaining schema needed
for Nikko's full question-linking flow. The worker can be tested on new papers
before that integration. See `docs/README.md`, `docs/TEAM_SYNC.md`, and the
pre-extraction plan for current details. Older status blocks below describe
their dates, not the present branch tip.

## Current state — 2026-09-23 (supersedes the 2026-09-14 block below)

OCR code work is complete for now. **The project is waiting for new bond paper
and yellow pad datasets.** Those are the paper types with the weakest evidence:
the held-out `samples/` set has only 2 bond and 4 yellow_pad pages, all from
writers also seen in training, so new-writer accuracy on these paper types is
unmeasured (`docs/ocr/LIMITATIONS.md`). Current data:
`datasets/verified/` has 168 pages (greenbook 131, bond 20, yellow 17), and
`samples/` has 20 (greenbook 14, yellow_pad 4, bond 2).

When the new papers arrive, follow `NEXT_STEPS.md`'s 2026-09-23 block. Continuation
association is **live** (`core/continuation.py`, `7640127`), not offline-only.
The web app receives it automatically through `extract_text_from_image`. 207 tests
pass; the live evaluator shows clean_ws CER 0.099 / clean WER 0.328 / clean token
accuracy 0.716.

**Deferred pages are excluded (user decision 2026-09-23).** The 7
`deferred_needs_line_exclusion/` pages will NOT be added with the next batch.
They are likely existing B1–B3 writers, two of them possibly test-set writers
(`green_writer13_B2`, `green_writer10_B2`), so they risk leaking test writers into
training and add no writer diversity. The per-line exclusion manifest in the
"Required next implementation" section below is therefore **shelved, not next**.
Evidence: `NEXT_STEPS.md`'s 2026-09-23 block.

**Web, 2026-09-24:**
- **Program tabs** are on branch `feature/program-tabs`, branched from `feature/reading-order-reassembly` and pushed. They make no OCR change. See `web/WEB_CODEBASE_GUIDE.md` and `superpowers/plans/2026-09-23-extra-program-editors.md`.
- **Team coordination:** `TEAM_SYNC.md` (tracked; edit only the Nombrado section). Teammates don't touch `ocr_feature/`.

## OCR session — 2026-09-14 (historical)

Read [session handoff](../ocr_feature/reports/2026-09-14-continuation-session-handoff.md) before using the older notes below. *At the time*, the association
prototype was offline only (`c991a7a`). It was integrated live on 2026-09-17. A manual
photo tester now lives at `ocr_feature/tests/manual_continuation.py` with run
instructions in its docstring. Reading order matches 8/8 development and 3/3
available reserved pages, but association remains incomplete and some cases
abstain. All 11 supplied photos were used. “Example 7 missing” is an unresolved
numbering mismatch, not a confirmed missing paper. Do not ask for a rewrite on
that basis. Additional writers are for future generalization evaluation, not a
prerequisite to run the tester. Preserve the frozen rules and recorded holdout.

## Teacher OCR-review UI (2026-09-05)

**Defense scope note:** not part of the defended scope (extract → save →
display for teacher editing). Stays on the experiment branches, unmerged.
Live testing found a real detection ceiling — some misreads land on valid
text and are invisible to any rule/parser/dictionary check without the
source image — so this is future work pending more training data, not a
finished feature to present. Raise it only if asked, framed honestly as an
explored prototype with a known, understood limit.

The Angular Review Code stage on `confidence-flagging-experiment-backup` combines
line confidence, conservative backend suggestions, and deterministic
current-text anomalies into violet OCR-review markers. These are transcription
review aids, not C syntax diagnostics.

Document-level structural imbalance stays in a banner **only for the count
mismatch itself** — that always cannot be pinned to one line (an opener left
unclosed by end-of-document has no single "where"). **Update 2026-09-05:** a
mismatched or orphaned CLOSER now *is* locatable and is flagged on its exact
line — `ocr-review-flags.ts`'s `detectBracketMismatches()` walks the text with
a bracket stack and reports the line where a `)`/`]`/`}` doesn't match what's
open (or has nothing open at all), instead of only the whole-document totals.
On a mismatch it still pops the stack (treats the closer as intended for the
innermost opener, just the wrong bracket type) so one bad character can't
cascade into false flags for the rest of the file. The same pass also widened
the "unusual line" check from exactly 1–2 alphanumeric characters to any short
(≤3 char) fragment that isn't a finished statement, label, or pure
punctuation — catching garbage like `s%d` that the narrower rule missed.
Separately, the backend (`c_code_suggestions.py`) now also flags a likely
misread word **inside** a printed message (e.g. `valind`→`valid`) against a
small curated word list, one edit-distance only, ties skipped — this is a
flag pointing at the paper, never a correction, since a message word's origin
(OCR vs. the student's own spelling) can't be determined. Empty findings
panels must not render; unmarked lines must not be described as correct or
confident; and no finding may auto-correct OCR or teacher text. Editing a row
dismisses extraction-era evidence for that row, while insertion or removal
invalidates stale line mappings. A fresh extraction replaces the prior
evidence.

Before changing this UI, read:

- `docs/superpowers/specs/2026-09-05-ocr-review-highlighting-design.md`
- `docs/PROJECT_OVERVIEW_AND_CHANGES.md`

Keep the review inside the existing `SubmissionsListComponent`, preserve the
original OCR output separately from teacher-edited and verified text, and keep
all existing save, destruction, grading, and function-harness protections.
Template regression specs read component HTML with Node's built-in `fs` module.
`@types/node` is therefore a development dependency and `tsconfig.spec.json`
includes the `node` type library; keep those types scoped to tests rather than
the browser application configuration.

### Function-call suggestion A/B (evaluated, not implemented)

> **⚠️ Removed 2026-09-12.** The OCR-review *suggestions* backend this document describes was deleted from `feature/reading-order-reassembly` (commit 43addce) as unused on that branch. Kept for history.

The current backend exact-match suggestion table does not catch `scainf` →
`scanf`. A 2026-09-05 A/B on identical cached OCR output for 20 held-out pages
found 0 suggestions from the current rules versus 3/3 helpful suggestions from
a refined unique one-edit matcher. The refined matcher also caught `scainf`
and produced 0 alerts across 188 literal-transcription negative controls.

Do not implement a naïve edit-distance rule: its first version falsely flagged
three student-written `print(...)` calls. Any implementation must keep the
measured guards for ambiguous `print`/`scan`, strings/comments, and functions
declared by the student. It must remain a soft, non-mutating OCR-review signal,
not automatic cleanup or syntax diagnosis. The positive count is only three,
and the guards were refined after inspecting false alerts in the same data, so
3/3 is exploratory rather than an unbiased precision estimate. Require a new
untouched validation set before making a performance claim. Read
`docs/ocr/OCR_REVIEW_SUGGESTION_AB.md` before changing suggestions.

> **Scope note (2026-08-30):** this doc covers `dataset_review/`, which is the
> **qualification-review stage** of the training-data pipeline, not a separate
> or unused batch. Its purpose is to decide which raw photos are good enough
> to proceed; the `usable/` folder (137 photos, mostly greenbook) then went
> through the quality gate → transcription → physical-paper verification →
> rename to the `writer<N>` convention, becoming the greenbook portion of the
> verified training set that produced the first fine-tune (CER 0.274→0.126).
> Full lineage (one pipeline, sequential stages — NOT competing batches):
> `dataset_review/usable/` (raw, triaged) → **quality gate crop/de-warp** →
> `image_to_transcribe/` (gate-cropped, ready to transcribe) → transcribe +
> physically verify + rename to `writer<N>` →
> `~/Downloads/image_to_transcribe_verified/` → import →
> `datasets/verified/` (committed training set). This is why the
> now-deleted `~/Desktop/image_to_transcribe/` matched the verified batch
> byte-for-byte: it was the gate-cropped intermediate, the same images one
> step before the rename. The only part of
> `dataset_review/` NOT yet in training is `deferred_needs_line_exclusion/`
> (7 pages awaiting the per-line exclusion manifest — see
> `docs/ocr/PER_LINE_EXCLUSION_HANDOFF.md`) and `not_usable/` (1, excluded by
> design). Full current picture: `NEXT_STEPS.md`'s dataset-provenance bullet.

## Current objective

Prepare the handwritten C-code images for recognition training. Classifications must
be based on the actual image pixels, not on previous verdicts or filenames.

Before changing the OCR dataset pipeline, read these existing project documents:

- `docs/CODEX_HANDOFF.md` — project ownership, ground-truth provenance, and hard rules
- `docs/NEXT_STEPS.md` — current OCR status and remaining work
- `docs/ocr/PER_LINE_EXCLUSION_HANDOFF.md` — scoped design for this exact deferred-line task
- `docs/ocr/DEFERRED_LINE_PROBE.md` — empirical check of whether scribbles merge with
  clean code in the same detected line (they mostly don't); read before designing the
  exclusion manifest's granularity
- `docs/ocr/DATASET_REVIEW_DETECTION_BASELINE.md` — full-batch (148 images) detection
  baseline on raw, un-gated dataset_review/ images; confirms the desk background is not
  causing phantom detections, but the quality gate is still required for angle
  correction and for the unreviewed friend-submitted batches
- `docs/ocr/FINE_TUNING_READINESS.md` — fine-tuning prerequisites and dataset constraints
- `docs/ocr/COLAB_FINE_TUNING_GUIDE.md` — downstream crop/training workflow
- `ocr_feature/dataset_review/VERDICTS.md` — current image-level decisions

If these documents conflict with this handoff, verify the live code and the newest
dated status block before acting. Do not replace the project’s provenance rules with
assumptions from this file.

## Review source and current status

The human-reviewed image staging set is:

`ocr_feature/dataset_review/`

Current verified folder counts:

- `usable/`: 137 images
- `usable_if_cropped/`: 3 images
- `deferred_needs_line_exclusion/`: 7 images
- `not_usable/`: 1 image

Three duplicate files were removed from the folders after the latest audit:
`IMG_0256`, `IMG_E0250` (duplicates of canonical `IMG_0250`), and `IMG_0351`
(duplicate of `IMG_0350`). The verdict table retains them as `dropped` for audit.

The detailed file-level decisions are in:

`ocr_feature/dataset_review/VERDICTS.md`

The folder contents and verdict table have been checked against each other. Do not
reclassify images by synchronizing with an old verdict; inspect the actual images.

## Categorization rules

- `usable`: C code is legible. Erasures, ticks, circles, grading marks, scratch work,
  readable strike-throughs, and additional legible handwriting do not disqualify it.
- `usable_if_cropped`: the page needs a simple page-level trim or orientation fix
  before line extraction. This is not the same as normal line-level cropping.
- `deferred_needs_line_exclusion`: keep the readable lines, but exclude only lines
  containing genuinely unrecoverable scribbles, whiteout, or erasure. Do not discard
  the whole page.
- `not_usable`: exclude because relevant content is materially unreadable or there is
  no useful C/algorithm content.

## Cropping and builder behavior

The recognition dataset should eventually contain one cropped image per handwritten
line for every accepted page:

1. `usable`: detect lines and crop them normally.
2. `usable_if_cropped`: apply the required page-level crop/rotation, then detect and
   crop lines.
3. `deferred_needs_line_exclusion`: detect lines, retain readable lines, and skip the
   explicitly obscured lines. This requires a per-page exclusion manifest or equivalent
   line-selection support.
4. `not_usable`: do not generate training samples.

The current implementation is:

`ocr_feature/evaluators/build_recognition_dataset.py`

> **⚠️ Updated 2026-08-30 — the two paragraphs below describe the builder's
> OLD behavior and are stale.** Since commit `aedd444`: (1) it reads ONLY
> `datasets/verified/labels.csv`, never `samples/` (test-set isolation); and
> (2) it no longer skips a whole page on any line-count mismatch — a
> monotonic line-alignment (`_align_lines`) pairs ground-truth lines to
> detected lines and keeps a page as long as ≥65% of its lines align
> confidently. **Still genuinely unbuilt:** the `deferred_needs_line_exclusion/`
> per-page *exclusion manifest* (a human explicitly marking which line
> indices to drop) — that's the actual task this handoff describes, and the
> alignment logic does not replace it (alignment handles OCR
> over/under-detection, not a human decision to exclude a scribbled line).

It currently reads `samples/labels.csv` and `datasets/verified/labels.csv`, not the
review folders. It crops detected lines, but if OCR line count and ground-truth line
count differ, it skips the entire page. It does not yet support page-level exclusion
lists or per-line label alignment for deferred pages.

The per-line exclusion change is additive: preserve the existing all-or-nothing skip
behavior for pages outside `deferred_needs_line_exclusion/`. Never guess the text of an
excluded line and never turn AI/OCR output into ground truth.

## Sequencing decision (2026-08-18)

`usable/` (137 pages, real training volume) and `deferred_needs_line_exclusion/`
(7 pages) are both blocked on the same human transcription step. **Transcribe
`usable/` first.** Building the per-line exclusion manifest for the 7 deferred
pages is deferred until that pass is underway — when a human transcribes a
deferred page anyway, they can note its excluded line indices in the same
pass, so the manifest becomes a small follow-up rather than a separate
blocking effort. See `docs/ocr/DEFERRED_LINE_PROBE.md` for why this is safe to
defer: a whole-line exclusion design (no sub-line cropping) already covers
what the real detector output shows on these 7 pages.

## Required next implementation (SHELVED 2026-09-23)

> Shelved: the deferred pages are excluded from the next batch (see the
> 2026-09-23 note at the top). Kept for reference in case they are ever used.
> Before any such use, confirm each page's writer with the physical papers.

Extend the dataset-building workflow without silently misaligning labels:

- Add a reviewed-page or per-page exclusion manifest for deferred images.
- Represent excluded line numbers/ranges explicitly.
- Crop only retained lines and pair each crop with the matching ground-truth text.
- Keep all accepted `usable` pages in the normal path.
- Apply page-level preprocessing for the three `usable_if_cropped` images before line
  detection.
- Report skipped pages and excluded lines clearly.
- Verify that every emitted crop has exactly one matching label.

Do not treat a deferred page as entirely unusable merely because some lines are
obscured. Do not use image-wide cropping to hide an obscured middle line when readable
content exists both above and below it.

## Important files

- `ocr_feature/dataset_review/VERDICTS.md` — authoritative human review and rationale
- `ocr_feature/evaluators/build_recognition_dataset.py` — line-crop dataset builder
- `ocr_feature/datasets/verified/` — verified training-page inputs
- `ocr_feature/samples/` — sample/test-page inputs
- `ocr_feature/datasets/recognition/` — derived line-crop output
- `docs/ocr/PER_LINE_EXCLUSION_HANDOFF.md` — detailed scoped implementation handoff
- `docs/ocr/DEFERRED_LINE_PROBE.md` — scribble/clean-code separation probe + sequencing decision
- `docs/ocr/DATASET_REVIEW_DETECTION_BASELINE.md` — full-batch raw detection baseline (148 images)
- `docs/CODEX_HANDOFF.md` — project-wide safety and provenance rules
