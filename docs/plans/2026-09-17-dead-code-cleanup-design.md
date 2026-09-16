# Dead-Code Cleanup Design

## Scope

Remove the unused question-form runner state, legacy weighted-mark shape, unused grading response fields, unused Judge0 languages proxy, debug logging, duplicate schema snapshot, and broken README link. Consolidate output normalization and Judge0 execution without changing the visible equal-weight grading workflow.

## Design

`Judge0Service` becomes the only Angular gateway to the Judge0 API. The runner component calls `runCCode` instead of constructing its own HTTP request. A shared `normalizeOutput` utility replaces the three component-local copies. The backend grading endpoint becomes a narrowly named logic-analysis endpoint accepting only model and student source and returning only the logic score and checks that the UI consumes.

Test cases no longer carry `mark`; each result remains worth one point by array position. Existing JSON records may still contain legacy `mark` properties, which JavaScript safely ignores. The question validation database columns are removed through a forward migration, and seed data is updated to match. Supabase migrations remain the schema authority, so the duplicate root `cloud-schema.sql` is removed.

The stylesheet remains intact because no component-local selectors are proven dead. Its explicit Angular warning budget is aligned with its verified current size rather than deleting visual rules without browser evidence.

## Verification

Use red-green tests for the shared normalization utility, the service-only runner, the logic-analysis endpoint, and mark-free saved payloads. Finish with the full Judge0 and Angular suites, an Angular production build, SQL/reference searches, and a clean diff check.
