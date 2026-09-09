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
        status: { id: 3, description: 'Accepted' },
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

  it('shows a notification and does not run code before a question is selected', () => {
    const post = vi.fn();
    const component = new Judge0(
      { post } as unknown as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.requiresQuestion = true;
    component.hasQuestion = false;
    component.runCode = 'int main(void) { return 0; }';

    component.executeCode();

    expect(post).not.toHaveBeenCalled();
    expect(component.runNotification).toBe(
      'Please select a question before running code.',
    );
  });

  it('shows a processing state instead of terminal results while code is running', () => {
    const component = new Judge0(
      {} as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );

    component.isRunning = true;

    expect(component.shouldShowProcessingState).toBe(true);
    expect(component.shouldShowTerminalResults).toBe(false);
  });

  it('hides stale previous results while rerunning code', () => {
    const component = new Judge0(
      {} as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.resultMode = 'run';
    component.isRunning = true;
    component.testCaseResults = [
      {
        caseNumber: 1,
        stdin: '',
        expectedOutput: '15',
        actualOutput: '32767',
        status: 'Wrong Answer',
        passed: false,
      },
    ];

    expect(component.shouldShowProcessingState).toBe(true);
    expect(component.shouldShowTerminalResults).toBe(false);
    expect(component.shouldShowRunResultPanel).toBe(false);
  });

  it('shows the first test case status after running code', () => {
    const post = vi.fn().mockReturnValue(
      of({
        stdout: '5\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const component = new Judge0(
      { post } as unknown as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.runCode = 'int main(void) { return 0; }';
    component.expectedOutput = '5';

    component.executeCode();

    expect(component.firstTestCasePassedLabel).toBe('First Test Case Passed');
    expect(component.runResultTitle).toBe('Accepted');
    expect(component.runResultSummary).toBe('1/1 test case passed');
    expect(component.hasErrorStatus).toBe(false);
  });

  it('hides the run result panel when submitting code', () => {
    const component = new Judge0(
      {} as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.firstRunTestCasePassed = true;
    component.stdout = '5\n';

    expect(component.shouldShowRunResultPanel).toBe(true);

    component.requestSubmit();

    expect(component.shouldShowRunResultPanel).toBe(false);
  });

  it('does not show an empty result panel while submit is in progress', () => {
    const component = new Judge0(
      {} as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.stdout = '5\n';
    component.firstRunTestCasePassed = true;
    component.isSubmitting = true;

    component.requestSubmit();

    expect(component.shouldShowTerminalResults).toBe(false);
    expect(component.shouldShowSubmitResults).toBe(false);
  });

  it('shows the run result panel again after running code', () => {
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
    component.expectedOutput = '5';
    component.requestSubmit();

    component.executeCode();

    expect(component.shouldShowRunResultPanel).toBe(true);
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
    expect(component.shouldShowTerminalResults).toBe(false);

    component.isRunning = false;
    component.stdout = '5\n';
    expect(component.shouldShowTerminalResults).toBe(true);

    component.stdout = '';
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

  it.each([
    [[true, true, true], 100, '3/3 test cases passed — Score: 100%'],
    [[true, true, false], 66.67, '2/3 test cases passed — Score: 66.67%'],
    [[true, true, true, false], 75, '3/4 test cases passed — Score: 75%'],
  ])(
    'calculates an equal-weight score for %j results',
    (outcomes, expectedPercentage, expectedSummary) => {
      const component = new Judge0(
        {} as HttpClient,
        { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
      );
      component.testCaseResults = outcomes.map((passed, index) => ({
        caseNumber: index + 1,
        stdin: '',
        expectedOutput: String(index),
        actualOutput: passed ? String(index) : 'wrong',
        status: passed ? 'Accepted' : 'Wrong Answer',
        passed,
      }));

      expect(component.testCaseScorePercentage).toBe(expectedPercentage);
      expect(component.testCaseScoreSummary).toBe(expectedSummary);
      expect(
        component.testCaseResults.map((result) =>
          component.getTestCasePointLabel(result),
        ),
      ).toEqual(outcomes.map((passed) => (passed ? '1/1 point' : '0/1 point')));
    },
  );

  it('does not invent a score before test results exist', () => {
    const component = new Judge0(
      {} as HttpClient,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );

    expect(component.testCaseScorePercentage).toBe(0);
    expect(component.testCaseScoreSummary).toBe('');
  });
});
