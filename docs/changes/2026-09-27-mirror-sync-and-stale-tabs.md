# Program 1 follows the page's code; a stale tab list can't delete tabs (2026-09-27)

> **Owner:** Jayrald. **Branch:** `judge0-integration`. **Commits:** `575474e` (migration `20260926001300`), `bcb0fea` (web). Worked on in parallel, then combined and tested together.

## What

- **Program 1 follows the page's code** (Nombrado's request "Close the Program 1 mirror gap"). `sync_program_one_with_page()` now follows `submissions.verified_text` as well as `question_id` (trigger `sync_program_one_on_page_change`):
  - new code updates Program 1 and clears its grade;
  - blank or NULL code removes Program 1;
  - a page with a question and code but no Program 1 gets one.

  A direct PATCH still advances the page revision once and returns the stored value. `save_submission_programs()` is unchanged.
- **A stale tab list can't delete another teacher's tab** (Nikko's review item 9). When a live refresh brings different Programs 2..n:
  - with nothing unsaved, the tabs refresh from the row;
  - with unsaved program changes, the draft keeps its old base revision, so the next save conflicts instead of deleting the other teacher's tab.

  Rows whose programs didn't change still advance the revision.
- **Decision:** the Program 1 mirror on the page row stays for now, kept in step both ways. It goes when the submissions list reads `submission_programs`.

## Why

- An older branch or `main` that saves code with a plain PATCH on `submissions` left Program 1 with stale code, and grading reads Program 1.
- A refresh moved the base revision forward but kept the old tab list, so the next save passed the revision check and deleted the other teacher's Program 3.

## Different from Nombrado's proposal

Nombrado proposed three things:
- copying from Program 1 to the page;
- `save_submission_programs()` no longer writing `verified_text`;
- revoking the browser's `UPDATE (verified_text)`, so old branches fail loudly.

Chosen instead: the page drives Program 1, and the grant stays, so old branches keep working and stay consistent.

## Files

- `supabase/migrations/20260926001300_sync_program_one_code.sql`, `supabase/tests/database/program_one_code_sync.test.sql` (24 checks), `supabase/tests/test_migration_contract.py`
- `maistra_web/src/app/components/submissions-list/submissions-list.ts` (the refresh loop in `applySubmissionRows()`), new `submissions-list.stale-tabs.spec.ts` (5 tests)
- `maistra_web/tests/e2e/submission-grading.spec.ts` (1 new test), `tests/e2e/support/fake-backend.ts` (`pushUpdate`)

## Affects

- **Nombrado:** nothing to change; the export's mismatch warning should stay quiet.
- **Nikko:** nothing to change; your finding is fixed.
- **Teachers:** a paper edited by two teachers at once gives the second one a conflict instead of silently losing a tab.

## Verification

- `program_one_code_sync.test.sql`: 24/24 (8 failed before).
- `supabase test db`: 173/173 across 10 files.
- Python contract tests: 23/23.
- `npx ng test`: 327/327 (5 new, 4 failed before). Both TypeScript checks pass. `npx ng build` passes (existing CSS budget warning).
- `npx playwright test --repeat-each=2`: 31/32. The new test fails before the fix. The one failure is Nikko's flaky question-bank test, which also fails without these changes.

## Still open

- Nikko's flaky Playwright test (TEAM_SYNC → Jayrald → Needs from others).
- Removing the mirror once the submissions list reads `submission_programs`.
