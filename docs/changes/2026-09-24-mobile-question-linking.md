# Mobile: pick a question before capture (2026-09-24)

> **Owner:** Nikko. **Commit:** `24a40aa` on `feature/question-linking`.
> Spec: `IMPLEMENTATION_SPEC_question_linking.md` §5–§6, build steps 7–10.

## What

The phone now links every uploaded page to a question chosen **before** the camera opens.

| Screen | Behaviour |
|---|---|
| 1. Pick a question (new) | Lists validated, sectioned questions grouped by section and sorted by number. One choice; **Start capturing** stays disabled until something is picked. Empty state: "No questions ready … Ask your teacher to validate a question in the web dashboard." The last choice is not remembered. |
| 2. Capture | The question stays in the app bar (`Q2 · Sum of two numbers`). The gate verdict shows as icon + heading + one sentence built from the gate's own issue strings. **Keep page is disabled on RETAKE.** Running "N pages kept" counter; **Done — review pages**. |
| 3. Review pages | Tally by verdict. A RETAKE page gets a red border, its own message and its own **Retake / Remove** buttons. **Submit is disabled** while any page is RETAKE or there are no pages, with the reason inline. Recrop kept. |
| 4. Submitted (new) | Page count, question label, time, and "Your teacher reviews the extracted code before it is graded." **Capture another answer** starts a fresh picker. |

Uploads insert `image_url`, `question_id`, `gate_result` (`PASS` / `FIXABLE` / `RETAKE`) and `status: 'pending'`. A page the gate auto-corrected is stored as `FIXABLE`. RETAKE pages can't be uploaded.

Theme: Material 3, brand red, slate surfaces, verdict colours always paired with an icon and text, dark mode supported.

## Why

Papers used to arrive with no question, and the teacher had to link each one by hand. The quality gate's verdict was thrown away.

## Files

- New: `lib/screens/question_picker_screen.dart`, `lib/screens/submitted_screen.dart`, `lib/models/question_choice.dart`, `lib/services/question_repository.dart`, `lib/services/submission_uploader.dart`, `lib/utils/page_capture.dart`, `lib/utils/verdict.dart`, `lib/widgets/verdict_view.dart`, `lib/theme/app_theme.dart`
- Changed: `lib/main.dart`, `lib/models/captured_page.dart`, `lib/screens/capture_screen.dart`, `lib/screens/batch_review_screen.dart`
- Tests: `test/question_choice_test.dart`, `test/verdict_test.dart`, `test/screens_test.dart`
- **Unchanged:** `lib/utils/quality_check.dart`, `lib/utils/quality_fix.dart`, `packages/edge_detection/` (the measured quality gate).

## Affects

- **Jayrald:** needs `submissions.gate_result` + INSERT grant, and `questions.can_publish`, before uploads and the picker work against the live database.
- **Nombrado:** the phone links Program 1 only; Programs 2+ stay on the web's program tabs.

## Verification

- `flutter test`: 53/53 (36 existing quality-gate tests + 17 new).
- `flutter analyze`: 12 issues, down from 14 before the branch; none in new code.
- Installed on a phone (M2101K6G, Android 13): launches to "Could not load questions", as expected while the tables are missing.
- **Tested end to end on 2026-09-26** against the live database: see [the test note](2026-09-26-end-to-end-test.md).

## Open

- *Resolved 2026-09-26:* pages of one answer share `submissions.batch_id` ([note](2026-09-26-mobile-batch-id.md)). Showing "2 pages" on the web is a later step.
