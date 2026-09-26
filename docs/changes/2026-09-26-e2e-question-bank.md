# End-to-end tests for question linking on the web (2026-09-26)

> **Owner:** Nikko. Uses Jayrald's Playwright setup (`maistra_web/playwright.config.ts`, fake backend in `tests/e2e/support/`).

## What

New `maistra_web/tests/e2e/question-bank.spec.ts`, 6 browser tests against the fake backend (nothing reaches the cloud):

1. The bank groups questions by section and number, an empty section says so, unsectioned questions come last; validated badge, paper count, search.
2. The question page shows `Basic · Q2 · …`, the summary, the test cases, the linked phone paper with ✓ Photo good, and only an **Edit** action.
3. A phone upload (`question_id` + `gate_result`) lands in its question's section folder with the label and photo badge.
4. Editing an unsectioned, unvalidated question: section required, taken numbers refused, Save locked until Validate passes, then filed under Basic as Q3 with `can_publish = true`.
5. Editing a validated question: renaming saves at once; changing a test case locks Save; Cancel sends nothing.
6. Changing test cases on a question with a graded paper shows the warning before anything is saved; **Save and clear grades** saves.

## Fake backend additions (Jayrald's `tests/e2e/support/fake-backend.ts`, additive only)

`PATCH /questions` (edit), `PATCH /question_section_items` (move), `GET /submission_programs` (graded-papers count; replaced a `HEAD` count on 2026-09-27), `addSectionItem()`, optional `can_publish` / `question_text` on questions.

## Verification

All 14 e2e tests pass (6 new + Jayrald's 8), run in the local Google Chrome: Playwright's own browser download timed out on this network, so a temporary config with `channel: 'chrome'` was used and deleted. On a machine with `npx playwright install` working, `npm run e2e` runs them as-is.
