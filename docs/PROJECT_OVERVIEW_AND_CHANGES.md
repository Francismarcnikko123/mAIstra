# mAIstra Project Overview and Change Log

## Project purpose

mAIstra is a vision-based assessment system for handwritten C programming submissions. It captures student work, stores submission images, extracts C code through OCR, allows a teacher to verify the extracted code, executes it against question test cases with Judge0, and presents grading feedback.

## Main applications

### `maistra_mobile`

The Flutter mobile application captures handwritten submissions, performs a basic image-quality check, uploads images to Supabase Storage, and creates submission records.

### `maistra_web`

The Angular teacher application manages questions and submissions. Teachers can review uploaded images, run OCR, correct extracted code, select the related question, execute code, and inspect test-case and logic results.

### `ocr_feature`

The Python FastAPI OCR service downloads or accepts submission images, preprocesses them, runs PaddleOCR, cleans recognized C tokens conservatively, and returns review suggestions and confidence information.

### `judge0_api`

The Python FastAPI Judge0 wrapper submits C code to Judge0, polls for results, decodes output, and provides the grading endpoint consumed by the Angular application.

### `supabase`

This directory contains local Supabase configuration, schema migrations, seed data, and database exports. Supabase provides PostgreSQL storage, realtime submission notifications, and submission image storage.

## Submission review workflow

The Angular submission review uses one existing `SubmissionsListComponent`; no additional visual components were introduced.

1. **Details**
   - Assign a topic or folder.
   - Select the related question.
   - The question is required before continuing.
   - Topic and `question_id` are persisted together.

2. **Review code**
   - Display the original submission image beside the editor.
   - Extract code with the OCR service.
   - Preserve the original OCR result separately from teacher edits.
   - Allow manual correction and formatting.
   - Save verified code before grading.

3. **Run and grade**
   - Execute the verified code through the Judge0 wrapper.
   - For function questions, generate a temporary `main()` test harness.
   - Run all configured test cases.
   - Display output comparison and logic-analysis results.

## Submission interface changes

The submission interface was redesigned to make its workflow easier to discover and navigate:

- Added search by student, topic, or question.
- Added filters for Needs OCR, Needs review, Ready to grade, and Graded.
- Replaced image-only thumbnails with cards containing student, question, date, and status information.
- Replaced the overloaded review modal with a larger three-stage workspace.
- Added a visible step indicator and persistent navigation footer.
- Moved question selection into the Details stage.
- Made question selection mandatory before code review.
- Added immediate saving feedback and loading indicators.
- Kept later stages visible but disabled until their requirements are satisfied.
- Made the interface responsive for desktop, tablet, narrow panels, mobile, and short landscape screens.
- Corrected portrait-image sizing so previews use the available width without cropping or distortion.
- Made the Ace editor fill the complete review panel while retaining its default height elsewhere.

## State and reliability decisions

The following state is intentionally retained in `SubmissionsListComponent`:

- Save generations prevent an older request from overwriting the result of a newer save.
- Per-save timers prevent stale confirmation timers from clearing current errors or messages.
- Destruction guards prevent asynchronous callbacks from updating a destroyed component.
- Original OCR text remains separate from editable and verified text so teacher corrections do not overwrite the OCR baseline.
- Judge0 result maps keep execution results associated with the correct submission.
- Execution-source helpers remain responsible for building function-question test harnesses.
- Linked Supabase questions are accepted in either object or array form.

## Code cleanup completed

- Removed the unused Supabase realtime callback parameter.
- Replaced `questions: any[]` with a typed question collection.
- Replaced the untyped realtime subscription with its inferred Supabase return type.
- Renamed `saveTopic()` to `saveSubmissionDetails()` to match its actual behavior.
- Replaced deprecated Angular/RxJS `.toPromise()` usage with `firstValueFrom()`.
- Added a typed OCR response instead of using `any`.
- Made workflow status detection respect persisted `extracted`, `verified`, and `graded` statuses.
- Added a method-level guard so grading cannot be opened without both student code and a question.

## Submission tests

Focused tests now cover:

- Repeated saves and confirmation timer isolation.
- Out-of-order save completion.
- Component destruction during an active save.
- Multiple Judge0 test cases.
- Edited code taking precedence over stale verified code.
- Wrong-answer handling.
- Clearing execution results after a question change.
- Blocking Details when no question is selected.
- Saving topic and question assignment together.
- Linked questions returned as either an object or array.
- Requiring both code and a question before grading.
- Mapping persisted workflow statuses.
- Remaining in Review Code after an OCR failure.
- Advancing after a successful verified-code save.
- Remaining in Review Code after a failed save.

## Setup documentation

- `JUDGE0_UBUNTU_DOCKER_SETUP.md` explains how to deploy Judge0 CE on an Ubuntu VM with Docker, connect through SSH, configure cgroups, set `AUTHN_TOKEN` and `AUTHZ_TOKEN`, and connect mAIstra.
- `SUPABASE_LOCAL_SETUP.md` explains local Supabase development.
- `SUPABASE_CLOUD_LOCAL_SWITCHING.md` explains switching between local and hosted Supabase environments.

## Verification status

- Angular application TypeScript compilation passes.
- The focused submission-list test file passes isolated TypeScript validation.
- Angular template compilation passed after the submission workflow changes.
- Running Vitest from the current WSL environment is blocked because `node_modules` contains Windows-native Rollup/esbuild packages. Run `npm ci` and the tests in the same operating system environment, or run them directly from Windows where the dependencies were installed.
- Repository-wide spec type-checking currently also reports an unrelated missing Node `fs` type used by `question-form.spec.ts`.

## Important security work

Before deploying mAIstra beyond a trusted development environment:

- Rotate the Supabase `service_role` key currently exposed in Angular configuration and replace it with an anon or publishable key.
- Never place a Supabase service-role key in browser or mobile code.
- Add complete Row Level Security policies for questions, submissions, and storage objects.
- Restrict access to handwritten submission images or serve them with signed URLs.
- Authenticate and rate-limit the OCR and Judge0 wrapper APIs.
- Restrict the OCR URL downloader to trusted storage hosts and enforce download-size limits.
- Move hardcoded service URLs into Angular environment configuration.
- Add missing migrations for application columns such as `question_type`, `topic`, and `question_id`.

## Recommended next steps

1. Rotate the exposed Supabase service-role key and correct the frontend key.
2. Add and verify Supabase migrations and RLS policies.
3. Reinstall Angular dependencies on the operating system used for testing, then run the complete frontend suite.
4. Add authentication and rate limiting to the OCR and Judge0 wrapper services.
5. Move API endpoints and mobile Supabase configuration into environment-specific configuration.
