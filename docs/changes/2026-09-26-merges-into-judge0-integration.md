# Nikko's and Nombrado's branches merged into `judge0-integration` (2026-09-26)

> **Owner:** Jayrald. **Branch:** `judge0-integration`. **Commits:** `138ef02`, `046b88c`, `c893b85`.

## What

- **`138ef02`** merges `feature/question-linking-v2` (Nikko, `ce000bc`): mobile question picker and quality-gate verdicts, question sections, question bank and question page, and `feature/pre-extraction` up to `d9df182`. One conflict (`docs/PROJECT_OVERVIEW_AND_CHANGES.md`); both sections kept.
- **`046b88c`** merges `feature/pre-extraction` (Nombrado, `0f87354`): the Save button beside the program tabs, the "Program 1 saved" label, `AGENTS.md`, the handoff notes and the `submission_programs` proposal. Seven conflicts; the resolutions are in the commit message. In short:
  - `AGENTS.md` and `ocr_feature/` take Nombrado's versions (the CORS change from `876880c` and its test are dropped, as asked).
  - The save message under the editor is kept next to Nombrado's label beside Save, because it is the only place the save-conflict warning shows.
  - Two of Nombrado's tests are updated for this branch's revision-guarded save.
- **`c893b85`** fixes what the merges broke or exposed:
  - A question saved on the question page now shows in the submissions list with its section label and folder without a reload (`refreshQuestions()`).
  - The Playwright tests follow the merged screens, and their fake backend serves the section tables and answers the OCR server's health check.

## Why

`judge0-integration` is the one branch all three lines of work now meet on (decided in `TEAM_SYNC.md`, 2026-09-26). Real merges (not squashes) keep the shared history, so later merges don't re-conflict.

## Affects

- **Everyone:** build on `judge0-integration`. `code-similarity/duplicate` is parked.
- **Nombrado:** two requests in Jayrald → Needs from others (`saveStatusLabel()` cases, the `readOnly` input in `code-editor.ts`).
- **Nikko:** a question for you about the `docs/` line in `.gitignore`.

## Verification

After `046b88c`: `npx ng test` 288/288, both TypeScript checks, `npx ng build` (existing CSS budget warning). After `c893b85`: 289/289 and `npx playwright test` 14/14 with `--repeat-each=2`.
