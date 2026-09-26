# Handwritten continuation development baseline

> **2026-09-17 follow-up:** This file records the pre-integration baseline. The five
> expected failures are now fixed in production column ordering. All eight development
> pages match annotation, every retained detection survives, and 204 tests pass with
> zero expected failures. See `2026-09-14-offline-association.md` for current limits.

> Session update: the offline prototype and manual tester are now implemented;
> see the [current handoff](2026-09-14-continuation-session-handoff.md).
> All 11 supplied photos were used. Historical “Example 7 missing” wording below
> reflects an unresolved numbering mismatch, not a confirmed missing upload.

## Scope and split

Eight supplied development photos were processed with the existing fine-tuned
`extract_text_from_image`: Examples 1, 2, 4, 5, 6, 8, 9 and 11. Production code,
thresholds and model weights were unchanged. No association prototype was enabled.
Examples 3, 10 and 12 remain excluded from OCR and rule tuning; Example 7 is missing
and remains reserved when received. Intake identification of reserved photographs
has occurred, so they are reserved from tuning, not images never seen by the agent.
All pages are from one writer and cannot establish unseen-writer performance.

The [intake manifest](2026-09-14-continuation-intake.json) records source hashes and
the split. Photos remain in ignored `outputs/continuation_association_intake/`.
Original downloads were not edited or deleted. No duplicates were found among the
eleven attached photographs by file hash, decoded-pixel hash or visual review.

## Annotation and measurement

Manual coarse block rectangles and intended relationships were recorded from the
photographs and agreed exercises. Retained OCR detection IDs were then assigned
to those regions by text and position, not by the pipeline's resulting order.
`tests/fixtures/writerX_development_annotations.json` records normalized original
photo regions, processed-coordinate detection unions, block/answer IDs, continuation
edges, intended rows, recognition losses and frozen fixture hashes. Eight separate
`writerX_pageNN_detections.json` fixtures preserve the actual recognizer output.
Images are 1536x2048; processed images are 1200x1600 with resizing but no crop.

The evaluator reports exact retained-detection order and pairwise order accuracy.
It verifies exact text/score/box multiplicity preservation, including repeated
payloads. Its row text is checked against the actual live extraction. A correct
order does not mean a complete or accurate transcription. In particular, characters
already missing at recognition/filtering time cannot be restored by grouping.

Answer-membership accuracy is explicitly **unavailable**: the current pipeline
does not emit association decisions. Do not infer an `independent` classification
merely because a left-then-right order happens to match an independent-answer page.
Examples 2 and 8 lack headings; intended answer labels are retained, but image-only
membership ambiguity is allowed. Correct function grouping and certain answer
membership are distinct questions.

## Results

| Example | Retained detections | Exact order | Pairwise order | Active ordering mechanism |
| --- | ---: | --- | ---: | --- |
| 1 | 8 | Match | 1.000 | Full two-column |
| 2 | 12 | Match | 1.000 | Full two-column |
| 4 | 7 | Match, one brace missing upstream | 1.000 | Banded |
| 5 | 15 | Wrong | 0.886 | Full two-column |
| 6 | 17 | Wrong | 0.890 | Full two-column |
| 8 | 12 | Wrong | 0.864 | Full two-column |
| 9 | 11 | Match | 1.000 | Banded |
| 11 | 8 | Match | 1.000 | Brace-assisted candidate reassembly |

Five of eight match the annotated order of retained detections. All 90 retained
detections survive grouping verbatim. This is a development baseline, not a held-out
accuracy claim or a measure of program-membership classification.

Examples 5, 6 and 8 all fail in the same way: the upper-right continuation comes
after the lower-left answer. The full-column path bypasses local association. This
reproduces the earlier two-question failure across three additional real pages.

Example 4 has a detected left closing brace at processed box `[212,309,235,348]`
recognized as empty text with score 0.0. The existing recognition filter drops it.
It is logged separately, not silently inserted into the fixture or reference order.

Example 11 is a real activation of `_reassemble_margin_candidates` and
`_reassemble_displaced_regions`, and the resulting order matches annotation.
The comment's delimiters are misrecognized (`1.* ... *;`), although its braces are
present. This successful ordering does not establish reliable comment parsing or
general continuation classification. It supersedes a blanket claim that the brace
fallback has never fired on real handwriting; earlier A/B/C observations remain true.

Full current and intended OCR text, detection IDs, and mechanism events are in
[machine-readable results](2026-09-14-development-baseline.json). Intended text
there consists of unedited recognized strings in annotated order, not corrected C.

## Reproduction and next gate

From `ocr_feature`:

```sh
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_development
PYTHONPATH=. .venv/bin/python -m unittest tests.test_continuation_development -v
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_cer
```

The three new desired-order tests were first run without decorators: each failed
at the documented wrong continuation position. They now use `expectedFailure`
during planning, alongside the two earlier known failures. Remove these markers
when implementing the fix; do not count them as passing acceptance tests.

Next: an offline candidate-association experiment using these development labels,
with independent-answer alternatives and an explicit ambiguous outcome. Do not use
the reserved set to choose thresholds. Review changed detection orders, false
cross-answer links and abstention separately before any production integration.
No new model or web UI change is required for that experiment.

## Verification

Full unittest discovery: 171 executed, 166 passed and 5 expected failures (the two
earlier planning cases plus the three new local-continuation cases). The live
`evaluate_cer` run completed with exit code 0 and retained average clean_ws CER
0.099, clean WER 0.328, clean token accuracy 0.716, and green_writer10 clean_ws
CER 0.061. Offline replay reproduces the saved development report exactly.
All annotated detection centers fall within their manually chosen photo regions,
and processed image sizes were checked. `git diff --check` passes.
