# Page revision from a trigger; leftover page grades cleared (2026-09-26)

> **Owner:** Jayrald. **Branch:** `judge0-integration`. **Commit:** `4060749`. Migration `20260926001200`.

## What

- **Page revision from a trigger:** the paper's `grading_revision` now moves from an AFTER trigger on `submission_programs`, fired when a program is inserted, deleted, moved, or gets new code or a new question. `advance_page_revision()`, which the browser could call, is dropped. Changes made by other triggers are skipped:
  - the Details step's question change already moved the revision, and its UPDATE must return the final value;
  - a question edit moves the affected pages itself;
  - cascading deletes.

  Grade writes don't fire it. A program edited outside the save function now moves the revision too.
- **Leftover page grades cleared:** `save_submission_programs()` now clears a paper-level grade left from before the paper had programs. That closes the known gap in review finding #4.

## Why

- A clean Supabase security report: this was the only advisor warning from our own code.
- No paper with programs can show an old paper-level grade, whatever state it came from.

## Files

- `supabase/migrations/20260926001200_revision_trigger_and_leftover_page_grade.sql`
- `supabase/tests/database/review_followups.test.sql` (9 checks)
- `supabase/tests/test_migration_contract.py`

## Affects

Nobody needs to change anything. The web's save and grade calls work as before.

## Verification

- `review_followups.test.sql`: 9/9 (5 failed before the fix).
- `supabase test db`: 149/149 across 9 files.
- `npx ng test`: 302/302. `npx playwright test`: 9/9.
- Python contract tests: 22/22.
- Through the local REST API as the browser role: `rpc/advance_page_revision` returns 404, and a save returns the stored revision.
