# Merge pre-extraction and judge0-integration into `feature/question-linking-v2` (2026-09-26)

> **Owner:** Nikko (merge). **Please review:** Nombrado and Jayrald, since most resolutions are in their code.
> **Commits:** `0e21d5c` (pre-extraction), `a727934` (question-linking), `ffcf908` (judge0-integration). Full decision list in the `ffcf908` commit message.

## What

`feature/question-linking-v2` starts at `ca45ddf` (quality gate + program tabs) and adds, in order:

1. `origin/feature/pre-extraction` (Nombrado): merged cleanly.
2. `feature/question-linking` (Nikko): merged cleanly.
3. `origin/judge0-integration` at `7ee9b03` (Jayrald): 17 conflicting files, resolved by hand.

No teammate's branch was changed. Their work was copied into this branch.

## Conflict resolutions

| File | Resolution |
|---|---|
| `services/supabase.ts` | Jayrald's revision-guarded `updateSubmissionDetails` / `updateSubmissionText` / `updateSubmissionGrade` and grade columns, plus Nombrado's `answers` fallback and Programs 2..n in the same guarded update. `subscribeToSubmissions(onInsert, onUpdate = onInsert)`. |
| `submissions-list.ts` | Jayrald's version as base. Added Nombrado's program tabs, OCR health / "Extracting…", re-extract confirmation, close prompt (then Jayrald's restore-on-close), instant OCR merge on UPDATE before Jayrald's row refetch; Nikko's section folders. Programs 2..n are sent only when the paper has tabs (or had saved ones to clear). |
| `submissions-list.html` | Nombrado's tabs; Program 1 editor goes through Jayrald's `updateSubmissionCode`; cards keep Nikko's time/label/badge plus Jayrald's grade summary. |
| `submissions-list.css` | Jayrald's split stylesheet (`.list`, `.review`, `.responsive`); Nombrado's re-extract dialog styles moved into `submissions-list.review.css`. |
| `question-form.ts` / `.html` | Jayrald's validation tracking, 15 s save timeout and `questionSaved` event, plus Nikko's section, number, `can_publish` and label preview. |
| `app.html` | Nikko's top-bar layout plus Jayrald's `questionSaved → loadQuestions` hook. |
| `code-editor.ts` | Both inputs: Nombrado's `placeholder`, Jayrald's `readOnly`. |
| `ocr_feature/main.py` CORS | Jayrald's localhost origin list with Nombrado's `allow_credentials=False`. **Both please confirm.** |
| `package.json` / lock | Jayrald's (Playwright, `@types/node` 26); lock regenerated with `npm install`. |
| `security_contract.test.sql` | Jayrald's two Realtime checks. |
| `main.dart`, `environment.ts` | Identical content, formatting/comment only. |
| `PROJECT_OVERVIEW_AND_CHANGES.md` | Owner lines kept, both change logs kept. |

## Tests adapted to the combined behaviour

- `submissions-list.program-tabs.spec.ts` (Nombrado): saves now pass the revision before the programs; the "never replaces teacher text" case types while the paper is open, because closing now saves or discards.
- `submissions-list.spec.ts` (Jayrald): two re-extract tests confirm Nombrado's prompt, because their fixtures already have saved code.
- `question-form.spec.ts` (Jayrald): the helper presets a section so his tests exercise validation as before.
- New: `services/supabase.answers.spec.ts` (Nombrado's answers tests on the new signatures), `question-form/question-form.sections.spec.ts`.
- `SubmissionQuestion.model_answer` kept as optional: still selected; test fixtures use it.

## Arrived unchanged from judge0-integration

`AGENTS.md` deleted; old grading code removed from `judge0_api/` (`logic_checker.py`, `output_checker.py`, `routers/judge0.py`); `mark` removed from question test cases.

## Bug found during the merge

Rewriting `supabase.ts` turned the `\b` in Nombrado's `/\banswers\b/` into a backspace character, breaking the "no answers column" fallback. His test caught it; fixed before committing.

## Verification

- Web: 282/282 tests, TypeScript clean, `ng build` passes (warning: review stylesheet 0.7 kB over its warning budget, under the error limit).
- Mobile: 53/53, analyze 12 issues, quality-gate files untouched.
- OCR: `test_main`, `test_auto_extract`, `test_c_code_cleanup` pass.
- Browser, against the live database: details dropdown, program tabs, "In Program 1" lock, "Remove?" arming, "Re-extract and discard edits?" prompt all work.
- `judge0_api` tests not run (`pytest` not installed locally).
- A running `ng serve` started before the merge served the submissions page unstyled (the new split CSS files weren't picked up); restarting it fixed it.

## Open

- Nombrado and Jayrald review the resolutions, especially CORS.
- Which branch this merges into is still an open question for Jayrald.
