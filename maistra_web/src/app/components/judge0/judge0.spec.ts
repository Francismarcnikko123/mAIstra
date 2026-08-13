import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { Judge0 } from './judge0';

describe('Judge0', () => {
  it('should create', () => {
    const component = new Judge0(
      {} as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );

    expect(component).toBeTruthy();
  });

  it('runs the provided code with stdin and keeps terminal output values', () => {
    const post = vi.fn().mockReturnValue(
      of({
        stdout: '5\n',
        stderr: '',
        compile_output: '',
        status: { description: 'Accepted' },
      }),
    );
    const component = new Judge0(
      { post } as unknown as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.runCode = 'int main(void) { return 0; }';
    component.stdin = '2 3';
    component.expectedOutput = '5';

    component.executeCode();

    expect(post).toHaveBeenCalledWith('http://127.0.0.1:8001/api/judge0/run', {
      source_code: 'int main(void) { return 0; }',
      language_id: 50,
      stdin: '2 3',
    });
    expect(component.stdout).toBe('5\n');
    expect(component.expectedOutput).toBe('5');
  });

  it('does not show the terminal before run or submit results exist', () => {
    const component = new Judge0(
      {} as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.stdin = '2 3';
    component.expectedOutput = '5';

    expect(component.shouldShowTerminalResults).toBe(false);

    component.isRunning = true;
    expect(component.shouldShowTerminalResults).toBe(true);

    component.isRunning = false;
    component.testCaseResults = [
      {
        caseNumber: 1,
        stdin: '2 3',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ];
    expect(component.shouldShowTerminalResults).toBe(true);
  });
});
