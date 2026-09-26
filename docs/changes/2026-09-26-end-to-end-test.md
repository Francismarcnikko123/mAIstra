# End-to-end test of question linking against the live database (2026-09-26)

> **Owner:** Nikko. **Branch:** `feature/question-linking-v2` at `49038c1` (web via `ng serve`, phone via `flutter run`). Cloud database after Jayrald's schema work (`judge0-integration` `268eb54`) and his database-side fix.

First run of the whole flow on real devices and the shared cloud project. No code changed for this note.

## Steps and results

| # | Step | Result |
|---|---|---|
| 1 | Web → Question bank → **+ Create question**: new section **Basic**, Question No. **1**, *Write a Program* "Sum of Two Integers", model answer with `scanf`/`printf`, 3 test cases (`2 3`→`5`, `10 -4`→`6`, `0 0`→`0`) | **Validate Test Cases** passed all 3; **Save** unlocked and saved |
| 2 | Question bank | **Basic** card → **Q1** · Program · 3 tests · **✓ Validated** |
| 3 | Phone (M2101K6G, Android 13) → Choose a question | **BASIC → Q1 · Sum of Two Integers** listed |
| 4 | Capture one page | "Photo is good · Nothing needs changing", **Keep page**, review shows **1 Good** |
| 5 | **Submit answer** | "Answer submitted · Basic · Q1 · Sum of Two Integers · 1 page · Sat, Sep 26 · 11:24 PM" |
| 6 | Web → Submissions | **Basic** folder with the card `Sep 26 · 23:24` · `Basic · Q1 · Sum of Two Integers`, status **Needs OCR** |
| 7 | Web → Question bank → Q1 | "used by 1 paper", **1 paper** under "Papers linked to this question" with **✓ Photo good** |

## Database check (read-only, publishable key)

New `submissions` row `5df52242-3d0f-4c02-9efa-53bf968ee681`:

| Column | Value |
|---|---|
| `question_id` | `a0b89846-93cb-435a-bd52-ca125651edc0` (Basic · Q1) |
| `gate_result` | `PASS` |
| `batch_id` | `3471ce96-607d-45bd-8701-34c64db82e46` |
| `status` | `pending` |
| `extracted_text`, `verified_text` | NULL, as agreed with Nombrado |

`question_section_items`: `Basic` → number `1` → "Sum of Two Integers", `can_publish = true`.

## Not covered

- **Two pages in one submit** sharing one `batch_id`: this run had one page. Checked by unit tests; to confirm on a device next time.
- **OCR:** the paper stays *Needs OCR* because the OCR server wasn't running. Nombrado's area.
- **Editing the 22 older questions:** UPDATE on `questions` is live (Jayrald), but the Edit screen isn't built yet. The question page still says editing isn't available.

## Data left in the cloud

Section `Basic`, question "Sum of Two Integers" (Basic · Q1) and one test submission. They're real, usable records; delete only if the team wants a clean start.
