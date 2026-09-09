# Question Validation Implementation Plan

**Goal:** Enforce the agreed C question formats, supply stdio consistently, and prevent silent or stale validation results from enabling Save.

**Architecture:** Shared source-building and lightweight structural checks in `maistra_web/src/app/utils/c-question.ts`; authoring owns validation feedback and execution snapshots. Submission grading and preview reuse the source builder. Judge0 retains responsibility for compilation and execution.

**Tech Stack:** Angular, TypeScript, RxJS, Ace, Vitest, Judge0.

## 1. Reproduce validation failures

- Extend `maistra_web/src/app/components/question-form/question-form.spec.ts` with Judge0 observable fixtures and the cases listed in the design.
- Run `node node_modules/vitest/vitest.mjs run src/app/components/question-form/question-form.spec.ts --environment jsdom` from `maistra_web`; confirm failures for the missing guards, empty stdout, and discarded function input.

## 2. Implement structural checks and execution snapshots

- Add `maistra_web/src/app/utils/c-question.ts` for C comment/string masking, question-format checks, and source assembly.
- Update `question-form.ts` to reject invalid fields, require at least one case and nonempty stdout, preserve diagnostics, forward stdin, and ignore stale responses.
- Update `question-form.html` and `.css` with editor guidance, inline field errors, and separate execution diagnostics. Remove the handwritten stdio include from the program template.
- Rerun focused validation tests until green.

## 3. Keep submission execution consistent

- Update source assertions and add a preview-wrapper case in `submissions-list.spec.ts`; observe missing-wrapper failures.
- Reuse the builder in `submissions-list.ts` for grading and preview; preserve the student's original source for logic analysis.
- Run both focused component suites.

## 4. Verify and document

- Add focused utility tests for comments/strings and continued directives as needed, using a failing-test-first cycle.
- Run relevant Vitest suites and `node node_modules/@angular/cli/bin/ng.js build --configuration development`.
- Review the diff and update `docs/PROJECT_OVERVIEW_AND_CHANGES.md` with the final behavior and verification limitations.
