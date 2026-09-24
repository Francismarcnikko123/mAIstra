# Code review — 2026-09-24

> **Later status:** The fixes described here were committed on
> `feature/program-tabs` and brought into the pushed `feature/pre-extraction`
> branch. The 209/92 counts below are the review-day checkpoint; after
> pre-extraction, the recorded counts are OCR 231/231 and web 114/114.

**Scope:** `ocr_feature/` (OCR server, pipeline, cleanup) and the program tabs on `feature/program-tabs` (`maistra_web` submissions list, `supabase.ts`, code editor, `answers` migration).
**Method:** one high-effort review pass with eight angles:
- line-by-line
- removed behavior
- cross-file callers
- reuse
- simplification
- efficiency
- root cause
- conventions

**Result at review time:** 10 findings. All 10 were fixed the same day; the
uncommitted status at that point is superseded by the note above.

**Verification after the fixes:**
- OCR tests: 209/209 (207 before, plus 2 new).
- Web tests: 92/92 (89 before, plus 3 new; one test was rewritten for the new save behavior).
- The web app and test type checks pass, and `ng build` succeeds; the only warning is the old CSS budget one.
- **OCR accuracy is unchanged.** `evaluate_cer` gives clean_ws CER **0.099**, clean WER **0.328** and clean token accuracy **0.716**, the same as the recorded numbers.

---

## Findings and fixes

"Introduced" comes from `git blame` / `git log -S`.

| # | Where | Bug | Introduced | Fix | Test |
|---|---|---|---|---|---|
| 1 | `ocr_feature/core/c_code_cleanup.py` | The `"1f" → "if"` rule also matched float literals: `1.1f` → `1.if`, `b-1f` → `b-if`. It changed the student's graded code. | `3e36e5c`, 2026-07-24 (first cleanup commit) | Rules whose misread starts with a digit (`1f`, `1nt`, `1nclude`) only apply after whitespace, `{`, `}`, `;`, `(` or `,`. | `test_preserves_float_suffixes…`, `test_still_fixes_digit_misreads_at_statement_start` |
| 2 | `ocr_feature/main.py` `/extract-upload` | Saved to `uploads/<client filename>`, so a name like `../main.py` could overwrite server files. CORS allowed any site with credentials, and a missing filename crashed. | `dff7d35`, 2026-07-24 | Each request uses a temporary folder with a fixed file name. CORS no longer allows credentials. | Compile check + existing suite |
| 3 | `ocr_feature/main.py` `/extract-from-url` | `submission_id` went straight into the file path (`../../x` escaped the folder), and downloads had no size limit. | `dff7d35`, 2026-07-24 | Temporary folder with a fixed name. URL must be http(s). Download capped at 25 MB. | Compile check |
| 4 | `submissions-list.ts` `loadSubmissions()` | Every reload replaced `editableText` with the saved text. Reloads also run on every realtime INSERT, so a new paper from the phone wiped unsaved Program 1 edits in an open review. | Seeding line `f53be47`, 2026-07-27 (Nombrado); realtime reload `0133859`, 2026-08-18 (Jayrald). **Each was fine alone; the bug only exists when both are present.** | Seed `editableText` once per submission. | `does not overwrite unsaved Program 1 edits when the list reloads` |
| 5 | `ocr_feature/main.py` | `extract_from_upload` was `async def` but ran seconds of blocking OCR, freezing every other request. | `dff7d35`, 2026-07-24 | Plain `def`, so FastAPI runs it in its threadpool. | — |
| 6 | `ocr_feature/core/ocr_pipeline.py` | One shared PaddleOCR predictor was called from several threads with no lock. | Model setup, 2026-07-24 onward | `_ocr_lock` around every `ocr.predict`, with results materialized inside the lock. | Existing pipeline tests |
| 7 | `submissions-list.html` (tab editors) | `trackByIndex` reused a removed tab's Ace editor for the next tab, so Ctrl+Z could bring back the removed tab's code. | Program tabs, 2026-09-24 | `trackByAnswer`: each editor tracks its own tab object. | `gives each tab editor its own identity…` |
| 8 | `submissions-list.ts` `saveVerifiedText()` | After a save, the list row got the new `answers` but the open review (`selectedSubmission`) kept the old ones, which is exactly what Step 3 grading would read. | Program tabs, 2026-09-24 | Update `selectedSubmission.answers` too. | `keeps the open review in sync with the saved programs` |
| 9 | `ocr_feature/main.py` | Every student photo, preprocessed copy and debug JSON was kept forever in `uploads/` / `outputs/` (91 and 322 files at review time). | `dff7d35`, 2026-07-24 | The temporary folder is deleted after each request. The old files are still on disk; delete them by hand. | — |
| 10 | `submissions-list.ts` `saveVerifiedText()` | With the `answers` migration pending, any content in an extra tab blocked the whole save, including Program 1. | Program tabs fallback, 2026-09-24 | Program 1 saves, the extra tabs stay as a preview, and the message says "Program 1 was saved. Programs 2 and up can't be saved yet…". | Rewritten test `saves Program 1 and keeps extra programs as a preview…` |

**Deliberately not done:** the OCR server still downloads from any http(s) host. Limiting it to the Supabase storage host needs a per-machine setting (cloud vs local Supabase); add it if the server is ever reachable beyond this laptop.

---

## Why we keep finding bugs without touching the algorithms

None of the 10 were in the algorithms: reading order, layout, continuation, braces, formatting. That's not luck. Here's what the findings have in common.

### 1. The algorithms are the only part that's measured

Every change to reading order or recognition went through the 209-test suite and the CER evaluator, and we argued about each number. The code *around* the algorithms was never measured this way:
- the HTTP server
- file handling
- the cleanup table
- component state

Bugs survive where nothing checks.

### 2. Most of these bugs are from the first week

Six of the ten (#1, #2, #3, #5, #6, #9) were written on **2026-07-24** and a seventh (#4, the seeding half) on 2026-07-27. That was the prototype week, when the goal was "make extraction work end to end". The code worked, so nobody reopened it. Every later review (the 2026-07-28 review bugs, the 2026-08-25 audit, the OCR reviews) looked at accuracy, save races or reading order, not at the server edges.

### 3. The evaluator can't see some bugs, by design

The float bug (#1) changed graded code, yet **the CER is identical before and after the fix**. The 20-page test set simply has no `1.1f` in it. A metric only covers the inputs it's given. The cleanup tests had the same blind spot: they checked what each rule *fixes*, never what it must *leave alone*.

### 4. Assumptions that were true at the start stopped being true

| Assumption in July | What changed |
|---|---|
| Only the teacher's own browser calls the OCR server | CORS was open to every site; the server may be hosted later |
| One extraction at a time | Several teachers, and the planned auto-extract worker |
| The submissions list only reloads when the page opens | 2026-08-18: realtime reload on every new paper (#4) |
| Each submission's data has one copy | Program tabs keep `answers` in three places: the list row, the open review and the tab state (#8) |

Nobody wrote these assumptions down, so nothing flagged it when they stopped holding.

### 5. Two correct pieces of code can be wrong together

#4 is the clearest case. Seeding the editor on load (Nombrado, July) was correct. Reloading the list on every new paper (Jayrald, August) was correct. Together they wipe a teacher's edits. Neither author could have seen it from their own change. It only shows up in a review of the combined code.

### 6. New features walk through old code

The program tabs added new paths through old code: the missing-column save (#10), editor reuse (#7) and a second copy of `answers` (#8). They also made the old reload path matter more (#4). Every feature that touches shared code re-tests that code's assumptions.

### 7. Different review angles find different bugs

This review added security, concurrency, privacy and removed-behavior angles. Earlier reviews didn't use those, and those angles found #2, #3, #5, #6 and #9. More bugs found here doesn't mean more bugs were written recently. Most of them were already there.

**This is normal, and it's the process working.** All ten were found by review, not by a teacher, and every behavior fix now has a test that fails if it comes back.

---

## How to find fewer of these later

1. **Cleanup rules need "must not change" tests.** Every rule in `c_code_cleanup.py` gets at least one test for a context it must leave alone: float literals, identifiers, strings. This is the cheapest guard for graded content.
2. **Write down the OCR server's trust model** in `docs/ocr/`: who may call it, what inputs it accepts, where files go. Re-check it whenever the server moves (hosted, auto-extract worker).
3. **One source of truth per submission** in the web component. `PENDING_FIXES.md` item 5 (parallel state maps) is the root of #4 and #8. Do it before adding more tab features, and coordinate with Jayrald (shared file).
4. **Review every feature branch before merging**, including the security, concurrency and state angles, not only correctness. Also re-read the old code the feature touches.
5. **Widen the evaluation inputs.** The dataset diversity plan (structs, pointers, switch, arrays, and now float literals) also makes the evaluator see more kinds of mistakes.
6. **Re-run `evaluate_cer` after any change to OCR code**, even a "safe" one, as done here, and record the numbers.

---

## Status

- At review time the fixes were in the working tree. They were later committed
  on `feature/program-tabs` and included in pushed `feature/pre-extraction`.
  The original commit grouping was:
  1. OCR fixes: `c_code_cleanup.py`, `main.py`, `ocr_pipeline.py`, and the cleanup tests
  2. Web fixes: `submissions-list.*` and its spec
  3. Docs: `PROJECT_OVERVIEW_AND_CHANGES.md`
- Local docs updated:
  - `web/WEB_CODEBASE_GUIDE.md`
  - `ocr/CODEBASE_GUIDE.md` (dated note in the `main.py` section)
  - `ocr/README.md` (`uploads/` no longer written)
- Earlier review logs: `PENDING_FIXES.md` (items 1–6).
