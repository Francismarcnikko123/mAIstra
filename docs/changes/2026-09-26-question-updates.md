# Questions can be edited; edited test cases clear stale grades (2026-09-26)

> **Owner:** Jayrald. **Commit:** `018fe7d` on `judge0-integration`.

## What

`20260926000400_allow_question_updates.sql`, applied to the cloud:

- **Policy `questions_public_update`:** edits get the same checks as new questions (type `function` or `program`, length limits, `test_cases` is an array).
- **Column grants:** the browser can update `question_name`, `question_text`, `model_answer`, `test_cases`, `question_type` and `can_publish`. Not `id` or `created_at`, and still no delete.
- **Trigger `invalidate_grades_on_question_change`:** when a question's `test_cases` or `question_type` change, every paper linked to it (`submissions.question_id`) loses its grade, goes from `graded` back to `verified`, and its `grading_revision` advances. Renaming the question or editing its text or model answer keeps grades.

## Why

- Nikko's question page has *Edit* and *Validate test cases* buttons that were disabled until questions could be updated.
- Grading reads the question's test cases and type. Without the trigger, editing test cases would leave old grades looking valid, and a grade being computed during the edit could still be saved. Advancing `grading_revision` makes `save_submission_grade()` refuse it, the same way it already refuses a grade after the code or question of a paper changes.
- The trigger function is `SECURITY DEFINER` because the browser has no UPDATE grant on `grading_revision`. It can't be called directly (EXECUTE revoked from `anon` and `authenticated`).

## Files

- The new migration.
- `supabase/tests/database/security_contract.test.sql`: update grants; anon can rename a question; an invalid `question_type` is refused. The old check "anon cannot update questions" became "anon does not have broad question update privileges".
- `supabase/tests/database/schema_contract.test.sql`: run as anon, a rename keeps the grade, a test-case edit clears it, and an ungraded linked paper still gets a new revision.
- `supabase/tests/test_migration_contract.py`: checks the policy, grant and trigger.

## Affects

- **Nikko:** the Edit and Validate buttons can be enabled. Send `can_publish: false` with any edit to the model answer or test cases that has not passed validation again; the database never resets it by itself. Warn the teacher before saving a test-case change on a question that has graded papers.
- **Nombrado / grading:** only Program 1 is covered. When grades move to `submission_programs`, that table needs the same trigger.

## Verification

- Local Supabase: `supabase test db` 58/58, Python contract tests 18/18.
- Cloud, queried after the push: at `20260926000400`; the policy and trigger exist; the function is `SECURITY DEFINER` and anon can't execute it; anon can update `test_cases` and `can_publish` but not `id`, and can't delete. Supabase's security advisor shows nothing new (only the unrelated leaked-password warning for Auth).

## Still open

- Programs 2+ once `submission_programs` exists (see Jayrald's section in `TEAM_SYNC.md`).
