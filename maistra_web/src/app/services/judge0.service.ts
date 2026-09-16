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
        language_id: 50,
        stdin,
      },
    );
  }
}
