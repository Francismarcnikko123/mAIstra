import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

// The wrapper refuses a batch with more runs (MAX_BATCH_RUNS in
// judge0_api/main.py), and every test case is one run, so a question can have
// at most this many test cases.
export const MAX_TEST_CASES = 30;

/**
 * One finished run, as the wrapper (judge0_api/main.py) returns it.
 * Empty fields come back as null.
 */
export interface Judge0RunResult {
  // What the program printed with printf(). This is what grading compares.
  stdout?: string | null;
  // What the program printed to the error stream, e.g. on a crash.
  stderr?: string | null;
  // gcc's messages: errors when compiling failed, sometimes only warnings.
  compile_output?: string | null;
  // Extra detail from Judge0, e.g. why a run was stopped.
  message?: string | null;
  // Judge0's verdict. id 3 "Accepted" means it compiled and ran normally
  // (not that the output is right). 5 time limit, 6 compile error, 7-12
  // runtime error. The full list is in judge0_api/main.py.
  status?: {
    id?: number;
    description?: string;
  };
}

/** A run that could not be done at all (Judge0 down, timeout), in a settled batch. */
export interface Judge0RunError {
  error: {
    status_code: number;
    detail: string;
  };
}

export type Judge0BatchOutcome = Judge0RunResult | Judge0RunError;

/**
 * The wrapper's reason a run could not be done, e.g. "Judge0 is busy and did
 * not start the run in time. Try again.", or `fallback` when there is none.
 *
 * Works on a failed request (an HttpErrorResponse) and on a settled batch
 * run's { error }: both carry the reason in `error.detail`. The detail isn't
 * text when FastAPI rejects the request body itself (a list of problems), and
 * a wrapper that isn't running sends none.
 */
export function judge0ErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { error?: { detail?: unknown } } | null)?.error
    ?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

/** One program to run: the full C source and the text for scanf(). */
export interface Judge0BatchRun {
  sourceCode: string;
  stdin?: string;
}

/**
 * Sends C code to the Judge0 wrapper (judge0_api, port 8001) and returns the
 * results. The browser never calls Judge0 directly; the wrapper holds its
 * address and key.
 *
 * Callers pass the complete program. Build it with buildCQuestionSource()
 * from utils/c-question.ts, which adds #include and, for function questions,
 * the generated main().
 */
@Injectable({
  providedIn: 'root',
})
export class Judge0Service {
  private apiUrl = 'http://127.0.0.1:8001/api/judge0';

  constructor(private http: HttpClient) {}

  // One run. Used by "Run Sample" in the grader (Judge0 component).
  runCCode(sourceCode: string, stdin = '') {
    return this.http.post<Judge0RunResult>(
      `${this.apiUrl}/run`,
      {
        source_code: sourceCode,
        stdin,
      },
    );
  }

  // All-or-nothing: the first failed run fails the whole request. Use this
  // when every result is required, e.g. to persist a grade.
  // Used by "Submit Code" in Step 3 (SubmissionsListComponent.runTestCases).
  runCCodeBatch(runs: ReadonlyArray<Judge0BatchRun>) {
    return this.http.post<Judge0RunResult[]>(`${this.apiUrl}/run-batch`, {
      runs: this.toBatchRuns(runs),
    });
  }

  // Each run reports its own outcome; a failed run comes back as
  // { error: { status_code, detail } } in its slot instead of failing the rest.
  // Used by "Validate Test Cases" in the question form.
  runCCodeBatchSettled(runs: ReadonlyArray<Judge0BatchRun>) {
    return this.http.post<Judge0BatchOutcome[]>(`${this.apiUrl}/run-batch`, {
      runs: this.toBatchRuns(runs),
      stop_on_error: false,
    });
  }

  // camelCase here, snake_case in the Python wrapper's request body.
  private toBatchRuns(runs: ReadonlyArray<Judge0BatchRun>) {
    return runs.map(({ sourceCode, stdin = '' }) => ({
      source_code: sourceCode,
      stdin,
    }));
  }
}
