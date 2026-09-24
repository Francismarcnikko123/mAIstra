import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface Judge0RunResult {
  stdout?: string;
  stderr?: string;
  compile_output?: string;
  message?: string;
  status?: {
    id?: number;
    description?: string;
  };
}

export interface Judge0RunError {
  error: {
    status_code: number;
    detail: string;
  };
}

export type Judge0BatchOutcome = Judge0RunResult | Judge0RunError;

export interface Judge0BatchRun {
  sourceCode: string;
  stdin?: string;
}

@Injectable({
  providedIn: 'root',
})
export class Judge0Service {
  private apiUrl = 'http://127.0.0.1:8001/api/judge0';

  constructor(private http: HttpClient) {}

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
  runCCodeBatch(runs: ReadonlyArray<Judge0BatchRun>) {
    return this.http.post<Judge0RunResult[]>(`${this.apiUrl}/run-batch`, {
      runs: this.toBatchRuns(runs),
    });
  }

  // Each run reports its own outcome; a failed run comes back as
  // { error: { status_code, detail } } in its slot instead of failing the rest.
  runCCodeBatchSettled(runs: ReadonlyArray<Judge0BatchRun>) {
    return this.http.post<Judge0BatchOutcome[]>(`${this.apiUrl}/run-batch`, {
      runs: this.toBatchRuns(runs),
      stop_on_error: false,
    });
  }

  private toBatchRuns(runs: ReadonlyArray<Judge0BatchRun>) {
    return runs.map(({ sourceCode, stdin = '' }) => ({
      source_code: sourceCode,
      stdin,
    }));
  }
}
