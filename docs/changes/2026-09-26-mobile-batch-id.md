# Mobile: pages of one answer share a `batch_id` (2026-09-26)

> **Owner:** Nikko. Requested by Jayrald (Nikko → To do). Column: `20260926000500_add_submission_batch_id.sql` (live).

## What

`SubmissionUploader.submit()` makes **one** id per submit and sends it as `batch_id` on every page's insert. A two-page answer is now two `submissions` rows with the same `batch_id`; each page is still its own row, so the OCR still reads one image per row.

The id is a random version-4 UUID from the phone's secure random source (`lib/utils/batch_id.dart`); no new package. The insert row is built by `SubmissionUploader.submissionRow()`, which also makes it testable. `extracted_text`, `verified_text` and `answers` are still left empty.

## Why

Before, nothing tied the pages of one answer together, so the web couldn't show "2 pages" or treat them as one paper (Nikko's open question from 2026-09-24). Jayrald chose a shared `batch_id` and added the column with an insert-only grant.

## Files

- New: `maistra_mobile/lib/utils/batch_id.dart`, `maistra_mobile/test/submission_uploader_test.dart`
- Changed: `maistra_mobile/lib/services/submission_uploader.dart`
- Unchanged: `quality_check.dart`, `quality_fix.dart`, `packages/edge_detection/`, `pubspec.yaml`

## Affects

- Nothing on the web reads `batch_id` yet; showing "2 pages" is a later step (Jayrald's note).
- Rows from before today, and rows not made by the phone, keep `batch_id` NULL.

## Verification

- `flutter test`: 58/58 (5 new: UUID format, uniqueness over 500 ids, seeded repeatability, same `batch_id` on every page, exact insert row).
- `flutter analyze`: 12 issues, unchanged; none in new code.
- **Not yet on a device:** checked by the end-to-end test (capture two pages, submit, both rows share one `batch_id`).
