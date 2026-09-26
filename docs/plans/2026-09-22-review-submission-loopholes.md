# Review Submission Loopholes Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use subagent-driven development and test-driven development task-by-task.

**Goal:** Fix review-state loss, realtime synchronization, concurrent grade overwrites, missing grade visibility, and overlapping Run/Submit operations without committing the changes.

**Architecture:** Keep an explicit local draft boundary in the review component so realtime reloads never overwrite unsaved edits and cancel restores the persisted snapshot. Make grade writes optimistic and atomic by advancing `grading_revision` in PostgreSQL whenever a grade is saved. Surface persisted grade metadata outside Step 3 and lock Run/Submit as one mutually exclusive execution state.

**Tech Stack:** Angular, Vitest, Supabase/PostgreSQL migrations and pgTAP/Python migration-contract tests.

---

### Task 1: Review draft and realtime state

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`
- Modify: `maistra_web/src/app/services/supabase.ts`
- Test: `maistra_web/src/app/services/supabase.spec.ts`

1. Add failing tests proving cancel restores an unsaved code/question edit and its grade.
2. Add a failing test proving an INSERT-triggered reload does not replace a dirty editor buffer.
3. Add a failing test proving the realtime channel subscribes to UPDATE as well as INSERT.
4. Implement persisted modal snapshots/draft tracking and merge reloads without replacing dirty text.
5. Refresh non-dirty selected state from realtime updates and preserve dirty state until save/cancel.
6. Run focused tests and the full Angular suite.

### Task 2: Atomic concurrent grade writes

**Files:**
- Create: `supabase/migrations/20260922000000_advance_grading_revision_on_grade.sql`
- Modify: `maistra_web/src/app/services/supabase.ts`
- Modify: `maistra_web/src/app/services/supabase.spec.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`
- Modify: `supabase/tests/database/schema_contract.test.sql`
- Modify: `supabase/tests/test_migration_contract.py`

1. Add failing database contract tests requiring a successful grade write to advance `grading_revision` exactly once.
2. Add failing service/component tests requiring the new revision to be returned and stored locally.
3. Add a PostgreSQL trigger that advances the revision for grade-field updates without double-incrementing code/question invalidation.
4. Return the new revision from `updateSubmissionGrade`; reject a stale second writer.
5. Run focused Angular and database tests.

### Task 3: Grade visibility and mutually exclusive execution

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.html`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`
- Modify: `maistra_web/src/app/components/judge0/judge0.html`
- Modify: `maistra_web/src/app/components/judge0/judge0.ts`
- Modify: `maistra_web/src/app/components/judge0/judge0.spec.ts`

1. Add failing tests for a persisted numerical grade summary visible when the modal reopens, before Step 3.
2. Add failing tests that Run and Submit reject/disable attempts while either operation is active.
3. Render the persisted passed/total/percentage summary in the review UI.
4. Guard both handlers and both buttons with one shared busy state.
5. Run focused tests, the full Angular suite, and production build.

### Final verification

1. Run all Angular tests and production build.
2. Run database pgTAP and Python migration-contract tests.
3. Inspect `git diff` to ensure OCR, rate limiting, CSS splitting, and unrelated pending work were not altered by these fixes.
4. Do not commit; present the exact changed files and test evidence to the user.
