# Question validation design

The agreed rules are:

- Write a Function: Model Answer contains function definitions; Test Code contains statements that exercise them. Reject `#include` directives and `main()` in either editor. The execution wrapper supplies `<stdio.h>` and `main()`.
- Write a Program: Model Answer supplies `main()`. The execution wrapper supplies `<stdio.h>`, so programs work without a handwritten include. Existing complete programs with an explicit include remain usable.

## Findings

`QuestionFormComponent.validateModelAnswer()` currently marks every Judge0 status 3 result as passed and replaces expected output with stdout, including empty stdout. It puts function Test Code inside a generated main without checking whether the pasted code contains another main. The Ace editor provides syntax highlighting only. Function validation also discards Standard Input, although submission grading sends it.

## Approach

Use a small shared C source builder and structural checks before execution. This gives understandable errors for the agreed authoring rules while leaving general C syntax and runtime diagnostics to Judge0. Compiler-only validation cannot enforce question format. Automatically stripping headers or extracting a pasted main body would obscure mistakes and alter authored code.

Checks ignore comments and quoted strings, and account for continued lines. Model Answer and individual Test Code errors appear next to their editors as code changes and when Validate is clicked. Program answers must contain a main definition. Function test code and model answers must not be empty. At least one test case is required.

Both authoring and submission execution use the same source builder: a stdio include followed by the program, or stdio plus the function answer and a generated main containing Test Code. Standard Input is sent for both question types. Explicit program headers are preserved; repeated stdio includes are valid C.

Successful execution must produce non-whitespace stdout before a test can pass and update expected output. Empty output gets an actionable failure explaining that the test must print the result. This app grades using stdout; intentionally silent tests are outside this change. Preserve existing automatic expected-output generation for successful, nonempty runs. Show execution status and compiler/runtime diagnostics separately from stdout so errors cannot be hidden by partial output.

Each validation run uses an immutable input snapshot. Editing code/input, changing type, or adding/removing a case invalidates the run; late responses cannot restore a passed state or overwrite edited data. Saving requires a successful validation for the current execution inputs.

## Verification

Regression tests cover forbidden headers/main in each function editor, comments and strings, valid function tests, program source with and without explicit headers, missing main, empty test sets/code, no output, compiler/runtime/network errors, Standard Input, and edits during validation. Submission tests verify the same stdio wrapper is used for grading and run preview. Run focused Vitest suites and an Angular development build. Live Judge0 verification depends on the local service being available.
