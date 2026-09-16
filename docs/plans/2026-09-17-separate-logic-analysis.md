# Separate Logic Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the complete Logic Analysis feature from `judge0-integration` while retaining it on `feature/logic-feature`.

**Architecture:** The feature branch already owns the full implementation, so it needs no merge or cherry-pick. The current branch becomes execution-only by deleting the parser/API boundary and all Angular logic-analysis request, state, presentation, and styling code.

**Tech Stack:** FastAPI, Python, Angular, TypeScript, Vitest, Judge0.

---

### Task 1: Specify the branch boundary

**Files:**
- Modify: `judge0_api/tests_judge0_api.py`
- Modify: `maistra_web/src/app/components/judge0/judge0.spec.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`

1. Change the backend test to require a 404 from `/api/judge0/analyze-logic`.
2. Add a component test requiring no Logic Analysis state on `Judge0`.
3. Change submission tests to assert grading runs test cases without calling `analyzeLogic`.
4. Run the focused tests and confirm they fail for the expected reasons.

### Task 2: Remove backend logic analysis

**Files:**
- Modify: `judge0_api/main.py`
- Delete: `judge0_api/logic_checker.py`
- Delete: `judge0_api/tests_logic_checker.py`

1. Remove the checker import, request model, and `/analyze-logic` route.
2. Delete the checker and its branch-specific tests.
3. Run the backend suite and confirm it passes.

### Task 3: Remove frontend logic analysis

**Files:**
- Modify: `maistra_web/src/app/services/judge0.service.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.html`
- Modify: `maistra_web/src/app/components/judge0/judge0.ts`
- Modify: `maistra_web/src/app/components/judge0/judge0.html`
- Modify: `maistra_web/src/app/components/judge0/judge0.css`

1. Remove the service logic-analysis types and method.
2. Remove submission logic requests, state, bindings, and error wording.
3. Remove Judge0 logic inputs, expansion state, panel markup, and panel-only CSS.
4. Run focused tests and confirm they pass.

### Task 4: Update documentation and verify

**Files:**
- Modify: `docs/PROJECT_OVERVIEW_AND_CHANGES.md`

1. Document that Logic Analysis is available only on `feature/logic-feature`.
2. Run all backend tests and frontend tests.
3. Run the Angular production build.
4. Scan the current branch for remaining Logic Analysis implementation references.
5. Run `git diff --check`, inspect the diff, and commit the verified removal.
