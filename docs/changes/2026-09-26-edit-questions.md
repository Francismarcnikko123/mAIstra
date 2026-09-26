# Web: edit and re-validate saved questions (2026-09-26)

> **Owner:** Nikko (question form, question page). Database side by Jayrald (`20260926000400_allow_question_updates.sql`, see [his note](2026-09-26-question-updates.md)).

## What

- **Question page:** **Edit** and **Validate test cases** work. Both open the create form in **edit mode**, pre-filled with the question's section, number, name, type, text, model answer and test cases. *Validate test cases* also runs validation as the form opens. The note "editing isn't available yet" is gone.
- **Edit mode:** title "Edit question", button **Save changes**, **Cancel** returns to the bank unchanged.
- **Save stays locked until validation passes** (Nikko's decision, 2026-09-26):
  - A question saved as validated stays validated while only its name, text, section or number change.
  - Editing the model answer or any test case clears validation; **Validate Test Cases** must pass again. Saving always writes `can_publish: true`, so a question never silently drops off the phone.
  - A question that was never validated must pass validation before it can be saved.
- **Graded papers:** if the test cases (or type) changed and papers linked to the question are graded, Save first shows "N graded papers use this question… Saving the changed test cases clears their grades" with **Save and clear grades**. Jayrald's trigger clears those grades on save. Changing only the name or text keeps grades and shows no warning.
- **Section and number:** changing either moves the question (`question_section_items` update); the question's own number is not shown as taken. An **unsectioned older question** gets its first section and number here, which is how the older questions reach the phone.

## Files

- `question-form/question-form.ts` / `.html` / `.css`: `EditQuestionRequest`, `editRequest` input, `editDone` output, `startEdit()`, `saveEdit()`, `cancelEdit()`, `confirmGradeReset()`, graded-papers warning.
- `question-bank/question-page.*`: live buttons, `edit` output. `question-bank/question-bank.*`: `editQuestion` output.
- `app.html` / `app.ts`: opens the form with the edit request; back to the bank when done.
- `services/supabase.ts` (Nikko's block): `updateQuestion()`, `moveQuestionToSection()`, `countGradedPapers()`.
- Tests: 10 new in `question-form/question-form.sections.spec.ts`.

## Affects

- **Jayrald:** edits go through his `questions_public_update` policy and column grants; test-case edits fire his grade-clearing trigger (Program 1 grades via `submissions.question_id`). Programs 2+ in `submission_programs` aren't covered by that trigger yet (his open item).
- **Nombrado:** after an edit, `questionSaved` refreshes the review's question list (`refreshQuestions()`).

## Verification

- Web: 310/310 tests, both TypeScript checks, `ng build` passes.
- **Not yet checked in the browser** against the live database.
