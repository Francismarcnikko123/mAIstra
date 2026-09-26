# Merge Jayrald's schema work into `feature/question-linking-v2` (2026-09-26)

> **Owner:** Nikko (merge). Jayrald's changes are his; see his notes in this folder.

## What

Pulled `origin/judge0-integration` at `268eb54` into `feature/question-linking-v2`. Jayrald had already merged the pushed v2 (`ce000bc`) and Nombrado's latest pre-extraction into his branch, then added:

- `gate_result`, `can_publish` (restored) and UPDATE on `questions` (`018fe7d`, migrations `20260926000200`–`0400`)
- `submissions.batch_id` for the pages of one answer (`ec5c910`, `…0500`)
- `submission_programs`, one row per program, graded on its own (`f85d99e`, `f3138c6`, `96eda09`, `…0600`)
- label refresh after saving, Playwright fixes, team docs

The schema is live in the cloud. Jayrald fixed a database-side error before this merge; no code change came with it.

## Conflicts

| File | Resolution |
|---|---|
| `submissions-list.html` | Kept Nombrado's Save area next to the tabs without the old message under the editor. Jayrald's side still had that message and his `saveStatusLabel()` did not know the conflict case; v2's label covers it and the old message's styles were already removed. |
| `submissions-list.program-tabs.spec.ts`, `submissions-list.spec.ts` | Comment wording only; took Jayrald's. |
| `TEAM_SYNC.md` | Kept Jayrald's two new To-dos for Nikko and Nikko's ticked answers to Nombrado. |
| `docs/changes/README.md` | Kept both sets of rows. |
| `PROJECT_OVERVIEW_AND_CHANGES.md` | Took Jayrald's layout (he moved Nombrado's Save section and updated the verification list); Nikko's sections are unchanged. |

## Verification

- Web: 300/300 tests (Jayrald's 299 + the conflict-label test), both TypeScript checks, `ng build` passes.
- No mobile files changed. `ocr_feature/` identical to `feature/pre-extraction`. `AGENTS.md` present.

## Open (Nikko)

- Jayrald's To-do: send one `batch_id` per submit from the phone.
- `saveStatusLabel()` differs between v2 and `judge0-integration`; noted for Jayrald in TEAM_SYNC.
