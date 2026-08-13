import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SupabaseService } from '../../services/supabase';
import { SubmissionsListComponent } from './submissions-list';

describe('SubmissionsListComponent save feedback', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  function createComponent(
    updateSubmissionText: ReturnType<typeof vi.fn>,
    judge0Overrides: Partial<Judge0Service> = {},
  ) {
    const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
    const supabase = { updateSubmissionText } as unknown as SupabaseService;
    const component = new SubmissionsListComponent(
      supabase,
      {} as HttpClient,
      cdr,
      judge0Overrides as Judge0Service,
    );

    return { component, cdr };
  }

  function selectSubmission(component: SubmissionsListComponent, id: string) {
    component.selectedSubmission = {
      id,
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
    };
    component.editableText[id] = `text for ${id}`;
  }

  function deferred<T>() {
    let resolve!: (value: T | PromiseLike<T>) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((resolvePromise, rejectPromise) => {
      resolve = resolvePromise;
      reject = rejectPromise;
    });

    return { promise, resolve, reject };
  }

  it('keeps a second save confirmation visible for its full three seconds', async () => {
    vi.useFakeTimers();
    const { component } = createComponent(vi.fn().mockResolvedValue(undefined));

    selectSubmission(component, 'a');
    await component.saveVerifiedText();
    await vi.advanceTimersByTimeAsync(1000);

    await component.saveVerifiedText();
    await vi.advanceTimersByTimeAsync(2000);
    expect(component.saveStatus['a']).toBe('saved');

    await vi.advanceTimersByTimeAsync(1000);
    expect(component.saveStatus['a']).toBe('');
  });

  it('does not let an earlier timer clear a later save error', async () => {
    vi.useFakeTimers();
    const { component } = createComponent(
      vi
        .fn()
        .mockResolvedValueOnce(undefined)
        .mockRejectedValueOnce(new Error('database unavailable')),
    );
    const errorSpy = vi
      .spyOn(console, 'error')
      .mockImplementation(() => undefined);

    selectSubmission(component, 'a');
    await component.saveVerifiedText();
    await vi.advanceTimersByTimeAsync(1000);

    await component.saveVerifiedText();
    await vi.advanceTimersByTimeAsync(2000);
    expect(component.saveStatus['a']).toBe('error');
    expect(errorSpy).toHaveBeenCalled();
  });

  it('clears each submission status on its own three-second timer', async () => {
    vi.useFakeTimers();
    const { component } = createComponent(vi.fn().mockResolvedValue(undefined));

    selectSubmission(component, 'a');
    await component.saveVerifiedText();
    await vi.advanceTimersByTimeAsync(1000);

    selectSubmission(component, 'b');
    await component.saveVerifiedText();
    await vi.advanceTimersByTimeAsync(2000);
    expect(component.saveStatus['a']).toBe('');
    expect(component.saveStatus['b']).toBe('saved');

    await vi.advanceTimersByTimeAsync(1000);
    expect(component.saveStatus['b']).toBe('');
  });

  it('does not trigger change detection from a cleared timer after destruction', async () => {
    vi.useFakeTimers();
    const { component, cdr } = createComponent(
      vi.fn().mockResolvedValue(undefined),
    );

    selectSubmission(component, 'a');
    await component.saveVerifiedText();
    (cdr.detectChanges as ReturnType<typeof vi.fn>).mockClear();

    component.ngOnDestroy();
    await vi.advanceTimersByTimeAsync(3000);

    expect(cdr.detectChanges).not.toHaveBeenCalled();
  });

  it('ignores an older in-flight save after a newer save fails', async () => {
    vi.useFakeTimers();
    const firstSave = deferred<void>();
    const { component } = createComponent(
      vi
        .fn()
        .mockReturnValueOnce(firstSave.promise)
        .mockRejectedValueOnce(new Error('database unavailable')),
    );
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    selectSubmission(component, 'a');
    const olderSave = component.saveVerifiedText();
    const newerSave = component.saveVerifiedText();
    await newerSave;
    expect(component.saveStatus['a']).toBe('error');

    firstSave.resolve();
    await olderSave;
    await vi.advanceTimersByTimeAsync(3000);

    expect(component.saveStatus['a']).toBe('error');
  });

  it('ignores an in-flight save that resolves after component destruction', async () => {
    vi.useFakeTimers();
    const pendingSave = deferred<void>();
    const { component, cdr } = createComponent(
      vi.fn().mockReturnValue(pendingSave.promise),
    );

    selectSubmission(component, 'a');
    const save = component.saveVerifiedText();
    component.ngOnDestroy();
    pendingSave.resolve();
    await save;

    expect(component.saveStatus['a']).toBe('');
    expect(vi.getTimerCount()).toBe(0);
    expect(cdr.detectChanges).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(3000);
    expect(cdr.detectChanges).not.toHaveBeenCalled();
  });

  it('shows every test case result after grading a program submission', async () => {
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: '5\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const gradeSubmission = vi.fn().mockReturnValue(
      of({
        logic_details: [{ name: 'Has main', passed: true }],
        output_details: {
          passed: true,
          expected_normalized: '5',
          actual_normalized: '5',
        },
      }),
    );
    const { component } = createComponent(vi.fn(), {
      runCCode,
      gradeSubmission,
    } as Partial<Judge0Service>);
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
    };
    component.selectedSubmission = submission;
    component.editableText['submission-1'] =
      'int main(void) { int a, b; scanf("%d %d", &a, &b); printf("%d", a + b); }';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Addition',
        question_type: 'program',
        model_answer: 'int main(void) { return 0; }',
        test_cases: [
          {
            test_code: '',
            test_input: '2 3',
            expected_output: '5',
            mark: 2,
          },
          {
            test_code: '',
            test_input: '4 1',
            expected_output: '5',
            mark: 2,
          },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    await component.checkSubmission(submission);

    expect(runCCode).toHaveBeenCalledWith(
      component.editableText['submission-1'],
      '2 3',
    );
    expect(gradeSubmission).toHaveBeenCalledWith({
      model_code: 'int main(void) { return 0; }',
      student_code: component.editableText['submission-1'],
      expected_output: '5',
      actual_output: '5',
      compilation_passed: true,
    });
    expect(component.submissionRunOutput['submission-1']).toBe('5');
    expect(component.submissionCheckStatus['submission-1']).toBe('Accepted');
    expect(runCCode).toHaveBeenCalledTimes(2);
    expect(component.submissionTestResults['submission-1']).toEqual([
      {
        caseNumber: 1,
        stdin: '2 3',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
      {
        caseNumber: 2,
        stdin: '4 1',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ]);
  });

  it('checks the edited runner code instead of stale verified text', async () => {
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: '7\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const gradeSubmission = vi.fn().mockReturnValue(
      of({
        logic_details: [{ name: 'Has main', passed: true }],
        output_details: {
          passed: true,
          expected_normalized: '7',
          actual_normalized: '7',
        },
      }),
    );
    const { component } = createComponent(vi.fn(), {
      runCCode,
      gradeSubmission,
    } as Partial<Judge0Service>);
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      verified_text: 'stale code',
    };
    component.editableText['submission-1'] = 'stale code';
    component.updateSubmissionCode('submission-1', 'edited code');
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Edited code',
        question_type: 'program',
        model_answer: 'model code',
        test_cases: [
          {
            test_code: '',
            test_input: '',
            expected_output: '7',
            mark: 2,
          },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    await component.checkSubmission(submission);

    expect(runCCode).toHaveBeenCalledWith('edited code', '');
    expect(gradeSubmission).toHaveBeenCalledWith(
      expect.objectContaining({
        student_code: 'edited code',
      }),
    );
  });

  it('shows wrong answer when code runs but output does not match', async () => {
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: 'sum = 11\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const gradeSubmission = vi.fn().mockReturnValue(
      of({
        logic_details: [{ name: 'Has main', passed: true }],
        output_details: {
          passed: false,
          expected_normalized: 'ascending order:3 5 8',
          actual_normalized: 'sum = 11',
        },
      }),
    );
    const { component } = createComponent(vi.fn(), {
      runCCode,
      gradeSubmission,
    } as Partial<Judge0Service>);
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
    };
    component.selectedSubmission = submission;
    component.editableText['submission-1'] = 'int main(void) { return 0; }';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Ascending order',
        question_type: 'program',
        model_answer: 'int main(void) { return 0; }',
        test_cases: [
          {
            test_code: '',
            test_input: '8 3 5',
            expected_output: 'ascending order:3 5 8',
            mark: 2,
          },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    await component.checkSubmission(submission);

    expect(component.submissionTestResults['submission-1'][0]).toMatchObject({
      passed: false,
      status: 'Wrong Answer',
    });
    expect(component.submissionCheckStatus['submission-1']).toBe(
      'Wrong Answer',
    );
  });

  it('uses the selected question test case for runner values when a question is selected', () => {
    const { component } = createComponent(vi.fn());
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      questions: {
        id: 'stale-question',
        question_name: 'Old linked question',
        question_type: 'program' as const,
        model_answer: 'int main(void) { return 0; }',
        test_cases: [],
      },
    };
    component.editableText['submission-1'] = 'int main(void) { return 0; }';
    component.questions = [
      {
        id: 'selected-question',
        question_name: 'Sum',
        question_type: 'program',
        model_answer: 'int main(void) { return 0; }',
        test_cases: [
          {
            test_code: '',
            test_input: '2 3',
            expected_output: '5',
            mark: 2,
          },
        ],
      },
    ];
    component.selectedQuestionId = 'selected-question';

    expect(component.getExecutionStdin(submission)).toBe('2 3');
    expect(component.getExecutionExpectedOutput(submission)).toBe('5');
  });
});
