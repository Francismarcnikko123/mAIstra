import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface LogicCheck{
  name: string;
  passed: boolean;
  weight: number;
  score: number;
}
export interface GradingResult{
    final_score: number;
  compilation_score: number;
  logic_score: number;
  output_score: number;
  logic_details: LogicCheck[];
  output_details: {
    passed: boolean;
    score: number;
    expected_normalized: string;
    actual_normalized: string;
  };
}
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

@Injectable({
  providedIn: 'root',
})

export class Judge0Service {
  private apiUrl = 'http://127.0.0.1:8001/api/judge0';
  constructor(private http: HttpClient) {}

  runCCode(sourceCode: string, stdin = '') {
    return this.http.post<Judge0RunResult>('http://127.0.0.1:8001/api/judge0/run', {
      source_code: sourceCode,
      language_id: 50,
      stdin,
    });
  }
  
  gradeSubmission(payload: {
  model_code: string;
  student_code: string;
  expected_output: string;
  actual_output: string;
  compilation_passed: boolean;
}) {
  return this.http.post<GradingResult>(
    `${this.apiUrl}/grade-submission`,
    payload
  );
}
}