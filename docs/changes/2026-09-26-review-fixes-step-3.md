# Review fixes: Step 3 stays on the graded program; grading waits for re-reads (2026-09-26)

> **Owner:** Jayrald. **Branch:** `judge0-integration`. **Commit:** `f3c3a69`. Web only; no migration.

## What

- **Stays on the graded program** (review finding #3). After grading, Step 3 used to move to the next ungraded program while still showing the results of the one just graded. Now the graded program stays selected until the teacher picks another chip. A reopened paper starts on its first ungraded program again.
- **Waits for re-reads** (finding #6). A Submit clicked while Step 3 was still re-reading the paper's programs graded the old rows. Grading now waits for that re-read.

## Why

Both could show or save a grade for the wrong program. Found by the code review in [`docs/reviews/2026-09-26-judge0-integration-code-review.md`](../reviews/2026-09-26-judge0-integration-code-review.md).

## Files

- `submissions-list.ts` and `submissions-list.program-grading.spec.ts` (2 new tests).
- `tests/e2e/submission-grading.spec.ts`: the two-program test also checks #3.

## Affects

Teachers grading papers with several programs. Nothing for Nombrado or Nikko to change.

## Verification

- `npx ng test` 302/302; each new test fails with its fix removed.
- Both TypeScript checks and `npx ng build` pass (existing CSS budget warning).
- `npx playwright test` 18/18 with `--repeat-each=2`.
