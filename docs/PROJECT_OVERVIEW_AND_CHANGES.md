# mAIstra Project Overview and Change Log

## Project purpose

mAIstra is a vision-based assessment system for handwritten C programming submissions. It captures student work, stores submission images, extracts C code through OCR, allows a teacher to verify the extracted code, executes it against question test cases with Judge0, and presents grading feedback.

## Main applications

### `maistra_mobile`

The Flutter mobile application captures handwritten submissions, performs a basic image-quality check, uploads images to Supabase Storage, and creates submission records.

### `maistra_web`

The Angular teacher application manages questions and submissions. Teachers can review uploaded images, run OCR, correct extracted code, select the related question, execute code, and inspect test-case results.

### `ocr_feature`

The Python FastAPI OCR service downloads or accepts submission images, preprocesses them, runs PaddleOCR, cleans recognized C tokens conservatively, and returns review suggestions and confidence information.

### `judge0_api`

The Python FastAPI Judge0 wrapper submits C code to Judge0, polls for results, and decodes execution output for the Angular application.

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
   - Display output comparison and equal-weight test-case results.

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
- Program submissions receive each test case's `test_input` as stdin during
  grading and the first-test run preview. Function questions use assigned
  values in Test Code and always execute with empty stdin.
- Linked Supabase questions are accepted in either object or array form.

The Judge0 wrapper now converts outbound Judge0 connectivity failures into a
clear HTTP `502` response that identifies the configured `JUDGE0_BASE_URL`,
instead of surfacing an internal FastAPI stack trace. This now also covers a
connectivity failure during the result-polling loop, not just the initial
submission request. `JUDGE0_BASE_URL` is validated at startup — the service
now fails fast with a clear error instead of silently building `None`-based
request URLs when the environment variable is missing.

## Judge0 output validation (model answer vs. submitted code)

The Judge0 wrapper compiles and runs code for question validation and student
grading. Expected Output is authored by the teacher and is never replaced by
Judge0 output:

- **Question authoring (`question-form`):** clicking "Validate Test Cases"
  requires a manually entered Expected Output, compiles and runs the model
  answer through Judge0, and compares the normalized actual and expected
  values. The result shows both Expected and Got for diagnosis. A mismatch
  fails validation without changing the teacher's entry.
- **Saving a question:** the Save button is now disabled until every test
  case has been validated and passed (`canPublish`), so a question can no
  longer be persisted with an unverified `expected_output`.
- **Grading (`submissions-list`):** the submitted code's Judge0 output is
  compared against the same teacher-authored `expected_output`.

**Compile status handling:** "compiled successfully" is now determined solely
by Judge0's own `status.id === 3` ("Accepted"), across the question-form
validator, submission grading, and the manual "Run" preview panel
(`judge0.ts`). Previously, any non-empty `stderr`/`compile_output` was also
treated as a failure, which incorrectly rejected code that compiled with only
warnings (e.g. calling `printf` without `#include <stdio.h>`) but still ran
and produced correct output. A real compile error (`status.id === 6`) or
runtime crash (`status.id` 7-12) still fails, as expected.

### Question format and manual-output validation (updated September 8, 2026)

- **Write a Function:** Model Answer and Test Code reject `#include`, `main()`, and `scanf()` before execution. Inline messages and editor borders explain what to remove. Comments and quoted text do not trigger these checks. Model Answer contains the functions; Test Code assigns fixed values, calls the functions, and prints results. Standard Input is hidden, ignored during validation and grading, and cleared when a function question is saved.
- **Write a Program:** Model Answer defines `main()`. The shared execution wrapper supplies `#include <stdio.h>` for question validation, model-run helpers, submission grading, and the submission run preview. Programs with their own explicit header still work. The program template contains only `main()`.
- Write a Program retains Standard Input and may use `scanf()` when required.
- Expected Output is required and entered manually for both question types. An accepted execution passes only when its normalized stdout matches that value. Empty stdout gets a **No output** failure, and a mismatch gets **Wrong Answer**; neither case changes Expected Output. Compiler warnings do not fail an otherwise successful run with matching output.
- Execution status, compiler details, stderr, and service messages are displayed separately from actual output.
- At least one test case is required. Code/input edits and test-case changes invalidate pending results, and Save verifies that the current inputs match the successful validation. A partially completed run cannot display “Passed all tests.”

Design and implementation notes are in [the validation design](plans/2026-09-06-question-validation-design.md) and [the implementation plan](plans/2026-09-06-question-validation.md).
The September 8 manual-output and function-input update is documented in [its design](plans/2026-09-08-manual-expected-output-function-inputs-design.md) and [implementation plan](plans/2026-09-08-manual-expected-output-function-inputs.md).

### Equal-weight test scoring prototype (September 9, 2026)

- Each passed test case earns one point and each failed case earns zero.
- The displayed score is `(passed test cases / total test cases) * 100`, rounded to at most two decimal places.
- Submission results show the passed fraction, percentage, and `1/1 point` or `0/1 point` for every case.
- The question form no longer exposes or stores test-case marks. Older records containing `mark` remain readable, but scoring ignores the property and awards one point per passed case.
- Logic Analysis is isolated on `feature/logic-feature`; this branch scores only Judge0 test-case results.
- This is intentionally a partial implementation: score persistence, teacher overrides, and any larger rubric formula are pending adviser approval.

The review questions are tracked in [the adviser-review task](plans/2026-09-09-adviser-review-equal-weight-scoring.md). The supporting rationale and implementation scope are in [the scoring design](plans/2026-09-09-equal-weight-test-scoring-design.md) and [implementation plan](plans/2026-09-09-equal-weight-test-scoring.md).

## C structural analysis

- The Tree-sitter checker, logic comparison endpoint, frontend request/state, and Logic Analysis panel are owned by `feature/logic-feature`.
- `judge0-integration` intentionally contains no structural-analysis implementation and uses Judge0 test cases as its only automatic correctness mechanism.
- Additional parser-based scoring should be developed and reviewed on the feature branch before integration.

## Code cleanup completed

- Removed the unused Supabase realtime callback parameter.
- Replaced `questions: any[]` with a typed question collection.
- Replaced the untyped realtime subscription with its inferred Supabase return type.
- Renamed `saveTopic()` to `saveSubmissionDetails()` to match its actual behavior.
- Replaced deprecated Angular/RxJS `.toPromise()` usage with `firstValueFrom()`.
- Added a typed OCR response instead of using `any`.
- Made workflow status detection respect persisted `extracted`, `verified`, and `graded` statuses.
- Added a method-level guard so grading cannot be opened without both student code and a question.
- Added timeout and exception handling to question saving so a stalled Supabase
  request no longer leaves the assignment form stuck in the saving state.
- Question saving no longer requests the inserted row back from Supabase, keeping
  the insert request lighter because the UI does not use the returned row.
- Added a visible assignment-saved confirmation before the submission review
  workflow advances from Details to Review code.

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
- Angular template compilation passed after the submission workflow changes, and after the Judge0 output-verification changes (`ng build --configuration development` succeeds).
- The earlier automatic Expected Output synchronization was verified live before being superseded by the September 8 manual-output workflow.
- The current `judge0_api` suite covers health/execution behavior and confirms the feature-only logic endpoint is unavailable on this branch.
- Running Vitest from the current WSL environment is blocked because `node_modules` contains Windows-native Rollup/esbuild packages. Run `npm ci` and the tests in the same operating system environment, or run them directly from Windows where the dependencies were installed.
- Question-validation follow-up (September 6): 71 focused Vitest tests pass across question-form, C structure checks, submissions-list, and Judge0 runner; `tsc --noEmit -p tsconfig.spec.json` and the Angular development build pass. Updated older fixtures to include real Judge0 status IDs and the test cases required by the existing submission workflow. Removed the redundant filesystem-based template string assertion; the changed UI was checked in the browser.
- Live browser/Judge0 checks confirmed immediate function-format errors, successful function output, successful programs both with and without an explicit stdio header using Standard Input, and an explicit No output failure with Save disabled. No test questions were saved to Supabase during verification.
- Manual-output and function-input update (September 8): 79 focused Vitest tests pass across question-form, C structure checks, submissions-list, and Judge0 runner; `tsc --noEmit -p tsconfig.spec.json` and the Angular development build pass. Live Judge0 verification was not run for this update.
- Equal-weight scoring prototype (September 9): all 85 frontend Vitest tests pass; `tsc --noEmit -p tsconfig.spec.json` and the Angular development build pass. Adviser approval and live Judge0 verification remain pending.

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
