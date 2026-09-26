# Codex task: Save-label follow-ups on the program tab bar (Nombrado)

Paste everything below the line into Codex.

---

You are working in the mAIstra repo (`/Users/johncalen.nombrado/Desktop/mAIstra`). Read these first, in order:

1. `AGENTS.md` (project rules and the **Commit messages** rule: subject + body, no AI attribution of any kind).
2. `docs/CODEX_HANDOFF.md`, the top block "Current state — 2026-09-26, evening".
3. `docs/TEAM_SYNC.md`: the ownership table, Jayrald's **Needs from others** (the three 2026-09-26 lines for Nombrado), and Nikko's **To do**.

## Branch

- Work on the existing local branch **`feature/review-save-followups`** (already created from `judge0-integration` at `268eb54`). Run `git switch feature/review-save-followups` and `git status`.
- The working tree already has **uncommitted doc edits made for you** in `docs/CODEX_HANDOFF.md`, `docs/README.md` and `docs/CLAUDE.md` (the 2026-09-26 evening blocks). Keep them and commit them in the docs commit below.
- Also present: `docs/handoffs/2026-09-26-codex-save-label-followups.md` (this prompt). It is untracked, under a gitignored folder; add it with `git add -f` in the docs commit.
- **Do not push. Do not merge.** The user reviews first.

## Background (why)

Step 2 (Review code) has a **Save** button at the right end of the program tab bar (`.program-save` in `submissions-list.html`, styles in `program-tabs.css`). Next to it, `saveStatusLabel(id)` in `submissions-list.ts` shows the result of the last save. Jayrald's branch added a save-conflict guard and asked for two fixes. His request, in `docs/TEAM_SYNC.md` → Jayrald → Needs from others:

> `saveStatusLabel()` says "✓ All programs saved" in two cases where it shouldn't: after a save conflict (`saveStatus = 'conflict'`, another teacher changed the paper), and after a successful save while the teacher keeps typing (`saveStatus` stays `'saved'`). Once it covers both, the older message under the editor can go.

> `EXTRA_PROGRAMS_UNSAVABLE` still says "the database is missing the answers column". It only shows on a database without `submission_programs` now; reword when convenient.

Today two places show save results: the label beside Save (`saveStatusLabel`, Nombrado's) and an older paragraph under the editor (`<p class="save-status">` driven by `saveStatusMessage(id)`, Jayrald's). The goal is **one** place: the label beside Save.

## Ownership (strict)

- **Yours to change (Nombrado's area):** `saveStatusLabel()`, the `.program-save` markup, `program-tabs.css`, the `EXTRA_PROGRAMS_UNSAVABLE` text, `submissions-list.program-tabs.spec.ts`, and Nombrado's lines in `docs/TEAM_SYNC.md`.
- **Removing the old paragraph under the editor and its `.save-status` / `.save-status.saved` CSS** in `submissions-list.review.css` is allowed: Jayrald OK'd it ("once it covers both, the older message under the editor can go").
- **Do not change:** `saveStatusMessage()` (keep it and reuse it, and keep its tests in `submissions-list.spec.ts` passing untouched), `saveVerifiedText()`, `saveCodeAndContinue()`, the conflict/revision logic, `hasUnsavedCode()`, `supabase.ts`, migrations, grading/Judge0, `ocr_feature/`, mobile, the question bank.

## The change

### 1. `saveStatusLabel(id)` in `submissions-list.ts`

Rewrite it to report the editor as it is **now**, reusing Jayrald's `saveStatusMessage(id)` for the conflict text instead of duplicating it:

| Situation | Label text | CSS modifier |
|---|---|---|
| `saveStatus[id] === 'error'` | `Save failed, try again` | `error` |
| `saveStatus[id] === 'conflict'` | exactly `saveStatusMessage(id)` (the "Someone else changed this submission…" sentence) | `error` |
| `saveStatus[id] === 'saved'` and **any program on the paper is unsaved** | `New changes need to be saved.` | `pending` |
| `saveStatus[id] === 'saved'` and `extraAnswersError[id] === EXTRA_PROGRAMS_UNSAVABLE` | `✓ Program 1 saved` | (default, green) |
| `saveStatus[id] === 'saved'` otherwise | `✓ All programs saved` | (default, green) |
| anything else | `''` | — |

- "Any program unsaved" must cover **Program 1 and the extra tabs**. Use the existing helpers: `hasUnsavedPrograms(id)` (tabs + Program 1 against the last loaded/saved snapshots) and/or `hasUnsavedCode(id)` (Program 1 against the stored `verified_text`). Read both, pick what matches "the editor differs from what is stored", and explain the choice in a short comment. Don't add new tracking state.
- Update the doc comment above `saveStatusLabel()`. It still mentions the dropped `answers` column. Describe the table above in one or two sentences.
- Add a small helper for the CSS modifier, e.g. `saveStatusTone(id): 'error' | 'pending' | ''`, so the template doesn't repeat the conditions.

### 2. Template, `submissions-list.html`

- The `.program-save-status` span: show it when `saveStatusLabel(selectedSubmission.id)` is non-empty (use the `*ngIf="… as label"` pattern). Bind `[class.error]` and `[class.pending]` from the tone helper. Keep `role="status"`.
- **Remove** the old paragraph under the editor:
  ```html
  <p class="save-status" *ngIf="saveStatusMessage(selectedSubmission.id) as message" [class.saved]="…">{{ message }}</p>
  ```
  Leave `extraAnswersError` and `extractionError` messages where they are.

### 3. Styles

- `program-tabs.css`:
  - Add `.program-save-status.pending` in amber (e.g. `#b45309`).
  - The conflict sentence is long, so let `.program-save-status` wrap for `.error` / `.pending`: `white-space: normal; max-width: 360px; text-align: right;`. Keep the short green confirmations on one line.
  - Check the bar at narrow widths: the tabs must still scroll sideways, and Save must stay visible.
- `submissions-list.review.css`: remove the now-unused `.save-status` and `.save-status.saved` rules, and nothing else.
- Keep every component stylesheet within its existing budget. `ng build` currently warns only for `submissions-list.list.css`; don't add new warnings.

### 4. `EXTRA_PROGRAMS_UNSAVABLE`

Reword to something accurate for the new schema, for example:
`"Program 1 was saved. Programs 2 and up can't be saved on this database: it has no submission_programs table yet. Ask Jayrald to apply the migrations."`
Update the program-tabs test that asserts the old sentence.

### 5. Tests

- `submissions-list.program-tabs.spec.ts`: extend the existing label tests (they currently expect `✓ All programs saved`, `✓ Program 1 saved`, `Save failed, try again`) and add:
  - conflict → the label equals `saveStatusMessage(id)` and the tone is `error`;
  - saved, then Program 1 edited → `New changes need to be saved.`, tone `pending`;
  - saved, then an extra tab edited → same;
  - saved, then the edit typed back to the saved text → `✓ All programs saved` again;
  - a template check that reads `submissions-list.html` with Node's `readFileSync`, as `question-form/question-form.sections.spec.ts` does: no element with class `save-status` remains, and `.program-save-status` is bound to `saveStatusLabel`.
- Do **not** edit Jayrald's `saveStatusMessage` tests in `submissions-list.spec.ts`; they must still pass as they are.

### 6. Docs (same branch, one docs commit)

- `docs/TEAM_SYNC.md`, **Nombrado section**:
  - **Changed (affects others):** a new top entry `(2026-09-26)` saying the label beside Save now covers conflict and unsaved-after-save, the old message under the editor is removed (with Jayrald's OK), and `EXTRA_PROGRAMS_UNSAVABLE` is reworded. Name the functions.
  - **Done:** one line per Jayrald request, with the commit hash. Don't edit Jayrald's own lines; he ticks them.
- `docs/TEAM_SYNC.md`, **Nikko's To do**: two of Nombrado's 2026-09-26 lines there are outdated ("FYI, no change for the phone" and "Read this before your next web or mobile step", which talk about `answers`). Rules: never edit or delete lines in someone else's section except by **adding a new line**. Add one new line at the top of Nikko's To do, `(2026-09-26, from Nombrado)`, saying: "Supersedes my two earlier 2026-09-26 lines below. `answers` is gone and Programs 2+ live in `submission_programs` (Jayrald's migration, live in the cloud). Your phone flow is unchanged, and Jayrald's `getQuestionPaperLinks()` already reads the new table, so there's nothing to do for these; you can tick both."
- `docs/PROJECT_OVERVIEW_AND_CHANGES.md`: under "Save next to the program tabs", add a dated sub-bullet describing the new label states and the removed paragraph.
- `docs/web/WEB_CODEBASE_GUIDE.md`: update the "Save next to the tabs" section (label states, tone helper, removed `.save-status`, new test count).

## Verification (run all, report the numbers)

From `maistra_web/`:

```
npx tsc -p tsconfig.app.json --noEmit
npx tsc -p tsconfig.spec.json --noEmit
npx ng test --watch=false        # was 299/299 on judge0-integration; report the new total
npx ng build                     # only the existing submissions-list.list.css warning is allowed
```

If Playwright is set up (`maistra_web/tests/e2e`, `npx playwright test`), run it too and report. If it can't run, say why; don't skip silently.

Don't click Save in a browser against the cloud database. The unit tests cover the behavior.

## Commits (follow AGENTS.md "Commit messages")

Two commits on `feature/review-save-followups`:
1. `fix(web): show conflict and unsaved changes beside Save` (code + tests), with a body: what changed and why (Jayrald's two requests), what was removed, what was deliberately not changed (`saveStatusMessage`, save/conflict logic), and the check numbers.
2. `docs: record the Save-label follow-ups and update team notes`: docs, including the pre-made handoff edits and this prompt file (`git add -f`).

No `Co-Authored-By`, no "Generated with", no mention of Codex/Claude/AI anywhere in the commits. **Do not push or merge.** Finish by printing `git log --oneline -3`, `git status --short`, and the check results.
