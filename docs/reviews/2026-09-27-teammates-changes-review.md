# Code review: Nikko's and Nombrado's changes in Jayrald's files (2026-09-27)

> **Branch:** `judge0-integration` · **Range:** `d854ae1..98b047b` (the 26 commits pulled on 2026-09-27).
> **Scope:** only the teammates' changes in Jayrald's files and the shared review code:
> - `maistra_web/src/app/services/supabase.ts`: Nikko's `updateQuestion`, `markQuestionValidated`, `moveQuestionToSection`, `countGradedPapers`;
> - `submissions-list.ts` / `.html` / `.review.css`: Nombrado's Save label, and Nikko's live photo badge and section-topic fix;
> - the Playwright fake backend;
> - the merge `fefbf9e`.
>
> Checked against the database on `judge0-integration` (migrations up to `20260926001300`).
> **Level:** high. Findings were not put through a separate verification pass. #1 was confirmed against the cloud data: 57 test cases in 20 of the 23 questions still carry an old `mark` field. Nothing was edited.

## Summary

| # | Severity | Finding | Where | Who fixes |
|---|---|---|---|---|
| 1 | **High** | Saving a question rewrites its test cases even for a rename, so old questions lose their graded papers' grades with no warning | `supabase.ts` `updateQuestion` + `question-form.ts` | Nikko |
| 2 | **High** | Editing a question has no check for a newer version: a second teacher's edit is overwritten silently | `supabase.ts` `updateQuestion` / `markQuestionValidated` | Nikko (Jayrald can add a revision column if wanted) |
| 3 | ✅ Fixed `8c11129` | "New changes need to be saved" disappears after 3 s while a program tab is still unsaved | `submissions-list.ts` `saveVerifiedText` timer | **Jayrald** |
| 4 | Medium (design) | Without the `submission_programs` table, the Save label always says "New changes need to be saved" | `submissions-list.ts` `saveStatusLabel` (merge `fefbf9e`) | Nombrado (decide) |
| 5 | Medium | If "mark validated" fails, a retry warns about grades that are already cleared | `question-form.ts` `saveEdit` | Nikko |
| 6 | Low-Medium | A live photo badge can be wiped by a reload that was already running | `submissions-list.ts` `loadSectionFolders` | Nikko |
| 7 | Low | A typed topic that matches a section name is silently replaced with "Uncategorized" | `submissions-list.ts` `isSectionName` | Nikko |
| 8 | Low | The fake backend's question PATCHes don't behave like the database | `tests/e2e/support/fake-backend.ts` | Nikko |
| 9 | Low | `countGradedPapers` downloads every program row and makes two round trips | `supabase.ts` | Nikko |
| 10 | Low | Leftover code: most of `saveStatusMessage` is dead, and the label's tone is computed three times per render | `submissions-list.ts` / `.html` | Jayrald + Nombrado |

---

## Findings

### 1. High — a rename clears grades on older questions

**Where:** `supabase.ts:155` (`updateQuestion`) and `question-form.ts` `startEdit`.

`updateQuestion` always sends `model_answer`, `test_cases` and `question_type`. `startEdit` rebuilds each test case with only three keys: `test_code`, `test_input` and `expected_output`. In the cloud, **57 test cases in 20 questions** also have a `mark` field (from before marks were removed), and one of those questions has graded papers.

So when a teacher only **renames** such a question:
1. The form thinks the tests are unchanged, so it shows no "Save and clear grades" warning.
2. The PATCH writes test cases without `mark`.
3. The database sees `test_cases` as changed and clears every linked grade (`invalidate_grades_for_question`). It also resets `can_publish` (migration `000800`).

**Fix:** send only the columns that actually changed, compared with what was loaded. Keep unknown keys such as `mark` when rewriting test cases, or drop them deliberately behind the grade warning.

### 2. High — question edits have no conflict check

**Where:** `supabase.ts:178`.

`updateQuestion` is last-writer-wins, and `markQuestionValidated` sets `can_publish = true` on whatever is stored when it runs.

**What goes wrong:**
1. Teacher A opens the edit form.
2. Teacher B saves new test cases.
3. A only renames the question and saves. This writes A's stale model answer and test cases over B's, then marks them validated.

B's edit is lost with no message. A client that skips validation (an older branch) could also publish unvalidated test cases in the gap between the two updates.

**Fix:** a compare-and-set like the paper saves use. Only update while the content (or an `updated_at` or revision column) still matches what the form loaded. Jayrald can add a `questions.revision` column and a guarded update function if Nikko wants one.

### 3. Medium — the "unsaved" warning clears too early (Jayrald's code)

> **Fixed in `8c11129`:** the reminder now stays while `hasUnsavedPrograms(id)` is true. Two new unit tests: the first failed before the fix, the second checks that a save with nothing unsaved still clears.

**Where:** `submissions-list.ts` `saveVerifiedText`, the 3-second auto-clear, working with Nombrado's `saveStatusTone`.

The timer that clears the save label is skipped only when **Program 1** changed while saving (`savedLatest`).

**What goes wrong:**
1. The teacher clicks Save and types into Program 2 while the save is running.
2. The label correctly shows "New changes need to be saved".
3. Program 1 didn't change, so the timer clears the label after 3 seconds, even though Program 2 is still unsaved.

**Fix (Jayrald):** keep the label while `hasUnsavedPrograms(id)` is true, not only when Program 1 changed.

### 4. Medium (design) — the Save label on databases without `submission_programs`

**Where:** `submissions-list.ts:1242` (`saveStatusLabel`), from the merge `fefbf9e`.

The merge kept Nombrado's label and dropped Nikko's rule for preview mode, where Programs 2+ are left unsaved on purpose.

**What goes wrong:** on a database without the table, adding Program 2 and saving shows the amber "New changes need to be saved" every time, next to the message "Program 1 was saved…". "✓ Program 1 saved" is never shown while any tab has content.

The cloud has the table, so only old local databases are affected. Nombrado's test asserts the current behaviour on purpose, so this is a design call for **Nombrado**: treat extra tabs as "not saveable here" rather than "unsaved" in preview mode, or accept the behaviour.

### 5. Medium — the retry after a failed "mark validated" is wrong

**Where:** `question-form.ts:687` (`saveEdit`).

**What goes wrong:**
1. `updateQuestion` succeeds, which clears the grades.
2. `markQuestionValidated` fails.
3. `saveEdit` returns before updating `editOriginal.testsKey` and `gradedPaperCount`.
4. "Save again to retry" then warns that N graded papers will lose their grades, but they were already cleared.

**Fix (Nikko):** update `editOriginal` and the count right after `updateQuestion` succeeds. On retry, only call `markQuestionValidated`.

### 6. Low-Medium — a live photo badge can disappear

**Where:** `submissions-list.ts:218`, with `loadSectionFolders`.

The realtime handler writes the new paper's `gate_result` into `gateResults`. A `loadSectionFolders` that was already running then replaces the whole map with a query result taken before the upload. The badge disappears until the next full reload.

**Fix (Nikko):** merge the maps instead of replacing them, or read `gate_result` in the single-row refetch.

### 7. Low — typed topics matching a section name are replaced

**Where:** `submissions-list.ts:546` (`isSectionName`).

A teacher who links a paper to an unsectioned question and types the topic "Basic" on purpose gets "Uncategorized", with no message. Empty sections aren't in `questionPlaces`, so their names aren't caught at all.

**Fix (Nikko):** the root cause is copying the section name into `topic`. Stop doing that, or put a typed topic that equals a section name into that section's folder.

### 8. Low — the e2e fake doesn't match the database for question edits

**Where:** `tests/e2e/support/fake-backend.ts:435`.

The fake's PATCH on `questions` has three gaps:
- it skips the grade-clearing trigger and the update policy check;
- its `can_publish` reset compares test cases with key-order-sensitive `JSON.stringify`, where Postgres compares JSONB by value;
- its PATCH on `question_section_items` ignores `UNIQUE(section_id, number)`.

So the graded-papers-warning test can't show grades being cleared, and the "number already used" error path is never covered.

**Fix (Nikko):** mirror the trigger, the unique rule and value-based comparison in the fake.

### 9. Low — `countGradedPapers` is heavier than needed

**Where:** `supabase.ts:201`.

It runs two queries one after the other, and the second downloads every program row for the question to filter `graded_at` in the browser. It runs on every edit open and after every edit save.

**Fix (Nikko):** use `Promise.all` and `.not('graded_at', 'is', null)`, or a count query.

### 10. Low — leftover code around the Save label

**Where:** `submissions-list.ts:737` and the template.

With the message under the editor removed, only the conflict branch of `saveStatusMessage` is still used; its other branches repeat `saveStatusLabel`'s strings. The template also calls `saveStatusTone` three times per render, and each call compares all the tabs.

**Fix:**
- **Jayrald:** reduce `saveStatusMessage` to the conflict text.
- **Nombrado:** compute the tone once in the template (`saveStatusTone(id) as tone`).

---

## What looked fine

- Nombrado's Save label now covers conflicts and unsaved changes (the gaps from Jayrald's 2026-09-26 request) and keeps the `readOnly` input in `code-editor.ts`.
- `markQuestionValidated` as its own update matches the `can_publish` reset trigger (`000800`).
- `moveQuestionToSection` uses the existing grants and policy on `question_section_items`.
- The reworded message about the missing `submission_programs` table.

## Suggested order

1. **#1 (Nikko), before anyone edits an older question.** A rename can clear real grades today.
2. **#2 (Nikko, Jayrald on request):** lost edits.
3. ~~**#3 (Jayrald)**~~: fixed in `8c11129`.
4. **#5 and #6 (Nikko).**
5. **#4 (Nombrado's decision), then #7–#10.**
