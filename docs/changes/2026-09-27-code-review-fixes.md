# Code review of question linking, and the fixes (2026-09-26 → 27)

> **Owner:** Nikko. Review run on `feature/question-linking-v2` (mobile question linking, question bank, question form incl. edit mode, section folders, and the merge resolutions in `submissions-list.ts` / `supabase.ts`).
> **Commits:** `df06e0e` (mobile), `47851dc` (web).

## Findings and what happened

| # | Area | Finding | Result |
|---|---|---|---|
| 1 | Phone upload | A submit that failed halfway, then retried, uploaded every page again under a new `batch_id`: duplicate papers. | **Fixed.** One `UploadBatch` per answer (its `batch_id` + pages already saved) is kept across retries; only missing pages are sent. Saved pages can't be retaken or removed; the error says how many were sent. |
| 2 | Capture | If the quality check threw (e.g. corrupt photo), "Checking photo quality…" spun forever with both buttons disabled. | **Fixed.** The view is cleared and the student is asked to rescan. Retake/Recrop on the review screen handle errors the same way. |
| 3 | Create form | Question saved but its number was taken meanwhile → saving again inserted a duplicate question. | **Fixed.** The form switches to editing the question it just created. |
| 4 | Edit warning | The graded-papers count missed programs graded in `submission_programs` (Programs 2..n, partly graded pages), and returned 0 on errors, so grades could be cleared without a warning. | **Fixed.** Counts both tables; if the count can't be read, the form warns anyway. |
| 5 | Save label (merge) | "✓ All programs saved" while Programs 2..n had unsaved edits. | **Fixed.** Checks every program; in Nombrado's preview mode (extra programs can't be stored yet) it still says "✓ Program 1 saved". |
| 6 | Submissions list | Papers arriving live from the phone had no photo badge until a reload. | **Fixed.** The badge comes from the realtime event. |
| 7 | Folders | Re-linking a paper to an unsectioned question kept the old section name as topic → two folders with the same name. | **Fixed.** The old section name is dropped (topic becomes Uncategorized). |
| 8 | Recrop | A recropped page was only re-checked, never auto-fixed, so it could be uploaded as `FIXABLE` without the correction. | **Fixed** (Nikko's decision). Recrop now uses the same check → auto-fix → re-check as a scan. `quality_check.dart` / `quality_fix.dart` unchanged. |
| 9 | Program tabs (others' code) | Two teachers on the same paper: tabs are seeded once while the revision advances, so a later save can delete another teacher's Program 3 without a conflict. | **Passed on** to Jayrald (save RPC) and Nombrado (tab seeding) in TEAM_SYNC. |
| 10 | Performance | An extra full-table query per reload; the bank rebuilds its groups on every change detection; no `trackBy` on rows. | **Later.** Fine at the current size (~213 papers). |

## Clarification: auto-fix is re-checked (for the conceptual diagram)

The capture pipeline already re-checks an auto-fixed image once (`checkAndFixQuality()` in `quality_fix.dart`): **Quality Gate → FIXABLE → Auto-Fix → Quality Gate again**. If the re-check says RETAKE (the fix made it worse), the correction is thrown away and the original image and verdict are kept; otherwise the corrected image is kept with the re-check's verdict. It runs once on purpose, so repeated contrast stretching can't damage the handwriting. The conceptual diagram should show an arrow **Auto-Fix → Quality Gate (re-check)** before Batch Review. With fix 8, every path (scan, gallery, recrop) goes through this.

## Verification

- Mobile: `flutter test` 60/60 (2 new retry tests), `flutter analyze` 12 (unchanged), gate files unchanged.
- Web: `npx ng test` 314/314 (5 new), both TypeScript checks, `npx ng build`; Playwright 14/14 in local Chrome.
- Not covered by automated tests: fix 2 and 8 run inside the camera/edge-detection plugin; check on a device.
