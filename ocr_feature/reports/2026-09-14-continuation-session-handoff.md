# Handwritten code continuation — session handoff

> **2026-09-17 follow-up:** The five production-order expected failures described
> below are now fixed by `core/continuation.py` and the live column finalizer. All
> eight development pages match annotation, 204 tests pass with zero expected
> failures, and the live OCR metrics remain 0.099 clean_ws CER / 0.328 clean WER /
> 0.716 clean token accuracy (`green_writer10` 0.061). The historical notes remain
> below for provenance. The frozen prototype is unchanged; reserved Example 10 is
> still outside the live column gate, and additional writers remain necessary.
>
> **2026-09-23:** 207 tests pass. OCR work is now waiting for the incoming bond
> paper and yellow pad datasets, which will supply the additional writers mentioned
> above. See `docs/PROJECT_OVERVIEW_AND_CHANGES.md`.

Date: 2026-09-14. Branch: `feature/reading-order-reassembly`.
Read this before resuming OCR association work. This is the current summary;
older plans and local guides retain dated historical results.

## User's requirement

Students can continue the same handwritten C function on the right to save space
below, then put another answer below or in another column. Infer which blocks
continue which code and in what order; do not assume one page = one program,
one column = one answer, or one function = one answer. Retain every recognized
character. Wrong student syntax must not be repaired by the ordering layer.

## Current implementation boundary

- **Production:** `core/ocr_pipeline.py` loads the fine-tuned recognizer, extracts
  and filters records, invokes `core/layout.py` (since 2026-09-17 the `core/layout/`
  package), and keeps raw/cleaned text separate.
  Its shorter size comes from the September 13 layout-module extraction. The
  offline experiment did not remove recognition code or shorten the pipeline.
- **Existing ordering:** full two-column, banded, severance and brace-assisted
  paths remain as before. Full-column ordering can bypass local association and
  put all left blocks before all right blocks, misplacing an upper continuation
  after the next question. Misread braces are not the only cause.
- **Offline prototype:** `evaluators/continuation_prototype.py` discovers local
  bands from unedited OCR records and emits detection order plus continuation,
  independent or ambiguous decisions with reasons. It uses geometry, headings and
  recognized C-scope evidence. It does not load labels or reference answers.
- **Not integrated:** neither FastAPI nor the web app imports the prototype.
  Running this feature in the web page still uses production ordering. No new
  model, weights, detection threshold or production layout threshold was added.
- **No automatic learning:** running more photos does not train the OCR model.
  Its fine-tuned weights are fixed until an explicit training/update process.

## Completed evidence

Relevant commits before this manual-runner update:

| Commit | Work |
| --- | --- |
| `0031e3e` | Real A/B/C calibration: region multiplier stayed 0.75; band gutter multiplier changed 1.5→0.5 |
| `e7da92e` | Brace-assisted margin candidate fallback |
| `053cd83` | Earlier two-question screenshot regression fixture |
| `7634e7f` | Eight development photos annotated and live baseline measured |
| `c991a7a` | Frozen offline association prototype and reserved evaluation |

The A/B/C pages demonstrate reading order, not a general membership classifier.
Example 11 later produced a real-photo brace-assisted fallback activation, so the
old statement that the brace path has never fired on real handwriting is obsolete.
Recognized braces provide fallible structural evidence; they do not prove intent.
Missing/misread braces are not corrected by association.

| Set | Baseline exact retained-record order | Prototype order | Explicit association |
| --- | --- | --- | --- |
| Development, 8 pages | 5/8 | 8/8 | 6/7 proposed edges exactly match gold; 6/8 gold edges recovered |
| Reserved, 3 available pages | 2/3 | 3/3 | 1/1 proposed edge matches gold; 1/2 gold edges recovered |

These are same-writer, small-sample results, not general handwriting accuracy.
Every retained record survives: 90 development + 28 reserved. No proposed
continuation crosses an annotated answer boundary in these sets.

Details matter:

- Development 5, 6, 8: local continuations are placed before the next left answer.
- Development 9: correct order, but the target block includes helper + main start.
  Strict edge scoring counts that as one wrong exact edge and a missed gold edge;
  it does not cross into a different answer.
- Development 2 and 11: prototype abstains, inheriting correct baseline order.
- Reserved 10: upper-left → right → lower-left order improves, but only the first
  continuation edge is explicitly predicted. The return edge remains missing.
- Reserved 3: headings are readable, but a 45 px / 1.364 median-height local gutter
  fails the 2.0 gate; it abstains rather than classifying the independent answers.
- Reserved 12: two complete unnumbered functions; membership remains ambiguous.
- Recognition/filtering loses a brace on development 4, reserved 3 and reserved 10.
  Those losses happen before association. Correct retained order is not a complete
  or correct transcription.

Full evidence: [prototype report](2026-09-14-offline-association.md),
[development baseline](2026-09-14-development-baseline.md),
[development prototype JSON](2026-09-14-offline-association-development.json),
[reserved JSON](2026-09-14-offline-association-reserved.json).

## Example 7 is intentionally skipped

The user confirms supplying all papers from the revised writing instructions.
All **11 supplied photographs were included**, with no byte/pixel/visual duplicates
identified. The intake assigns them IDs 1–6 and 8–12. The original final numbered
writing list has not been reconciled with that mapping. Per the user's decision,
Example 7 is intentionally out of scope for this run and is not required for the
current experiment.

Treat Example 7 as **out of scope**, not a request for the user to rewrite
anything and not a blocker to testing. Existing frozen JSON fields named
`missing_examples` / `missing_reserved` still contain 7 as historical bookkeeping.
They remain untouched to preserve the recorded experiment; they are not proof of
a missing upload. A future dataset may assign a descriptive label if needed.

The reserved photographs were visually identified at intake and excluded from rule
tuning until after freeze; they were not wholly unseen images. Do not claim the
current evaluation is writer-disjoint. The frozen rule SHA-256 remains:
`3cb2cdde542605d2f3cfa5c3b4f21599fa1a24b572e188810de567efdf0ff298`.

## New manual terminal tester

`tests/manual_continuation.py` packages the previously supplied terminal snippet.
Its module docstring includes usage. From `ocr_feature`:

```sh
PYTHONPATH=. .venv/bin/python -m tests.manual_continuation --help
PYTHONPATH=. .venv/bin/python -m tests.manual_continuation "/path/to/photo.jpg"
```

Existing development paper, ready to run on this workspace:

```sh
PYTHONPATH=. .venv/bin/python -m tests.manual_continuation \
  outputs/continuation_association_intake/development/writerX_page05.jpg
```

Optional output root: append `--output-dir outputs/my_continuation_checks`.
Each invocation creates a unique `run-*` directory; it saves preprocessed image,
OCR debug detections/dropped records, and `comparison.json`. It never overwrites
fixtures, labels, previous runs or input photos. The model loads only after valid
CLI arguments; unit discovery does not invoke this script or run OCR.

The terminal prints current raw text, proposed order, relationship decisions and
reasons, changed-order status, retention check and report path. Proposed text is
one retained detection per line, **not final production whitespace/indentation**.
`ambiguous` means abstention, not correct baseline order. `supported` means heuristic
evidence, not semantic proof. The manual command does not grade accuracy without
ground truth and does not enable the feature in the live app.

Fresh smoke test: development page05, 15 retained records, both local continuations
recognized, intended order reproduced, no records changed, no upstream drops.

Reproducible frozen evaluations (no fresh OCR):

```sh
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_development --prototype
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_reserved
```

The reserved evaluator verifies rule and fixture hashes. Future manual runs are
exploratory and do not replace the first frozen evaluation result.

## What to do next in ocr_feature

1. **Use the manual tester now.** Inspect the saved photo/debug boxes alongside
   output. Classify failures as missing detection, wrong recognized text, wrong
   block boundaries, wrong association, or wrong final order. These need different
   fixes; another gap-threshold reduction cannot solve all of them.
2. **Keep v1 frozen; design a separate v2 offline.** Investigate explicit chains
   that return from right to left, finer helper/main boundaries, and heading
   evidence when a real gutter is narrow. Preserve an ambiguous alternative and
   avoid assuming that two functions mean separate programs. This session does
   not implement those rule changes.
3. **Add writer diversity for evaluation.** Ask other people to write a mix of
   independent columns, right-margin continuations, left→right→left chains and
   multiple functions in one answer. Record pseudonymous writer/page IDs, region
   boxes, intended next-block links, answer membership and genuine ambiguity.
   These are initially association-test data, not automatically training examples.
   Additional writers are not required to run the tester or continue development.
4. **Choose the next holdout before tuning v2.** Since reserved 3/10/12 results are
   now known, using their failure details to adjust rules makes them development
   evidence for the next version. Keep whole writers and duplicate/recaptured pages
   together in splits; preserve a fresh, separately held-out evaluation set.
5. **Diagnose brace loss separately.** Distinguish undetected ink, detected but
   empty/filtered recognition, and recognized wrong symbols. Consider model/data
   work only against that measured failure class; never invent missing student
   braces from expected syntax. Do not change the fine-tuned model merely because
   association is incomplete.
6. **Integrate only after offline acceptance.** Measure exact order, strict edge
   precision/recall, false cross-answer links, abstentions and record preservation
   separately. Then consider shadow-mode integration before teacher-visible
   automatic reordering. Keep original OCR and verified/edited text separate.

No general reliability claim or new-model requirement follows from this pilot.

## Documentation storage

The committed source of this session is this report plus the prototype report and
`docs/PROJECT_OVERVIEW_AND_CHANGES.md`. Existing guides under `docs/` are mostly
local/gitignored. Their current-state banners, command references and handoff links
were updated in this workspace without changing the repository's ignore policy.
Do not rely on an ignored local guide reaching another checkout: link this report.

## Verification of this session update

- TDD: runner tests first failed because the module did not exist; both pass after
  implementation. Help/missing-file paths do not import the OCR runtime.
- Full unittest discovery: **187 executed, 182 passed, 5 expected failures**. Those
  five are the existing production-order gaps, not successful acceptance tests.
- Fresh live `evaluate_cer`, 20 photos, exit 0: clean_ws CER **0.099**, clean WER
  **0.328**, clean token accuracy **0.716**, green_writer10 clean_ws **0.061**.
- The real manual page05 run matches its frozen 15-record fixture and annotated
  order exactly. It preserves text/score/box payloads and identifies two links.
- Frozen prototype hash and both recorded experiment JSON outputs are unchanged.
  The default production pipeline and model were not edited.
- New handoff/tester links checked across 21 documents; CLI help checked without
  model loading; `git diff --check` clean.
