# Separate Logic Analysis Design

## Goal

Keep the complete Logic Analysis feature on `feature/logic-feature` and remove it from `judge0-integration`, while preserving Judge0 execution, expected-output comparison, and equal-weight test-case scoring on the current branch.

## Branch ownership

`feature/logic-feature` already points to the commit immediately before the logic cleanup and contains the parser, backend comparison endpoint, frontend request/state, and collapsible Logic Analysis panel. It remains unchanged as the feature branch.

`judge0-integration` removes the logic checker module and tests, the `/api/judge0/analyze-logic` endpoint, Angular service types and method, submission logic-analysis requests and state, component input/state, panel markup, and panel-only CSS. Submission grading continues to execute every test case and determine pass/fail from Judge0 status plus normalized output.

## Verification

Use test-first changes to prove the current branch no longer calls logic analysis and no longer exposes its component state or API route. Run the full Python and Angular suites, the Angular production build, a repository reference scan, and `git diff --check` before committing.
