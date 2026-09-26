# Review of the pulled changes in Jayrald's files, and the save-reminder fix (2026-09-27)

> **Owner:** Jayrald. **Branch:** `judge0-integration`. **Commit:** `8c11129` (web fix). Review: `docs/reviews/2026-09-27-teammates-changes-review.md`.

## What

- **Code review** of Nikko's and Nombrado's 26 pulled commits (`d854ae1..98b047b`) where they touch Jayrald's files: `supabase.ts`, the review screen (`submissions-list.*`) and the e2e fake backend. There are 10 findings with owners and fixes. #1 was confirmed in the cloud data: 57 test cases in 20 of the 23 questions still carry an old `mark` field, so renaming such a question clears its papers' grades with no warning.
- **Fix #3 (Jayrald's code):** after a save, "New changes need to be saved" stays while any program tab is still unsaved. Before, it cleared after 3 seconds unless Program 1 had changed.

## Who must act

- **Nikko:** #1 (urgent: don't edit older questions until it's fixed), #2, and #5–#9, in Nikko's To do.
- **Nombrado:** #4 (a design call) and #10, under Jayrald → Needs from others.

## Verification

- 2 new unit tests (the first failed before the fix).
- `npx ng test` 329/329. Both TypeScript checks and `npx ng build` pass (existing CSS budget warning).
- `npx playwright test` 15/15, with Nikko's known flaky test excluded.
