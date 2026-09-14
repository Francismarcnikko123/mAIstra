# Continuation association: test-first plan and findings

> Session update: the offline prototype and manual tester are now implemented;
> see the [current handoff](2026-09-14-continuation-session-handoff.md).
> All 11 supplied photos were used. Historical “Example 7 missing” wording below
> reflects an unresolved numbering mismatch, not a confirmed missing upload.

Status: planning and baseline testing only. No production ordering changes.

## Requirement

Infer whether a spatially separate handwritten C block continues nearby code or
belongs to an independent answer, then locate the continuation within that answer.
Do not assume a whole page is one program or that each function is an answer.
Preserve recognized text and detection multiplicity. Incorrect student syntax is
valid input; neither compiler success nor balanced braces proves student intent.

## Verified failure

The live debug payload corresponding to the supplied two-question screenshot was
located by its recognized strings (`suwerturn 1;`, `Qvestion 2;`, `{else {`).
Its 20 detections were copied without modification to
`tests/fixtures/writerX_two_question_margin_detections.json`. The original uploaded
photo remains locally available. Fixture naming uses a writer pseudonym.

IDs are zero-based fixture indices. Human annotation from the supplied photo:

| Region | Detection IDs |
| --- | --- |
| Question 1 heading and left | 0, 1, 3, 5, 7, 9, 12 |
| Question 1 right continuation | 2, 4, 6, 8, 10, 11 |
| Question 2 heading and left | 13, 14, 16 |
| Question 2 right continuation | 15, 17, 18, 19 |

Expected order concatenates these four rows. Current order is:
`0,1,3,5,7,9,12,13,14,16,2,4,6,8,10,11,15,17,18,19`.
The first error is Question 2 starting before Question 1's continuation.

Instrumentation confirms the full two-column path runs; banded detection and
`_reassemble_margin_candidates` are not called. All 20 detections survive verbatim.
The returned geometry-valid flag is true, which does NOT certify correct reading
order or continuation association.

A counterfactual replay changes only detection 2 from `{else {` to `} else {` in
memory. It produces the identical wrong order. This is NOT a new OCR result or a
corrected fixture. Other recognition errors remain. Therefore the earlier claim
that the screenshot failed because of the misread brace was incomplete: the
geometric early return is sufficient to reproduce the ordering failure.

The existing A/B/C results still demonstrate successful output ordering, not an
independent ability to classify a continuation. In some layouts independent
programs and a continuation have exactly the same flattened line order, so order
accuracy alone cannot evaluate association.

## Research and design inference

- [Recognizing Handwritten Source Code (2017)](https://arxiv.org/abs/1706.00069)
  studies handwritten Python recognition with grammar information. Relevant to
  programming-specific evidence; does not establish this C margin-order solution.
- [Reading order detection on handwritten documents (2022)](https://link.springer.com/article/10.1007/s00521-022-06948-5)
  learns ordering relations between regions/lines in handwritten documents.
- [LayoutReader (2021)](https://aclanthology.org/2021.emnlp-main.389/)
  combines text and layout; its Word-derived benchmark is not handwritten C.
- [Modeling Layout Reading Order as Ordering Relations (2024)](https://aclanthology.org/2024.emnlp-main.540/)
  supports evaluating relationships rather than only a single permutation.

Proposed adaptation, not a published or validated solution: compare local
continuation and independent-answer hypotheses using geometry plus fallible C
structure. Start with inspectable rules and no new model. A learned relationship
predictor is a later alternative if held-out data shows rules are inadequate.
More gutter tuning alone cannot establish answer membership.

## Proposed architecture and boundaries

Keep OCR recognition unchanged. Separate block discovery from final column
concatenation so a full-column early return cannot bypass association analysis.
Preserve the existing baseline ordering as a fallback when evidence is insufficient.
This fallback is explicitly an abstention, not a claim that baseline is correct.

A proposed pure module `core/continuation.py` accepts blocks containing stable
detection IDs, original text, boxes and page IDs. Its result contains ordered IDs,
candidate association edges, and one of `continuation`, `independent`, `ambiguous`.
Record supporting/conflicting evidence and proposed insertion boundaries for each
candidate. Do not call a heuristic score a probability without calibration.

Use local vertical bands, gutters and heading positions to propose candidates.
Use recognized headings and C structure as evidence, never mandatory perfect OCR.
Distinguish a new function from a new answer: multiple functions may belong to one
program. Braces in strings/comments must not count as scopes. OCR confidence is
line-level and can be high on a wrong brace (0.960 on `{else {` here); it must not
be treated as character certainty. A missing or incorrect brace cannot authorize
inserting one. Do not rank by reference answers, test-case success, or presumed
correct algorithm. No character rewriting is permitted by this layer.

Several candidate insertion points may exist. Accept a move only with independently
corroborating spatial and association evidence and no competing supported placement.
Cycles, conflicting answer membership, duplicate IDs, missing boxes, crossed gutters,
or unresolved alternatives cause abstention. Preserve within-block order.
Thresholds must be calibrated on labeled development examples, not invented here.

Physical page identity and answer identity differ. Separate pages may continue one
answer; two functions on one page may be separate answers. Cross-upload association
is excluded from the first version because extraction currently handles one image.
Side-by-side photographed pages require labeled examples and explicit page-boundary
handling before claiming support. Teacher-facing ambiguity controls are a subsequent
UI task; first expose decisions in offline diagnostics without changing API contracts.

## Test matrix before production integration

| Case | Desired decision | Evidence status |
| --- | --- | --- |
| A/B/C single margin continuations | continuation, left then margin | Real fixtures; order covered, association labels need adding |
| Two questions, each with right continuation | two local associations in question order | Real fixture; current desired-order test fails |
| Same case with one corrected brace | same order | Counterfactual test fails, not real OCR |
| Two independent side-by-side answers | independent; no cross-answer association | Existing green_writer10 order fixture; verify membership against photo |
| Several functions within one answer | same answer; no false split | Obtain/annotate real example |
| Continuation returning to left-side lines below | insert at local boundary, preserve remainder | Obtain/annotate real example |
| Missing headings or misread braces | use corroboration or abstain | Misreads present here; more real examples needed |
| Both placements plausible / invalid student syntax | ambiguous, preserve text | Add explicitly labeled ambiguous cases |
| Adjacent photographed pages, independent and continuing | correct membership or abstain | Additional examples required |

Do not report missing real cases as tested. Synthetic controls can test constraints
but cannot establish real-photo accuracy. Freeze annotations before inspecting
candidate output. Reserve unseen writers/layouts as held-out validation; three photos
from one writer are inadequate to calibrate general association confidence.

## Execution sequence after planning review

1. Complete annotations in a separate sidecar: block IDs, answer membership,
   continuation edges, insertion positions and allowed ambiguous outcomes. Keep
   recognition fixtures unedited. Reconfirm green_writer10 against its photo.
2. Implement an offline evaluator before changing the runtime. Report exact order,
   pairwise order, association precision/recall, wrong cross-answer links, abstention
   coverage and exact detection multiset preservation separately. Duplicate text
   must be identified by stable detection ID, not a text-key dictionary.
3. Build candidate analysis offline in `core/continuation.py`, with focused tests
   covering both competing placements and independent-answer controls. Evaluate
   geometry-only and geometry-plus-code variants on the same detections. Record
   every changed order and why; manually adjudicate each changed historical case.
4. Stop and review if real negative examples are absent, thresholds only fit one
   writer, false cross-answer links occur, or evidence cannot distinguish the two
   hypotheses. Do not ship just because the screenshot starts passing.
5. Only after this gate, integrate association before final column concatenation
   in `core/layout.py`. Remove the two expected-failure decorators, retain exact
   desired-order assertions, and replace the early-return characterization with a
   test proving full-column discovery no longer bypasses local association.
6. Run the full suite and live evaluator after every atomic implementation commit.
   Keep clean_ws CER 0.099, clean WER 0.328, clean token accuracy 0.716 and
   green_writer10 clean_ws 0.061, checking per-page output too. Preserve all A/B/C
   orders and all detection multiplicities. Log the current replay corpus size
   rather than copying a historical count. An unchanged corpus is not evidence
   of correctness on unannotated continuation cases.
7. Update `docs/PROJECT_OVERVIEW_AND_CHANGES.md` and this report with verified
   outcomes and limits. No attribution trailers. Keep unrelated changes intact.

## Reproduction and TDD status

Run from `ocr_feature`:

```sh
PYTHONPATH=. .venv/bin/python -m unittest tests.test_continuation_planning -v
PYTHONPATH=. .venv/bin/python -m unittest tests.test_real_margin_layout -v
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_cer
```

Before adding expected-failure markers, the four new tests produced two assertion
failures (desired order) and two passes (preservation and bypass characterization).
The ordering tests are now explicitly marked `unittest.expectedFailure` during
planning. Unexpected success will fail the suite and require removing the marker.
This does not mean the desired ordering works. Production code is unchanged.

Fresh verification on September 14: 163 tests executed, 161 passed and 2 expected
failures. The live fine-tuned evaluator completed with exit code 0: average
clean_ws CER 0.099, clean WER 0.328, clean token accuracy 0.716 and green_writer10
clean_ws CER 0.061. Its model initialization was slow and logged a sandbox
`sysctl` warning, but the original run completed without a restart. `git diff
--check` passed. No improved association accuracy is claimed by these baseline
results. No production code, thresholds, model weights or web UI were changed.
