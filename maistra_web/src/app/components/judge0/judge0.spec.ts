import '@angular/compiler';
import {
  ChangeDetectorRef,
  Component,
  EventEmitter,
  Input,
  Output,
  SimpleChange,
} from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of, Subject, throwError } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { Judge0Service } from '../../services/judge0.service';
import { CodeEditorComponent } from '../code-editor/code-editor';
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

  it("shows the wrapper's reason when the sample could not be run", () => {
    const component = new Judge0(
      {
        runCCode: vi.fn().mockReturnValue(
          throwError(() => ({
            status: 504,
            error: {
              detail: 'Judge0 is busy and did not start the run in time. Try again.',
            },
          })),
        ),
      } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    component.executeCode();

    expect(component.displayedOutput).toBe(
      'Judge0 is busy and did not start the run in time. Try again.',
    );
    expect(component.displayedStatus).toBe('Execution failed');
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

    component.requestSubmit();
    component.isSubmitting = true;

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

  it('shows persisted test-case results when a graded submission is reopened', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    const persistedResults = [
      {
        caseNumber: 1,
        stdin: '2 3',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ];
    component.testCaseResults = persistedResults;

    component.ngOnChanges({
      testCaseResults: new SimpleChange(undefined, persistedResults, true),
    });

    expect(component.resultMode).toBe('submit');
    expect(component.shouldShowSubmitResults).toBe(true);
    expect(component.testCaseScoreSummary).toBe(
      '1/1 test cases passed — Score: 100%',
    );
  });

  it('keeps the sample run view when the same results are re-sent', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    const persistedResults = [
      {
        caseNumber: 1,
        stdin: '2 3',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ];
    component.testCaseResults = persistedResults;
    component.ngOnChanges({
      testCaseResults: new SimpleChange(undefined, persistedResults, true),
    });
    component.resultMode = 'run';

    // A realtime reload restores the same persisted grade as a new array.
    const reloadedResults = persistedResults.map((result) => ({ ...result }));
    component.testCaseResults = reloadedResults;
    component.ngOnChanges({
      testCaseResults: new SimpleChange(
        persistedResults,
        reloadedResults,
        false,
      ),
    });

    expect(component.resultMode).toBe('run');
  });

  it('switches to a regrade that arrives while a sample run is shown', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    const result = (caseNumber: number, passed: boolean) => ({
      caseNumber,
      stdin: '',
      expectedOutput: '5',
      actualOutput: passed ? '5' : '4',
      status: passed ? 'Accepted' : 'Wrong Answer',
      passed,
    });
    const earlierGrade = [result(1, true), result(2, true), result(3, false)];
    component.testCaseResults = earlierGrade;
    component.ngOnChanges({
      testCaseResults: new SimpleChange(undefined, earlierGrade, true),
    });
    component.resultMode = 'run';

    // Another teacher regrades: 2/3 becomes 3/3.
    const regrade = [result(1, true), result(2, true), result(3, true)];
    component.testCaseResults = regrade;
    component.ngOnChanges({
      testCaseResults: new SimpleChange(earlierGrade, regrade, false),
    });

    expect(component.resultMode).toBe('submit');
  });

  it('treats a reload with fields in database order as the same grade', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    const localGrade = [
      {
        caseNumber: 1,
        stdin: '2 3',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ];
    component.testCaseResults = localGrade;
    component.ngOnChanges({
      testCaseResults: new SimpleChange(undefined, localGrade, true),
    });
    component.resultMode = 'run';

    // jsonb stores object keys in its own order, so a reload differs in shape only.
    const reloadedGrade = [
      {
        stdin: '2 3',
        passed: true,
        status: 'Accepted',
        caseNumber: 1,
        actualOutput: '5',
        expectedOutput: '5',
      },
    ];
    component.testCaseResults = reloadedGrade;
    component.ngOnChanges({
      testCaseResults: new SimpleChange(localGrade, reloadedGrade, false),
    });

    expect(component.resultMode).toBe('run');
  });

  it('switches to the submit view when a new grade arrives', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.resultMode = 'run';
    const gradedResults = [
      {
        caseNumber: 1,
        stdin: '2 3',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ];
    component.testCaseResults = gradedResults;

    component.ngOnChanges({
      testCaseResults: new SimpleChange([], gradedResults, false),
    });

    expect(component.resultMode).toBe('submit');
  });

  it('does not start a sample run while full grading is active', () => {
    const runCCode = vi.fn();
    const component = new Judge0(
      { runCCode } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    component.isSubmitting = true;

    component.executeCode();

    expect(runCCode).not.toHaveBeenCalled();
    expect(component.isExecutionBusy).toBe(true);
  });

  it('does not request full grading while a sample run is active', () => {
    const component = new Judge0(
      {} as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    const emit = vi.spyOn(component.submitCode, 'emit');
    component.isRunning = true;

    component.requestSubmit();

    expect(emit).not.toHaveBeenCalled();
    expect(component.isExecutionBusy).toBe(true);
  });

  it('tells the parent when a sample run starts and when it ends', () => {
    const answer = new Subject<unknown>();
    const component = new Judge0(
      { runCCode: vi.fn().mockReturnValue(answer) } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    const running: boolean[] = [];
    component.runningChange.subscribe((value) => running.push(value));

    component.executeCode();
    expect(running).toEqual([true]);

    answer.next({ stdout: '5\n', status: { id: 3, description: 'Accepted' } });
    expect(running).toEqual([true, false]);
  });

  it('tells the parent the sample run ended when it fails', () => {
    const component = new Judge0(
      { runCCode: vi.fn().mockReturnValue(throwError(() => new Error('502'))) } as unknown as Judge0Service,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    );
    const running: boolean[] = [];
    component.runningChange.subscribe((value) => running.push(value));
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    component.executeCode();

    expect(running).toEqual([true, false]);
  });

  it('ignores the answer of a sample run whose grader was closed', () => {
    const answer = new Subject<unknown>();
    const detectChanges = vi.fn();
    const component = new Judge0(
      { runCCode: vi.fn().mockReturnValue(answer) } as unknown as Judge0Service,
      { detectChanges } as unknown as ChangeDetectorRef,
    );
    component.executeCode();
    detectChanges.mockClear();

    component.ngOnDestroy();
    answer.next({ stdout: '5\n', status: { id: 3, description: 'Accepted' } });

    expect(component.stdout).toBe('');
    expect(detectChanges).not.toHaveBeenCalled();
  });
});

// Ace needs a real browser, so the header tests render a plain stand-in editor.
@Component({ selector: 'app-code-editor', standalone: true, template: '' })
class FakeCodeEditor {
  @Input() value = '';
  @Input() readOnly = false;
  @Output() valueChange = new EventEmitter<string>();
}

function renderJudge0(inputs: Record<string, unknown> = {}) {
  TestBed.configureTestingModule({
    imports: [Judge0],
    providers: [{ provide: Judge0Service, useValue: {} }],
  });
  TestBed.overrideComponent(Judge0, {
    remove: { imports: [CodeEditorComponent] },
    add: { imports: [FakeCodeEditor] },
  });
  const fixture = TestBed.createComponent(Judge0);
  for (const [name, value] of Object.entries(inputs)) {
    fixture.componentRef.setInput(name, value);
  }
  fixture.detectChanges();
  const element = fixture.nativeElement as HTMLElement;
  return {
    fixture,
    title: () => element.querySelector('.runner-title')?.textContent?.trim(),
    hint: () => element.querySelector('.runner-hint')?.textContent?.trim(),
    editButton: () => element.querySelector<HTMLButtonElement>('.edit-code-link'),
  };
}

describe('Judge0 header', () => {
  it('keeps the Code Execution heading when the code can be edited here', () => {
    const view = renderJudge0();

    expect(view.title()).toBe('Code Execution');
    expect(view.hint()).toBeUndefined();
  });

  it('calls read-only code the saved code', () => {
    const view = renderJudge0({ codeReadOnly: true });

    expect(view.title()).toBe('Saved code');
    expect(view.hint()).toBe('Read-only');
  });

  it('hides Edit in Review code unless the parent opts in', () => {
    const view = renderJudge0({ codeReadOnly: true });

    expect(view.editButton()).toBeNull();
  });

  it('offers Edit in Review code when the parent opts in', () => {
    const view = renderJudge0({ codeReadOnly: true, canEditCode: true });

    expect(view.editButton()?.textContent?.trim()).toBe('Edit in Review code');
    expect(view.editButton()?.disabled).toBe(false);
  });

  it('never offers Edit in Review code for code that can be edited here', () => {
    const view = renderJudge0({ canEditCode: true });

    expect(view.editButton()).toBeNull();
  });

  it('asks the parent to open the code for editing', () => {
    const view = renderJudge0({ codeReadOnly: true, canEditCode: true });
    const editCode = vi.fn();
    view.fixture.componentInstance.editCode.subscribe(editCode);

    view.editButton()!.click();

    expect(editCode).toHaveBeenCalledTimes(1);
  });

  it('does not leave the grader while code is running or being graded', () => {
    const view = renderJudge0({ codeReadOnly: true, canEditCode: true, isSubmitting: true });
    const editCode = vi.fn();
    view.fixture.componentInstance.editCode.subscribe(editCode);

    expect(view.editButton()!.disabled).toBe(true);

    view.fixture.componentRef.setInput('isSubmitting', false);
    view.fixture.componentInstance.isRunning = true;
    view.fixture.componentInstance.requestEditCode();

    expect(editCode).not.toHaveBeenCalled();
  });
});
