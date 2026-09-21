import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { of, throwError } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { Judge0Service } from '../../services/judge0.service';
import { Judge0 } from './judge0';

describe('Judge0', () => {
  it('should create', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );

    expect(component).toBeTruthy();
  });

  it('does not expose Logic Analysis state on the execution branch', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );

    expect('logicAnalysisResults' in component).toBe(false);
    expect('logicAnalysisExpanded' in component).toBe(false);
    expect('toggleLogicAnalysis' in component).toBe(false);
  });

  it('runs the provided code with stdin and keeps terminal output values', () => {
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: '5\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const component = new Judge0(
      { runCCode } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.runCode = 'int main(void) { return 0; }';
    component.stdin = '2 3';
    component.expectedOutput = '5';

    component.executeCode();

    expect(runCCode).toHaveBeenCalledWith(
      'int main(void) { return 0; }',
      '2 3',
    );
    expect(component.stdout).toBe('5\n');
    expect(component.expectedOutput).toBe('5');
  });

  it('shows a notification and does not run code before a question is selected', () => {
    const runCCode = vi.fn();
    const component = new Judge0(
      { runCCode } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.requiresQuestion = true;
    component.hasQuestion = false;
    component.runCode = 'int main(void) { return 0; }';

    component.executeCode();

    expect(runCCode).not.toHaveBeenCalled();
    expect(component.runNotification).toBe(
      'Please select a question before running code.',
    );
  });

  it('shows a processing state instead of terminal results while code is running', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );

    component.isRunning = true;

    expect(component.shouldShowProcessingState).toBe(true);
    expect(component.shouldShowTerminalResults).toBe(false);
  });

  it('hides stale previous results while rerunning code', () => {
    const component = new Judge0(
      {} as Judge0Service,
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
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: '5\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const component = new Judge0(
      { runCCode } as unknown as Judge0Service,
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

  it('shows a new execution failure instead of a previously passed grade', () => {
    const runCCode = vi
      .fn()
      .mockReturnValue(throwError(() => new Error('network failure')));
    const component = new Judge0(
      { runCCode } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.submittedOutput = 'old passing output';
    component.submitStatus = 'Accepted';
    component.testCaseResults = [
      {
        caseNumber: 1,
        stdin: '',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ];

    component.executeCode();

    expect(component.resultMode).toBe('run');
    expect(component.displayedOutput).toBe('Failed to execute code.');
    expect(component.displayedStatus).toBe('Execution failed');
    expect(component.runResultTitle).toBe('');
    expect(component.hasErrorStatus).toBe(true);
  });

  it('shows a new successful run instead of a previously failed grade', () => {
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: 'new passing output',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const component = new Judge0(
      { runCCode } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.expectedOutput = 'new passing output';
    component.submittedOutput = 'old failing output';
    component.submitStatus = 'Wrong Answer';
    component.testCaseResults = [
      {
        caseNumber: 1,
        stdin: '',
        expectedOutput: '5',
        actualOutput: '4',
        status: 'Wrong Answer',
        passed: false,
      },
    ];

    component.executeCode();

    expect(component.resultMode).toBe('run');
    expect(component.displayedOutput).toBe('new passing output');
    expect(component.displayedStatus).toBe('Accepted');
    expect(component.firstTestCasePassedLabel).toBe('First Test Case Passed');
    expect(component.runResultTitle).toBe('Accepted');
  });

  it('hides the run result panel when submitting code', () => {
    const component = new Judge0(
      {} as Judge0Service,
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
      {} as Judge0Service,
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
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: '5\n',
        stderr: '',
        compile_output: '',
        status: { description: 'Accepted' },
      }),
    );
    const component = new Judge0(
      { runCCode } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.expectedOutput = '5';
    component.requestSubmit();

    component.executeCode();

    expect(component.shouldShowRunResultPanel).toBe(true);
  });

  it('does not show the terminal before run or submit results exist', () => {
    const component = new Judge0(
      {} as Judge0Service,
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
    component.resultMode = 'submit';
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
        {} as Judge0Service,
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
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );

    expect(component.testCaseScorePercentage).toBe(0);
    expect(component.testCaseScoreSummary).toBe('');
  });
});
