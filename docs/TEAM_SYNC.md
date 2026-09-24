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
- (2026-09-24) **Integration checkpoint:** `feature/pre-extraction` is pushed and includes `feature/program-tabs` via merge commit `d9df182`. Both remain outside `main`. The worker/list badge live checks passed, including server-off **Needs OCR** and restart catch-up. Nikko owns sending the mobile `question_id` for Program 1; Jayrald owns the cloud schema and migrations needed for the complete new question-linking flow. The OCR worker can be tested independently on new papers.
- (2026-09-24) **OCR:** waiting on the new bond paper and yellow pad datasets. No OCR code change is pending.
- (2026-09-24) **Program tabs** (one paper → several programs, each linked to a question) built on branch `feature/program-tabs`, pushed to `origin/feature/program-tabs`. Base branch: `feature/reading-order-reassembly`. 102/102 web tests; `ng build` clean. Review aids added the same day: OCR text beside the photo, View question, unsaved dots and close prompt.

### Changed (affects others)
- (2026-09-24) **Shared branch handoff:** the `answers` column-level UPDATE grant is pushed on both `feature/program-tabs` and `feature/pre-extraction`. The realtime `supabase.ts` UPDATE listener, list badge, and OCR `GET /` health field are already implemented on `feature/pre-extraction`; the old request in Jayrald's To do section for his view on that listener is historical and remains for him to update. The badge behavior was live-tested with new phone papers.
- (2026-09-24) **For Nikko:** yes, the phone's one `question_id` per paper is Program 1's question in the review tabs. If a paper contains more programs, the teacher creates extra tabs and selects each extra question manually; the phone need not split the paper.
- (2026-09-24) **`answers` migration grant:** `20260923000000_add_submission_answers.sql` now grants `UPDATE (answers)` to `anon` and `authenticated`, matching the column-level grants in the public API lockdown migration. No database migration was applied by me.
- (2026-09-24) **Option A list status:** `supabase.ts` now adds an optional realtime UPDATE callback to `subscribeToSubmissions()`; INSERT callers still work. The list badge shows **Extracting…** for new unread papers while the OCR worker runs, then **Needs review** when its UPDATE arrives. `GET /` on the OCR server now includes `auto_extract` (`enabled`, `since`, `failed`); the web checks it on load, every 30 seconds and after reloads. The update merge fills empty fields without replacing teacher edits, verified text or program tabs.
- (2026-09-24) **Pre-extraction on arrival** (branch `feature/pre-extraction`, not merged).
  - The OCR server can read new papers by itself and save `extracted_text` to `submissions` when `AUTO_EXTRACT=true` in its `.env`.
  - It only touches unread papers captured after it starts, and it never overwrites text.
  - It's **off by default**, and I won't switch it on against the cloud until Jayrald OKs it.
  - `supabase.ts` gained one read method, `getSubmission(id)`.
- (2026-09-24) **Closing the review now goes through `requestCloseModal()`** in `submissions-list.ts`. The ✕, the overlay click, Cancel (Step 1) and Finish review (Step 3) use it. If anything on the paper is unsaved, it asks Keep editing / Discard changes / Save and close; otherwise it closes as before. `closeModal()` itself is unchanged. Use `requestCloseModal()` for any new close button.
- (2026-09-24) **Re-extract on a paper that has program tabs** no longer replaces Program 1. The fresh reading opens read-only beside the photo ("OCR text" panel), and `extracted_text` is still saved from it. Papers without tabs behave as before.
- (2026-09-24) **New column `submissions.answers jsonb`**, migration `supabase/migrations/20260923000000_add_submission_answers.sql`. It holds Programs 2..n as `[{ code, question_id }]`. Program 1 is still `verified_text` + `question_id`. Until the migration runs, the app still works: it detects the missing column and marks extra tabs as preview-only.
- (2026-09-24) **`getSubmissions()` and `updateSubmissionText()`** in `maistra_web/src/app/services/supabase.ts` now read and write `answers`. The signature gained an optional 4th argument; existing callers are unchanged.
- (2026-09-24) **Grading hand-off:** `programsForGrading(verified_text, question_id, answers)` in `submissions-list/extra-answers.ts` returns every gradable program on a paper as `{ program, code, question_id }`.
- (2026-09-24) **Review Code (Step 2)** in `submissions-list.ts` / `.html` now has program tabs and a question picker; styles are in `submissions-list/program-tabs.css`. Expect a small merge conflict there: import lines with `judge0-integration`, and `openModal()` resets with `feature/question-bank`.

### Needs from others
- (2026-09-24) **Jayrald:** the `answers` migration now includes the narrow browser UPDATE grant. Please apply it to the cloud project in the agreed migration order; Nikko's `gate_result` and validated-question requests on `feature/question-linking` are separate schema work you own.
- (2026-09-24) **Everyone:** please don't change `ocr_feature/` or the program-tabs code; send requests here instead.
- (2026-09-24) **Jayrald:** OK to run pre-extraction against the cloud project? For now it would use the publishable key (it works because `submissions` has no RLS). When you enable RLS, I'll need a secret key (`sb_secret_…`) for the OCR server's `.env` only.
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
  7. Once assessments exist, how does a submission link to its assessment (e.g. an `assessment_id` on `submissions`)? The tab picker needs it to list only that paper's questions.

### Done
- (2026-09-23) Browser now uses the publishable Supabase key (`a448198`). Note: RLS is enabled on `questions` but **not** on `submissions`.

---

## Jayrald (submissions/review UI, Judge0, Supabase)

### To do (requested by teammates; please update this section when done)
- [ ] (2026-09-24, from Nombrado) **Answer the open questions** in Nombrado's section: which branch is current, whether `code-similarity/duplicate` merges, option A or B for multi-program papers, migration order, and the target branch for `feature/program-tabs`.
- [ ] (2026-09-24, from Nombrado) **Apply `supabase/migrations/20260923000000_add_submission_answers.sql`** to the cloud project, unless we choose option B.
- [ ] (2026-09-24, from Nombrado) **Grade every program on a paper:** loop over `programsForGrading(verified_text, question_id, answers)` and grade each entry against its own question's model answer and test cases. Decide how per-program results are keyed and how scores combine.
- [ ] (2026-09-24, from Nombrado) **OK pre-extraction on the cloud project** (see Nombrado → Changed). Later: a secret key for the OCR server once RLS is on, and your view on also listening for realtime UPDATEs in `subscribeToSubmissions()` so the list badge refreshes by itself.
- [ ] (2026-09-24, from Nombrado) **Enable RLS on `submissions`.** It is currently enabled only on `questions`.
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

### Changed (affects others)

### Needs from others

### Open questions

### Done
