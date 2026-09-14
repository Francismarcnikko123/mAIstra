# Offline continuation association experiment

Status: frozen prototype, not integrated into OCR or the web app. This is an
experiment with one writer, not a general handwriting accuracy claim.

## What was implemented

`evaluators/continuation_prototype.py` accepts only retained OCR records
(text, score, box), discovers candidate blocks, and returns stable detection IDs,
proposed continuation/independent/ambiguous relationships, and reasons. It cannot
read answer labels, example numbers, reference code, tests, or photographs.
The development evaluator alone compares its output with manual annotations.
No model was added and no production file, model weight, or threshold was changed.

The prototype uses the unique widest uncrossed horizontal gutter to propose two
sides. Within each side, ink gaps greater than 1.2 median box heights or recognized
numbered question headings start local bands. A right band needs exactly one
vertically overlapping left band and a local gutter at least 2 median box heights.
These are development-selected heuristic constants, not calibrated probabilities.
Local rather than page-wide gap measurement lets staggered bands be evaluated
without allowing a box to cross the proposed gutter.

Distinct recognized question numbers or two `main` entries support independence.
Otherwise, recognized opening/closing scope evidence supports continuation, with
complete literals/comments masked for evidence only. An uncertain lexical boundary,
unbalanced prefix, absent closing evidence, or competing insertion point causes
abstention. There is no character repair or use of compiler/answer correctness.
A continuation is inserted after its matching left block, before the next answer.
Every original record remains exactly once. Ambiguous decisions retain the current
pipeline order; that fallback can still be wrong.

This is deliberately limited to two sides and one plausible local target. It does
not implement a complete C parser, a learned semantic model, or page-boundary
recognition. A student syntax error or confidently misrecognized brace can still
mislead a heuristic. Multiple functions do not inherently mean multiple answers.

## Development results

| Example | Baseline exact order | Prototype exact order | Association result |
| --- | --- | --- | --- |
| 1 | Yes | Yes | Independent, distinct numbered headings |
| 2 | Yes | Yes | Ambiguous, local gap insufficient |
| 4 | Yes | Yes | Independent, two recognized main entries |
| 5 | No | Yes | Two exact continuation links |
| 6 | No | Yes | Two exact continuation links |
| 8 | No | Yes | Two exact continuation links |
| 9 | Yes | Yes | Continuation, but target also contains helper function |
| 11 | Yes | Yes | Ambiguous, local gap insufficient; baseline retained |

Exact retained-detection order improves from 5/8 to 8/8. All 90 retained records
are preserved without changing their text, scores or boxes. Missing recognition
content remains missing: Example 4's filtered closing brace is not restored.

Association and ordering are scored separately. The strict block-edge metric gives
6 correct out of 7 proposed continuation links (precision 0.857), with 8 annotated
links total (recall 0.750). Example 9 is counted as an incorrect exact edge plus a
missed gold edge because the inferred left block merges the helper and main start.
It stays inside the correct answer and preserves correct ordering; this is a block
boundary error, not a cross-answer merge. No proposed continuation spans different
annotated answers. Both independent decisions match annotation. Two relationships
are ambiguous. Correct ordering on those pages is inherited from the baseline,
not evidence that the prototype identified their membership.

Examples 2 and 8 have unnumbered functions. Writer-provided answer intent is useful
ground truth, but cannot always be proven from the image alone. Correct local
function continuation in Example 8 does not prove that its two functions belong to
different answers.

Full decisions, unchanged OCR text, orders and per-page scores:
[development results](2026-09-14-offline-association-development.json).

## Frozen evaluation protocol

The [freeze record](2026-09-14-offline-association-freeze.json) records the rule-file
SHA-256, development/held-out split, missing Example 7 and expected reserved layouts.
Rules were frozen before running reserved OCR. Examples 3, 10 and 12 were visually
identified at intake, so they are held out from tuning, not wholly unseen images.
Reserved results must not be used to tune this version. Future revisions that use
these failures require fresh evaluation papers, ideally from additional writers.

## Reproduction

From `ocr_feature`:

```sh
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_development --prototype
PYTHONPATH=. .venv/bin/python -m unittest tests.test_continuation_prototype -v
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_cer
```

The default development evaluator remains baseline-only and rejects reserved
examples. Prototype tests cover actual development failures, independence,
ambiguous unnumbered functions, missing/misread braces, comment/literal masking,
invalid geometry, narrow gaps, competing targets, scale invariance, duplicate
payloads and exact record preservation. The initial test run failed before the
module existed; the development Example 6 assertion then failed until local-gutter
candidate handling was implemented. The association scorer was also tested red
before implementation.

The five existing expected failures concern production ordering. They remain
expected failures because the runtime has not been changed; they are not passing
acceptance tests and must be resolved before a production fix is claimed.

## First reserved evaluation

| Example | Baseline exact order | Frozen prototype exact order | Decision |
| --- | --- | --- | --- |
| 3 | Yes | Yes | Ambiguous: 45 px local gutter, 1.364 median heights, below 2.0 gate |
| 10 | No | Yes | Upper-left → right continuation → lower-left |
| 12 | Yes | Yes | Ambiguous: two complete unnumbered functions |
| 7 | Missing | Not evaluated | Keep reserved when supplied |

All three available reserved pages have correct retained-detection order, versus
2/3 for the baseline. All 28 retained detections are preserved verbatim. Only one
page's order changes. This small result from the same writer cannot establish
unseen-writer reliability or claim that all three pages were classified correctly.
No rule changes were made after inspecting reserved OCR or results.

The prototype proposes one exact continuation edge, upper-left → right on Example
10, and no cross-answer links. That page also requires a return from right to
lower-left. The output order happens to preserve that final step, but the prototype
does not emit its association edge. Explicit edge recall is therefore 1/2, with
precision 1/1 on this tiny reserved set. Examples 3 and 12 are abstentions, not
successful independent-program classifications. Example 3 has recognizable
question headings but fails the conservative geometry gate before their evidence
is considered. Example 12 remains visually ambiguous about answer membership.

Recognition is still a separate limitation. Example 3's right loop closer and
Example 10's final function closer were detected with empty text/score 0 and dropped
upstream. Their original detections are logged separately. Example 10 also reads
`x = = x;` and `return +;`; association does not correct these characters.

[Reserved results](2026-09-14-offline-association-reserved.json) contain actual and
intended retained text, orders, all decisions and scores. Frozen detections and
manual labels are stored separately under `tests/fixtures/continuation_reserved/`.
They are never loaded by development tests/evaluation. Explicit replay:

```sh
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_reserved
```

That evaluator rejects a changed rule-file hash or changed fixture hashes. Original
photos and first live extraction/debug results remain in ignored
`outputs/continuation_association_intake/frozen_evaluation/`. To repeat recognition,
use `extract_text_from_image` on the corresponding `reserved_evaluation/` photos;
compare results with the frozen fixtures rather than overwriting them.

## Verification and next decision

Fresh full discovery: 185 tests executed, 180 passed and the same 5 expected
production-order failures. Fresh live evaluation of all 20 baseline photographs
completed successfully: average clean_ws CER 0.099, clean WER 0.328, clean token
accuracy 0.716; green_writer10 clean_ws CER 0.061. These are production-pipeline
regression results; the prototype was not enabled in that CER run.

The default development evaluator reproduces its previous baseline report exactly.
The prototype's pre-evaluation SHA-256 remains unchanged. Frozen result replay,
photo/fixture provenance, record preservation and `git diff --check` were checked.

Verdict: useful offline evidence that local association can repair the demonstrated
reading-order failure without rewriting OCR. **Not ready for automatic live
integration.** Remaining gaps include coarse block boundaries (Example 9), explicit
right-to-left continuation edges (Example 10), abstention on a narrow but real gutter
(Example 3), unreliable recognition, and ambiguous unnumbered functions.

Keep this version frozen as the recorded experiment. Before another version,
collect Example 7 and additional writers, with a fresh evaluation split. Test explicit
multi-block answer chains and ambiguity handling offline. Then test a production
integration in shadow mode, where proposed associations are recorded without
changing teacher-visible text, before enabling automatic reordering. A new model is
not required for this first experiment; these results alone do not settle whether
rules will be sufficient across writers and layouts.
