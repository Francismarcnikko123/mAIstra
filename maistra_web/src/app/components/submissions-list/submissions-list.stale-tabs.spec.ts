import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SupabaseService } from '../../services/supabase';
import { SubmissionAnswer } from './extra-answers';
import { SubmissionsListComponent } from './submissions-list';

// Two teachers on one paper (code review 2026-09-27, item 9). A save sends
// the whole tab list and the database deletes programs missing from it, so
// a live update that changes the saved programs must either refresh this
// screen's tabs (nothing unsaved) or keep the draft's base revision so the
// next save gets the normal conflict (unsaved tab changes).

const program2: SubmissionAnswer = { code: 'program 2 code', question_id: 'q-2' };
const program3: SubmissionAnswer = { code: 'program 3 code', question_id: 'q-3' };

function row(revision: number, answers: SubmissionAnswer[], extra: Record<string, unknown> = {}) {
  return {
    id: 'paper-1',
    image_url: 'https://example.test/paper.png',
    captured_at: '2026-09-27T09:00:00.000Z',
    status: 'verified',
    question_id: 'q-1',
    verified_text: 'program 1 code',
    grading_revision: revision,
    answers: answers.map((answer) => ({ ...answer })),
    ...extra,
  };
}

function setup() {
  const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
  const getSubmissions = vi.fn();
  const getSubmission = vi.fn().mockResolvedValue({ data: null, error: null });
  // The database answers with the page's next revision, or null on a conflict.
  const updateSubmissionText = vi
    .fn()
    .mockImplementation(async (_id, _text, _ocr, revision: number) => revision + 1);
  const supabase = {
    getSubmissions,
    getSubmission,
    updateSubmissionText,
    answersColumnAvailable: true,
    getQuestionSections: vi.fn().mockResolvedValue({ data: [], error: null }),
    getSectionItems: vi.fn().mockResolvedValue({ data: [], error: null }),
    getGateResults: vi.fn().mockResolvedValue(new Map()),
  } as unknown as SupabaseService;
  const http = { get: vi.fn().mockReturnValue(of({})) } as unknown as HttpClient;
  const component = new SubmissionsListComponent(supabase, http, cdr, {} as Judge0Service);
  return { component, getSubmissions, getSubmission, updateSubmissionText };
}

type Ctx = ReturnType<typeof setup>;

// Loads the paper the way the page does and opens it on the Code step.
async function open(ctx: Ctx, answers: SubmissionAnswer[]) {
  ctx.getSubmissions.mockResolvedValue({ data: [row(4, answers)], error: null });
  await ctx.component.loadSubmissions();
  ctx.component.openModal(ctx.component.submissions[0]);
  ctx.component.reviewStep = 2;
  await Promise.resolve();
}

// A realtime event for the paper: the page refetches that one row.
async function liveUpdate(ctx: Ctx, fresh: ReturnType<typeof row>) {
  ctx.getSubmission.mockResolvedValue({ data: fresh, error: null });
  await (ctx.component as unknown as { refreshSubmission(id: string): Promise<void> })
    .refreshSubmission('paper-1');
}

describe('SubmissionsListComponent program tabs changed by another teacher', () => {
  it('refreshes the tabs when nothing is unsaved, so the next save keeps the new program', async () => {
    const ctx = setup();
    const { component, updateSubmissionText } = ctx;
    await open(ctx, [program2]);

    await liveUpdate(ctx, row(5, [program2, program3]));

    expect(component.getExtraAnswers('paper-1')).toEqual([program2, program3]);
    expect(component.hasUnsavedPrograms('paper-1')).toBe(false);

    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledWith(
      'paper-1',
      'program 1 code',
      undefined,
      5,
      [program2, program3],
    );
    expect(component.saveStatus['paper-1']).toBe('saved');
  });

  it('keeps an unsaved tab edit and its old base revision, so the save conflicts', async () => {
    const ctx = setup();
    const { component, updateSubmissionText } = ctx;
    await open(ctx, [program2]);
    component.selectTab(1);
    component.updateExtraAnswerCode(0, 'edited program 2');

    await liveUpdate(ctx, row(5, [program2, program3]));

    // The draft stays on screen.
    expect(component.getExtraAnswers('paper-1')).toEqual([
      { code: 'edited program 2', question_id: 'q-2' },
    ]);
    expect(component.hasUnsavedPrograms('paper-1')).toBe(true);

    // The save is still based on revision 4, so the database refuses it.
    updateSubmissionText.mockResolvedValueOnce(null);
    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenLastCalledWith(
      'paper-1',
      'program 1 code',
      undefined,
      4,
      [{ code: 'edited program 2', question_id: 'q-2' }],
    );
    expect(component.saveStatus['paper-1']).toBe('conflict');
    expect(component.getExtraAnswers('paper-1')).toEqual([
      { code: 'edited program 2', question_id: 'q-2' },
    ]);

    // After the conflict, a second save replaces the other version knowingly.
    await component.saveVerifiedText();
    expect(updateSubmissionText).toHaveBeenLastCalledWith(
      'paper-1',
      'program 1 code',
      undefined,
      5,
      [{ code: 'edited program 2', question_id: 'q-2' }],
    );
    expect(component.saveStatus['paper-1']).toBe('saved');
  });

  it('keeps the old base revision when a live update arrives later with only a status change', async () => {
    const ctx = setup();
    const { component, updateSubmissionText } = ctx;
    await open(ctx, [program2]);
    component.selectTab(1);
    component.updateExtraAnswerCode(0, 'edited program 2');

    await liveUpdate(ctx, row(5, [program2, program3]));
    await liveUpdate(ctx, row(6, [program2, program3], { status: 'graded' }));

    updateSubmissionText.mockResolvedValueOnce(null);
    await component.saveVerifiedText();

    expect(updateSubmissionText.mock.calls[0][3]).toBe(4);
  });

  it('still advances the base revision when the saved programs did not change', async () => {
    const ctx = setup();
    const { component, updateSubmissionText } = ctx;
    await open(ctx, [program2]);
    component.selectTab(1);
    component.updateExtraAnswerCode(0, 'edited program 2');

    await liveUpdate(ctx, row(5, [program2], { status: 'graded' }));
    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledWith(
      'paper-1',
      'program 1 code',
      undefined,
      5,
      [{ code: 'edited program 2', question_id: 'q-2' }],
    );
    expect(component.saveStatus['paper-1']).toBe('saved');
  });

  it('moves off a tab another teacher removed', async () => {
    const ctx = setup();
    const { component } = ctx;
    await open(ctx, [program2, program3]);
    component.selectTab(2);

    await liveUpdate(ctx, row(5, [program2]));

    expect(component.getExtraAnswers('paper-1')).toEqual([program2]);
    expect(component.activeTab).toBe(1);
  });
});

describe('SubmissionsListComponent save label with unsaved program tabs', () => {
  it('keeps "New changes need to be saved" while a tab edited during the save is unsaved (review 2026-09-27, #3)', async () => {
    vi.useFakeTimers();
    try {
      const ctx = setup();
      const { component, updateSubmissionText } = ctx;
      await open(ctx, [program2]);

      // The save is still running when the teacher types into Program 2.
      let finishSave!: (revision: number) => void;
      updateSubmissionText.mockImplementationOnce(
        () => new Promise<number>((resolve) => { finishSave = resolve; }),
      );
      component.updateSubmissionCode('paper-1', 'program 1 code, edited');
      const saving = component.saveVerifiedText();
      component.updateExtraAnswerCode(0, 'program 2 code, typed during the save');
      finishSave(5);
      await saving;

      expect(component.saveStatusLabel('paper-1')).toBe('New changes need to be saved.');
      await vi.advanceTimersByTimeAsync(3500);
      expect(component.saveStatusLabel('paper-1')).toBe('New changes need to be saved.');
    } finally {
      vi.useRealTimers();
    }
  });

  it('still clears the confirmation after a save with nothing left unsaved', async () => {
    vi.useFakeTimers();
    try {
      const ctx = setup();
      const { component } = ctx;
      await open(ctx, [program2]);

      component.updateSubmissionCode('paper-1', 'program 1 code, edited');
      await component.saveVerifiedText();
      expect(component.saveStatusLabel('paper-1')).not.toBe('');
      await vi.advanceTimersByTimeAsync(3500);
      expect(component.saveStatusLabel('paper-1')).toBe('');
    } finally {
      vi.useRealTimers();
    }
  });
});

