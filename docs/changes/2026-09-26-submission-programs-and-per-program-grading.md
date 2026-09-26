# Every program on a paper is its own row, graded on its own (2026-09-26)

> **Owner:** Jayrald. **Branch:** `judge0-integration`. **Commits:** `f85d99e`, `f3138c6` (migration), `96eda09` (web). Migration applied to the cloud.

## What

**Database** (`20260926000600_add_submission_programs.sql`, Nombrado's proposal as decided in `TEAM_SYNC.md`):

- `submission_programs`: one row per verified program, Program 1 included, with its question (`on delete restrict`), code and grade (`grading_results`, counts, generated `score_percent`, `graded_at`, `grading_revision`). One question per paper; the uniqueness check is deferred so a save can swap two tabs' questions.
- The same stale-grade rules as `submissions`: changing a program's code or question clears its grade. Editing a question's test cases or type clears the grades of every program linked to it.
- `save_submission_programs(p_submission_id, p_grading_revision, p_programs, p_extracted_text, p_replace_all)`: saves every program of a paper in one call, only while the page is still at `p_grading_revision`. Program 1 is mirrored to `submissions.verified_text` / `question_id` and uses the page's question when none is sent. With `p_replace_all = false`, only the programs given are written.
- `save_program_grade(...)`: the same compare-and-set as `save_submission_grade()`, for one program.
- A page is `graded` only when every program on it is graded.
- RLS and column grants in the lock-down style. The copy step brought Program 1 of the 4 cloud pages across, keeping the one existing grade. `submissions.answers` (empty) is dropped.

**Web:**

- `supabase.ts` loads each paper's programs and still gives the review screen and the question bank `answers` (Programs 2..n), so their code is unchanged. Saves go through `save_submission_programs()`. There is a fallback for databases without the table.
- Step 3 shows a chip per program when a paper has several. The teacher picks one, runs a sample, and submits. It's graded against its own question and saved with `save_program_grade()`. The grader is recreated per program. Single-program papers look as before.
- Cards show `Q1 3/4 · Q2 not graded` for several programs (`Program 2` when the question has no section number), and the old summary for one.

## Why

Programs 2..n had no foreign key, no place for grades, and a different storage from Program 1. The decisions (table, grades on it, restrict, page graded only when all are, per-program scores) are recorded in `TEAM_SYNC.md`, Jayrald → Changed.

## Files

- `supabase/migrations/20260926000600_add_submission_programs.sql`; tests `supabase/tests/database/submission_programs.test.sql` (18 checks) and `test_migration_contract.py`.
- `maistra_web/src/app/services/supabase.ts` (+ `supabase.answers.spec.ts` rewritten, `supabase.spec.ts` adjusted).
- `submissions-list.ts` / `.html`, new `program-grading.css` (its own stylesheet: the component's other styles are at their size budget), new `submissions-list.program-grading.spec.ts`.
- Playwright: the fake backend serves `submission_programs` and both RPCs; one new two-program test.

## Affects

- **Nombrado:** no change needed in the review screen. `programsForGrading()` is no longer used by grading.
- **Nikko:** `answers` is gone; `getQuestionPaperLinks()` returns the same shape from the new table.
- **Grading:** papers without program rows (a database without the table) keep the old Program 1 path.

## Verification

- `supabase test db` 80/80 locally. The whole migration was re-applied from a pre-migration state in a rolled-back transaction, and the copy step was checked on sample data.
- `npx ng test` 299/299, both TypeScript checks, `npx ng build` (existing CSS budget warning), `npx playwright test` 16/16 (8 tests × 2).
- The anon save and grade calls were made through the local Supabase REST API.
- Cloud after the push: at `20260926000600`, 4 program rows (1 graded), `answers` gone, RLS on, anon can execute both functions. Security advisor: nothing new.

## Still open

- The phone doesn't group pages yet (`batch_id` is ready, see its note).
- Similarity (parked) should compare programs grouped by question when it comes back.
