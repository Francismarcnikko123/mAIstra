# Team Sync

A short, shared record of **what each of us changed that affects the others**, **what we need from each other**, and **open questions**. Details live elsewhere (code, `PROJECT_OVERVIEW_AND_CHANGES.md`, personal notes). Link to them instead of pasting them here.

**Rules that keep this file merge-friendly**
- Edit **only your own section**. Git can merge different people's edits to this file cleanly as long as nobody touches another person's lines.
- Keep the same four headings in every section. Put the newest entries **at the top** of each heading, and add a date to each entry: `(2026-09-24)`.
- When something is resolved, move it to **Done** in your own section; don't delete it.
- For a quick question, use Messenger. Record the answer here once it's agreed.

---

## Nombrado (OCR, review editor)

### Status
- (2026-09-24) **OCR:** waiting on the new bond paper and yellow pad datasets. No OCR code change is pending.
- (2026-09-24) **Program tabs** (one paper → several programs, each linked to a question) built on branch `feature/program-tabs` (tip `a49d737`, local, not pushed yet). Base branch: `feature/reading-order-reassembly`. 89/89 web tests; `ng build` clean.

### Changed (affects others)
- (2026-09-24) **New column `submissions.answers jsonb`**, migration `supabase/migrations/20260923000000_add_submission_answers.sql`. It holds Programs 2..n as `[{ code, question_id }]`. Program 1 is still `verified_text` + `question_id`. Until the migration runs, the app still works: it detects the missing column and marks extra tabs as preview-only.
- (2026-09-24) **`getSubmissions()` and `updateSubmissionText()`** in `maistra_web/src/app/services/supabase.ts` now read and write `answers`. The signature gained an optional 4th argument; existing callers are unchanged.
- (2026-09-24) **Grading hand-off:** `programsForGrading(verified_text, question_id, answers)` in `submissions-list/extra-answers.ts` returns every gradable program on a paper as `{ program, code, question_id }`.
- (2026-09-24) **Review Code (Step 2)** in `submissions-list.ts` / `.html` now has program tabs and a question picker; styles are in `submissions-list/program-tabs.css`. Expect a small merge conflict there: import lines with `judge0-integration`, and `openModal()` resets with `feature/question-bank`.

### Needs from others
- (2026-09-24) **Jayrald:** apply the `answers` migration to the cloud project (or tell me if we go with option B below, where it may be unnecessary).
- (2026-09-24) **Jayrald:** grade every program on a paper through `programsForGrading()`, not just Program 1.
- (2026-09-24) **Nikko:** questions can't be told apart except by name. There's no question number, no quiz grouping, and no screen showing each question's model answer and test cases. **Check Jayrald's `assessments` / `assessment_questions(position)` tables on `code-similarity/duplicate` first**; they may already cover this.

### Open questions
- (2026-09-24) **Jayrald:**
  1. Which branch are you working on: `judge0-integration` (same commit as `codex/supabase-security`) or `code-similarity/duplicate`?
  2. Is `code-similarity/duplicate` still going to be merged, and in what order?
  3. For papers with several programs:
     - **A.** keep the `answers` column and have similarity/grading read `programsForGrading()`, or
     - **B.** make one submission row per program, which matches your one-row-per-(assessment, question, student) index?
  4. Who applies migrations to the cloud, and in what order?
  5. Should Nikko wait for your `assessments` tables?
  6. Which branch should `feature/program-tabs` target for its pull request?

### Done
- (2026-09-23) Browser now uses the publishable Supabase key (`a448198`). Note: RLS is enabled on `questions` but **not** on `submissions`.

---

## Jayrald (submissions/review UI, Judge0, Supabase)

### Status

### Changed (affects others)

### Needs from others

### Open questions

### Done

---

## Nikko (mobile capture, question bank)

### Status

### Changed (affects others)

### Needs from others

### Open questions

### Done
