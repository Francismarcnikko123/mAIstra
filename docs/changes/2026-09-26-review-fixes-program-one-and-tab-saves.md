# Review fixes: Program 1 follows the page's question; tab-only saves are guarded (2026-09-26)

> **Owner:** Jayrald. **Branch:** `judge0-integration`. **Commit:** `446b05c`. Migration `20260926000700`.

## What

- **Program 1 follows the page's question** (review finding #1). A trigger on `submissions.question_id` (the Details step) moves Program 1's `submission_programs` row to the new question, which clears its grade. It creates Program 1 from the page's saved code when a page gets its first question, and removes Program 1 when the question is cleared. One question per paper still holds. The web re-reads the paper's programs after a Details save.
- **Tab-only saves are guarded** (finding #2). `save_submission_programs()` now advances the page's `grading_revision` whenever it inserts, changes or deletes a program (through `advance_page_revision()`). A second teacher saving from an older view gets the usual conflict instead of deleting the first teacher's tab.

## Why

Found by the code review in [`docs/reviews/2026-09-26-judge0-integration-code-review.md`](../reviews/2026-09-26-judge0-integration-code-review.md):
- without #1, Program 1 was graded against the question chosen before;
- without #2, the revision guard didn't cover Programs 2+.

## Files

- `supabase/migrations/20260926000700_sync_program_one_and_guard_tab_saves.sql`
- `supabase/tests/database/submission_programs_sync.test.sql` (9 checks), `test_migration_contract.py`
- `submissions-list.ts` (one line: re-read programs after a Details save), `submissions-list.program-grading.spec.ts`
- Playwright: the fake backend mirrors both behaviours; one new test.

## Affects

- **Nombrado:** nothing to change. A save that only touches tabs now returns a new page revision, which the review already uses.
- **Teachers:** changing a paper's question on Details ungrades Program 1, and it is graded again against the new question.

## Verification

- `supabase test db` 89/89 (6 of the 9 new checks failed before the fix).
- `npx ng test` 300/300, both TypeScript checks, `npx ng build` (existing CSS budget warning).
- `npx playwright test` 18/18 with `--repeat-each=2`.
- The new unit and Playwright tests fail with the web change removed.
