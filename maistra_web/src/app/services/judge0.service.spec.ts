import '@angular/compiler';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { Judge0Service } from './judge0.service';

describe('Judge0Service', () => {
  it('does not let the browser choose the Judge0 language', () => {
    const post = vi.fn().mockReturnValue(of({}));
    const service = new Judge0Service({ post } as unknown as HttpClient);

    service.runCCode('int main(void) { return 0; }', '2 3');

    expect(post).toHaveBeenCalledWith('http://127.0.0.1:8001/api/judge0/run', {
      source_code: 'int main(void) { return 0; }',
      stdin: '2 3',
    });
  });

  it('sends multiple test cases in one batch request', () => {
    const post = vi.fn().mockReturnValue(of([]));
    const service = new Judge0Service({ post } as unknown as HttpClient);

    service.runCCodeBatch([
      { sourceCode: 'first source', stdin: 'first input' },
      { sourceCode: 'second source', stdin: '' },
    ]);

    expect(post).toHaveBeenCalledWith(
      'http://127.0.0.1:8001/api/judge0/run-batch',
      {
        runs: [
          { source_code: 'first source', stdin: 'first input' },
          { source_code: 'second source', stdin: '' },
        ],
      },
    );
  });

  it('asks the batch endpoint for per-run outcomes when settling', () => {
    const post = vi.fn().mockReturnValue(of([]));
    const service = new Judge0Service({ post } as unknown as HttpClient);

    service.runCCodeBatchSettled([{ sourceCode: 'only source' }]);

    expect(post).toHaveBeenCalledWith(
      'http://127.0.0.1:8001/api/judge0/run-batch',
      {
        runs: [{ source_code: 'only source', stdin: '' }],
        stop_on_error: false,
      },
    );
  });
});
