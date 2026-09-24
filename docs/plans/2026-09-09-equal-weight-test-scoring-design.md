# Equal-Weight Test Scoring Design

## Status

Automatic scoring, display, and submission-grade persistence are implemented. Manual overrides and integration into a larger course-grade formula remain deferred until the adviser confirms the rubric.

## Agreed scoring behavior

Every test case has equal weight and contributes one raw point. A passed case contributes `1`; a failed, compilation-error, or runtime-error case contributes `0`. The automatic percentage is:

```text
(passed test cases / total test cases) * 100
```

The result panel displays both the fraction and percentage, for example `2/3 test cases passed — Score: 66.67%`. Percentages are rounded to at most two decimal places. Individual result cards show `1/1 point` for a pass and `0/1 point` for a failure.

The question-authoring form no longer exposes an editable Mark field. Test cases do not store a `mark` property; older records may still contain it, but the application ignores it. Automatic scoring derives one point directly from each passed test case.

Logic analysis remains visible as feedback only. It does not affect the numeric test-case score because a correct student solution may use a different valid algorithm than the Model Answer.

## Data flow

Student code is executed once per test case as before. Each `TestCaseResult.passed` value becomes a binary point. After every test case completes, the submissions workflow saves the result collection and its passed/total counts to Supabase. PostgreSQL generates the stored percentage from those counts, and reopening a submission restores the same per-test collection for display.

## Deferred decisions

- Whether the test-case percentage is the entire question grade or one component of a broader rubric.
- Whether teachers need a manual override after reviewing handwritten/OCR code.
- Whether logic feedback should remain visible to students or only to teachers.

These decisions are tracked in the accompanying adviser-review task.
