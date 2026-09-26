# Web: question form, bank, question page and section folders (2026-09-24)

> **Owner:** Nikko. **Commit:** `a72644d` on `feature/question-linking` (layout restyle to Nombrado's mock included).
> Spec: `IMPLEMENTATION_SPEC_question_linking.md` §4, build steps 4–6 and 11.

## What

| Area | Behaviour |
|---|---|
| **Top bar** (`app.html`, `app.ts`) | `mAIstra` · **Question bank** · **Submissions**, each a full page, following Nombrado's mock. The submissions page is hidden, never destroyed, so an open review keeps its unsaved edits and realtime updates. |
| **Create question** (`question-form.*`) | Required **Section** (dropdown + "New section name") and **Question No.** (whole number ≥ 1, lists numbers already used, refuses duplicates). Name placeholder "e.g. Sum of two numbers". Live preview "Teachers will see: **Basic · Q3 · Count vowels**". **Save is locked until every test case passes**, with the reason under the button. Saves `can_publish: true`, then links the question to its section and number. |
| **Question bank** (`question-bank/`, new) | Section cards sorted by position, questions by number: red Q#, bold name, question text, `Program · 3 tests · Validated`, papers pill. "No section yet" last (dashed, grey). Search across all sections. **+ Create question** opens the form. |
| **Question page** (`question-bank/question-page.*`, new) | `Basic · Q2 · Name`, question text, summary, warning strip when not validated, model answer and test cases side by side, **Papers linked to this question** (Program 1 or "Program N on this paper") with the phone's photo verdict. Edit / Validate greyed out: the database has no UPDATE on `questions`. |
| **Submissions folders** (`submissions-list.*`, folder/Details parts only) | Folders come from the Program 1 question's section, then older typed topics, then Uncategorized. Details shows **Section** read-only from the chosen question. Cards show capture time, `Section · Q# · Name` and the photo verdict badge instead of "Unnamed student". |

Supporting code: seven methods in a *QUESTION SECTIONS (Nikko)* block in `services/supabase.ts`; `question-bank/question-labels.ts` (section index, label, gate badge, folder rules); `.gate-badge` in global `styles.css` (the submissions stylesheet is at its budget).

## Why

Questions could only be told apart by free-text name; folders were typed by hand; unvalidated model answers could be saved.

## Affects

- **Shared files:** `submissions-list.*` (folder/Details/card parts only), `supabase.ts` (new block only), `app.html`/`app.ts` (layout everyone sees). Recorded in `docs/TEAM_SYNC.md`.
- **Nombrado:** asked (in TEAM_SYNC) to show `Section · Q# · Name` in his question pickers.
- **Jayrald:** `can_publish` + INSERT grant, UPDATE on `questions`, apply the sections migration.

## Verification

- Web: 128/128 tests at this commit (39 new), TypeScript and `ng build` pass.
- Checked in the browser against the live database: bank lists all 22 questions under "No section yet" with the notice; question page renders; form shows the section fields and "Could not load sections" (expected, table missing).
- Found and fixed while checking: pages didn't switch (the submissions `:host { display: block }` beat `[hidden]`), unlabelled new-section box, red dashes for unnumbered rows.

## Beyond / against the spec

- No page count on cards: one row per page, nothing groups them.
- Student name dropped from cards, as the spec says; Nombrado's mock still shows it.

## Open

- Edit screen (needs UPDATE on `questions`).
- The 22 existing questions stay "Not validated" and unsectioned until editing exists.
