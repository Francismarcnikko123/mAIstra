import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SupabaseService } from '../../services/supabase';
import { SubmissionsListComponent } from './submissions-list';

const paper = (overrides: Record<string, unknown> = {}) => ({
  id: 'paper-1', image_url: 'image', captured_at: '2026-09-24T10:10:00Z',
  extracted_text: '', verified_text: '', status: 'new', ...overrides,
});

function makeComponent(options: {
  health?: ReturnType<typeof vi.fn>;
  getSubmission?: ReturnType<typeof vi.fn>;
} = {}) {
  let onUpdate: ((payload: { new: ReturnType<typeof paper> }) => void) | undefined;
  const unsubscribe = vi.fn();
  const get = options.health ?? vi.fn().mockReturnValue(of({ auto_extract: {
    enabled: true, since: '2026-09-24T10:09:00Z', failed: [],
  } }));
  const supabase = {
    getQuestions: vi.fn().mockResolvedValue({ data: [], error: null }),
    getSubmissions: vi.fn().mockResolvedValue({ data: [paper()], error: null }),
    getSubmission: options.getSubmission ?? vi.fn().mockResolvedValue({ data: null, error: null }),
    subscribeToSubmissions: vi.fn((_onInsert, update) => {
      onUpdate = update;
      return { unsubscribe };
    }),
    answersColumnAvailable: true,
  };
  const component = new SubmissionsListComponent(
    supabase as unknown as SupabaseService,
    { get } as unknown as HttpClient,
    { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
    {} as Judge0Service,
  );
  return { component, get, supabase, unsubscribe, update: (row: ReturnType<typeof paper>) => onUpdate!({ new: row }) };
}

afterEach(() => vi.useRealTimers());

describe('auto-extraction status in the submissions list', () => {
  it('checks on init, after reload, and every 30 seconds; clears the timer on destroy', async () => {
    vi.useFakeTimers();
    const { component, get, unsubscribe } = makeComponent();
    await component.ngOnInit();
    expect(get).toHaveBeenCalledTimes(2);
    expect(component.autoExtract.enabled).toBe(true);

    await vi.advanceTimersByTimeAsync(30_000);
    expect(get).toHaveBeenCalledTimes(3);
    component.ngOnDestroy();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(get).toHaveBeenCalledTimes(3);
    expect(unsubscribe).toHaveBeenCalledOnce();
  });

  it('treats an off or unreachable server as disabled', async () => {
    const health = vi.fn().mockReturnValueOnce(of({ auto_extract: { enabled: false } }))
      .mockReturnValueOnce(throwError(() => new Error('offline')));
    const { component } = makeComponent({ health });
    await component.checkOcrServer();
    expect(component.autoExtract.enabled).toBe(false);
    component.autoExtract.enabled = true;
    await component.checkOcrServer();
    expect(component.autoExtract.enabled).toBe(false);
  });

  it('shows Extracting only for unread papers after the worker start and outside its failed set', async () => {
    const { component } = makeComponent();
    await component.checkOcrServer();
    const newPaper = paper();
    expect(component.getSubmissionStatusLabel(newPaper)).toBe('Extracting…');
    expect(component.getSubmissionStatus(newPaper)).toBe('new');
    expect(component.getSubmissionStatusLabel(paper({ captured_at: '2026-09-24T10:08:00Z' }))).toBe('Needs OCR');
    component.autoExtract.failed.add('paper-1');
    expect(component.getSubmissionStatusLabel(newPaper)).toBe('Needs OCR');
    component.autoExtract.failed.clear();
    expect(component.getSubmissionStatusLabel(paper({ extracted_text: 'OCR' }))).toBe('Needs review');
    expect(component.getSubmissionStatusLabel(paper({ verified_text: 'teacher' }))).toBe('Ready to grade');
  });

  it('merges a worker UPDATE into an empty row and editor without making it unsaved', async () => {
    const { component, update } = makeComponent();
    await component.ngOnInit();
    update(paper({ extracted_text: 'OCR text', status: 'extracted' }));
    expect(component.submissions[0].extracted_text).toBe('OCR text');
    expect(component.getSubmissionStatusLabel(component.submissions[0])).toBe('Needs review');
    expect(component.editableText['paper-1']).toBe('OCR text');
    expect(component.isProgram1Unsaved('paper-1')).toBe(false);
    component.ngOnDestroy();
  });

  it('never replaces teacher edits, verified text, or program tabs on UPDATE', async () => {
    const { component, update } = makeComponent();
    await component.ngOnInit();
    component.openModal(component.submissions[0]);
    component.updateSubmissionCode('paper-1', 'teacher edit');
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'program two');
    component.selectedSubmission!.verified_text = 'teacher verified';
    update(paper({ extracted_text: 'OCR text', verified_text: 'incoming verified', status: 'extracted' }));

    expect(component.submissions[0].extracted_text).toBe('OCR text');
    expect(component.selectedSubmission!.extracted_text).toBe('OCR text');
    expect(component.selectedSubmission!.verified_text).toBe('teacher verified');
    expect(component.editableText['paper-1']).toBe('teacher edit');
    expect(component.getExtraAnswers('paper-1')[0].code).toBe('program two');
    expect(component.isProgram1Unsaved('paper-1')).toBe(true);
    component.ngOnDestroy();
  });

  it('uses the same merge when an opened paper is re-read', async () => {
    const getSubmission = vi.fn().mockResolvedValue({
      data: paper({ extracted_text: 'fresh OCR', status: 'extracted' }), error: null,
    });
    const { component } = makeComponent({ getSubmission });
    await component.loadSubmissions();
    component.openModal(component.submissions[0]);
    await vi.waitFor(() => expect(component.selectedSubmission!.extracted_text).toBe('fresh OCR'));
    expect(component.submissions[0].extracted_text).toBe('fresh OCR');
    expect(component.editableText['paper-1']).toBe('fresh OCR');
    expect(component.isProgram1Unsaved('paper-1')).toBe(false);
  });
});
