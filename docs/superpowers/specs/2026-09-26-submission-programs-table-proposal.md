# Proposal: one row per program on a paper (`submission_programs`)

**From:** Nombrado · **For:** Jayrald (schema, grading owner) · **Date:** 2026-09-26
**Status:** waiting for Jayrald's decision. Nothing here is built or applied.
**Replaces, if approved:** `supabase/migrations/20260923000000_add_submission_answers.sql` (never applied to the cloud, so no data moves).

---

## 1. The problem

One photographed page can hold several student programs (for example Question 1 and Question 2 side by side). The review screen lets the teacher split the page into program tabs, each linked to its own question. Today that split is stored like this:

| Column on `submissions` | Holds |
|---|---|
| `extracted_text` | raw OCR of the **whole page** (all programs) |
| `verified_text` + `question_id` | **Program 1** only, teacher-verified |
| `answers` (jsonb) | Programs 2..n as `[{ "code": …, "question_id": … }]`, teacher-verified |

It works, but **the database does not explain itself**:

- Someone reading the table sees `verified_text` for Program 1 and an `answers` list with `code` for the rest. Nothing says Programs 2..n are verified exactly like Program 1 (they are: the same Save writes both).
- `question_id` inside JSON has no foreign key: it can point at a deleted question.
- "One question per paper" is enforced only by the web app.
- Grading results exist for one program per row (`grading_results`, `grading_revision`, …). Programs 2..n have nowhere to keep theirs.
- The OCR training export reads `verified_text` as the whole page's ground truth. On a split paper that is only Program 1.

## 2. Options considered

| | A. Keep one jsonb column, rename it | **B. Table `submission_programs`** | C. One `submissions` row per program |
|---|---|---|---|
| Reader sees every program is verified the same way | partly (P1 still elsewhere) | **yes** | yes |
| Page stays one row (one photo, one raw OCR) | yes | **yes** | no, photo duplicated per program |
| FK to `questions`, one question per paper enforced by the DB | no | **yes** | yes / hard |
| Per-program grading results keyed by question | another jsonb | **natural, reuses your grading design** | natural |
| "All answers to question X" | jsonb operators + GIN index | **plain `where question_id = …`** | plain filter |
| Security with the publishable key | one column grant | new table: RLS + grants like the lock-down | web must INSERT rows, clashes with the lock-down insert policy |
| Save is all-or-nothing | one UPDATE | **one SQL function** | several writes |
| Size | small | **medium** | large (phone, list, grading) |

**Recommendation: B.** `submissions` stays the **page** (photo, raw whole-page OCR, status). `submission_programs` holds **each verified program on that page, Program 1 included**, with its question and its grade. Nobody has to know that "Program 1 is special and the rest are in a JSON list".

## 3. Proposed schema (sketch for review, not final SQL)

```sql
create table public.submission_programs (
  id                uuid primary key default gen_random_uuid(),
  submission_id     uuid not null references public.submissions (id) on delete cascade,
  position          smallint not null check (position >= 1),       -- tab order: 1 = Program 1
  question_id       uuid not null references public.questions (id) on delete restrict,
  verified_text     text not null check (btrim(verified_text) <> ''),
  -- grading, mirroring the columns already on submissions (judge0-integration):
  grading_results   jsonb not null default '[]'::jsonb,
  passed_test_cases integer,
  total_test_cases  integer,
  graded_at         timestamptz,
  grading_revision  bigint not null default 0,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint submission_programs_position_key unique (submission_id, position),
  constraint submission_programs_question_key unique (submission_id, question_id)
    deferrable initially deferred   -- lets a save swap two tabs' questions in one transaction
);

-- Postgres does not index foreign keys by itself.
create index submission_programs_submission_id_idx on public.submission_programs (submission_id);
create index submission_programs_question_id_idx   on public.submission_programs (question_id);

comment on table  public.submission_programs is
  'Each teacher-verified program on a photographed page, in tab order. Program 1 is position 1.';
comment on column public.submission_programs.verified_text is
  'Teacher-verified code of this program. Raw OCR of the whole page stays in submissions.extracted_text.';
```

Open for your choice: `on delete restrict` vs `set null` for `question_id` (restrict keeps a verified program from silently losing its question; your `submissions.question_id` uses `set null`).

**Grades per program.** Mirror your existing design on this table:
- the `invalidate_submission_grade` trigger logic → clear the grade and advance `grading_revision` when `verified_text` or `question_id` changes;
- the `advance_grading_revision_on_grade` trigger → advance the revision on a grade write;
- a `save_program_grade(p_program_id, p_grading_revision, p_question_id, p_graded_code, p_grading_results)` function with the same compare-and-set as `save_submission_grade`.

This also answers my earlier TEAM_SYNC note about stale grades: your trigger already does it; it would just run per program.

**Page status.** `submissions.status` stays the page's workflow state. Suggested rule for you to decide: `graded` only when every program on the page is graded.

## 4. Saving the review (one transaction)

supabase-js cannot run a multi-table transaction, so the web calls one function instead of separate writes:

```sql
-- SECURITY INVOKER, like save_submission_grade: the caller's grants and RLS stay in force.
create function public.save_submission_programs(
  p_submission_id  uuid,
  p_programs       jsonb,        -- [{ "verified_text": …, "question_id": … }, …] in tab order
  p_extracted_text text default null   -- only when a fresh OCR run happened in the session
) returns void language plpgsql security invoker set search_path = '' as $$ … $$;
```

Inside, in order:
1. Upsert each program on `(submission_id, position)`. Updating in place (not delete + insert) lets the grade trigger clear only the programs whose code or question actually changed.
2. Delete positions beyond the new count (tabs the teacher removed).
3. Update the page row: `status = 'verified'`, `verified_at = now()`, `extracted_text` if given.
4. **Transition only:** also set `submissions.verified_text` / `question_id` to Program 1, so your current grading and the current OCR export keep working until they read the new table. Mark those two columns deprecated in their comments.

## 5. Security (same pattern as `20260921000000_lock_down_public_api.sql`)

- `alter table public.submission_programs enable row level security;`
- Policies for `anon, authenticated`: `select using (true)`; insert/update/delete `using (true)` with checks mirroring the submissions policy, to be tightened together when auth arrives.
- Minimal grants: `select`, `insert (submission_id, position, question_id, verified_text)`, `update (position, question_id, verified_text)`, `delete`. Grade columns are written only through `save_program_grade`.
- `grant execute` on the two functions to `anon, authenticated`; `revoke all … from public` first.
- Add the table to the realtime publication if the list should update live (see your `20260926000000_repair_realtime_publication.sql`).

## 6. What each part reads

| Part | Reads |
|---|---|
| Review screen (Nombrado) | `select *, submission_programs(*)` in one query (no per-paper queries); tabs = rows ordered by `position` |
| Grading (Jayrald) | one grade per `submission_programs` row, against that row's `question_id` |
| Similarity (Jayrald) | programs grouped by `question_id` |
| OCR training export (Nombrado) | all programs of a page by `submission_id`; each block is matched to its own lines on the photo, so tab order never matters |
| Phone (Nikko) | unchanged: still inserts one `submissions` row per page with `status = 'pending'`; its `question_id` pre-fills Program 1 |

## 7. Questions for Jayrald

1. **B (this table), or A (keep jsonb, renamed to `extra_programs` with `verified_text` keys)?**
2. Grade columns on `submission_programs` as sketched, or a separate grades table?
3. When does grading switch from `submissions.verified_text` to the new table, and until then is the Program 1 mirror (section 4, step 4) acceptable?
4. Who writes the migration: you, or me drafting it for your review? It would be dated after your latest (`20260926…`) and replace `20260923000000_add_submission_answers.sql`.
5. `question_id`: `on delete restrict` or `set null`?
6. Page `status = 'graded'` only when all programs are graded?

## 8. Until you decide

- **Please don't apply `20260923000000_add_submission_answers.sql`.** If B is chosen it is deleted, never applied.
- Nothing else changes: the review keeps saving Program 1 to `verified_text`, and extra tabs stay preview-only in the cloud.
- After your answer, I update the web review, `supabase.ts` calls (with your OK, it's your file), the export and the tests on a new branch, and show you the diff before merging.
