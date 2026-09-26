# Stale Grading Guard Design and Implementation Plan

**Goal:** Prevent an older Judge0 grading run from restoring or persisting results after the active grading inputs change.

**Architecture:** The Angular workflow assigns a monotonically increasing in-memory generation to every grading run and checks it after each asynchronous boundary. PostgreSQL stores a `grading_revision` that is incremented by a trigger whenever the persisted question or verified code changes. The final grade update is conditional on both the captured revision and question ID, so stale browser work cannot overwrite a newer persisted input state.

**Scope:** This change cancels in-progress work when code, question, modal, or component state changes. It does not implement finding #3's immediate clearing of an already completed visible grade while the teacher types.

## Implementation

1. Add failing schema tests for `grading_revision` and automatic revision/grade invalidation when persisted inputs change.
2. Add a migration containing the revision column and a short `BEFORE UPDATE` trigger.
3. Add failing service tests requiring grade updates to match the captured revision and question ID.
4. Return `false` when the conditional database update matches no row.
5. Add failing component tests for question changes during grading and overlapping grading runs.
6. Add generation helpers and guard every Judge0/database `await`, including `finally`.
7. Invalidate the active generation when code, question, modal, or component state changes.
8. Reset local Supabase, run pgTAP and migration tests, then run the full Angular suite and production build.
