import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, from, of, Subject, throwError } from 'rxjs';
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
    updateSubmissionGrade: ReturnType<typeof vi.fn> = vi
      .fn()
      .mockResolvedValue(1),
  ) {
    const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
    const supabase = {
      updateSubmissionText,
      updateSubmissionGrade,
    } as unknown as SupabaseService;
    const judge0 = { ...judge0Overrides } as Partial<Judge0Service>;
    if (!judge0.runCCodeBatch && judge0.runCCode) {
      judge0.runCCodeBatch = (runs) =>
        from(
          Promise.all(
            runs.map(({ sourceCode, stdin = '' }) =>
              firstValueFrom(judge0.runCCode!(sourceCode, stdin)),
            ),
          ),
        );
    }
    const component = new SubmissionsListComponent(
      supabase,
      {} as HttpClient,
      cdr,
      judge0 as Judge0Service,
    );

    return { component, cdr, updateSubmissionGrade };
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

  function createWorkflowComponent(options?: {
    updateSubmissionDetails?: ReturnType<typeof vi.fn>;
    updateSubmissionText?: ReturnType<typeof vi.fn>;
    post?: ReturnType<typeof vi.fn>;
    updateSubmissionGrade?: ReturnType<typeof vi.fn>;
    getSubmissions?: ReturnType<typeof vi.fn>;
    getQuestions?: ReturnType<typeof vi.fn>;
    subscribeToSubmissions?: ReturnType<typeof vi.fn>;
  }) {
    const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
    const updateSubmissionDetails =
      options?.updateSubmissionDetails ?? vi.fn().mockResolvedValue(undefined);
    const updateSubmissionText =
      options?.updateSubmissionText ?? vi.fn().mockResolvedValue(undefined);
    const post =
      options?.post ??
      vi.fn().mockReturnValue(of({ cleaned_text: 'int main() {}' }));
    const updateSubmissionGrade =
      options?.updateSubmissionGrade ?? vi.fn().mockResolvedValue(1);
    const getSubmissions =
      options?.getSubmissions ?? vi.fn().mockResolvedValue({ data: [], error: null });
    const getQuestions =
      options?.getQuestions ?? vi.fn().mockResolvedValue({ data: [], error: null });
    const subscribeToSubmissions =
      options?.subscribeToSubmissions ??
      vi.fn().mockReturnValue({ unsubscribe: vi.fn() });
    const supabase = {
      updateSubmissionDetails,
      updateSubmissionText,
      updateSubmissionGrade,
      getSubmissions,
      getQuestions,
      subscribeToSubmissions,
    } as unknown as SupabaseService;
    const http = { post } as unknown as HttpClient;
    const component = new SubmissionsListComponent(
      supabase,
      http,
      cdr,
      {} as Judge0Service,
    );

    return {
      component,
      cdr,
      post,
      updateSubmissionDetails,
      updateSubmissionText,
      updateSubmissionGrade,
      getSubmissions,
      getQuestions,
      subscribeToSubmissions,
    };
  }

  it('subscribes before initial loading and reconciles an event with the final snapshot', async () => {
    const questions = deferred<{ data: unknown[]; error: null }>();
    const eventReload = deferred<{ data: unknown[]; error: null }>();
    const finalSnapshot = deferred<{ data: unknown[]; error: null }>();
    const getSubmissions = vi
      .fn()
      .mockReturnValueOnce(eventReload.promise)
      .mockReturnValueOnce(finalSnapshot.promise);
    const subscription = { unsubscribe: vi.fn() };
    let realtimeCallback: (() => void) | undefined;
    const subscribeToSubmissions = vi.fn().mockImplementation((callback) => {
      realtimeCallback = callback;
      return subscription;
    });
    const { component } = createWorkflowComponent({
      getQuestions: vi.fn().mockReturnValue(questions.promise),
      getSubmissions,
      subscribeToSubmissions,
    });

    const initialization = component.ngOnInit();

    expect(realtimeCallback).toBeTypeOf('function');
    realtimeCallback!();
    expect(getSubmissions).toHaveBeenCalledTimes(1);

    eventReload.resolve({
      data: [
        {
          id: 'submission-from-event',
          image_url: 'https://example.test/event.png',
          captured_at: '2026-09-22T00:00:00.000Z',
        },
      ],
      error: null,
    });
    await eventReload.promise;
    questions.resolve({ data: [], error: null });
    await questions.promise;
    await vi.waitFor(() => expect(getSubmissions).toHaveBeenCalledTimes(2));
    finalSnapshot.resolve({
      data: [
        {
          id: 'submission-from-snapshot',
          image_url: 'https://example.test/snapshot.png',
          captured_at: '2026-09-22T00:01:00.000Z',
        },
      ],
      error: null,
    });

    await initialization;

    expect(component.submissions.map((submission) => submission.id)).toEqual([
      'submission-from-snapshot',
    ]);
    component.ngOnDestroy();
    expect(subscription.unsubscribe).toHaveBeenCalledOnce();
  });

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
    const analyzeLogic = vi.fn().mockReturnValue(
      of({
        logic_details: [
          { name: 'Has main', passed: true, weight: 1, score: 1 },
        ],
      }),
    );
    const updateSubmissionGrade = vi.fn().mockResolvedValue(8);
    const { component } = createComponent(
      vi.fn(),
      {
        runCCode,
        analyzeLogic,
      } as unknown as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      question_id: 'question-1',
      grading_revision: 7,
    };
    component.submissions = [{ ...submission }];
    component.selectedSubmission = submission;
    component.editableText['submission-1'] =
      'int main(void) { int a, b; scanf("%d %d", &a, &b); printf("%d", a + b); }';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Addition',
        question_type: 'program',
        test_cases: [
          {
            test_code: '',
            test_input: '2 3',
            expected_output: '5',
          },
          {
            test_code: '',
            test_input: '4 1',
            expected_output: '5',
          },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    await component.checkSubmission(submission);

    expect(runCCode).toHaveBeenCalledWith(
      '#include <stdio.h>\n\n' + component.editableText['submission-1'],
      '2 3',
    );
    expect(analyzeLogic).not.toHaveBeenCalled();
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
    expect(updateSubmissionGrade).toHaveBeenCalledWith(
      'submission-1',
      component.submissionTestResults['submission-1'],
      7,
      'question-1',
    );
    expect(component.selectedSubmission?.grading_revision).toBe(8);
    expect(component.submissions[0].grading_revision).toBe(8);
  });

  it('grades every test case with one batch request', async () => {
    const runCCode = vi.fn();
    const runCCodeBatch = vi.fn().mockReturnValue(
      of([
        { stdout: '5', status: { id: 3, description: 'Accepted' } },
        { stdout: '7', status: { id: 3, description: 'Accepted' } },
      ]),
    );
    const updateSubmissionGrade = vi.fn().mockResolvedValue(1);
    const { component } = createComponent(
      vi.fn(),
      { runCCode, runCCodeBatch } as unknown as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
    const submission = {
      id: 'submission-batch',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-09-22T00:00:00.000Z',
      question_id: 'question-1',
      verified_text: 'int main(void) { return 0; }',
      grading_revision: 0,
    };
    component.submissions = [{ ...submission }];
    component.selectedSubmission = submission;
    component.editableText[submission.id] = submission.verified_text;
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Batch grading',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '2 3', expected_output: '5' },
          { test_code: '', test_input: '3 4', expected_output: '7' },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    await component.checkSubmission(submission);

    expect(runCCodeBatch).toHaveBeenCalledOnce();
    expect(runCCode).not.toHaveBeenCalled();
    expect(updateSubmissionGrade).toHaveBeenCalledOnce();
  });

  it('does not publish a completed grade when persistence fails', async () => {
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: '5\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const updateSubmissionGrade = vi
      .fn()
      .mockRejectedValue(new Error('database unavailable'));
    const { component } = createComponent(
      vi.fn(),
      { runCCode } as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      status: 'verified',
    };
    component.selectedSubmission = submission;
    component.editableText['submission-1'] = 'int main(void) { return 0; }';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Addition',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '2 3', expected_output: '5' },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    await component.checkSubmission(submission);

    expect(component.submissionTestResults['submission-1']).toEqual([]);
    expect(component.submissionCheckStatus['submission-1']).toBe('Error');
    expect(component.checkError).toBe(
      'Test cases completed, but the grade could not be saved.',
    );
    expect(submission.status).toBe('verified');
  });

  it('refuses to grade an unsaved question change without calling Judge0', async () => {
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: '5\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const updateSubmissionGrade = vi.fn().mockResolvedValue(1);
    const { component } = createComponent(
      vi.fn(),
      { runCCode } as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
    // Persisted assignment is question-1 (this is what lives in the list).
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      question_id: 'question-1',
      grading_revision: 0,
    };
    component.submissions = [{ ...submission }];
    component.selectedSubmission = submission;
    component.editableText['submission-1'] = 'int main(void) { return 0; }';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'First',
        question_type: 'program',
        test_cases: [{ test_code: '', test_input: '2 3', expected_output: '5' }],
      },
      {
        id: 'question-2',
        question_name: 'Second',
        question_type: 'program',
        test_cases: [{ test_code: '', test_input: '4 1', expected_output: '5' }],
      },
    ];
    // Teacher switches the dropdown to question-2 but never saves it, so the
    // list (persisted state) still holds question-1.
    component.onSelectedQuestionChange('question-2');

    await component.checkSubmission(submission);

    expect(runCCode).not.toHaveBeenCalled();
    expect(updateSubmissionGrade).not.toHaveBeenCalled();
    expect(component.checkError).toBe(
      'Save the selected question before grading.',
    );
  });

  it('refuses to grade unsaved code without calling Judge0', async () => {
    const runCCode = vi.fn().mockReturnValue(
      of({
        stdout: '7\n',
        stderr: '',
        compile_output: '',
        status: { id: 3, description: 'Accepted' },
      }),
    );
    const updateSubmissionGrade = vi.fn().mockResolvedValue(1);
    const { component } = createComponent(
      vi.fn(),
      { runCCode } as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
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
        test_cases: [
          {
            test_code: '',
            test_input: '',
            expected_output: '7',
          },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    await component.checkSubmission(submission);

    expect(runCCode).not.toHaveBeenCalled();
    expect(updateSubmissionGrade).not.toHaveBeenCalled();
    expect(component.checkError).toBe('Save the edited code before grading.');
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
    const { component } = createComponent(vi.fn(), {
      runCCode,
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
        test_cases: [
          {
            test_code: '',
            test_input: '8 3 5',
            expected_output: 'ascending order:3 5 8',
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
        test_cases: [],
      },
    };
    component.editableText['submission-1'] = 'int main(void) { return 0; }';
    component.questions = [
      {
        id: 'selected-question',
        question_name: 'Sum',
        question_type: 'program',
        test_cases: [
          {
            test_code: '',
            test_input: '2 3',
            expected_output: '5',
          },
        ],
      },
    ];
    component.selectedQuestionId = 'selected-question';

    expect(component.getExecutionStdin(submission)).toBe('2 3');
    expect(component.getExecutionExpectedOutput(submission)).toBe('5');
    expect(component.getExecutionSourceCode(submission)).toBe(
      '#include <stdio.h>\n\nint main(void) { return 0; }',
    );
  });

  it('uses the same function wrapper for grading and runner preview', async () => {
    const runCCode = vi
      .fn()
      .mockReturnValue(of({ stdout: '5', status: { id: 3 } }));
    const { component } = createComponent(vi.fn(), {
      runCCode,
    });
    selectSubmission(component, 'function-1');
    component.editableText['function-1'] =
      'int add(int a, int b) { return a + b; }';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Addition',
        question_type: 'function',
        test_cases: [
          {
            test_code: 'printf("%d", add(2, 3));',
            test_input: '2 3',
            expected_output: '5',
          },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';
    const source = component.getExecutionSourceCode(
      component.selectedSubmission,
    );
    expect(component.getExecutionStdin(component.selectedSubmission)).toBe('');
    await component.checkSubmission(component.selectedSubmission);
    expect(runCCode).toHaveBeenCalledWith(source, '');
    expect(source).toContain('#include <stdio.h>');
    expect(source.match(/\bmain\s*\(/g)).toHaveLength(1);
    expect(source).toContain('printf("%d", add(2, 3));');
  });

  it('clears stale execution results when the selected question changes', () => {
    const { component } = createComponent(vi.fn());
    component.selectedSubmission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
    };
    component.submissionRunOutput['submission-1'] = 'sum= 32765';
    component.submissionCheckStatus['submission-1'] = 'Wrong Answer';
    component.submissionTestResults['submission-1'] = [
      {
        caseNumber: 1,
        stdin: '5 3',
        expectedOutput: 'sum: 8',
        actualOutput: 'sum= 32765',
        status: 'Wrong Answer',
        passed: false,
      },
    ];
    component.onSelectedQuestionChange('question-2');

    expect(component.selectedQuestionId).toBe('question-2');
    expect(component.submissionRunOutput['submission-1']).toBe('');
    expect(component.submissionCheckStatus['submission-1']).toBe('');
    expect(component.submissionTestResults['submission-1']).toEqual([]);
  });

  it('discards an in-progress grade when the selected question changes', async () => {
    const pendingRun = new Subject<{
      stdout: string;
      status: { id: number; description: string };
    }>();
    const runCCode = vi.fn().mockReturnValue(pendingRun);
    const updateSubmissionGrade = vi.fn().mockResolvedValue(1);
    const { component } = createComponent(
      vi.fn(),
      { runCCode } as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      question_id: 'question-1',
      grading_revision: 0,
    };
    component.selectedSubmission = submission;
    component.editableText['submission-1'] = 'int main(void) { return 0; }';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'First question',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '', expected_output: '5' },
        ],
      },
      {
        id: 'question-2',
        question_name: 'Second question',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '', expected_output: '7' },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    const grading = component.checkSubmission(submission);
    component.onSelectedQuestionChange('question-2');
    pendingRun.next({
      stdout: '5',
      status: { id: 3, description: 'Accepted' },
    });
    pendingRun.complete();
    await grading;

    expect(updateSubmissionGrade).not.toHaveBeenCalled();
    expect(component.submissionTestResults['submission-1']).toEqual([]);
    expect(component.submissionCheckStatus['submission-1']).toBe('');
    expect(component.isChecking).toBe(false);
  });

  it('discards an in-progress grade when the runner code changes', async () => {
    const pendingRun = new Subject<{
      stdout: string;
      status: { id: number; description: string };
    }>();
    const runCCode = vi.fn().mockReturnValue(pendingRun);
    const updateSubmissionGrade = vi.fn().mockResolvedValue(1);
    const { component } = createComponent(
      vi.fn(),
      { runCCode } as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      question_id: 'question-1',
      grading_revision: 0,
    };
    component.selectedSubmission = submission;
    component.editableText['submission-1'] = 'old code';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'First question',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '', expected_output: '5' },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    const grading = component.checkSubmission(submission);
    component.updateSubmissionCode('submission-1', 'new code');
    pendingRun.next({
      stdout: '5',
      status: { id: 3, description: 'Accepted' },
    });
    pendingRun.complete();
    await grading;

    expect(updateSubmissionGrade).not.toHaveBeenCalled();
    expect(component.submissionTestResults['submission-1']).toEqual([]);
    expect(component.isChecking).toBe(false);
  });

  it('discards an in-progress grade when the modal closes', async () => {
    const pendingRun = new Subject<{
      stdout: string;
      status: { id: number; description: string };
    }>();
    const runCCode = vi.fn().mockReturnValue(pendingRun);
    const updateSubmissionGrade = vi.fn().mockResolvedValue(1);
    const { component } = createComponent(
      vi.fn(),
      { runCCode } as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      question_id: 'question-1',
      grading_revision: 0,
    };
    component.selectedSubmission = submission;
    component.editableText['submission-1'] = 'code';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'First question',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '', expected_output: '5' },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    const grading = component.checkSubmission(submission);
    component.closeModal();
    pendingRun.next({
      stdout: '5',
      status: { id: 3, description: 'Accepted' },
    });
    pendingRun.complete();
    await grading;

    expect(updateSubmissionGrade).not.toHaveBeenCalled();
    expect(component.submissionTestResults['submission-1']).toEqual([]);
    expect(component.isChecking).toBe(false);
  });

  it('does not let an older grading request stop a newer request', async () => {
    const firstRun = new Subject<{
      stdout: string;
      status: { id: number; description: string };
    }>();
    const secondRun = new Subject<{
      stdout: string;
      status: { id: number; description: string };
    }>();
    const runCCode = vi
      .fn()
      .mockReturnValueOnce(firstRun)
      .mockReturnValueOnce(secondRun);
    const updateSubmissionGrade = vi.fn().mockResolvedValue(1);
    const { component } = createComponent(
      vi.fn(),
      { runCCode } as Partial<Judge0Service>,
      updateSubmissionGrade,
    );
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      question_id: 'question-1',
      grading_revision: 0,
    };
    component.selectedSubmission = submission;
    component.editableText['submission-1'] = 'int main(void) { return 0; }';
    component.questions = [
      {
        id: 'question-1',
        question_name: 'First question',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '', expected_output: '5' },
        ],
      },
      {
        id: 'question-2',
        question_name: 'Second question',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '', expected_output: '7' },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

    const olderGrading = component.checkSubmission(submission);
    component.onSelectedQuestionChange('question-2');
    const newerGrading = component.checkSubmission(submission);

    firstRun.next({
      stdout: '5',
      status: { id: 3, description: 'Accepted' },
    });
    firstRun.complete();
    await olderGrading;

    expect(component.isChecking).toBe(true);

    secondRun.next({
      stdout: '7',
      status: { id: 3, description: 'Accepted' },
    });
    secondRun.complete();
    await newerGrading;

    expect(updateSubmissionGrade).toHaveBeenCalledTimes(1);
    expect(component.submissionCheckStatus['submission-1']).toBe('Accepted');
    expect(component.isChecking).toBe(false);
  });

  it('does not leave Details until a question is selected', async () => {
    const { component, updateSubmissionDetails } = createWorkflowComponent();
    selectSubmission(component, 'submission-1');
    component.reviewStep = 1;

    await component.continueFromDetails();

    expect(updateSubmissionDetails).not.toHaveBeenCalled();
    expect(component.reviewStep).toBe(1);
  });

  it('saves the topic and selected question together before code review', async () => {
    const updateSubmissionDetails = vi.fn().mockResolvedValue(4);
    const { component } = createWorkflowComponent({ updateSubmissionDetails });
    selectSubmission(component, 'submission-1');
    component.submissions = [component.selectedSubmission!];
    component.editableTopic = 'Loops';
    component.selectedQuestionId = 'question-1';

    await component.continueFromDetails();

    expect(updateSubmissionDetails).toHaveBeenCalledWith(
      'submission-1',
      'Loops',
      'question-1',
    );
    expect(component.reviewStep).toBe(2);
    expect(component.selectedSubmission?.grading_revision).toBe(4);
  });

  it('does not apply a completed assignment save to a different open submission', async () => {
    const pendingSave = deferred<number>();
    const updateSubmissionDetails = vi
      .fn()
      .mockReturnValue(pendingSave.promise);
    const { component } = createWorkflowComponent({ updateSubmissionDetails });
    const first = {
      id: 'submission-a',
      image_url: 'https://example.test/a.png',
      captured_at: '2026-09-22T00:00:00.000Z',
      topic: 'Original A',
      question_id: 'question-a',
      grading_revision: 1,
    };
    const second = {
      id: 'submission-b',
      image_url: 'https://example.test/b.png',
      captured_at: '2026-09-22T00:00:00.000Z',
      topic: 'Original B',
      question_id: 'question-b',
      grading_revision: 9,
    };
    component.submissions = [first, second];
    component.openModal(first);
    component.editableTopic = 'Saved A';
    component.selectedQuestionId = 'question-a-new';

    const save = component.continueFromDetails();
    component.closeModal();
    component.openModal(second);
    pendingSave.resolve(2);
    await save;

    expect(updateSubmissionDetails).toHaveBeenCalledWith(
      'submission-a',
      'Saved A',
      'question-a-new',
    );
    expect(component.selectedSubmission?.id).toBe('submission-b');
    expect(component.selectedSubmission?.grading_revision).toBe(9);
    expect(component.selectedSubmission?.topic).toBe('Original B');
    expect(component.selectedQuestionId).toBe('question-b');
    expect(component.reviewStep).toBe(1);
    expect(component.submissions[0]).toMatchObject({
      topic: 'Saved A',
      question_id: 'question-a-new',
      grading_revision: 2,
    });
  });

  it.each([
    ['object', false],
    ['array', true],
  ])('restores a linked question returned as an %s', (_, asArray) => {
    const { component } = createWorkflowComponent();
    const question = {
      id: 'question-1',
      question_name: 'Addition',
      question_type: 'program' as const,
      test_cases: [],
    };
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      questions: asArray ? [question] : question,
    };

    component.openModal(submission);

    expect(component.selectedQuestionId).toBe('question-1');
    expect(component.getQuestionName(submission)).toBe('Addition');
  });

  it('restores a persisted grade when reopening a submission', () => {
    const { component } = createWorkflowComponent();
    const persistedResults = [
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
        stdin: '4 4',
        expectedOutput: '8',
        actualOutput: '7',
        status: 'Wrong Answer',
        passed: false,
      },
    ];
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      status: 'graded',
      grading_results: persistedResults,
      passed_test_cases: 1,
      total_test_cases: 2,
      score_percent: 50,
      graded_at: '2026-09-17T12:00:00.000Z',
    };

    component.openModal(submission);

    expect(component.submissionTestResults['submission-1']).toEqual(
      persistedResults,
    );
    expect(component.submissionCheckStatus['submission-1']).toBe(
      'Wrong Answer',
    );
    expect(component.submissionRunOutput['submission-1']).toBe('7');
  });

  it('exposes the persisted numerical grade as soon as the review reopens', () => {
    const { component } = createWorkflowComponent();
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      status: 'graded',
      grading_results: [],
      passed_test_cases: 4,
      total_test_cases: 6,
      score_percent: 66.67,
      graded_at: '2026-09-17T12:00:00.000Z',
    };

    component.openModal(submission);

    expect(component.reviewStep).toBe(1);
    expect(component.getSubmissionGradeSummary(component.selectedSubmission)).toBe(
      '4/6 test cases passed — Score: 66.67%',
    );
  });

  it('clears a completed grade immediately when the student code changes', () => {
    const { component } = createWorkflowComponent();
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
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      status: 'graded',
      verified_text: 'old code',
      grading_results: persistedResults,
      passed_test_cases: 1,
      total_test_cases: 1,
      score_percent: 100,
      graded_at: '2026-09-17T12:00:00.000Z',
    };
    component.submissions = [submission];
    component.editableText[submission.id] = 'old code';
    component.openModal(submission);

    component.updateSubmissionCode(submission.id, 'edited code');

    expect(component.editableText[submission.id]).toBe('edited code');
    expect(component.submissionTestResults[submission.id]).toEqual([]);
    expect(component.submissionCheckStatus[submission.id]).toBe('');
    expect(component.submissionRunOutput[submission.id]).toBe('');
    expect(component.selectedSubmission?.status).toBe('verified');
    expect(submission.status).toBe('verified');
    expect(component.selectedSubmission?.grading_results).toEqual([]);
    expect(submission.grading_results).toEqual([]);
    expect(component.selectedSubmission?.score_percent).toBeUndefined();
    expect(submission.score_percent).toBeUndefined();
    expect(component.getSubmissionStatusLabel(submission)).toBe(
      'Ready to grade',
    );
  });

  it('clears a completed grade immediately when the question changes', () => {
    const { component } = createWorkflowComponent();
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
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      status: 'graded',
      verified_text: 'int main(void) { return 0; }',
      question_id: 'question-1',
      grading_results: persistedResults,
      passed_test_cases: 1,
      total_test_cases: 1,
      score_percent: 100,
      graded_at: '2026-09-17T12:00:00.000Z',
    };
    component.submissions = [submission];
    component.openModal(submission);

    component.onSelectedQuestionChange('question-2');

    expect(component.selectedQuestionId).toBe('question-2');
    expect(component.submissionTestResults[submission.id]).toEqual([]);
    expect(component.selectedSubmission?.status).toBe('verified');
    expect(submission.status).toBe('verified');
    expect(component.selectedSubmission?.grading_results).toEqual([]);
    expect(submission.grading_results).toEqual([]);
    expect(component.getSubmissionStatusLabel(submission)).toBe(
      'Ready to grade',
    );
  });

  it('restores persisted code, question, and grade when unsaved edits are canceled', () => {
    const { component } = createWorkflowComponent();
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
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      status: 'graded',
      verified_text: 'persisted code',
      question_id: 'question-1',
      grading_results: persistedResults,
      passed_test_cases: 1,
      total_test_cases: 1,
      score_percent: 100,
      graded_at: '2026-09-17T12:00:00.000Z',
    };
    component.submissions = [submission];
    component.openModal(submission);

    component.updateSubmissionCode(submission.id, 'unsaved code');
    component.onSelectedQuestionChange('question-2');
    component.closeModal();
    component.openModal(submission);

    expect(component.editableText[submission.id]).toBe('persisted code');
    expect(component.selectedQuestionId).toBe('question-1');
    expect(component.submissionTestResults[submission.id]).toEqual(
      persistedResults,
    );
    expect(component.getSubmissionStatusLabel(submission)).toBe('Graded');
    expect(submission.score_percent).toBe(100);
  });

  it('keeps a dirty editor buffer when a realtime-triggered reload completes', async () => {
    const remoteSubmission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      status: 'verified',
      verified_text: 'persisted code',
      question_id: 'question-1',
    };
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ ...remoteSubmission }],
      error: null,
    });
    const { component } = createWorkflowComponent({ getSubmissions });
    component.submissions = [{ ...remoteSubmission }];
    component.openModal(component.submissions[0]);
    component.updateSubmissionCode(remoteSubmission.id, 'unsaved code');

    await component.loadSubmissions();

    expect(component.editableText[remoteSubmission.id]).toBe('unsaved code');
    expect(component.selectedSubmission?.verified_text).toBe('persisted code');
  });

  it('refreshes a non-dirty open submission after a realtime update', async () => {
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
    const originalSubmission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      status: 'verified',
      verified_text: 'persisted code',
      question_id: 'question-1',
    };
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [
        {
          ...originalSubmission,
          status: 'graded',
          grading_results: persistedResults,
          passed_test_cases: 1,
          total_test_cases: 1,
          score_percent: 100,
          graded_at: '2026-09-22T00:00:00.000Z',
        },
      ],
      error: null,
    });
    const { component } = createWorkflowComponent({ getSubmissions });
    component.submissions = [{ ...originalSubmission }];
    component.openModal(component.submissions[0]);

    await component.loadSubmissions();

    expect(component.selectedSubmission?.status).toBe('graded');
    expect(component.selectedSubmission?.score_percent).toBe(100);
    expect(component.submissionTestResults[originalSubmission.id]).toEqual(
      persistedResults,
    );
  });

  it('ignores an older submissions reload that completes after a newer reload', async () => {
    const olderReload = deferred<{ data: unknown[]; error: null }>();
    const newerReload = deferred<{ data: unknown[]; error: null }>();
    const getSubmissions = vi
      .fn()
      .mockReturnValueOnce(olderReload.promise)
      .mockReturnValueOnce(newerReload.promise);
    const { component } = createWorkflowComponent({ getSubmissions });

    const firstLoad = component.loadSubmissions();
    const secondLoad = component.loadSubmissions();
    newerReload.resolve({
      data: [
        {
          id: 'submission-1',
          image_url: 'https://example.test/submission.png',
          captured_at: '2026-09-22T00:00:00.000Z',
          verified_text: 'newest persisted code',
        },
      ],
      error: null,
    });
    await secondLoad;
    olderReload.resolve({
      data: [
        {
          id: 'submission-1',
          image_url: 'https://example.test/submission.png',
          captured_at: '2026-09-22T00:00:00.000Z',
          verified_text: 'stale persisted code',
        },
      ],
      error: null,
    });
    await firstLoad;

    expect(component.submissions[0].verified_text).toBe(
      'newest persisted code',
    );
    expect(component.editableText['submission-1']).toBe(
      'newest persisted code',
    );
  });

  it('preserves an unsaved topic through realtime reload and restores it on cancel', async () => {
    const persistedSubmission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-09-22T00:00:00.000Z',
      topic: 'Loops',
      verified_text: 'persisted code',
    };
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ ...persistedSubmission, topic: 'Updated Loops' }],
      error: null,
    });
    const { component } = createWorkflowComponent({ getSubmissions });
    component.submissions = [{ ...persistedSubmission }];
    component.openModal(component.submissions[0]);
    component.editableTopic = 'Arrays';

    await component.loadSubmissions();

    expect(component.editableTopic).toBe('Arrays');

    component.closeModal();
    expect(component.editableTopic).toBe('Updated Loops');
  });

  it('blocks grading until student code and a question with test cases exist', () => {
    const { component } = createWorkflowComponent();
    selectSubmission(component, 'submission-1');

    expect(component.canOpenGradingStep()).toBe(false);

    component.questions = [
      {
        id: 'question-1',
        question_name: 'Addition',
        question_type: 'program',
        test_cases: [],
      },
    ];
    component.selectedQuestionId = 'question-1';

    expect(component.canOpenGradingStep()).toBe(false);
    component.questions[0].test_cases.push({
      test_code: '',
      test_input: '',
      expected_output: '5',
    });
    expect(component.canOpenGradingStep()).toBe(true);
  });

  it.each([
    ['pending', 'new'],
    ['extracted', 'extracted'],
    ['verified', 'verified'],
    ['graded', 'graded'],
  ] as const)('maps persisted status %s to %s', (status, expected) => {
    const { component } = createWorkflowComponent();
    const submission = {
      id: `submission-${status}`,
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      status,
    };

    expect(component.getSubmissionStatus(submission)).toBe(expected);
  });

  it('keeps the user in code review and displays an OCR error on failure', async () => {
    const post = vi
      .fn()
      .mockReturnValue(throwError(() => new Error('OCR unavailable')));
    const { component } = createWorkflowComponent({ post });
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    selectSubmission(component, 'submission-1');
    component.reviewStep = 2;

    await component.extractText();

    expect(component.reviewStep).toBe(2);
    expect(component.extractionError['submission-1']).toContain(
      'Failed to extract text',
    );
    expect(component.extractingId).toBeNull();
  });

  it('treats re-extracted OCR as a dirty edit and preserves it through realtime reload', async () => {
    const persistedResults = [
      {
        caseNumber: 1,
        stdin: '',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ];
    const persistedSubmission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-09-22T00:00:00.000Z',
      status: 'graded',
      verified_text: 'old persisted code',
      grading_results: persistedResults,
      passed_test_cases: 1,
      total_test_cases: 1,
      score_percent: 100,
      graded_at: '2026-09-22T00:00:00.000Z',
    };
    const post = vi.fn().mockReturnValue(of({ cleaned_text: 'fresh OCR code' }));
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ ...persistedSubmission }],
      error: null,
    });
    const { component } = createWorkflowComponent({ post, getSubmissions });
    component.submissions = [{ ...persistedSubmission }];
    component.editableText[persistedSubmission.id] =
      persistedSubmission.verified_text;
    component.openModal(component.submissions[0]);

    await component.extractText();

    expect(component.editableText[persistedSubmission.id]).toBe(
      'fresh OCR code',
    );
    expect(component.submissionTestResults[persistedSubmission.id]).toEqual(
      [],
    );

    await component.loadSubmissions();

    expect(component.editableText[persistedSubmission.id]).toBe(
      'fresh OCR code',
    );
  });

  it('advances to grading only after verified code saves successfully', async () => {
    const updateSubmissionText = vi.fn().mockResolvedValue(5);
    const { component } = createWorkflowComponent({ updateSubmissionText });
    selectSubmission(component, 'submission-1');
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Addition',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '', expected_output: '5' },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';
    component.reviewStep = 2;

    await component.saveCodeAndContinue();

    expect(updateSubmissionText).toHaveBeenCalled();
    expect(component.reviewStep).toBe(3);
    expect(component.selectedSubmission?.grading_revision).toBe(5);
  });

  it('does not advance to grading when verified code fails to save', async () => {
    const updateSubmissionText = vi
      .fn()
      .mockRejectedValue(new Error('database unavailable'));
    const { component } = createWorkflowComponent({ updateSubmissionText });
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    selectSubmission(component, 'submission-1');
    component.questions = [
      {
        id: 'question-1',
        question_name: 'Addition',
        question_type: 'program',
        test_cases: [
          { test_code: '', test_input: '', expected_output: '5' },
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';
    component.reviewStep = 2;

    await component.saveCodeAndContinue();

    expect(component.saveStatus['submission-1']).toBe('error');
    expect(component.reviewStep).toBe(2);
  });
});
