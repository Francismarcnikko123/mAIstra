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
- (2026-09-26) **Save next to the program tabs** is done on `feature/program-tabs-save` and merged into `feature/pre-extraction`. Web tests 121/121, TypeScript checks and `ng build` pass (existing CSS budget warning only). No OCR, schema or grading change. Full handoff under **Changed (affects others)** below; what each of you needs to do is in **your own To do**.
- (2026-09-24) **Integration checkpoint:** `feature/pre-extraction` is pushed and includes `feature/program-tabs` via merge commit `d9df182`. Both remain outside `main`. The worker/list badge live checks passed, including server-off **Needs OCR** and restart catch-up. Nikko owns sending the mobile `question_id` for Program 1; Jayrald owns the cloud schema and migrations needed for the complete new question-linking flow. The OCR worker can be tested independently on new papers.
- (2026-09-24) **OCR:** waiting on the new bond paper and yellow pad datasets. No OCR code change is pending.
- (2026-09-24) **Program tabs** (one paper → several programs, each linked to a question) built on branch `feature/program-tabs`, pushed to `origin/feature/program-tabs`. Base branch: `feature/reading-order-reassembly`. 102/102 web tests; `ng build` clean. Review aids added the same day: OCR text beside the photo, View question, unsaved dots and close prompt.

### Changed (affects others)
- (2026-09-26) **HANDOFF: Save next to the program tabs** (branch `feature/program-tabs-save`, merged into `feature/pre-extraction`; not in `main`).

  **1. The problem it fixes.** On Review Code (Step 2) a teacher could only save by going to grading ("Save and continue to grading") or by leaving (✕ → "Save and close"). "Save and close" closed the whole paper, so a teacher who checked Program 1, 2 and 3 and saved had to reopen the paper to grade. Nikko's first review screen (`da00269`) had a plain Save; the 3-step redesign (`aca278e`) replaced it.

  **2. What the teacher sees now.**
  | Where | Before | Now |
  |---|---|---|
  | Program tab bar (Step 2) | tabs and **+** only | tabs, **+**, and a **Save** button at the right end. It saves every tab of the paper and stays on Step 2; the unsaved dots clear and "✓ All programs saved" shows. **Cmd/Ctrl+S** does the same. |
  | Step 2 footer (Jayrald's button) | "Save and continue to grading" | "**Continue to grading**". Same logic: it still saves first and opens Step 3 only if the save succeeds. |
  | ✕ / overlay / Cancel / Finish with unsaved changes | Keep editing / Discard changes / Save and close | **Discard changes** / **Keep editing** (primary). |
  | Save message | "✓ Verified code saved" under the editor | next to the Save button: "✓ All programs saved", or "✓ Program 1 saved" while the cloud has no `answers` column (see point 4) |

  **3. How it's wired (one save function for everything).** The Save button, Cmd/Ctrl+S and "Continue to grading" all call the existing `saveVerifiedText()` in `submissions-list.ts`. That function is **unchanged**: same save rules (`answerProblems`: a tab with code needs a question, no duplicate questions), same save-generation/timer/destroy guards, same single update `updateSubmissionText(id, verified_text, extracted_text?, answers)` → `verified_text`, `answers`, `status = 'verified'`, `verified_at`. `extracted_text` is still written only with OCR output, never with teacher edits.
  - `submissions-list.html`: the tab row is wrapped in `.program-tabs-bar`; the Save area (`.program-save`) sits after `role="tablist"`, not inside it. Footer label changed. Prompt buttons changed.
  - `submissions-list.ts`: new `onSaveShortcut()` (`@HostListener('document:keydown')`: Cmd/Ctrl+S, only with a paper open on Step 2, prompt closed, code extracted, no save running); `saveAndClose()` removed.
  - `program-tabs.css`: bar and Save styles. `submissions-list.css`: the unused `.save-status` rules removed.

  **4. Two behaviours worth knowing.**
  - Save works even when no dot shows. An untouched pre-extracted paper *looks* saved (the editor matches the worker's `extracted_text`) but is still `pending` with no `verified_text`; Save still verifies it.
  - Saving a paper that was already **graded** sets `status` back to `verified` (this was already true of the old buttons). See Jayrald's To do about stale grading results.
  - **Programs 2+ are not stored in the cloud yet.** The cloud `submissions` table has no `answers` column (Nikko's read-only check, 2026-09-24), so Save stores Program 1 only: the extra tabs keep their unsaved dots, the label says "✓ Program 1 saved" and the message under the editor says Programs 2+ can't be saved yet. Nothing is lost on screen, but a reload loses them. This ends when Jayrald applies `20260923000000_add_submission_answers.sql`.

  **5. Fix included in shared code (for Jayrald).** The app is zoneless, so setting `reviewStep` after an `await` didn't re-render: "Save and review code" and "Continue to grading" could stay on the old step until the next click. I added `this.cdr.detectChanges()` after `reviewStep = 2` in `continueFromDetails()` and after `reviewStep = 3` in `saveCodeAndContinue()`. It's the same two-line fix as your `8e20fd5` on `judge0-integration`; keep either copy when merging.

  **6. Merging with `judge0-integration` (checked read-only on 2026-09-26 with a dry-run `git merge-tree`).** Your branch split from ours on 2026-09-01 (`4dafcc2`) and doesn't have the program tabs or pre-extraction. Pulling `feature/pre-extraction` into it conflicts in 12+ files: `AGENTS.md` (deleted on your side in `7de2372`, changed on ours), `docs/PROJECT_OVERVIEW_AND_CHANGES.md`, `maistra_web/package.json` + `package-lock.json`, `code-editor.ts`, `submissions-list.ts` / `.html` / `.css` / `.spec.ts`, `supabase.ts` + `supabase.spec.ts`, `environment.ts` (both sides use the publishable key; only comments differ) and `ocr_feature/main.py`. Keep both sides:
  - the program-tab markup (tab bar wrapper, Save area, tabs, picker, OCR panel) **and** your step logic (`stepBlocker`, `hasUnsavedDetails`, etc.);
  - the footer label "Continue to grading" (your side still says "Save and continue to grading");
  - the `detectChanges()` calls (same on both sides);
  - your style split (`1f02135`, `6e6235b`) plus `program-tabs.css`, which the component loads through `styleUrls`.
  - `ocr_feature/main.py` also conflicts. See Needs from others.

  **7. Tests.** `submissions-list.program-tabs.spec.ts`: 7 new tests (Save stays on Step 2 and clears dots; a rule-blocked Save writes nothing; Save verifies an untouched pre-extracted paper; Cmd/Ctrl+S saves and blocks the browser dialog; the shortcut ignores other steps, the prompt, missing modifier, a running save and unextracted papers; the prompt has no save action). They replace the old "Save and close" test. `submissions-list.spec.ts`: Continue to grading now asserts Step 3 is rendered. Suite 121/121.

  **8. For Nikko:** I checked your pushed branches read-only. Pulling `feature/pre-extraction` into `feature/question-linking` or `feature/capture-quality-gate` is a **clean merge (no conflicts)**, your pushed phone insert (`image_url` + `status: 'pending'`) works with the OCR worker, and your lock-down migration still lets the worker read papers and write `extracted_text`. What to keep in mind for your next steps is in your To do.

  **9. Label fix (same day).** Found while checking the missing-column case: the label beside Save said "✓ All programs saved" even when only Program 1 was stored. It now uses `saveStatusLabel(id)` in `submissions-list.ts` ("✓ Program 1 saved" / "✓ All programs saved" / "Save failed, try again"), with tests. Suite 121/121.
- (2026-09-24) **Shared branch handoff:** the `answers` column-level UPDATE grant is pushed on both `feature/program-tabs` and `feature/pre-extraction`. The realtime `supabase.ts` UPDATE listener, list badge, and OCR `GET /` health field are already implemented on `feature/pre-extraction`; the old request in Jayrald's To do section for his view on that listener is historical and remains for him to update. The badge behavior was live-tested with new phone papers.
- (2026-09-24) **For Nikko:** yes, the phone's one `question_id` per paper is Program 1's question in the review tabs. If a paper contains more programs, the teacher creates extra tabs and selects each extra question manually; the phone need not split the paper.
- (2026-09-24) **`answers` migration grant:** `20260923000000_add_submission_answers.sql` now grants `UPDATE (answers)` to `anon` and `authenticated`, matching the column-level grants in the public API lockdown migration. No database migration was applied by me.
- (2026-09-24) **Option A list status:** `supabase.ts` now adds an optional realtime UPDATE callback to `subscribeToSubmissions()`; INSERT callers still work. The list badge shows **Extracting…** for new unread papers while the OCR worker runs, then **Needs review** when its UPDATE arrives. `GET /` on the OCR server now includes `auto_extract` (`enabled`, `since`, `failed`); the web checks it on load, every 30 seconds and after reloads. The update merge fills empty fields without replacing teacher edits, verified text or program tabs.
- (2026-09-24) **Pre-extraction on arrival** (branch `feature/pre-extraction`, not merged).
  - The OCR server can read new papers by itself and save `extracted_text` to `submissions` when `AUTO_EXTRACT=true` in its `.env`.
  - It only touches unread papers captured after it starts, and it never overwrites text.
  - It's **off by default**, and I won't switch it on against the cloud until Jayrald OKs it.
  - `supabase.ts` gained one read method, `getSubmission(id)`.
- (2026-09-24) **Closing the review now goes through `requestCloseModal()`** in `submissions-list.ts`. The ✕, the overlay click, Cancel (Step 1) and Finish review (Step 3) use it. If anything on the paper is unsaved, it asks Keep editing / Discard changes / Save and close; otherwise it closes as before. `closeModal()` itself is unchanged. Use `requestCloseModal()` for any new close button. *(Updated 2026-09-26: "Save and close" was removed; the prompt is now Discard changes / Keep editing. See the 2026-09-26 handoff above.)*
- (2026-09-24) **Re-extract on a paper that has program tabs** no longer replaces Program 1. The fresh reading opens read-only beside the photo ("OCR text" panel), and `extracted_text` is still saved from it. Papers without tabs behave as before.
- (2026-09-24) **New column `submissions.answers jsonb`**, migration `supabase/migrations/20260923000000_add_submission_answers.sql`. It holds Programs 2..n as `[{ code, question_id }]`. Program 1 is still `verified_text` + `question_id`. Until the migration runs, the app still works: it detects the missing column and marks extra tabs as preview-only.
- (2026-09-24) **`getSubmissions()` and `updateSubmissionText()`** in `maistra_web/src/app/services/supabase.ts` now read and write `answers`. The signature gained an optional 4th argument; existing callers are unchanged.
- (2026-09-24) **Grading hand-off:** `programsForGrading(verified_text, question_id, answers)` in `submissions-list/extra-answers.ts` returns every gradable program on a paper as `{ program, code, question_id }`.
- (2026-09-24) **Review Code (Step 2)** in `submissions-list.ts` / `.html` now has program tabs and a question picker; styles are in `submissions-list/program-tabs.css`. Expect a small merge conflict there: import lines with `judge0-integration`, and `openModal()` resets with `feature/question-bank`.

### Needs from others
- (2026-09-26) **Jayrald:** your decision on the `submission_programs` proposal (see your To do). I'll wait for it before changing how extra programs are stored.
- (2026-09-26) **Jayrald:** please OK the footer label change "Save and continue to grading" → "Continue to grading" (your button; logic untouched). If you'd rather keep the old label, tell me and I'll revert just the label.
- (2026-09-26) **Jayrald:** `judge0-integration` changes `ocr_feature/main.py` (`876880c`, CORS origins). `ocr_feature/` is OCR-owned, and that hunk sets `allow_credentials=True`, which undoes the 2026-09-24 review fix (`allow_credentials=False`) and will conflict. Please drop that hunk from your branch; if you need an origin allowlist, add it to Needs from others and I'll make it in `ocr_feature/` with credentials off.
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
  3. For papers with several programs *(2026-09-26: now written up as a concrete proposal, recommending a `submission_programs` table; see Jayrald's To do)*:
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
- [ ] (2026-09-26, from Nombrado) **Decide: proposal `docs/superpowers/specs/2026-09-26-submission-programs-table-proposal.md`.** It proposes a `submission_programs` table (one row per program on a paper, Program 1 included, each with `verified_text`, `question_id` and its own grade, reusing your `grading_revision` / stale-grade trigger / `save_submission_grade` pattern) instead of the `answers` jsonb column, because from the database side it isn't clear that Programs 2+ are teacher-verified. It replaces open question 3 (A/B). Six questions for you are in section 7. **Until you decide, please HOLD the `answers` migration** (this supersedes my "Top blocker: apply …answers…" line below): if the table is chosen, that migration is deleted and never applied.
- [ ] (2026-09-26, from Nombrado) **Top blocker: apply `supabase/migrations/20260923000000_add_submission_answers.sql` to the cloud.** Until then, teachers who split a paper into program tabs can save **Program 1 only**: Programs 2+ show "Program 1 saved" plus a warning, and are lost on reload. Nothing else is needed from you for this; the grant for the lock-down is already inside that migration.
- [ ] (2026-09-26, from Nombrado) **Keep `AGENTS.md` when you merge.** Your branch deleted it (`7de2372`); ours now holds the shared project rules and the commit-message rule (subject + body, no AI attribution). The dry-run merge flags it as a modify/delete conflict.
- [ ] (2026-09-26, from Nombrado) **`code-editor.ts` is in my area** (see Ownership). Your branch changes it in `e21038d` and `457d318`. When you merge, keep my version (placeholder input, `refresh()`) and send me what you need from your changes; I'll add it.
- [ ] (2026-09-26, from Nombrado) **Review the Step 2 save change** (handoff in Nombrado → Changed, 2026-09-26): a Save button next to the program tabs, your footer button relabelled "Continue to grading" (logic unchanged), "Save and close" removed from the unsaved prompt, and `detectChanges()` after the step changes (same as your `8e20fd5`). OK the label or ask me to revert it.
- [ ] (2026-09-26, from Nombrado) **When grading more than Program 1:** key each program's results by its `question_id` (unique per paper; the tab picker enforces it), not by tab number, because removing a tab renumbers the later tabs. When a teacher re-saves code that was already graded, the old result no longer matches the code: clear it or mark it for re-grading (a save already sets `status` back to `verified`).
- [ ] (2026-09-26, from Nombrado) **Drop the `ocr_feature/main.py` hunk** (`876880c`) from `judge0-integration` before merging; see Nombrado → Needs from others.
- [ ] (2026-09-26, from Nombrado) **Merging `judge0-integration` with `feature/pre-extraction`:** see the conflict notes in Nombrado → Changed, 2026-09-26, point 6. Keep both the program-tab markup and your step logic.
- [x] (2026-09-24, from Nombrado) **Answer the open questions** in Nombrado's section: which branch is current, whether `code-similarity/duplicate` merges, option A or B for multi-program papers, migration order, and the target branch for `feature/program-tabs`.
- [x] (2026-09-24, from Nombrado) **Apply `supabase/migrations/20260923000000_add_submission_answers.sql`** to the cloud project, unless we choose option B.
- [ ] (2026-09-24, from Nombrado) **Grade every program on a paper:** loop over `programsForGrading(verified_text, question_id, answers)` and grade each entry against its own question's model answer and test cases. Decide how per-program results are keyed and how scores combine.
- [ ] (2026-09-24, from Nombrado) **OK pre-extraction on the cloud project** (see Nombrado → Changed). Later: a secret key for the OCR server once RLS is on, and your view on also listening for realtime UPDATEs in `subscribeToSubmissions()` so the list badge refreshes by itself.
- [x] (2026-09-24, from Nombrado) **Enable RLS on `submissions`.** It is currently enabled only on `questions`.
- [x] (2026-09-24, from Nikko) **Add `submissions.gate_result text`** and add `gate_result` to the submissions INSERT grant (and allow it in `submissions_public_insert`). The phone's quality gate decides PASS / FIXABLE / RETAKE and currently throws that away; without it a low grade can't be traced back to a bad photo. Every screen reads submissions, so a column avoids a join in three places. Until this is applied, **mobile uploads fail**.
- [x] (2026-09-24, from Nikko) **Add a reliable "model answer validated" flag on `questions`.** `can_publish` was dropped in `20260917000000_remove_unused_question_validation_columns.sql`. The mobile picker filters on `questions.can_publish = true`; if you prefer another name, tell me and I'll switch the query. Until this exists, the picker shows "Could not load questions". The web question form now writes `can_publish: true` on insert (it only saves after every test case passes), so please also add `can_publish` to the `questions` INSERT grant. Until then, saving a question from the form fails on this branch.
- [x] (2026-09-24, from Nikko) **Allow updating questions** (an UPDATE grant + policy on `questions`, plus UPDATE on `question_section_items`, which the migration already grants). The question page's *Edit* and *Validate test cases* buttons are disabled until then, and unsectioned questions can't be given a section.
- [x] (2026-09-26, from Nikko) **Renamed my sections migration** from `20260924000000_add_question_sections.sql` to `20260926000100_add_question_sections.sql`: it had the same version number as your `20260924000000_save_grade_for_stored_code.sql`. Contents unchanged; please apply it under the new name.
- [x] (2026-09-24, from Nikko) **Apply `supabase/migrations/20260926000100_add_question_sections.sql`** (two new tables, `question_sections` and `question_section_items`; nothing on `questions` changes).
- Do **not** change `ocr_feature/` or the program-tabs code. If grading needs something from them, add it under Needs from others.

When you finish an item: tick it, add the date and commit, and note anything that affects others under **Changed (affects others)**.

### Status

### Changed (affects others)
- (2026-09-26) **For Nombrado, answers to section 7 of the `submission_programs` proposal:**
  1. **Table, not jsonb.** `submission_programs` it is.
  2. **Grade columns go on `submission_programs`**, as sketched (results, passed/total, `graded_at`, `grading_revision`), with the same stale-grade triggers and a `save_program_grade()` like `save_submission_grade()`. No separate grades table.
  3. **Switch-over:** grading moves to the new table as part of my "grade every program" task. Until then the Program 1 mirror (your section 4, step 4) is fine: each save also writes Program 1 to `submissions.verified_text` / `question_id`. The mirror is removed once grading reads the table.
  4. **I write the migration** (schema, triggers, `save_submission_programs()`, `save_program_grade()`, RLS, grants, dropping the empty `answers` column). You then switch the review screen to it; I'll add the `supabase.ts` calls you need or OK yours.
  5. **`question_id … on delete restrict`**: a question with verified programs can't be deleted.
  6. **A page is `graded` only when every program on it is graded.** Editing any program's code or question sends it back to `verified`. **Scores stay per program** (e.g. `Q1 3/4 · Q2 2/2`); there is no page total, because each program answers a different question and pages of one answer aren't grouped yet.
- (2026-09-26) **For Nombrado, answers to your open questions (2026-09-24):**
  1. **Current branch:** `judge0-integration`. It already contains `codex/supabase-security`.
  2. **`code-similarity/duplicate` is parked**, not merged. It is 25 commits behind, rewrites `submissions-list.*`, and its one-submission-per-(assessment, question, student) index assumes one program per row. Similarity comes back later, rebuilt on top of `submission_programs` (programs grouped by question).
  3. **Multi-program papers: your `submission_programs` table proposal is accepted.** Note: I applied `20260923000000_add_submission_answers.sql` to the cloud before I saw your "hold" request (it's on `feature/pre-extraction`, not on my branch). The column is empty (0 of 212 rows), so the `submission_programs` migration will simply drop it. Answers to its section 7 are in the next entry.
  4. **Migrations:** I apply them to the cloud, in version order, with `supabase db push`. The cloud is at `20260926000400`; date new migrations after that and announce them here.
  5. **Nikko doesn't wait for `assessments`.** Nikko's question sections (live in the cloud) cover grouping and numbering.
  6. **Target branch:** merge `feature/pre-extraction` (which includes `feature/program-tabs`) into **`judge0-integration`**. Everything goes to `main` later in one merge.
  7. **Submission → assessment link:** none for now; assessments are parked with the similarity branch. The tab picker can list all validated questions (optionally Program 1's section first).
- (2026-09-26) **For Nikko, questions can be edited now** (`20260926000400_allow_question_updates`, applied to the cloud). The browser can update `question_name`, `question_text`, `model_answer`, `test_cases`, `question_type` and `can_publish`; edits are checked like new questions (`questions_public_update`). Still no delete. You can enable *Edit* and *Validate test cases*.
  - **Send `can_publish: false`** with any edit to the model answer or test cases that hasn't passed validation again. The database can't tell whether the new test cases were run, so it never resets the flag by itself.
  - **Editing `test_cases` or `question_type` clears the grades** of every paper linked to that question (Program 1), moves `graded` papers back to `verified`, and advances `grading_revision`, so a grade computed against the old test cases can't be saved. Renaming or editing the text or model answer keeps grades. Warn the teacher before saving such an edit if the question has graded papers.
- (2026-09-26) **Cloud project is now at `20260926000300`.** Applied with `supabase db push --include-all`: `20260923000000_add_submission_answers`, `20260926000100_add_question_sections`, `20260926000200_add_submission_gate_result`, `20260926000300_restore_question_can_publish`. `submissions.answers`, `question_sections`, `question_section_items`, `submissions.gate_result` and `questions.can_publish` all exist in the cloud now.
- (2026-09-26) **For Nikko, `submissions.gate_result`:** accepts `PASS`, `FIXABLE`, `RETAKE` or NULL. The browser can set it on **insert only** (no UPDATE grant). `submissions_public_insert` accepts NULL, `PASS` or `FIXABLE` and **rejects `RETAKE`**, matching the phone's rule. Mobile uploads should work again.
- (2026-09-26) **For Nikko, `questions.can_publish`:** kept your name. `boolean NOT NULL DEFAULT false`; the browser can set it on insert. All 22 existing cloud questions were set to `true` (every one has test cases and was created after the form started requiring passing validation on 2026-09-04). There is still no UPDATE on `questions`; that's the next item.
- (2026-09-26) **For Nombrado:** applying the `answers` migration doesn't lock us into option A; it only adds a column. The A/B decision is still open.

### Needs from others

### Open questions

### Done
- (2026-09-26) Question updates: `20260926000400_allow_question_updates.sql` written, tested locally (pgTAP 58/58) and applied to the cloud. Commit `018fe7d`.
- (2026-09-26) `submissions.gate_result` and `questions.can_publish` migrations written, tested locally (pgTAP 51/51) and applied to the cloud. Commit `018fe7d`.
- (2026-09-26) Applied Nombrado's `answers` migration and Nikko's sections migration (under its new `20260926000100` name) to the cloud.
- (2026-09-26) RLS on `submissions`: already enabled in the cloud by `20260921000000_lock_down_public_api.sql`; nothing to do.

---

## Nikko (mobile capture, question bank)

### To do (requested by teammates; please update this section when done)
- [ ] (2026-09-26, from Nombrado) **FYI, no change for the phone:** I proposed to Jayrald a `submission_programs` table for multi-program papers (`docs/superpowers/specs/2026-09-26-submission-programs-table-proposal.md`). Your phone keeps inserting one `submissions` row per page with `status = 'pending'`; its `question_id` still pre-fills Program 1. If it's approved, point 4 below changes: the grant to keep becomes the new table's, not `UPDATE (answers)`.
- [ ] (2026-09-26, from Nombrado) **Read this before your next web or mobile step** (checked read-only against your pushed branches):
  1. **Pull `feature/pre-extraction` before building the web bank/folders.** It has the program tabs, pre-extraction and the new Save button. The dry-run merge into `feature/question-linking` and `feature/capture-quality-gate` is clean now; building on top of it keeps it that way.
  2. **Phone inserts:** keep inserting `status: 'pending'` with `extracted_text`, `verified_text` and `answers` left empty. The OCR worker only reads unread pending papers, and it fills `extracted_text` itself. Your planned `question_id` + `gate_result` fields are fine to add.
  3. **`question_id` from the phone = Program 1's question.** The review opens with it pre-selected in Details. If a page holds more programs, the teacher adds tabs and picks those questions on the web; the phone doesn't need to split anything.
  4. **Migrations:** your lock-down (`20260921…`) runs before my `answers` migration (`20260923…`), which grants `UPDATE (answers)` itself, so no change is needed. If you write a later migration that revokes or re-grants `submissions` columns, keep `SELECT`, `UPDATE (extracted_text)` (the OCR worker uses the publishable key) and `UPDATE (answers)` (the review tabs).
  5. **Question labels in the review picker:** the program-tab picker shows `question_name`, a prompt preview and the test-case count. Once `question_sections` exists and you want labels like `Basic · Q2` there, add it to your Needs from others; the picker is my code and I'll change it.
  6. **Don't change** `ocr_feature/`, the program tabs, the Save button or `code-editor/`; request changes instead.
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
- (2026-09-24) **New migration `supabase/migrations/20260926000100_add_question_sections.sql`** (not applied). Tables `question_sections(id, name, position)` and `question_section_items(section_id, question_id, number)`; a question belongs to at most one section, and numbers are unique within a section. RLS + column grants mirror `20260921000000_lock_down_public_api.sql`. A question with no section never appears on the phone.
- (2026-09-24) **Shared file `maistra_web/src/app/services/supabase.ts`:** added seven methods under a new *QUESTION SECTIONS (Nikko)* block (`getQuestionSections`, `createQuestionSection`, `getSectionNumbers`, `addQuestionToSection`, `getSectionItems`, `getQuestionPaperLinks`, `getGateResults`). Nothing existing changed. `getGateResults` reads `submissions.gate_result` in its own query, so `getSubmissions()` is untouched and keeps working before that column exists.
- (2026-09-24) **App shell `app.html` / `app.ts`, layout from Nombrado's mock:** a top bar (`mAIstra` · *Question bank* · *Submissions*) replaces the side-by-side panels; each is a full page, and *+ Create question* on the bank opens the form. `<app-submissions-list>` is only hidden when you switch pages, never destroyed, so an open review keeps its unsaved edits and realtime updates. The submissions component itself is unchanged. The initial bundle is now ~6 kB over the 1.10 MB warning budget.
- (2026-09-24) **Question form** now requires a section and a question number, shows the label preview (`Basic · Q3 · Count vowels`), and won't save until validation passes.
- (2026-09-24) **Shared `submissions-list.*`, folder and Details parts only:** folders now come from the Program 1 question's section (sections by position, then older typed topics, then *Uncategorized*). Details step 1 shows **Section** read-only from the chosen question instead of the typed *Topic or folder* field; saving writes the section name to `topic`, and an unsectioned question keeps the old topic. Cards show capture time + `Section · Q# · Name` + the phone's photo verdict instead of *Unnamed student*. Review, grading and program tabs are unchanged. New tests in `submissions-list.sections.spec.ts`.
- (2026-09-24) **Global `styles.css`:** added `.gate-badge` (photo verdict badge), used by the submission cards and the question page. It lives there because `submissions-list.css` is at its 12 kB error budget.
- (2026-09-24) **Question bank → question page:** clicking a bank row opens the question (label, summary, "not validated" warning, model answer, test cases, and papers linked as Program 1 or Program 2+ with their photo verdict).
- (2026-09-24) **Mobile inserts into `submissions` now always set `question_id` and `gate_result`** (`'PASS' | 'FIXABLE' | 'RETAKE'`; a page the gate auto-corrected is stored as `FIXABLE`). RETAKE pages can't be uploaded. Each page is still one row.

### Needs from others
- (2026-09-24) **Jayrald:** `submissions.gate_result` + grant, a validated flag on `questions`, and applying the sections migration (see his To do).
- (2026-09-24) **Nombrado:** confirm one `question_id` per paper from the phone (Program 1) is what program tabs expect.
- (2026-09-24) **Nombrado:** show `Section · Q# · Name` in the program-tab question picker and the Details question dropdown. `questionLabel()` and `indexQuestionPlaces()` in `components/question-bank/question-labels.ts` build it; `SubmissionsListComponent.questionPlaces` is already loaded.

### Open questions
- (2026-09-24) **Pages of one answer aren't grouped.** The phone saves one `submissions` row per page, and nothing ties the pages of one answer together, so the web can't show "2 pages" or treat them as one paper. Options: a shared `batch_id` column set by the phone, or one row per answer with several image URLs. Needs a decision with Jayrald (his table) and Nombrado (OCR reads one image per row).

### Done
