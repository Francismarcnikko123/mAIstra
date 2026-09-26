# mAIstra — Project docs

## Web update — 2026-09-26 (read with the block below)

Review Code (Step 2) has a **Save** button next to the program tabs (and
Cmd/Ctrl+S). It saves every tab of the paper and keeps the teacher on the step,
so checking several programs and then grading no longer means closing and
reopening the paper. The footer button is now **Continue to grading** (it still
saves first), and the unsaved-changes prompt offers Keep editing / Discard
changes. Branch `feature/program-tabs-save`, merged into `feature/pre-extraction`;
web tests 121/121. Details: [overview](PROJECT_OVERVIEW_AND_CHANGES.md)
("Save next to the program tabs"), [web guide](web/WEB_CODEBASE_GUIDE.md),
and the handoff in [TEAM_SYNC.md](TEAM_SYNC.md).

## Current integration state — 2026-09-24

`feature/pre-extraction` is pushed and includes the program-tabs work from
`feature/program-tabs`. Auto-extraction is off by default. With the OCR server
enabled, a new paper shows **Extracting…** and then **Needs review** without a
reload; the live phone-photo, server-off, and restart catch-up checks passed.
The OCR suite passed 231/231 tests and the web suite passed 114/114 at that
checkpoint. See the [implementation plan](superpowers/plans/2026-09-24-pre-extraction-on-arrival.md),
[running guide](setup/RUNNING_LOCALLY.md), and [project overview](PROJECT_OVERVIEW_AND_CHANGES.md).

Nikko owns mobile question selection and sending the paper's `question_id`
(Program 1's question). Jayrald owns the remaining cloud schema and migration
work, including `answers`, `gate_result`, validated-question fields and question
sections. The user can test the OCR worker on new papers independently; testing
Nikko's complete new flow against the shared cloud waits for the schema work.
See [TEAM_SYNC.md](TEAM_SYNC.md) for the handoff and current owner decisions.

This directory contains both current guides and dated design/research records.
Some files are tracked and pushed even though `docs/` is gitignored by default;
older status statements remain as historical snapshots. Start with this block,
the overview and TEAM_SYNC for current state.

## OCR data status — 2026-09-23

OCR is code-complete for now. Continuation association is live (2026-09-17), 207 tests
pass, and the live evaluator shows clean_ws CER 0.099. **The project is waiting for the
new bond paper and yellow pad datasets.** Start with [`NEXT_STEPS.md`](NEXT_STEPS.md)'s
2026-09-23 block for why these matter and the import checklist.

**Web, 2026-09-24:** program tabs are on `feature/program-tabs` and were brought
into `feature/pre-extraction` (both pushed; neither merged to `main`).
One paper can now hold several programs, each linked to a question. See
[`web/WEB_CODEBASE_GUIDE.md`](web/WEB_CODEBASE_GUIDE.md) and the plan
[`superpowers/plans/2026-09-23-extra-program-editors.md`](superpowers/plans/2026-09-23-extra-program-editors.md).
Cross-team changes, requests and open questions are in [`TEAM_SYNC.md`](TEAM_SYNC.md)
(tracked; edit only the Nombrado section).

## OCR reference — 2026-09-14

[session handoff](../ocr_feature/reports/2026-09-14-continuation-session-handoff.md) is the committed session handoff: prototype versus live behavior, terminal
photo testing, measured results and remaining work. Most guides here remain local
and gitignored; the project overview and selected setup/spec files are tracked
exceptions. Use the committed handoff when sharing this session with another
checkout. All 11 supplied photos were used; Example 7 is an unresolved ID mapping.

This folder is gitignored by default, with selected files force-tracked and
pushed. It tracks
design decisions, fixes, and known limitations as work happened, so context
isn't lost and doesn't need re-deriving later.

> **⚠️ OCR STATUS (2026-08-30) — fine-tuning has happened; read
> `NEXT_STEPS.md`'s 2026-08-30 status block first, not the block below.**
> `PP-OCRv6_medium_rec` has been fine-tuned on 2,491 physically-verified
> handwritten C-code line crops and is now the pipeline's required
> recognizer (no stock fallback). CER dropped **0.274 (stock) → 0.126
> (fine-tuned), −54%** on a genuinely held-out 20-image test set — the
> "fine-tuning target" the block below describes is done, not future work.
> The block below is kept for history; do not cite its `0.149` baseline as
> current (it's a different, easier, retired test set — see
> `EVALUATION.md`'s methodology note).
>
> **OCR STATUS (2026-08-03) — supersedes the 2026-08-02 retraction.** All 13
> sample labels were physically verified and carry literal provenance, so the
> evaluators run and their numbers are citable. Models were swapped to
> **`PP-OCRv6_medium`**. **Baseline update 2026-08-04:** the original 13-page
> `0.148` is superseded (5 non-representative `nikko` close-ups deleted); the
> current reproducible baseline is **`clean_ws 0.149`** over 14 samples, all
> gate-framed (deconfounded raw-vs-gate experiment ran 2026-08-06, then two
> `writer1` pages added — see the EVALUATION.md entry below; `0.190`/`0.151`
> were interim figures); v6 still beats
> v5 `0.181` (see `ocr/EVALUATION.md`). Consensus was evaluated, rejected, and its
> code removed 2026-08-04
> (pipeline is baseline-only). The dominant residual error is handwritten C punctuation (braces
> ~0% recall) — the fine-tuning target. Source restructured: evaluators live in
> `ocr_feature/evaluators/` (run `python -m evaluators.evaluate_cer`), tests in
> `ocr_feature/tests/` (run `python run_tests.py`).
> _Superseded 2026-08-02 retraction: held `.181`/`.186` and all rankings
> uncitable because the labels were unverified — resolved by the verification._

## Start here

- [`CODE_REVIEW_2026-09-24.md`](CODE_REVIEW_2026-09-24.md): the latest code review (10 findings, all fixed, accuracy unchanged) and why bugs keep turning up outside the algorithms.

- [`NEXT_STEPS.md`](NEXT_STEPS.md) — current project state: what's done, what's
  valid vs retracted, what's blocked, and what's next. Read this first when
  resuming work.

## OCR backend (`ocr_feature/`)

- [`ocr/README.md`](ocr/README.md) — setup, how to run, file overview
- [`ocr/PIPELINE.md`](ocr/PIPELINE.md) — how extraction works and why (model
  selection, reading-order correction, confidence filtering, cleanup scope),
  with the measurements behind each decision
- [`ocr/EVALUATION.md`](ocr/EVALUATION.md) — CER methodology and the current
  20-page production result: **clean_ws CER 0.099**, clean WER 0.328 and
  clean token accuracy 0.716. Its earlier 14-page `0.149` baseline and other
  cohort figures remain in the dated evaluation history; do not cite them as
  the current production result.
- [`ocr/OCR_REVIEW_SUGGESTION_AB.md`](ocr/OCR_REVIEW_SUGGESTION_AB.md) —
  2026-09-05 A/B of the current exact function-call suggestion table against a
  guarded one-edit candidate, including the rejected naïve variant, held-out
  results, literal-transcription false-alert controls, and implementation gate
- [`ocr/LIMITATIONS.md`](ocr/LIMITATIONS.md) — known limitations and why
  fine-tuning is the identified next step
- [`ocr/TROUBLESHOOTING.md`](ocr/TROUBLESHOOTING.md) — environment/setup
  issues and fixes (cross-platform requirements.txt, PaddlePaddle bug)
- [`ocr/FINE_TUNING_READINESS.md`](ocr/FINE_TUNING_READINESS.md) — status
  report: what "ready" means precisely, evidence table, what blocks the
  fine-tuning phase and who owns each blocker, work still to be written
- [`ocr/DEFENSE_PREP.md`](ocr/DEFENSE_PREP.md) — code-test study guide:
  file-by-file walkthrough, every magic number with its defense,
  counterfactuals ("what breaks if this line changes"), likely panel
  questions with answers
- [`ocr/CAPTURE_GATE_FINDINGS.md`](ocr/CAPTURE_GATE_FINDINGS.md) — measured
  analysis of the mobile capture gate (`feature/document-scanner`) and its
  effect on OCR accuracy, plus the joint calibration protocol.
  **Written to be shared** with the teammate who owns that component;
  delivery notes are kept separately in `NEXT_STEPS.md`
- [`ocr/CAPTURE_GATE_FINDINGS_2.md`](ocr/CAPTURE_GATE_FINDINGS_2.md) —
  round 2, reviewing `513661c`. **RETRACTED** — see round 3
- [`ocr/CAPTURE_GATE_FINDINGS_3_CORRECTION.md`](ocr/CAPTURE_GATE_FINDINGS_3_CORRECTION.md)
  — **the current findings.** Retracts rounds 1–2: their CER numbers scored
  against `verified_text` values that were largely the OCR's own unedited
  output, making the comparison circular. Its later `0.095 → 0.083` and
  "best variant" statements are also historical canonical-reference
  diagnostics, not validated accuracy or a defensible ranking, until the
  referenced papers receive literal human transcription. It documents the
  verified-dataset contamination problem and a ground-truth validation
  protocol (§8) to stop this recurring at fine-tuning time. Shareable only
  with this correction attached

## Web verification UI (`maistra_web/`)

- [`web/WEB_CODEBASE_GUIDE.md`](web/WEB_CODEBASE_GUIDE.md) — file-by-file
  walkthrough of Nombrado's frontend work: the `code-editor` component
  (Ace wrapper + brace-depth Format button) in full, and the OCR-extraction/
  save-safety/feedback logic layered into `submissions-list.ts` and
  `services/supabase.ts`, plus the program tabs (2026-09-24). Companion to `ocr/CODEBASE_GUIDE.md` — same
  style, current-code reference rather than a changelog
- [`web/VERIFICATION_UI.md`](web/VERIFICATION_UI.md) — bugs found and fixed
  in the submissions verification panel, in the order they happened (read
  this for *why*; read `WEB_CODEBASE_GUIDE.md` for *how it works now*)

## Attribution

Most of the OCR-side work is self-contained. The web verification panel's
folder/topic UI was built by a teammate; documented fixes were applied on
top of that rewrite. Work touching another teammate's code (e.g. validating
the mobile app's capture-quality gate using OCR confidence data) is noted as
such, not implied to be a from-scratch build.
