# Open Findings 2, 3, and 4 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use test-driven-development to implement this plan task-by-task.

**Goal:** Enforce C-only Judge0 execution, immediately invalidate local grades when the assigned question changes, and split the oversized submissions stylesheet into maintainable budget-compliant files.

**Architecture:** The Judge0 API will own its configured C language ID instead of trusting request data, and the Angular client will stop sending a language ID. Submission code and question changes will share one local completed-grade invalidation method, while the existing database trigger remains the persistence safeguard. The submissions styles will be separated into list, review, and responsive concerns with a stricter component-style build budget.

**Tech Stack:** FastAPI/Pydantic/pytest, Angular/TypeScript/Vitest, CSS, Angular CLI budgets.

---

### Task 1: Enforce C-only Judge0 execution

**Files:**
- Modify: `judge0_api/tests_judge0_api.py`
- Modify: `judge0_api/main.py`
- Modify: `judge0_api/.env.example`
- Modify: `maistra_web/src/app/services/judge0.service.ts`
- Create: `maistra_web/src/app/services/judge0.service.spec.ts`

1. Add a backend test proving a caller-supplied non-C language ID is ignored and the configured C ID is forwarded.
2. Add a frontend service test proving the browser sends only source code and stdin.
3. Run both tests and confirm they fail for the missing server-owned behavior.
4. Add `JUDGE0_C_LANGUAGE_ID`, remove `language_id` from the request model, and use the configured value in the upstream payload.
5. Remove `language_id` from the Angular request payload.
6. Run the focused tests and confirm they pass.

### Task 2: Invalidate a completed grade on question change

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`

1. Add a regression test that starts from a graded submission, changes its question, and expects empty results plus `Ready to grade` immediately.
2. Run the focused test and confirm it fails on the stale `graded` status.
3. Extract the completed-grade clearing logic already used for code edits into a shared private method.
4. Call the shared method from both code and question changes.
5. Run the focused suite and confirm it passes.

### Task 3: Split and enforce the component stylesheet budget

**Files:**
- Modify: `maistra_web/angular.json`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.css`
- Create: `maistra_web/src/app/components/submissions-list/submissions-list.review.css`
- Create: `maistra_web/src/app/components/submissions-list/submissions-list.responsive.css`

1. Tighten the component-style error budget to 9 KB and run the production build to prove the current 14.8 KB stylesheet exceeds it.
2. Move review-workspace rules into `submissions-list.review.css` and responsive rules into `submissions-list.responsive.css`, preserving selector order.
3. Register all three stylesheets on the component.
4. Run the production build and confirm every individual stylesheet is within budget.

### Task 4: Full verification

1. Run the complete Angular test suite.
2. Run the Angular production build.
3. Run all Judge0 API tests.
4. Run Supabase schema and migration tests.
5. Run `git diff --check` and report any warnings separately from failures.

No commit will be created because this branch already contains the user's uncommitted work.
