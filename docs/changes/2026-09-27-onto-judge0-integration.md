# Nikko's work onto `judge0-integration`, Edit-screen validation fix, dead scanner removed (2026-09-27)

> **Owner:** Nikko. **Branch:** `feature/nikko-edit-and-batch`, made from `judge0-integration` (`1c9c716`) as Nombrado asked.

## What

1. **Merged** Nikko's local `feature/question-linking-v2` work (phone `batch_id` with safe retry, recrop auto-fix, question Edit screen, section-folder fixes, e2e tests, docs) into a branch made from the team branch `judge0-integration`. Nombrado's `saveStatusLabel()` (`a2d39a3`) was kept over Nikko's version of the same idea. Commit `fefbf9e`.
2. **Edit screen and Jayrald's reset trigger** (`20260926000800`, commit `719dac1`): an update that changes the model answer, test cases or type sets `can_publish = false` even if it sends `true`. The Edit screen now saves the content, then calls `markQuestionValidated()` (only `can_publish`) as a second update, as Jayrald asked. Without this, an edited and validated question would drop off the phone. The e2e fake backend mirrors the trigger. Commit `751bc7a`.
3. **Removed `maistra_mobile/packages/cunning_document_scanner/`** (45 files). It was replaced by `packages/edge_detection` and nothing referenced it (pubspec, `lib/`, `test/`, Android). Nombrado pointed it out. Older planning notes that mention it are kept as history.

## Answers recorded in TEAM_SYNC (Nikko → To do)

- Test only from `judge0-integration`: yes, this work is on a branch made from it.
- `batch_id`: done (with retry); `docs/` gitignore: answered; old `answers` lines: ticked.
- **Landscape two-page check** (`e9ac574`, never merged): **not in the current gate.** Planned: port it and calibrate the width/height ratio (1.3 was never calibrated) on real captures after the Chapter III numbers are final, so the measured gate doesn't change mid-thesis.

## Verification

- Web: `npx ng test` 322/322, both TypeScript checks, `npx ng build`; Playwright 15/15 (local Chrome, fresh dev server; a stale test server on port 4300 had served a mid-merge template and was stopped).
- Mobile: `flutter test` 60/60, `flutter analyze` 12 (unchanged) after removing the scanner package.
