import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject, of, throwError } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SupabaseService } from '../../services/supabase';
import { Judge0Service } from '../../services/judge0.service';
import {
  SimilarityService,
  SimilaritySummary,
} from '../../services/similarity.service';
import { SubmissionsListComponent } from './submissions-list';

function setup() {
  const api = {
    scanSubmission: vi
      .fn()
      .mockReturnValue(
        of({ status: 'complete', submission_id: 'a', matches: [] }),
      ),
    getSubmissionSimilarity: vi
      .fn()
      .mockReturnValue(of({ status: 'not_checked', submission_id: 'a' })),
    getMatchDetail: vi.fn(),
  };
  const save = vi.fn().mockResolvedValue(undefined);
  const cdr = { detectChanges: vi.fn() };
  const component = new SubmissionsListComponent(
    {
      updateSubmissionText: save,
      getSubmissionContextOptions: vi.fn().mockResolvedValue({
        assessments: [],
        assessmentQuestions: [],
        roster: [],
      }),
    } as unknown as SupabaseService,
    {} as HttpClient,
    cdr as unknown as ChangeDetectorRef,
    {} as Judge0Service,
    api as unknown as SimilarityService,
  );
  component.selectedSubmission = {
    id: 'a',
    image_url: 'image',
    captured_at: '',
    verified_version: 1,
    is_current: true,
    verified_text: 'old',
    assessment_id: 'assessment',
    question_id: 'question',
    student_id: 'student',
    block_section_id: 'section',
  };
  component.selectedAssessmentId = 'assessment';
  component.selectedQuestionId = 'question';
  component.selectedStudentId = 'student';
  component.selectedBlockSectionId = 'section';
  component.questions = [
    {
      id: 'question',
      question_name: 'Q',
      question_type: 'program',
      model_answer: '',
      test_cases: [
        { test_code: '', test_input: '', expected_output: '', mark: 1 },
      ],
    },
  ];
  component.editableText['a'] = 'new';
  return { component, api, save, cdr };
}

describe('Similarity workflow', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('invalidates an older scan as soon as a new save starts', async () => {
    vi.useFakeTimers();
    const { component, api, save } = setup();
    component.editableText['a'] = 'old';
    const pending = new Subject<SimilaritySummary>();
    api.scanSubmission.mockReturnValue(pending);
    const check = component.refreshSimilarity('a', true);
    let finish!: () => void;
    save.mockReturnValue(
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
    );
    const saving = component.saveVerifiedText();
    pending.next({ status: 'complete', submission_id: 'a' });
    await check;
    expect(component.similarityState['a']).not.toBe('complete');
    finish();
    await saving;
    component.ngOnDestroy();
  });

  it('loads a match once when it is collapsed and expanded again', async () => {
    const { component, api } = setup();
    component.similarityState['a'] = 'complete';
    component.similaritySummary['a'] = {
      status: 'complete',
      submission_id: 'a',
      scan_id: 'scan',
    };
    api.getMatchDetail.mockReturnValue(
      of({
        scan_id: 'scan',
        submission_code: 'old',
        peer_code: 'peer',
        submission_ranges: [],
        peer_ranges: [],
      }),
    );
    await component.inspectSimilarityMatch('a', 'b');
    await component.inspectSimilarityMatch('a', 'b');
    await component.inspectSimilarityMatch('a', 'b');
    expect(api.getMatchDetail).toHaveBeenCalledOnce();
  });

  it('refreshes a persisted pending scan until it completes', async () => {
    vi.useFakeTimers();
    const { component, api } = setup();
    component.editableText['a'] = 'old';
    api.getSubmissionSimilarity
      .mockReturnValueOnce(of({ status: 'checking', submission_id: 'a' }))
      .mockReturnValueOnce(of({ status: 'complete', submission_id: 'a' }));
    await component.refreshSimilarity('a');
    await vi.advanceTimersByTimeAsync(3000);
    expect(component.similarityState['a']).toBe('complete');
    component.ngOnDestroy();
  });

  it('enters grading after save without waiting for the similarity scan', async () => {
    vi.useFakeTimers();
    const { component, api } = setup();
    api.scanSubmission.mockReturnValue(new Subject<SimilaritySummary>());
    await component.saveCodeAndContinue();
    expect(component.reviewStep).toBe(3);
    expect(api.scanSubmission).toHaveBeenCalledWith('a');
    expect(api.scanSubmission.mock.calls[0]).toHaveLength(1);
    expect(component.similarityState['a']).toBe('checking');
    component.ngOnDestroy();
  });

  it('does not scan after a failed code save', async () => {
    const { component, api, save } = setup();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    save.mockRejectedValue(new Error('offline'));
    await component.saveCodeAndContinue();
    expect(api.scanSubmission).not.toHaveBeenCalled();
    expect(component.reviewStep).not.toBe(3);
  });

  it('allows grading and finishing when similarity fails', async () => {
    const { component, api } = setup();
    component.editableText['a'] = 'old';
    api.scanSubmission.mockReturnValue(throwError(() => new Error('offline')));
    await component.refreshSimilarity('a', true);
    expect(component.similarityState['a']).toBe('unavailable');
    expect(component.canOpenGradingStep()).toBe(true);
    component.closeModal();
    expect(component.selectedSubmission).toBeNull();
  });

  it('marks unsaved changes outdated and refuses to scan editor text', async () => {
    const { component, api } = setup();
    component.similarityState['a'] = 'complete';
    component.updateSubmissionCode('a', 'unsaved');
    await component.refreshSimilarity('a', true);
    expect(component.similarityState['a']).toBe('outdated');
    expect(api.scanSubmission).not.toHaveBeenCalled();
  });

  it('ignores scan completion after a newer edit or destruction', async () => {
    const { component, api, cdr } = setup();
    component.editableText['a'] = 'old';
    const pending = new Subject<SimilaritySummary>();
    api.scanSubmission.mockReturnValue(pending);
    const work = component.refreshSimilarity('a', true);
    component.updateSubmissionCode('a', 'new edit');
    pending.next({ status: 'complete', submission_id: 'a' });
    await work;
    expect(component.similarityState['a']).toBe('outdated');
    component.editableText['a'] = 'old';
    const second = new Subject<SimilaritySummary>();
    api.scanSubmission.mockReturnValue(second);
    const later = component.refreshSimilarity('a', true);
    component.ngOnDestroy();
    cdr.detectChanges.mockClear();
    second.next({ status: 'complete', submission_id: 'a' });
    await later;
    expect(cdr.detectChanges).not.toHaveBeenCalled();
  });

  it('loads persisted findings on reopening a submission', async () => {
    const { component, api } = setup();
    component.editableText['a'] = 'old';
    component.openModal(component.selectedSubmission!);
    await Promise.resolve();
    expect(api.getSubmissionSimilarity).toHaveBeenCalledWith('a');
    expect(component.similarityState['a']).toBe('not_checked');
  });

  it('requires saved group metadata and ignores findings after a group change', async () => {
    const { component, api } = setup();
    component.editableText['a'] = 'old';
    component.onSelectedStudentChange('other');
    await component.refreshSimilarity('a', true);
    expect(api.scanSubmission).not.toHaveBeenCalled();
    expect(component.similarityState['a']).toBe('missing_metadata');
  });

  it('does not allow Run & grade to bypass unsaved comparison details', () => {
    const { component } = setup();
    component.reviewStep = 1;
    component.selectedStudentId = 'different-student';

    component.setReviewStep(3);

    expect(component.reviewStep).toBe(1);
  });

  it('ignores a pending summary after the review modal closes', async () => {
    const { component, api } = setup();
    component.editableText['a'] = 'old';
    const pending = new Subject<SimilaritySummary>();
    api.getSubmissionSimilarity.mockReturnValue(pending);
    const request = component.refreshSimilarity('a');

    component.closeModal();
    pending.next({ status: 'complete', submission_id: 'a' });
    await request;

    expect(component.similarityState['a']).not.toBe('complete');
  });
});
