# Per-Line Exclusion in the Recognition Dataset Builder — Handoff

> **SHELVED 2026-09-23 (user decision).** The 7 deferred pages are excluded from
> the next dataset batch, so this manifest is not needed. They are likely
> existing B1–B3 writers, possibly including test-set writers `green_writer13_B2`
> and `green_writer10_B2`. See `../NEXT_STEPS.md`'s 2026-09-23 block. The design
> below is kept for reference only.

**Date:** 2026-08-17 (counts refreshed after independent visual re-audit)
**Scope:** OCR fine-tuning dataset pipeline only (`evaluators/build_recognition_dataset.py`).
Not in scope: preprocessing, the mobile quality gate, cleanup rules, Judge0/grading.

> **⚠️ Note (2026-08-30):** since commit `aedd444`, the builder no longer uses
> the strict "line counts must match exactly or discard all lines" logic this
> doc's examples describe (see the "all 9 lines discarded" case below) — it now
> does a monotonic line-alignment that keeps confidently-matched lines and
> tolerates OCR over/under-detection. **This does NOT replace the feature this
> handoff asks for:** a human-authored *exclusion manifest* for
> `deferred_needs_line_exclusion/` pages, marking which line indices to drop
> because a person judged them unrecoverable scribble. Alignment handles the
> machine's detection errors; the manifest handles a human's exclusion
> decision. The manifest is still unbuilt but shelved for the next batch, as
> the 2026-09-23 note above explains. Its pre-`aedd444` baseline is stale.

## Context

We manually reviewed 160 candidate photos of handwritten C answer sheets (already
teacher-graded papers, being repurposed as OCR fine-tuning data) and sorted them by
usability. Full review notes: `ocr_feature/dataset_review/VERDICTS.md`.

Sorted into (current folder counts):
- `ocr_feature/dataset_review/usable/` (137) — clean, or has non-overlapping marks/
  legible-through self-corrections, ready for page-level transcription review before
  adding to `datasets/verified/labels.csv`.
- `ocr_feature/dataset_review/usable_if_cropped/` (3) — needs a simple page-level
  trim or orientation fix before line extraction; no code change is needed for the
  crop itself.
- `ocr_feature/dataset_review/deferred_needs_line_exclusion/` (7) — **this is the
  problem this handoff is about.**
- `ocr_feature/dataset_review/not_usable/` (1) — too damaged to use at all.

The earlier `(119)/(6)/(17)` counts in this handoff were superseded by the later
independent visual re-audit. The authoritative per-file notes are in
`ocr_feature/dataset_review/VERDICTS.md`.

## The problem

The 7 retained photos in `deferred_needs_line_exclusion/` each have exactly one defect: a
small number of lines (usually 1, sometimes 2) are made genuinely illegible by a
scribble or whiteout mark — not a strike-through you can still read, an actual
opaque cover. Every other line on each of those pages is perfectly legible.

Example: `IMG_0320.jpg` — 9 lines of code total, one `if` line in the middle is
covered by a dense black scribble, the other 8 lines are fully readable.

`evaluators/build_recognition_dataset.py` currently converts whole pages into
per-line training crops by:
1. Running OCR on the page to detect lines.
2. Splitting the human ground-truth transcription on newlines.
3. Comparing the two counts. **If they don't match exactly, the entire page is
   skipped** (see the module docstring and `_load_rows`/`main` in that file —
   this is deliberate, to avoid silently misaligning a crop with the wrong label).

That means: if we transcribe only the 8 legible lines of `IMG_0320` and omit the
illegible one, the line counts won't match and the tool discards **all 9 lines**,
not just the 1 bad one. There is currently no way to keep the 8 good lines.

## What's needed

A way to mark specific line(s) within a page as intentionally excluded, so the
builder can:
- Skip only those line(s) from both OCR-detected lines and ground truth before
  the count comparison, and
- Still emit crops for the remaining legible lines on that page.

This needs a real mechanism for indicating *which* line is excluded and *why*
(so it's auditable, not a silent guess) — e.g. a convention in
`datasets/verified/labels.csv` for marking a specific ground-truth line as
"illegible, exclude," or a parallel exclusion list keyed by source image name
and line index. Whatever the mechanism, it must never guess or reconstruct the
excluded content — per project rule (see `ocr-cleanup-scope` in project memory
and `EVALUATION.md`), cleanup/tooling must never alter or infer graded content.
Excluding is fine; inventing text for the illegible line is not.

## Reference material

- `evaluators/build_recognition_dataset.py` — the file to change, see its
  module docstring for the existing all-or-nothing skip logic and rationale.
- `ocr_feature/dataset_review/VERDICTS.md` — full per-photo review notes,
  including why each of the 9 deferred photos needs this specifically.
- `ocr_feature/dataset_review/deferred_needs_line_exclusion/` — the 7 actual
  example images to test against.
- `docs/ocr/FINE_TUNING_READINESS.md` §5, item 2 — existing note that the
  train/val split doesn't yet group by page/writer; a related but separate gap
  in the same file, don't conflate the two.

## Non-goals

- Don't touch preprocessing, cleanup rules, or anything outside
  `build_recognition_dataset.py`'s line-matching/skip logic.
- Don't try to reconstruct or guess the content of an excluded line.
- Don't change the existing all-or-nothing behavior for pages that aren't in
  `deferred_needs_line_exclusion/` — the whole-page skip is correct and
  intentional for genuine misalignment; this is additive, not a replacement.
