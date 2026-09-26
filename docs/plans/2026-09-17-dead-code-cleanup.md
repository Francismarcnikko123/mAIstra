# Dead-Code Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the confirmed dead code and duplicate contracts while preserving C execution, question validation, and equal-weight grading.

**Architecture:** Angular uses one Judge0 service and one normalization utility. The Python API exposes only execution and logic analysis. Supabase migrations are the sole schema source, with a forward migration for obsolete columns.

**Tech Stack:** Angular 21, TypeScript, Vitest, FastAPI, pytest, PostgreSQL/Supabase migrations.

---

### Task 1: Remove dead question-form state and marks

**Files:**
- Modify: `maistra_web/src/app/components/question-form/question-form.ts`
- Modify: `maistra_web/src/app/components/question-form/question-form.spec.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`

1. Change tests to require mark-free saved/reset cases and run them red.
2. Remove `mark`, `customInput`, the unused model runner method, and its state.
3. Remove obsolete runner tests and mark fixtures.
4. Run the focused component tests green.

### Task 2: Consolidate output normalization

**Files:**
- Create: `maistra_web/src/app/utils/normalize-output.ts`
- Create: `maistra_web/src/app/utils/normalize-output.spec.ts`
- Modify the three components that normalize output.

1. Add utility tests and run them red.
2. Implement the shared utility and replace local methods.
3. Run utility and component tests green.

### Task 3: Consolidate Judge0 execution and logic analysis

**Files:**
- Modify: `maistra_web/src/app/services/judge0.service.ts`
- Modify: `maistra_web/src/app/components/judge0/judge0.ts`
- Modify: `maistra_web/src/app/components/judge0/judge0.spec.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`
- Modify: `judge0_api/main.py`
- Modify: `judge0_api/tests_judge0_api.py`

1. Add failing tests for service-only execution and `/analyze-logic`.
2. Replace direct runner HTTP usage with `Judge0Service`.
3. Replace `/grade-submission` with `/analyze-logic` and delete unused scoring/output normalization.
4. Remove `/languages`.
5. Run both suites green.

### Task 4: Clean schema, docs, and budget

**Files:**
- Delete: `cloud-schema.sql`
- Create: `supabase/migrations/20260917_remove_unused_question_validation_columns.sql`
- Modify: `supabase/seed.sql`
- Modify: `README.md`
- Modify: `docs/PROJECT_OVERVIEW_AND_CHANGES.md`
- Modify: `docs/plans/2026-09-09-equal-weight-test-scoring*.md`
- Modify: `maistra_web/angular.json`

1. Add a forward migration dropping the three unused validation columns.
2. Remove legacy columns and marks from seed data.
3. Remove outdated documentation and the broken `AGENTS.md` link.
4. Align the component-style warning budget with the verified stylesheet size.

### Task 5: Verify and commit

1. Run `python -m pytest -q` in `judge0_api`.
2. Run `npm test -- --watch=false` and `npm run build` in `maistra_web`.
3. Run dead-reference searches and `git diff --check`.
4. Review the final diff and commit the cleanup.
