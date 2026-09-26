# Gate verdicts, the validated flag, and catching the cloud up (2026-09-26)

> **Owner:** Jayrald. **Commit:** `018fe7d` on `judge0-integration`.

## What

- **`20260926000200_add_submission_gate_result.sql`:** new column `submissions.gate_result text`, limited to `PASS`, `FIXABLE`, `RETAKE` or NULL. The browser can set it on insert only (no UPDATE grant). `submissions_public_insert` now also accepts NULL, `PASS` or `FIXABLE` and rejects `RETAKE`.
- **`20260926000300_restore_question_can_publish.sql`:** brings back `questions.can_publish boolean NOT NULL DEFAULT false` (dropped in `20260917000000`) and grants it on insert. Existing questions with test cases were set to `true`.
- **Cloud project caught up.** Applied with `supabase db push --include-all`: `20260923000000_add_submission_answers` (Nombrado), `20260926000100_add_question_sections` (Nikko), and the two above. The cloud was at `20260926000000` before.

## Why

- Nikko's phone sends `gate_result` with every page and its question picker filters on `can_publish`; without the columns, mobile uploads failed and the picker showed "Could not load questions". The web question form also writes `can_publish: true` on insert.
- Rejecting `RETAKE` in the database matches the phone's rule that such pages are captured again, never uploaded.
- The backfill: the form has refused to save a question until every test case passes since 2026-09-04 (`366da40`), and all 22 cloud questions were created on or after 2026-09-05 and have test cases. Leaving them `false` would have emptied the mobile picker, and questions couldn't be edited yet.

## Files

- The two new migrations.
- `supabase/tests/test_migration_contract.py`: checks for both columns, the policy and the grants.
- `supabase/tests/database/security_contract.test.sql`: column grants, plus anon uploading a `FIXABLE` page (allowed) and a `RETAKE` page (refused).

## Affects

- **Nikko:** mobile uploads and the question picker work against the cloud again (not yet tried on a phone). The name `can_publish` was kept.
- **Nombrado:** `submissions.answers` now exists in the cloud, but it was applied before I saw the "hold" request on `feature/pre-extraction`. It is empty (0 of 212 rows) and will be dropped by the `submission_programs` migration.

## Verification

- Local Supabase: `supabase test db` 51/51, Python contract tests 17/17.
- Cloud, queried after the push: all migrations up to `20260926000300` recorded; `gate_result`, `can_publish`, `answers`, `question_sections` and `question_section_items` exist; 22/22 questions validated; anon can insert but not update `gate_result`; the insert policy checks `gate_result`.
- RLS on `submissions` was already enabled in the cloud by `20260921000000_lock_down_public_api.sql`.

## Still open

- `supabase db push` prints a "failed to cache migrations catalog" certificate warning from the CLI's local cache. The migrations themselves applied.
