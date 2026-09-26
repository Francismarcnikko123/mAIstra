# Manual Expected Output and Function Inputs Design

## Agreed behavior

Write a Function questions treat the Model Answer as function definitions and each Test Code field as the generated `main()` body. Function test values are declared and assigned in Test Code, which then calls the function and prints the result. Standard Input is not part of this question type. The authoring form hides it, execution sends an empty stdin string, and `scanf()` is rejected in both the function Model Answer and Test Code with an actionable field error. The existing checks for `#include` and `main()` remain. Checks continue to ignore comments and quoted strings.

Write a Program questions retain the current contract: the Model Answer contains `main()`, Standard Input remains visible, and programs may use `scanf()` when the exercise requires input. The system still supplies `<stdio.h>` and sends each test case's Standard Input to Judge0.

Expected Output is authored manually for both question types. Every test case requires a non-whitespace Expected Output before validation. A successful Judge0 run passes only when its normalized stdout matches the normalized manually entered expectation. Validation never replaces or edits Expected Output. The validation result continues to show Expected and Got so a teacher can diagnose a mismatch. Compile, runtime, empty-output, and request errors remain distinct failures, and Save remains available only after every current test case passes.

## Implementation approach

Extend the shared C structural checker with function-only `scanf()` detection. Reuse its existing comment/string masking so documentation and string literals do not cause false errors. Keep the source builder unchanged: function answers and Test Code are still wrapped in the generated `main()`, while programs retain their own `main()`.

In the question form, validate all required Expected Output fields before starting Judge0 requests. For function questions, always pass an empty stdin string. Change execution validation from "successful run with output" to "successful run with output matching the manual expectation," using the same whitespace- and case-tolerant normalization used by submission grading. Do not mutate the test-case expectation after execution. Update hints and visibility in the template to make these contracts explicit.

## Verification

Vitest coverage will prove that function `scanf()` is rejected without false positives, function execution ignores stored stdin, program execution still forwards stdin, empty expectations prevent execution, matching expectations pass, mismatches fail while showing Expected and Got, and validation never overwrites the teacher's value. Existing question-form, source utility, submission-list, and Judge0 component tests plus the Angular development build will be run after implementation.
