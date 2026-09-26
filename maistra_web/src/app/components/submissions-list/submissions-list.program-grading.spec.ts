import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SubmissionProgramRow, SupabaseService } from '../../services/supabase';
import { SubmissionsListComponent } from './submissions-list';

// Grading a paper with several programs (submission_programs, 2026-09-26):
// each program is graded against its own question and saved on its own row;
// the page counts as graded only when every program is.

const accepted = (stdout: string) => ({ stdout, status: { id: 3, description: 'Accepted' } });

function programRow(
  position: number,
  questionId: string,
  code: string,
  grade: Partial<SubmissionProgramRow> = {},
): SubmissionProgramRow {
  return {
    id: `program-${position}`,
    position,
    question_id: questionId,
    verified_text: code,
    grading_results: [],
    passed_test_cases: null,
    total_test_cases: null,
    score_percent: null,
    graded_at: null,
    grading_revision: 0,
    ...grade,
  };
}

function paper(programs: SubmissionProgramRow[]) {
  return {
    id: 'paper-1',
    image_url: 'https://example.test/paper.png',
    captured_at: '2026-09-26T09:30:00.000Z',
    status: 'verified',
    question_id: 'q-sum',
    verified_text: programs[0]?.verified_text,
    grading_revision: 4,
    submission_programs: programs,
  };
}

function setup(options: {
  runs?: ReturnType<typeof accepted>[];
  saveProgramGrade?: ReturnType<typeof vi.fn>;
  getSubmission?: ReturnType<typeof vi.fn>;
} = {}) {
  const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
  const saveProgramGrade =
    options.saveProgramGrade ?? vi.fn().mockImplementation(async (_id, revision) => revision + 1);
  const getSubmission =
    options.getSubmission ?? vi.fn().mockResolvedValue({ data: null, error: null });
  const updateSubmissionGrade = vi.fn();
  const getSubmissions = vi.fn();
  const updateSubmissionDetails = vi.fn().mockImplementation(async (_id, _topic, _q, revision) => revision + 1);
  const supabase = {
    saveProgramGrade,
    getSubmission,
    getSubmissions,
    updateSubmissionDetails,
    updateSubmissionGrade,
    getQuestionSections: vi.fn().mockResolvedValue({ data: [], error: null }),
    getSectionItems: vi.fn().mockResolvedValue({ data: [], error: null }),
    getGateResults: vi.fn().mockResolvedValue(new Map()),
  } as unknown as SupabaseService;
  const runCCodeBatch = vi.fn().mockReturnValue(of(options.runs ?? [accepted('3')]));
  const component = new SubmissionsListComponent(
    supabase,
    {} as HttpClient,
    cdr,
    { runCCodeBatch } as unknown as Judge0Service,
  );
  component.questions = [
    {
      id: 'q-sum',
      question_name: 'Sum',
      question_type: 'program',
      test_cases: [{ test_code: '', test_input: '1 2', expected_output: '3' }],
    },
    {
      id: 'q-max',
      question_name: 'Max',
      question_type: 'program',
      test_cases: [{ test_code: '', test_input: '1 2', expected_output: '2' }],
    },
  ];
  return { component, saveProgramGrade, getSubmission, getSubmissions, updateSubmissionGrade, runCCodeBatch };
}

// Loads the paper the way the page does, then opens it on Step 3.
async function open(
  { component, getSubmissions }: ReturnType<typeof setup>,
  programs: SubmissionProgramRow[],
) {
  getSubmissions.mockResolvedValue({ data: [paper(programs)], error: null });
  await component.loadSubmissions();
  // Basic · Q1 is Sum, Basic · Q2 is Max.
  component.questionPlaces = new Map([
    ['q-sum', { sectionId: 's', sectionName: 'Basic', sectionPosition: 0, number: 1 }],
    ['q-max', { sectionId: 's', sectionName: 'Basic', sectionPosition: 0, number: 2 }],
  ]);
  component.openModal(component.submissions[0]);
  component.reviewStep = 3;
  return component.selectedSubmission!;
}

describe('SubmissionsListComponent grading several programs', () => {
  it('grades the selected program against its own question and saves it on its row', async () => {
    const ctx = setup({
      runs: [accepted('2')],
    });
    const { component, saveProgramGrade, updateSubmissionGrade, runCCodeBatch } = ctx;
    const selected = await open(ctx, [
      programRow(1, 'q-sum', 'sum code', { graded_at: '2026-09-26T10:00:00Z', passed_test_cases: 1, total_test_cases: 1 }),
      programRow(2, 'q-max', 'max code'),
    ]);

    // The first ungraded program is picked by default.
    expect(component.selectedGradingProgram(selected)?.id).toBe('program-2');
    await component.checkSubmission(selected);

    expect(runCCodeBatch.mock.calls[0][0]).toEqual([
      expect.objectContaining({ stdin: '1 2', sourceCode: expect.stringContaining('max code') }),
    ]);
    expect(saveProgramGrade).toHaveBeenCalledWith('program-2', 0, 'q-max', 'max code', [
      expect.objectContaining({ passed: true, expectedOutput: '2' }),
    ]);
    expect(updateSubmissionGrade).not.toHaveBeenCalled();
    expect(component.checkError).toBe('');
  });

  it('marks the page graded only once every program is graded', async () => {
    const ctx = setup({ runs: [accepted('3')] });
    const { component } = ctx;
    const selected = await open(ctx, [programRow(1, 'q-sum', 'sum code'), programRow(2, 'q-max', 'max code')]);

    await component.checkSubmission(selected);

    expect(component.getSubmissionStatus(component.submissions[0])).toBe('verified');
    expect(component.getSubmissionGradeSummary(component.submissions[0])).toBe(
      'Q1 1/1 · Q2 not graded',
    );

    component.selectGradingProgram(selected, 'program-2');
    await component.checkSubmission(component.selectedSubmission);

    expect(component.getSubmissionStatus(component.submissions[0])).toBe('graded');
    expect(component.getSubmissionGradeSummary(component.submissions[0])).toBe('Q1 1/1 · Q2 0/1');
  });

  it('keeps the one-program summary teachers already know', async () => {
    const ctx = setup({ runs: [accepted('3')] });
    const { component } = ctx;
    const selected = await open(ctx, [programRow(1, 'q-sum', 'sum code')]);

    await component.checkSubmission(selected);

    expect(component.getSubmissionStatus(component.submissions[0])).toBe('graded');
    expect(component.getSubmissionGradeSummary(component.submissions[0])).toBe(
      '1/1 test cases passed — Score: 100%',
    );
  });

  it('refuses a grade the database no longer accepts', async () => {
    const ctx = setup({ saveProgramGrade: vi.fn().mockResolvedValue(null) });
    const { component } = ctx;
    const selected = await open(ctx, [programRow(1, 'q-sum', 'sum code')]);

    await component.checkSubmission(selected);

    expect(component.checkError).toBe('Submission inputs changed during grading. Run grading again.');
    expect(component.getSubmissionStatus(component.submissions[0])).toBe('verified');
    expect(component.submissions[0].submission_programs?.[0].graded_at).toBeNull();
  });

  it('shows the selected program in the sample run and its own stored results', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, [
      programRow(1, 'q-sum', 'sum code', {
        graded_at: '2026-09-26T10:00:00Z',
        passed_test_cases: 1,
        total_test_cases: 1,
        grading_results: [{ caseNumber: 1, passed: true, actualOutput: '3' }],
      }),
      programRow(2, 'q-max', 'max code'),
    ]);

    component.selectGradingProgram(selected, 'program-1');
    expect(component.getExecutionSourceCode(selected)).toContain('sum code');
    expect(component.getExecutionExpectedOutput(selected)).toBe('3');
    expect(component.gradingQuestionLabel(selected)).toBe('Basic · Q1 · Sum');
    expect(component.submissionTestResults['paper-1']).toHaveLength(1);

    component.selectGradingProgram(selected, 'program-2');
    expect(component.getExecutionSourceCode(selected)).toContain('max code');
    expect(component.getExecutionExpectedOutput(selected)).toBe('2');
    expect(component.submissionTestResults['paper-1']).toEqual([]);
    expect(component.gradingKey(selected)).toBe('program-2');
  });

  it('re-reads the program rows of a paper saved this session before grading', async () => {
    const fresh = paper([programRow(1, 'q-sum', 'sum code, saved', { grading_revision: 1 })]);
    const getSubmission = vi.fn().mockResolvedValue({ data: fresh, error: null });
    const ctx = setup({ getSubmission });
    const { component, saveProgramGrade } = ctx;
    const selected = await open(ctx, [programRow(1, 'q-sum', 'sum code')]);
    (component as unknown as { staleProgramIds: Set<string> }).staleProgramIds.add('paper-1');

    await component.checkSubmission(selected);

    expect(getSubmission).toHaveBeenCalledWith('paper-1');
    expect(saveProgramGrade).toHaveBeenCalledWith(
      'program-1',
      1,
      'q-sum',
      'sum code, saved',
      expect.any(Array),
    );
  });

  it('grades Program 1 against the question just chosen on Details (review #1)', async () => {
    // After the Details save the database has moved Program 1 to q-max.
    // The Details save moved the page from revision 4 to 5.
    const moved = {
      ...paper([programRow(1, 'q-max', 'sum code', { grading_revision: 1 })]),
      question_id: 'q-max',
      grading_revision: 5,
    };
    const getSubmission = vi.fn().mockResolvedValue({ data: moved, error: null });
    const ctx = setup({ getSubmission, runs: [accepted('2')] });
    const { component, saveProgramGrade } = ctx;
    await open(ctx, [programRow(1, 'q-sum', 'sum code')]);
    component.reviewStep = 1;

    component.onSelectedQuestionChange('q-max');
    expect(await component.saveSubmissionDetails()).toBe(true);
    await component.checkSubmission(component.selectedSubmission);

    expect(getSubmission).toHaveBeenCalledWith('paper-1');
    expect(saveProgramGrade).toHaveBeenCalledWith('program-1', 1, 'q-max', 'sum code', [
      expect.objectContaining({ passed: true, expectedOutput: '2' }),
    ]);
  });
});
