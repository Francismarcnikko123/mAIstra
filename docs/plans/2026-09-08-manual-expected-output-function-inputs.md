# Manual Expected Output and Function Inputs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make function tests assignment-driven with no stdin and require teacher-authored Expected Output that validation compares without overwriting.

**Architecture:** Extend the shared C question validator for the function-only input rule, then update `QuestionFormComponent` to validate required expectations and compare Judge0 stdout. Keep program stdin behavior and the shared generated source wrapper intact.

**Tech Stack:** Angular 21, TypeScript, RxJS, Vitest, Judge0.

---

### Task 1: Enforce the function input contract

**Files:**
- Modify: `maistra_web/src/app/utils/c-question.spec.ts`
- Modify: `maistra_web/src/app/utils/c-question.ts`
- Modify: `maistra_web/src/app/components/question-form/question-form.spec.ts`
- Modify: `maistra_web/src/app/components/question-form/question-form.ts`
- Modify: `maistra_web/src/app/components/question-form/question-form.html`

1. Add utility tests that require real `scanf()` calls to fail for function code and comments/strings containing `scanf()` to remain valid.
2. Run the utility test and confirm the new case fails because no `scanf()` check exists.
3. Add the minimal structural check and actionable message.
4. Add component tests proving function execution sends empty stdin while program execution still sends its configured stdin.
5. Run the component test and confirm the function-stdin assertion fails.
6. Update the component execution calls and template so Standard Input is visible only for program questions and function guidance demonstrates assigned values.
7. Rerun the focused tests until green.

### Task 2: Require and compare manual Expected Output

**Files:**
- Modify: `maistra_web/src/app/components/question-form/question-form.spec.ts`
- Modify: `maistra_web/src/app/components/question-form/question-form.ts`
- Modify: `maistra_web/src/app/components/question-form/question-form.html`

1. Add tests for empty Expected Output, normalized matches, mismatches, preserved manual values, and visible Expected/Got result data.
2. Run the focused component test and confirm failures caused by automatic output acceptance and overwrite.
3. Add pre-execution required-field validation and normalized stdout comparison.
4. Remove automatic assignment of actual output to `expected_output`.
5. Update hints to say Expected Output is entered manually and validation compares against it.
6. Rerun the focused component tests until green.

### Task 3: Verify the integrated workflow

**Files:**
- Modify: `docs/PROJECT_OVERVIEW_AND_CHANGES.md`

1. Run the C-question utility and question-form Vitest suites.
2. Run the submissions-list and Judge0 component suites to catch execution/grading regressions.
3. Run TypeScript checking and an Angular development build.
4. Review the scoped diff for accidental changes and update the project behavior documentation.
5. Repeat the focused tests and build after documentation/code cleanup.
