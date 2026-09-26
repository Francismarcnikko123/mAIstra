# Live test: renaming an older question keeps its grades (2026-09-27)

> **Owner:** Nikko. **Branch:** `judge0-integration` with the fix `a7fcf76` (web via `npm start`, phone app, OCR server and Judge0 wrapper running locally, Judge0 on the VM). Cloud database at `20260926001300`.

Checks Jayrald's review finding #1 (`docs/reviews/2026-09-27-teammates-changes-review.md`) on the real system after the fix. The same two cases are covered by Playwright tests against the fake backend; this run confirms them against the cloud.

## Setup

| # | Step | Result |
|---|---|---|
| 1 | Web: new section **E2E TEST**, Q1 "E2E rename test", program, 2 test cases (`2 3`→`5`, `10 -4`→`6`), validated and saved | question `c6c66f0c-a23e-4ed7-a444-54bda00e3cb1` |
| 2 | Supabase SQL Editor: added `"mark": 5` to both test cases, then `can_publish = true` again | now looks like the 20 older cloud questions |
| 3 | Phone: picked E2E TEST · Q1, captured one dataset page (PASS), submitted | submission `b2efc1f5-b00b-43f9-99ab-001427772bef` |
| 4 | Web: Extract (OCR read the page well), replaced the code with the sum program, Save, **Submit Code** | 2/2, score 100% |

## Results

Database read with the app's publishable key before and after each step.

| What | Before | After rename only | After adding a test case |
|---|---|---|---|
| Question name | E2E rename test | E2E rename test 2 | E2E rename test 2 |
| Test cases | 2, with `mark` | 2, **`mark` kept** | 3, without `mark` |
| `can_publish` | true | true | true |
| Warning on Save | – | **none** | "1 graded paper uses this question…" |
| Page `status` | graded | **graded** | verified |
| Program grade | 2/2, 100% | **2/2, 100%** | cleared |
| `graded_at` | 22:37:03 UTC | **unchanged** | NULL |
| `grading_revision` | 1 | **1** (trigger didn't run) | 2 |

- **Rename:** saved at once with no warning; grades untouched. Before the fix this rename cleared the grade silently.
- **Changed test case:** the warning appeared first; nothing was saved until **Save and clear grades**; then the grade was cleared and the question stayed validated.

## Not covered

- **#5** (retry after a failed "mark validated") needs the network to drop between two updates; covered by a unit test only.
- **#2** (two teachers editing the same question) is still open.

## Data left in the cloud

Section **E2E TEST**, question **E2E rename test 2** (3 test cases, validated) and one submission, now ungraded. Test data; delete when the team wants a clean start.
