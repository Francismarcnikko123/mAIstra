# Details dropdown labels; automatic OCR decisions (2026-09-27)

> **Owner:** Jayrald. **Branch:** `judge0-integration`. **Commit:** `33e35d2`.

## What

- **The Details question dropdown** shows `Section · Q# · Name` (`questionOptionLabel()`), like the program-tab picker and View question. Questions without a section show just their name. This was Nombrado's request, passing on Nikko's.
- **Automatic OCR (`AUTO_EXTRACT`), decided for Nombrado:**
  1. It stays on against the cloud. It only fills `extracted_text` on new, empty papers.
  2. When teacher logins and stricter RLS arrive, Jayrald issues an `sb_secret_…` key for the OCR server's `.env` only.
  3. Only one machine runs it at a time: Nombrado's.

## Files

- `maistra_web/src/app/components/submissions-list/submissions-list.html` (one line).
- `maistra_web/tests/e2e/teacher-workflow.spec.ts` (picks the new label).

## Verification

- The updated Playwright test failed before the change.
- `npx ng test` 339/339. Both TypeScript checks and `npx ng build` pass (existing CSS budget warning).
- `npx playwright test --repeat-each=2`: 38/38.
