# Submission Grade Persistence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist completed equal-weight test-case grades in Supabase and restore them when a submission is reopened.

**Architecture:** Store the per-test result collection and passed/total counts on `submissions`. PostgreSQL derives the stored percentage from those counts. The submissions workflow saves a grade only after every Judge0 test completes, and the existing Judge0 child component continues to derive its display from the restored result collection.

**Tech Stack:** PostgreSQL/Supabase migrations and pgTAP, Angular 21, TypeScript, Vitest.

---

### Task 1: Define the grade schema contract

**Files:**
- Create: `supabase/migrations/20260917130000_add_submission_grades.sql`
- Modify: `supabase/tests/database/schema_contract.test.sql`
- Modify: `supabase/tests/test_migration_contract.py`

1. Write failing schema tests for result JSON, passed/total counts, generated percentage, and grading timestamp.
2. Run the static contract tests and confirm they fail because the columns are absent.
3. Add the migration with count consistency checks and a stored generated percentage.
4. Reset the local Supabase database and run the pgTAP and static contract tests.

### Task 2: Add the grade persistence service

**Files:**
- Modify: `maistra_web/src/app/services/supabase.spec.ts`
- Modify: `maistra_web/src/app/services/supabase.ts`

1. Write failing tests for the grade update payload and database error propagation.
2. Add `updateSubmissionGrade()` to persist counts, results, `graded_at`, and the `graded` status.
3. Select the persisted grade fields from `getSubmissions()`.
4. Run the focused service tests.

### Task 3: Save and restore completed grades

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`

1. Write failing tests requiring grading to call the persistence service and reopening to restore results.
2. Persist the complete result set before publishing it to the UI.
3. Update the in-memory submission after a successful save.
4. Hydrate result, status, and output state in `openModal()`.
5. Report a distinct error if execution succeeds but grade persistence fails.

### Task 4: Verify

1. Run the focused Angular tests.
2. Run the complete Angular test suite and build.
3. Reset the local Supabase database and run both schema test suites.
4. Confirm findings 3 and 4 remain outside this change.
