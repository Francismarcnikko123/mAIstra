# Question page: drop marks (2026-09-26)

> **Owner:** Nikko. **Commit:** `c6178c6` on `feature/question-linking-v2`.

## What

- The question page's test-case table no longer has a **Mark** column.
- The summary line no longer includes marks: `Function · 6 test cases · used by 1 paper`.
- The unused `totalMarks()` helper and its test are removed from `question-bank/bank-groups.ts`.

## Why

`judge0-integration` (Jayrald) removed the `mark` field from question test cases, and the form no longer asks for it. After the merge, the column was empty and every summary said "0 marks".

## Files

- `maistra_web/src/app/components/question-bank/question-page.ts`, `question-page.html`, `question-page.spec.ts`, `bank-groups.ts`

## Affects

Nobody else. The question page is Nikko's.

## Verification

Web: 281/281 tests (one fewer: the marks-total test went with the helper), TypeScript clean, `ng build` passes.
