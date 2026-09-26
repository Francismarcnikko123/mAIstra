# Question sections migration (2026-09-24)

> **Owner:** Nikko (author). **Applies:** Jayrald (only he applies migrations to the cloud project).
> **Commit:** `50ab4ab` on `feature/question-linking`. File renamed on 2026-09-26, see [migration rename](2026-09-26-migration-rename.md).

## What

Two new tables so every question can have a section and a number (`Basic · Q2 · Sum of two numbers`):

| Table | Columns | Rules |
|---|---|---|
| `question_sections` | `id`, `name` (unique), `position`, `created_at` | a section name exists once |
| `question_section_items` | `section_id`, `question_id`, `number` | `unique (section_id, number)` refuses a duplicate number in a section; `unique (question_id)` keeps a question in one section |

Both have RLS on, public read, and column-level INSERT/UPDATE grants, following `20260921000000_lock_down_public_api.sql`. There is no DELETE from the API.

## Why

The spec (`IMPLEMENTATION_SPEC_question_linking.md`) puts section and number in new tables owned by Nikko instead of new columns on `questions`, so the five-column INSERT grant on `questions` stays untouched.

A question with no row in `question_section_items` is **unsectioned**: it shows under "No section yet" on the web and never appears in the phone's picker.

## Files

- `supabase/migrations/20260926000100_add_question_sections.sql` (was `20260924000000_…`)

## Affects

- **Jayrald:** has to apply it. Listed in his To do in `docs/TEAM_SYNC.md`.
- **Everyone:** nothing on `questions` or `submissions` changes.

## Beyond the spec

`unique (question_id)` was added so a question can't carry two labels.

## Verification

Applied to the cloud by Jayrald on 2026-09-26. Used end to end the same day: section *Basic* with question number 1 ([test note](2026-09-26-end-to-end-test.md)).

## Open

- *Done 2026-09-26:* applied by Jayrald, together with `can_publish`, `gate_result` and UPDATE on `questions`.
