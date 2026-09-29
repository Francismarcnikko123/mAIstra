import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SubmissionProgramRow, SupabaseService } from '../../services/supabase';
import { SubmissionsListComponent } from './submissions-list';

// Step 3 grades the saved code read-only. "Edit in Review code" takes the
// teacher back to Step 2, on the tab of the program being graded.

function programRow(position: number, questionId: string, code: string): SubmissionProgramRow {
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
  };
}

// As SupabaseService returns it: Programs 2..n also come back as answers.
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
    answers: programs
      .filter((program) => program.position > 1)
      .map((program) => ({ code: program.verified_text, question_id: program.question_id })),
  };
}

function setup() {
  const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
  const getSubmissions = vi.fn();
  const supabase = {
    getSubmissions,
    getSubmission: vi.fn().mockResolvedValue({ data: null, error: null }),
    getQuestionSections: vi.fn().mockResolvedValue({ data: [], error: null }),
    getSectionItems: vi.fn().mockResolvedValue({ data: [], error: null }),
    getGateResults: vi.fn().mockResolvedValue(new Map()),
  } as unknown as SupabaseService;
  const component = new SubmissionsListComponent(
    supabase,
    {} as HttpClient,
    cdr,
    {} as Judge0Service,
  );
  component.questions = [
    { id: 'q-sum', question_name: 'Sum', question_type: 'program', test_cases: [] },
    { id: 'q-max', question_name: 'Max', question_type: 'program', test_cases: [] },
    { id: 'q-min', question_name: 'Min', question_type: 'program', test_cases: [] },
  ];
  return { component, getSubmissions };
}

// Loads the paper the way the page does, then opens it on Step 3.
async function open(
  { component, getSubmissions }: ReturnType<typeof setup>,
  programs: SubmissionProgramRow[],
) {
  getSubmissions.mockResolvedValue({ data: [paper(programs)], error: null });
  await component.loadSubmissions();
  component.openModal(component.submissions[0]);
  component.reviewStep = 3;
  return component.selectedSubmission!;
}

const threePrograms = () => [
  programRow(1, 'q-sum', 'sum code'),
  programRow(2, 'q-max', 'max code'),
  programRow(3, 'q-min', 'min code'),
];

describe('SubmissionsListComponent editing a program from Step 3', () => {
  it('opens Program 1 on the first tab', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, threePrograms());
    component.activeTab = 2; // left on another tab in Review code
    component.selectGradingProgram(selected, 'program-1');

    component.editProgramInReview(selected);

    expect(component.reviewStep).toBe(2);
    expect(component.activeTab).toBe(0);
  });

  it('opens a later program on the tab linked to its question', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, threePrograms());
    // A blank tab is never saved, so here tab numbers and program positions
    // differ: Program 3 (Min) is on tab 3, not tab 2.
    component.extraAnswers['paper-1'].unshift({ code: '', question_id: null });
    component.selectGradingProgram(selected, 'program-3');

    component.editProgramInReview(selected);

    expect(component.reviewStep).toBe(2);
    expect(component.activeTab).toBe(3);
    expect(component.getActiveExtraAnswer()?.question_id).toBe('q-min');
  });

  it('stays on Step 3 while grading is running', async () => {
    const ctx = setup();
    const { component } = ctx;
    const selected = await open(ctx, threePrograms());
    component.selectGradingProgram(selected, 'program-3');
    component.isChecking = true;

    component.editProgramInReview(selected);

    expect(component.reviewStep).toBe(3);
    expect(component.activeTab).toBe(0);
  });
});
