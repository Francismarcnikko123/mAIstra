# Code review: Jayrald's changes on `judge0-integration` (2026-09-26)

> **Branch:** `judge0-integration` · **Reviewed:** Jayrald's own commits from 2026-09-26, not the teammates' merged code.
> **Code:** `018fe7d` (gate_result, can_publish, question updates), `c893b85` (label refresh, e2e repair), `ec5c910` (batch_id), `f85d99e` + `f3138c6` (submission_programs), `96eda09` (per-program grading), and the conflict resolutions in `046b88c`.
> **Docs checked for accuracy:** `0b5d7c4`, `2d31248`, `268eb54`.
> **Level:** high. Findings were de-duplicated but not put through a separate verification pass. Jayrald's author checked #1, #2, #3, #6 and #9 against the code and confirmed them.

## Summary

| # | Severity | Area | Finding | Owner |
|---|---|---|---|---|
| 1 | ✅ Fixed `446b05c` | Web + DB | Changing Program 1's question on Details doesn't update its `submission_programs` row, so it is graded against the old question | Jayrald |
| 2 | ✅ Fixed `446b05c` | DB | The save guard (page `grading_revision`) doesn't move when only Programs 2+ change, so two teachers can overwrite each other's tabs | Jayrald |
| 3 | **Medium** | Web | After grading, Step 3 jumps to the next ungraded program but still shows the previous program's results | Jayrald |
| 4 | Medium | DB | `save_program_grade()` marks the page graded but never updates the page row's grade columns | Jayrald |
| 5 | Medium | DB + Web | A question edit that clears a Program 2+ grade sends no realtime event for pages that weren't `graded`, so the old grade stays on screen | Jayrald |
| 6 | Medium | Web | A fast Submit right after "Continue to grading" can grade stale program rows | Jayrald |
| 7 | Low | DB | Nothing on the server resets `can_publish` when a question's answer or test cases change | Jayrald (+ Nikko's edit form) |
| 8 | Low | OCR | `ocr_feature/main.py` is back to `allow_origins=["*"]` (Nombrado's version, as they asked) | Nombrado |
| 9 | Low | Web + DB | Clearing a middle tab renumbers the later tabs, which wipes their grades | Jayrald (+ Nombrado's `answersToSave`) |

Two claims in the docs (`2d31248`) were wrong because of #1 and #2; the fixes make them true (see [Docs accuracy](#docs-accuracy)).

---

## Findings

### 1. High — Program 1 is graded against the old question after a Details change

> **Fixed in `446b05c`** (migration `20260926000700`): a trigger on `submissions.question_id` moves Program 1 to the new question and clears its grade, creates Program 1 from the page's saved code when missing, and removes it when the question is cleared; the web re-reads a paper's programs after a Details save. Tests: `submission_programs_sync.test.sql`, a unit test and a Playwright test, all of which fail without the fix.

**Where:** `maistra_web/src/app/components/submissions-list/submissions-list.ts:779` (`saveCodeAndContinue`), `maistra_web/src/app/services/supabase.ts:257` (`updateSubmissionDetails`).

`updateSubmissionDetails()` writes only `submissions.question_id`. The Program 1 row in `submission_programs` keeps its old `question_id`. If the code wasn't edited, `saveCodeAndContinue()` goes straight to Step 3 without calling `save_submission_programs()`, and nothing marks the paper's program rows for a re-read.

**What goes wrong:** Program 1 was saved and graded against Q_A. The teacher reopens the paper, picks Q_B on Details, saves, and clicks *Continue to grading* without touching the code. Step 3's label, sample run and Submit all use Q_A. `save_program_grade()` accepts the grade because the row still says Q_A. The card then shows `Q1 3/4` for the wrong question, while `submissions.question_id` is Q_B.

There's a related case. If a page had no question when its code was saved, and it has Programs 2+, it has no Program 1 row at all. Program 1 can't be graded, and the page turns `graded` once only Programs 2+ are graded.

**Fix:** make changing the question on Details also update Program 1's row. The simplest way is to have `saveSubmissionDetails()` call `save_submission_programs()` with Program 1 (`p_replace_all = false`) whenever the question changed, or to do the same in a trigger on `submissions.question_id`. Also add the paper to `staleProgramIds` after a Details save.

### 2. High — concurrent tab edits aren't detected

> **Fixed in `446b05c`** (migration `20260926000700`): any program insert, change or delete in `save_submission_programs()` now advances the page's `grading_revision` (through `advance_page_revision()`), so a save from an older view of the tabs is refused as a conflict. Tests: `submission_programs_sync.test.sql`.

**Where:** `supabase/migrations/20260926000600_add_submission_programs.sql:241` (`save_submission_programs`).

The only guard is the page's `grading_revision`. It advances only when Program 1's code or question changes, or when a page-level grade is written. A save that changes only Programs 2+ leaves it unchanged.

**What goes wrong:** Teachers A and B open the same paper at revision 7. A adds Program 3 and saves; Program 1 is unchanged, so the page stays at 7. B, whose screen still shows only Program 2, edits it and saves with revision 7 and `p_replace_all = true`. The guard passes, and A's Program 3 is deleted with no conflict shown to anyone.

**Fix:** advance the page's `grading_revision` whenever `save_submission_programs()` actually changes any program (insert, update or delete), and return the new value. The web already treats a changed revision as a conflict.

### 3. Medium — Step 3 shows the previous program's results after grading

**Where:** `submissions-list.ts:1667` (`selectedGradingProgram`).

With no chip picked by the teacher, the selection is "first ungraded". Once a program is graded, the selection moves to the next program. But `submissionTestResults` and `submissionCheckStatus` are stored per paper, not per program, so they still hold the program just graded.

**What goes wrong:** On a two-program paper, the teacher submits Program 1 and gets 4/4. The Program 2 chip becomes active and the grader shows Program 2's code, but still displays Program 1's four passing cards and "Accepted". The teacher could read that as Program 2's result.

**Fix:** after a successful grade, record the graded program as the selection (`gradingProgramIds[id] = program.id`), so the view stays on it until the teacher picks another chip. Longer term, store results per program id.

### 4. Medium — the page row claims "graded" with no grade on it

**Where:** `20260926000600_add_submission_programs.sql:324` (`save_program_grade`).

`save_program_grade()` writes the grade only on the program row. `sync_page_graded_status()` then sets `submissions.status = 'graded'`, while `passed_test_cases`, `total_test_cases` and `graded_at` on the page row stay empty or hold an older grade.

**What goes wrong:** anything still reading the page row shows a wrong or missing score. That includes the list's fallback summary, and possibly the OCR export, which `268eb54` says still uses the Program 1 copy.

**Fix:** decide what the page row's grade columns mean now. Either mirror Program 1's grade onto them in `save_program_grade()`, like `verified_text` is mirrored, or document them as legacy and stop reading them.

### 5. Medium — cleared Program 2+ grades don't reach open pages

**Where:** `20260926000600_add_submission_programs.sql:178` (`invalidate_grades_for_question`).

When a question's test cases change, the trigger clears the grades of the programs linked to it. It only touches the `submissions` row if that page was `graded`. The web listens for realtime changes on `submissions` only.

**What goes wrong:** a page whose Program 1 is ungraded, but whose Program 2 was graded 3/4 against Q_B, keeps showing `Q2 3/4` after Q_B is edited, until a full reload.

**Fix:** in that function, touch every page with an affected program (for example, advance its `grading_revision`), so a realtime UPDATE always fires.

### 6. Medium — grading can use stale program rows

**Where:** `submissions-list.ts:1736` (`ensureFreshPrograms`).

The paper is removed from `staleProgramIds` before the re-read finishes. A Submit clicked while `prepareGradingStep()` is still re-reading skips the wait.

**What goes wrong:** the teacher saves tabs, clicks *Continue to grading*, and immediately clicks *Submit Code*. Either Judge0 runs everything and the save is refused ("Submission inputs changed during grading"), or, if the ids and revisions happen to still match, the wrong program is graded.

**Fix:** keep the in-flight re-read as a promise per paper and have `checkSubmission()` await it. Remove the paper from the set only after the re-read succeeds.

### 7. Low — `can_publish` isn't reset on the server

**Where:** `supabase/migrations/20260926000400_allow_question_updates.sql:24`.

The rule "send `can_publish: false` with any unvalidated edit" is only a comment and a TEAM_SYNC note, and no web code sends question updates yet. A client that forgets it leaves an edited question marked as validated, and the phone keeps offering it.

**Fix:** add a BEFORE UPDATE trigger on `questions` that sets `NEW.can_publish = false` when `model_answer`, `test_cases` or `question_type` change, unless the same update sets `can_publish` to true explicitly. Do it before Nikko enables the Edit button.

### 8. Low — OCR server accepts requests from any website (Nombrado's area)

**Where:** `ocr_feature/main.py:39`.

The `046b88c` merge restored Nombrado's `allow_origins=["*"]`, as they asked; the earlier localhost allowlist came from `876880c`. While the OCR server is running, any page the teacher visits could make it fetch arbitrary `image_url`s, including internal addresses (server-side request forgery), or keep it busy.

**Action:** not ours to change. Add a note under Needs from others asking Nombrado to restrict the origins (and ideally the allowed image hosts). This is already on the "Important security work" list in the overview.

### 9. Low — clearing a middle tab loses the later tabs' grades

**Where:** `submissions-list.ts:992` (`saveVerifiedText` → `answersToSave`) and `save_submission_programs`.

`answersToSave()` (Nombrado's helper) drops blank tabs before positions are numbered by array index. Clearing tab 2 moves tab 3's program to position 2. The row changes its question and code, the trigger wipes its grade, and the old position-3 row is deleted. The SQL comment that a blank entry "keeps its tab number" never applies.

**Fix:** match programs by `question_id`, which is unique per paper, instead of by position when upserting. Or send blank entries through instead of dropping them. Either way, correct the SQL comment.

---

## Docs accuracy

- **`2d31248`, TEAM_SYNC and the change note:** "Editing any program's code or question sends it back to `verified`" wasn't true for a question change on the Details step (#1). **True since `446b05c`.**
- **`2d31248`, change note:** "saves every program ... only while the page is still at `p_grading_revision`" suggested every program was protected. It wasn't (#2). **True since `446b05c`.**
- **`0b5d7c4` and `268eb54`:** no issues found.

## What was checked and looked fine

- The migrations `20260926000200` / `000300` / `000500`: permissions, policies, and the `RETAKE` rejection.
- The stale-grade triggers mirror the existing `submissions` design correctly for single-program pages.
- Row-level security and permissions on `submission_programs`: grade columns can't be set on insert.
- The copy step in `000600`, which was also checked on sample data before the cloud push.
- `refreshQuestions()` (`c893b85`) and the e2e fake backend changes.
- The merge resolutions in `046b88c`: `ocr_feature/` matches Nombrado's branch, and the save-conflict message is kept.

## Suggested order

1. ~~**#1 and #2.**~~ Fixed in `446b05c`.
2. **#3 and #6.** Small web fixes that prevent misleading results.
3. **#4 and #5.** Consistency of the page row and live updates.
4. **#7.** Before Nikko turns on question editing.
5. **#9.** Grade preservation.
6. **#8.** Request to Nombrado.
