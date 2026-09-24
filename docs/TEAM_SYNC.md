# Team Sync

A short, shared record of **what each of us changed that affects the others**, **what we need from each other**, and **open questions**. Details live elsewhere (code, `PROJECT_OVERVIEW_AND_CHANGES.md`, personal notes). Link to them instead of pasting them here.

**Rules that keep this file merge-friendly**
- Edit **only your own section**. Git can merge different people's edits to this file cleanly as long as nobody touches another person's lines.
- **One exception:** to request something from someone, you may **add a new line** to the **To do** list in *their* section, starting with the date and `from <your name>`. Never edit or delete their existing lines; the owner ticks and updates them.
- Keep the same headings in every section. Put the newest entries **at the top** of each heading, and add a date to each entry: `(2026-09-24)`.
- When something is resolved, move it to **Done** in your own section; don't delete it.
- For a quick question, use Messenger. Record the answer here once it's agreed.

---

## Ownership and boundaries (read before changing anything)

**Work only on your own tasks.** Don't change code, schema, data or docs that belong to someone else, even to "fix" something small. If you need a change in another person's area, add it to **Needs from others** in *your* section and message them. The owner makes the change.

| Area | Owner | Others must not change |
|---|---|---|
| **OCR system:** everything in `ocr_feature/` (pipeline, preprocessing, layout/reading order, cleanup, models, datasets, labels, evaluators, reports, tests) | **Nombrado** | **Do not touch.** It is measured and defended for the thesis; any change can invalidate recorded accuracy results. |
| Review-code editor: `maistra_web/src/app/components/code-editor/`, the program tabs (`submissions-list/extra-answers.ts`, `program-tabs.css`, the tab/picker parts of `submissions-list.*`), OCR extraction calls in the web app | **Nombrado** | Don't change; request it. |
| Submissions list, review workflow, grading and Judge0: `maistra_web/.../submissions-list/*` (except the parts above), `components/judge0/`, `services/judge0.service.ts`, `judge0_api/` | **Jayrald** | Don't change; request it. |
| Supabase schema, migrations, RLS, cloud project: `supabase/`, `maistra_web/src/app/services/supabase.ts`, `environment.ts` | **Jayrald** | You may **add a migration for your own feature** (as Nombrado did for `answers`), but announce it here. Only Jayrald applies migrations to the cloud project. |
| Question bank: `maistra_web/src/app/components/question-form/` and any question-bank screens | **Nikko** | Don't change; request it. |
| Mobile app: `maistra_mobile/` | **Nikko** | Don't change; request it. |

**Shared files** (`submissions-list.ts` / `.html`, `supabase.ts`, `PROJECT_OVERVIEW_AND_CHANGES.md`): several people edit these, so touch only the lines for your own feature, don't reformat or reorganize the rest, and note what you changed under **Changed (affects others)**.

**After you finish a task:** update your own section. Move the item to **Done** (with date and commit), and add anything that affects others under **Changed (affects others)**.

---

## Nombrado (OCR, review editor)

### Status
- (2026-09-24) **OCR:** waiting on the new bond paper and yellow pad datasets. No OCR code change is pending.
- (2026-09-24) **Program tabs** (one paper → several programs, each linked to a question) built on branch `feature/program-tabs`, pushed to `origin/feature/program-tabs`. Base branch: `feature/reading-order-reassembly`. 89/89 web tests; `ng build` clean.

### Changed (affects others)
- (2026-09-24) **New column `submissions.answers jsonb`**, migration `supabase/migrations/20260923000000_add_submission_answers.sql`. It holds Programs 2..n as `[{ code, question_id }]`. Program 1 is still `verified_text` + `question_id`. Until the migration runs, the app still works: it detects the missing column and marks extra tabs as preview-only.
- (2026-09-24) **`getSubmissions()` and `updateSubmissionText()`** in `maistra_web/src/app/services/supabase.ts` now read and write `answers`. The signature gained an optional 4th argument; existing callers are unchanged.
- (2026-09-24) **Grading hand-off:** `programsForGrading(verified_text, question_id, answers)` in `submissions-list/extra-answers.ts` returns every gradable program on a paper as `{ program, code, question_id }`.
- (2026-09-24) **Review Code (Step 2)** in `submissions-list.ts` / `.html` now has program tabs and a question picker; styles are in `submissions-list/program-tabs.css`. Expect a small merge conflict there: import lines with `judge0-integration`, and `openModal()` resets with `feature/question-bank`.

### Needs from others
- (2026-09-24) **Everyone:** please don't change `ocr_feature/` or the program-tabs code; send requests here instead.
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

### To do (requested by teammates; please update this section when done)
- [ ] (2026-09-24, from Nombrado) **Answer the open questions** in Nombrado's section: which branch is current, whether `code-similarity/duplicate` merges, option A or B for multi-program papers, migration order, and the target branch for `feature/program-tabs`.
- [ ] (2026-09-24, from Nombrado) **Apply `supabase/migrations/20260923000000_add_submission_answers.sql`** to the cloud project, unless we choose option B.
- [ ] (2026-09-24, from Nombrado) **Grade every program on a paper:** loop over `programsForGrading(verified_text, question_id, answers)` and grade each entry against its own question's model answer and test cases. Decide how per-program results are keyed and how scores combine.
- [ ] (2026-09-24, from Nombrado) **Enable RLS on `submissions`.** It is currently enabled only on `questions`.
- [ ] (2026-09-24, from Nikko) **Add `submissions.gate_result text`** and add `gate_result` to the submissions INSERT grant (and allow it in `submissions_public_insert`). The phone's quality gate decides PASS / FIXABLE / RETAKE and currently throws that away; without it a low grade can't be traced back to a bad photo. Every screen reads submissions, so a column avoids a join in three places. Until this is applied, **mobile uploads fail**.
- [ ] (2026-09-24, from Nikko) **Add a reliable "model answer validated" flag on `questions`.** `can_publish` was dropped in `20260917000000_remove_unused_question_validation_columns.sql`. The mobile picker filters on `questions.can_publish = true`; if you prefer another name, tell me and I'll switch the query. Until this exists, the picker shows "Could not load questions".
- [ ] (2026-09-24, from Nikko) **Apply `supabase/migrations/20260924000000_add_question_sections.sql`** (two new tables, `question_sections` and `question_section_items`; nothing on `questions` changes).
- Do **not** change `ocr_feature/` or the program-tabs code. If grading needs something from them, add it under Needs from others.

When you finish an item: tick it, add the date and commit, and note anything that affects others under **Changed (affects others)**.

### Status

### Changed (affects others)

### Needs from others

### Open questions

### Done

---

## Nikko (mobile capture, question bank)

### To do (requested by teammates; please update this section when done)
- [ ] (2026-09-24, from Nombrado) **Make questions identifiable.** Right now a question can only be told apart by its free-text name. There is no question number, no quiz grouping, and model answers and test cases can't be viewed after saving. **First check with Jayrald:** his branch `code-similarity/duplicate` already has `assessments` and `assessment_questions(position)`, which may cover grouping and numbering. Then, as your design decides:
  - a quiz/assessment and question number per question
  - a question bank list screen with view and edit of each model answer and its test cases
  - the same label wherever a question is picked (e.g. `ST1 · Q2 · Even or odd`)
- [ ] (2026-09-24, from Nombrado) Until then, **name questions with quiz and number**, e.g. `ST1 – Q2: Even or odd`, so teachers can pick the right one in the review screen.
- Do **not** change `ocr_feature/` or the review/program-tabs code. If the review picker should show your new fields, add it under Needs from others and Nombrado will update the picker.

When you finish an item: tick it, add the date and commit, and note anything that affects others under **Changed (affects others)**.

### Status
- (2026-09-24) **Question linking, mobile part** built on `feature/question-linking` **(mobile code local, pushed after an on-device test)** (spec: `IMPLEMENTATION_SPEC_question_linking.md`). The phone now picks a validated, sectioned question before capture and sends `question_id` + `gate_result` with every page. Web bank/form/folders are next. Blocked on Jayrald's three items above for an end-to-end run.
- (2026-09-24) **Live DB check** (read-only, with the app's publishable key): `question_sections`, `questions.can_publish`, `submissions.gate_result` and `submissions.answers` are all **missing** in the cloud project. So Nombrado's `answers` migration is also still unapplied.

### Changed (affects others)
- (2026-09-24) **New migration `supabase/migrations/20260924000000_add_question_sections.sql`** (not applied). Tables `question_sections(id, name, position)` and `question_section_items(section_id, question_id, number)`; a question belongs to at most one section, and numbers are unique within a section. RLS + column grants mirror `20260921000000_lock_down_public_api.sql`. A question with no section never appears on the phone.
- (2026-09-24) **Mobile inserts into `submissions` now always set `question_id` and `gate_result`** (`'PASS' | 'FIXABLE' | 'RETAKE'`; a page the gate auto-corrected is stored as `FIXABLE`). RETAKE pages can't be uploaded. Each page is still one row.

### Needs from others
- (2026-09-24) **Jayrald:** `submissions.gate_result` + grant, a validated flag on `questions`, and applying the sections migration (see his To do).
- (2026-09-24) **Nombrado:** confirm one `question_id` per paper from the phone (Program 1) is what program tabs expect.

### Open questions

### Done
