import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { of, throwError } from 'rxjs';
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
      verified_version: 0,
      is_current: true,
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
    getSubmissionContextOptions?: ReturnType<typeof vi.fn>;
    post?: ReturnType<typeof vi.fn>;
  }) {
    const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
    const updateSubmissionDetails =
      options?.updateSubmissionDetails ?? vi.fn().mockResolvedValue(undefined);
    const updateSubmissionText =
      options?.updateSubmissionText ?? vi.fn().mockResolvedValue(undefined);
    const getSubmissionContextOptions =
      options?.getSubmissionContextOptions ??
      vi.fn().mockResolvedValue({
        assessments: [],
        assessmentQuestions: [],
        roster: [],
      });
    const post =
      options?.post ??
      vi.fn().mockReturnValue(of({ cleaned_text: 'int main() {}' }));
    const supabase = {
      updateSubmissionDetails,
      updateSubmissionText,
      getSubmissionContextOptions,
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
      getSubmissionContextOptions,
    };
  }

  function configureComparisonContext(
    component: SubmissionsListComponent,
    assessmentId = 'assessment-1',
  ) {
    const question = {
      id: 'question-1',
      question_name: 'Addition',
      question_type: 'program' as const,
      model_answer: 'int main(void) { return 0; }',
      test_cases: [
        {
          test_code: '',
          test_input: '2 3',
          expected_output: '5',
          mark: 2,
        },
      ],
    };
    component.assessments = [
      {
        id: assessmentId,
        name: 'Midterm',
        status: 'active',
        starts_at: null,
      },
    ];
    component.assessmentQuestions = [
      {
        assessment_id: assessmentId,
        question_id: question.id,
        starter_code: '',
        position: 1,
        questions: question,
      },
    ];
    component.assessmentRoster = [
      {
        assessment_id: assessmentId,
        student_id: 'student-1',
        block_section_id: 'section-a',
        students: {
          id: 'student-1',
          student_number: '2026-001',
          display_name: 'Ana',
        },
        block_sections: { id: 'section-a', name: 'BSCS 2A' },
      },
      {
        assessment_id: assessmentId,
        student_id: 'student-2',
        block_section_id: 'section-a',
        students: {
          id: 'student-2',
          student_number: '2026-002',
          display_name: 'Ben',
        },
        block_sections: { id: 'section-a', name: 'BSCS 2A' },
      },
    ];
    component.questions = [question];
    component.selectedAssessmentId = assessmentId;
    component.selectedBlockSectionId = 'section-a';
    component.selectedStudentId = 'student-1';
    component.selectedQuestionId = question.id;
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
        logic_details: [
          { name: 'Has main', passed: true, weight: 1, score: 1 },
        ],
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
      verified_version: 0,
      is_current: true,
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
      expected_output: '',
      actual_output: '',
      compilation_passed: false,
    });
    expect(gradeSubmission).toHaveBeenCalledTimes(1);
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
    expect(component.submissionLogicResults['submission-1']).toEqual([
      { name: 'Has main', passed: true, weight: 1, score: 1 },
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
      verified_version: 1,
      is_current: true,
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
      verified_version: 0,
      is_current: true,
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
      verified_version: 0,
      is_current: true,
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

  it('clears stale execution results when the selected question changes', () => {
    const { component } = createComponent(vi.fn());
    component.selectedSubmission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-07-28T00:00:00.000Z',
      verified_version: 0,
      is_current: true,
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
    component.submissionLogicResults['submission-1'] = [
      { name: 'Has main', passed: true, weight: 1, score: 1 },
    ];

    component.onSelectedQuestionChange('question-2');

    expect(component.selectedQuestionId).toBe('question-2');
    expect(component.submissionRunOutput['submission-1']).toBe('');
    expect(component.submissionCheckStatus['submission-1']).toBe('');
    expect(component.submissionTestResults['submission-1']).toEqual([]);
    expect(component.submissionLogicResults['submission-1']).toEqual([]);
  });

  it('does not leave Details until every comparison field is selected', async () => {
    const { component, updateSubmissionDetails } = createWorkflowComponent();
    selectSubmission(component, 'submission-1');
    component.selectedQuestionId = 'question-1';
    component.reviewStep = 1;

    await component.continueFromDetails();

    expect(updateSubmissionDetails).not.toHaveBeenCalled();
    expect(component.reviewStep).toBe(1);
  });

  it('saves the topic and selected question together before code review', async () => {
    const { component, updateSubmissionDetails } = createWorkflowComponent();
    selectSubmission(component, 'submission-1');
    component.submissions = [component.selectedSubmission!];
    component.editableTopic = 'Loops';
    configureComparisonContext(component);

    await component.continueFromDetails();

    expect(updateSubmissionDetails).toHaveBeenCalledWith('submission-1', {
      topic: 'Loops',
      assessment_id: 'assessment-1',
      question_id: 'question-1',
      student_id: 'student-1',
      block_section_id: 'section-a',
    });
    expect(component.reviewStep).toBe(2);
  });

  it('filters questions and roster choices by assessment and section', () => {
    const { component } = createWorkflowComponent();
    configureComparisonContext(component);
    component.assessmentQuestions.push({
      assessment_id: 'assessment-2',
      question_id: 'question-2',
      starter_code: '',
      position: 1,
      questions: {
        id: 'question-2',
        question_name: 'Arrays',
        question_type: 'program',
        model_answer: 'int main(void) { return 0; }',
        test_cases: [],
      },
    });

    expect(
      component.getAvailableQuestions('assessment-1').map((q) => q.id),
    ).toEqual(['question-1']);
    expect(
      component.getAvailableSections('assessment-1').map((s) => s.id),
    ).toEqual(['section-a']);
    expect(
      component
        .getAvailableStudents('assessment-1', 'section-a')
        .map((student) => student.id),
    ).toEqual(['student-1', 'student-2']);
  });

  it('clears group choices that are invalid in a newly selected assessment', async () => {
    const getSubmissionContextOptions = vi.fn().mockResolvedValue({
      assessments: [
        {
          id: 'assessment-2',
          name: 'Final',
          status: 'active',
          starts_at: null,
        },
      ],
      assessmentQuestions: [],
      roster: [],
    });
    const { component } = createWorkflowComponent({
      getSubmissionContextOptions,
    });
    selectSubmission(component, 'submission-1');
    configureComparisonContext(component);

    await component.onSelectedAssessmentChange('assessment-2');

    expect(component.selectedAssessmentId).toBe('assessment-2');
    expect(component.selectedQuestionId).toBe('');
    expect(component.selectedBlockSectionId).toBe('');
    expect(component.selectedStudentId).toBe('');
  });

  it('shows legacy submissions as missing comparison details without guessing', () => {
    const { component } = createWorkflowComponent();

    component.openModal({
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      verified_version: 0,
      is_current: true,
    });

    expect(component.selectedAssessmentId).toBe('');
    expect(component.selectedBlockSectionId).toBe('');
    expect(component.selectedStudentId).toBe('');
    expect(component.selectedQuestionId).toBe('');
    expect(component.getComparisonContextStatus()).toBe(
      'Missing comparison details',
    );
  });

  it('clears grading and similarity state when group identity changes', () => {
    const { component } = createWorkflowComponent();
    selectSubmission(component, 'submission-1');
    configureComparisonContext(component);
    component.submissionRunOutput['submission-1'] = '5';
    component.submissionCheckStatus['submission-1'] = 'Accepted';
    component.submissionTestResults['submission-1'] = [
      {
        caseNumber: 1,
        stdin: '2 3',
        expectedOutput: '5',
        actualOutput: '5',
        status: 'Accepted',
        passed: true,
      },
    ];
    component.similarityState['submission-1'] = 'complete';

    component.onSelectedStudentChange('student-2');

    expect(component.submissionRunOutput['submission-1']).toBe('');
    expect(component.submissionCheckStatus['submission-1']).toBe('');
    expect(component.submissionTestResults['submission-1']).toEqual([]);
    expect(component.similarityState['submission-1']).toBeUndefined();
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
      model_answer: 'int main(void) { return 0; }',
      test_cases: [],
    };
    const submission = {
      id: 'submission-1',
      image_url: 'https://example.test/submission.png',
      captured_at: '2026-08-18T00:00:00.000Z',
      verified_version: 0,
      is_current: true,
      questions: asArray ? [question] : question,
    };

    component.openModal(submission);

    expect(component.selectedQuestionId).toBe('question-1');
    expect(component.getQuestionName(submission)).toBe('Addition');
  });

  it('blocks grading until both student code and a question exist', () => {
    const { component } = createWorkflowComponent();
    selectSubmission(component, 'submission-1');

    expect(component.canOpenGradingStep()).toBe(false);

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
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';

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
      verified_version: status === 'verified' || status === 'graded' ? 1 : 0,
      is_current: true,
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

  it('advances to grading only after verified code saves successfully', async () => {
    const updateSubmissionText = vi.fn().mockResolvedValue(undefined);
    const { component } = createWorkflowComponent({ updateSubmissionText });
    selectSubmission(component, 'submission-1');
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
        ],
      },
    ];
    component.selectedQuestionId = 'question-1';
    component.reviewStep = 2;

    await component.saveCodeAndContinue();

    expect(updateSubmissionText).toHaveBeenCalled();
    expect(component.reviewStep).toBe(3);
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
    component.selectedQuestionId = 'question-1';
    component.reviewStep = 2;

    await component.saveCodeAndContinue();

    expect(component.saveStatus['submission-1']).toBe('error');
    expect(component.reviewStep).toBe(2);
  });
});
