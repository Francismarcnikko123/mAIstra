# Equal-Weight Test Scoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a reviewable equal-weight test-case score without committing to grade persistence or a broader rubric.

**Architecture:** Derive the score from `TestCaseResult.passed` in the Judge0 presentation component, which already receives the complete grading result set. Normalize authored test-case marks to one for data-shape compatibility and remove editable weighting from the form.

**Tech Stack:** Angular 21, TypeScript, Vitest, Judge0 result data.

---

### Task 1: Specify equal-weight scoring

**Files:**
- Modify: `maistra_web/src/app/components/judge0/judge0.spec.ts`
- Modify: `maistra_web/src/app/components/question-form/question-form.spec.ts`

1. Add failing tests for full, partial, and empty result collections.
2. Require a two-decimal maximum percentage and `earned/total` summary.
3. Require every saved and newly created test case to have `mark: 1`.

### Task 2: Implement and display the partial score

**Files:**
- Modify: `maistra_web/src/app/components/judge0/judge0.ts`
- Modify: `maistra_web/src/app/components/judge0/judge0.html`
- Modify: `maistra_web/src/app/components/judge0/judge0.css`
- Modify: `maistra_web/src/app/components/question-form/question-form.ts`
- Modify: `maistra_web/src/app/components/question-form/question-form.html`

1. Add derived score getters and point labels.
2. Replace the result header with the fraction and percentage.
3. Label individual cases as `1/1 point` or `0/1 point`.
4. Remove the editable Mark input and explain equal weighting.
5. Normalize saved test-case marks to one.

### Task 3: Verify and hand off for adviser review

**Files:**
- Modify: `docs/PROJECT_OVERVIEW_AND_CHANGES.md`
- Reference: `docs/plans/2026-09-09-adviser-review-equal-weight-scoring.md`

1. Run the focused Judge0 and question-form tests.
2. Run the complete frontend test suite, TypeScript check, and Angular development build.
3. Update the project overview with the partial status and verification evidence.
4. Leave persistence and broader rubric work pending adviser feedback.
