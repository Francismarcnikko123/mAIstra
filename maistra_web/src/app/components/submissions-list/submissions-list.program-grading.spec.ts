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
      'P1 1/1 · P2 not graded',
    );

    component.selectGradingProgram(selected, 'program-2');
    await component.checkSubmission(component.selectedSubmission);

    expect(component.getSubmissionStatus(component.submissions[0])).toBe('graded');
    expect(component.getSubmissionGradeSummary(component.submissions[0])).toBe('P1 1/1 · P2 0/1');
  });

  it('numbers each program by its place on the paper, whatever its section', async () => {
    const ctx = setup();
    const { component } = ctx;
    await open(ctx, [
      programRow(1, 'q-sum', 'sum code', { graded_at: '2026-09-26T10:00:00Z', passed_test_cases: 0, total_test_cases: 3 }),
      programRow(2, 'q-max', 'max code'),
      programRow(3, 'q-loose', 'loose code'),
    ]);
    // Basic · Q1 and E2E TEST · Q1 are both "Q1"; the third has no section.
    component.questionPlaces = new Map([
      ['q-sum', { sectionId: 's', sectionName: 'Basic', sectionPosition: 0, number: 1 }],
      ['q-max', { sectionId: 'e2e', sectionName: 'E2E TEST', sectionPosition: 1, number: 1 }],
    ]);

    expect(component.getSubmissionGradeSummary(component.submissions[0])).toBe(
      'P1 0/3 · P2 not graded · P3 not graded',
    );
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

  it('refuses to grade a program with more test cases than one Judge0 batch can run', async () => {
    const ctx = setup();
    const { component, runCCodeBatch, saveProgramGrade } = ctx;
    component.questions[0].test_cases = Array.from({ length: 31 }, () => ({
      test_code: '',
      test_input: '1 2',
      expected_output: '3',
    }));
    const selected = await open(ctx, [programRow(1, 'q-sum', 'sum code')]);

    await component.checkSubmission(selected);

    expect(runCCodeBatch).not.toHaveBeenCalled();
    expect(saveProgramGrade).not.toHaveBeenCalled();
    expect(component.checkError).toBe(
      'This question has 31 test cases, but grading can run at most 30. Remove some in the question form.',
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

  it('stays on the program just graded, with its own results (review #3)', async () => {
    const ctx = setup({ runs: [accepted('3')] });
    const { component } = ctx;
    const selected = await open(ctx, [programRow(1, 'q-sum', 'sum code'), programRow(2, 'q-max', 'max code')]);
    expect(component.selectedGradingProgram(selected)?.id).toBe('program-1');

    await component.checkSubmission(selected);

    // Program 2 is now the first ungraded one, but the view must not jump
    // to it while showing Program 1's results.
    const open1 = component.selectedSubmission!;
    expect(component.selectedGradingProgram(open1)?.id).toBe('program-1');
    expect(component.gradingKey(open1)).toBe('program-1');
    expect(component.gradingQuestionLabel(open1)).toBe('Basic · Q1 · Sum');
    expect(component.submissionTestResults['paper-1']).toEqual([
      expect.objectContaining({ expectedOutput: '3', passed: true }),
    ]);

    // Reopened later, the paper starts on its first ungraded program.
    component.closeModal();
    component.openModal(component.submissions[0]);
    expect(component.selectedGradingProgram(component.selectedSubmission)?.id).toBe('program-2');
  });

  it('waits for a re-read already in progress before grading (review #6)', async () => {
    let finishRead!: (value: unknown) => void;
    const fresh = {
      ...paper([programRow(1, 'q-sum', 'sum code, saved', { id: 'program-new', grading_revision: 2 })]),
      grading_revision: 5,
    };
    const getSubmission = vi.fn().mockImplementation(
      () => new Promise((resolve) => { finishRead = () => resolve({ data: fresh, error: null }); }),
    );
    const ctx = setup({ getSubmission });
    const { component, saveProgramGrade } = ctx;
    const selected = await open(ctx, [programRow(1, 'q-sum', 'sum code')]);
    (component as unknown as { staleProgramIds: Set<string> }).staleProgramIds.add('paper-1');
    getSubmission.mockClear(); // opening the paper re-reads it once already

    // Opening Step 3 starts the re-read; Submit is clicked before it ends.
    component.setReviewStep(3);
    const grading = component.checkSubmission(selected);
    finishRead(undefined);
    await grading;

    expect(getSubmission).toHaveBeenCalledTimes(1);
    expect(saveProgramGrade).toHaveBeenCalledWith(
      'program-new',
      2,
      'q-sum',
      'sum code, saved',
      expect.any(Array),
    );
  });
});

// A program that passed 0 of 3 used to show a green "✓ 0/3" on its Step 3
// chip, which reads as a pass. The chip now says "0/3 passed" in red.
describe('SubmissionsListComponent grade on the Step 3 program chips', () => {
  const graded = (passed: number | null, total: number | null) =>
    programRow(1, 'q-sum', 'sum code', {
      graded_at: '2026-09-26T10:00:00Z',
      passed_test_cases: passed,
      total_test_cases: total,
    });
  const readSource = async (file: string) =>
    (await import('fs')).readFileSync(`src/app/components/submissions-list/${file}`, 'utf8');

  it('picks the tone from how many test cases passed', () => {
    const { component } = setup();

    expect(component.programGradeTone(graded(3, 3))).toBe('full');
    expect(component.programGradeTone(graded(1, 3))).toBe('partial');
    expect(component.programGradeTone(graded(0, 3))).toBe('none');
    // The paper summary on the list card still uses the bare count.
    expect(component.programGradeLabel(graded(0, 3))).toBe('0/3');
  });

  it('treats a program with no usable counts as not graded', () => {
    const { component } = setup();

    expect(component.programGradeTone(programRow(1, 'q-sum', 'sum code'))).toBe('pending');
    // Counts left over without a grade time are not a grade.
    expect(
      component.programGradeTone(
        programRow(1, 'q-sum', 'sum code', { passed_test_cases: 3, total_test_cases: 3 }),
      ),
    ).toBe('pending');
    expect(component.programGradeTone(graded(null, 3))).toBe('pending');
    expect(component.programGradeTone(graded(0, null))).toBe('pending');
    expect(component.programGradeTone(graded(0, 0))).toBe('pending');
  });

  it('shows the grade in words as well as colour on each chip', async () => {
    const template = await readSource('submissions-list.html');
    const chip = new DOMParser()
      .parseFromString(template, 'text/html')
      .querySelector('.grading-program');

    expect(chip?.getAttribute('[attr.data-grade]')).toBe('programGradeTone(program)');
    // The old class painted every graded chip green, 0/3 included.
    expect(chip?.hasAttribute('[class.graded]')).toBe(false);
    expect(chip?.querySelector('small')?.textContent?.trim()).toBe(
      "{{ programGradeTone(program) === 'pending' ? 'Not graded' : programGradeLabel(program) + ' passed' }}",
    );
  });

  it('colours each tone with a readable colour and leaves Not graded gray', async () => {
    const css = await readSource('program-grading.css');
    const colours = Object.fromEntries(
      [...css.matchAll(/\[data-grade='(\w+)'\] small \{[^}]*?color: (#[0-9a-f]{6});/g)].map(
        ([, tone, colour]) => [tone, colour],
      ),
    );

    // Each is at least 4.5:1 on the white chip; program-tabs.css uses the same.
    expect(colours).toEqual({ full: '#15803d', partial: '#b45309', none: '#991b1b' });
    expect(css).toMatch(/\.grading-program small \{[^}]*color: #64748b;/);
    expect(css).not.toContain('.graded');
  });
});

// Switching programs rebuilds the grader, so switching during a sample run
// used to drop the run without a word. The chips now wait for it, as they
// already did for grading.
describe('SubmissionsListComponent program chips during a sample run', () => {
  const programs = () => [programRow(1, 'q-sum', 'sum code'), programRow(2, 'q-max', 'max code')];

  it('keeps the teacher on the program whose sample run is going', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, programs());
    const key = component.gradingKey(selected);

    component.onSampleRunChange(key, true);
    component.selectGradingProgram(selected, 'program-2');

    expect(component.isSampleRunning(selected)).toBe(true);
    expect(component.selectedGradingProgram(selected)?.id).toBe('program-1');
    expect(component.gradingLockReason(selected)).toBe('Wait for the sample run to finish');
  });

  it('lets the teacher switch once the run has finished', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, programs());
    const key = component.gradingKey(selected);

    component.onSampleRunChange(key, true);
    component.onSampleRunChange(key, false);
    component.selectGradingProgram(selected, 'program-2');

    expect(component.isSampleRunning(selected)).toBe(false);
    expect(component.gradingLockReason(selected)).toBeNull();
    expect(component.selectedGradingProgram(selected)?.id).toBe('program-2');
  });

  it('says why the chips are locked while grading runs', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, programs());

    component.isChecking = true;

    expect(component.gradingLockReason(selected)).toBe('Wait for grading to finish');
  });

  it('unlocks when the teacher leaves Step 3 or closes the paper mid-run', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, programs());
    const key = component.gradingKey(selected);

    component.onSampleRunChange(key, true);
    component.setReviewStep(2);
    component.reviewStep = 3;
    expect(component.isSampleRunning(selected)).toBe(false);

    component.onSampleRunChange(key, true);
    component.closeModal();
    component.openModal(component.submissions[0]);
    component.reviewStep = 3;
    expect(component.isSampleRunning(component.selectedSubmission)).toBe(false);
  });

  it('does not lock a program whose grader replaced the running one', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, programs());

    // A grader that is gone never reports its end, so only the program
    // shown right now can be locked.
    component.onSampleRunChange('program-gone', true);

    expect(component.isSampleRunning(selected)).toBe(false);
  });

  it('wires the lock into the chips and the grader', async () => {
    const template = (await import('fs')).readFileSync(
      'src/app/components/submissions-list/submissions-list.html',
      'utf8',
    );
    const doc = new DOMParser().parseFromString(template, 'text/html');
    const chip = doc.querySelector('.grading-program');
    const grader = doc.querySelector('app-judge0');

    expect(chip?.getAttribute('[disabled]')).toBe('!!gradingLockReason(selectedSubmission)');
    expect(chip?.getAttribute('[attr.title]')).toBe('gradingLockReason(selectedSubmission)');
    expect(grader?.getAttribute('(runningchange)')).toBe('onSampleRunChange(key, $event)');
  });
});
