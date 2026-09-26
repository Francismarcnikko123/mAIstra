# Rename the question sections migration (2026-09-26)

> **Owner:** Nikko. **Commit:** `246cb7e` on `feature/question-linking-v2`.

## What

`supabase/migrations/20260924000000_add_question_sections.sql` → `supabase/migrations/20260926000100_add_question_sections.sql`. Contents unchanged (pure rename).

## Why

After merging `judge0-integration`, two migrations had version `20260924000000`: this one and Jayrald's `20260924000000_save_grade_for_stored_code.sql`. Supabase identifies migrations by that number and would refuse one. The new number sorts after every existing migration, so it runs last; it only needs `questions`, which already exists.

## Files

- The migration (renamed).
- `docs/TEAM_SYNC.md`: both references updated, plus a note in Jayrald's To do about the rename.
- `maistra_web/src/app/services/supabase.ts`: comment pointing at the migration.

## Affects

- **Jayrald:** apply it under the new name. He saw the old name on 2026-09-24.

## Verification

No duplicate version numbers left in `supabase/migrations/`; no references to the old name outside the rename note.
