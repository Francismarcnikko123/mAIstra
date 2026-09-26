import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from './supabase';

describe('SupabaseService', () => {
  it('subscribes to both inserted and updated submissions', () => {
    const subscription = { unsubscribe: vi.fn() };
    const channel = {
      on: vi.fn(),
      subscribe: vi.fn().mockReturnValue(subscription),
    };
    channel.on.mockReturnValue(channel);
    const supabase = { channel: vi.fn().mockReturnValue(channel) };
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: typeof supabase }).supabase = supabase;
    const callback = vi.fn();

    const result = service.subscribeToSubmissions(callback);

    expect(channel.on).toHaveBeenNthCalledWith(
      1,
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'submissions' },
      callback,
    );
    expect(channel.on).toHaveBeenNthCalledWith(
      2,
      'postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'submissions' },
      callback,
    );
    expect(result).toBe(subscription);
  });

  it('fetches one submission with the same columns as the list', async () => {
    const query = {
      select: vi.fn(),
      eq: vi.fn(),
      order: vi.fn().mockResolvedValue({ data: [], error: null }),
      maybeSingle: vi
        .fn()
        .mockResolvedValue({ data: { id: 'submission-1' }, error: null }),
    };
    query.select.mockReturnValue(query);
    query.eq.mockReturnValue(query);
    const from = vi.fn().mockReturnValue(query);
    const service = Object.create(SupabaseService.prototype) as SupabaseService;

    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };

    await service.getSubmissions();
    const listColumns = query.select.mock.calls[0][0];
    const result = await service.getSubmission('submission-1');

    expect(from).toHaveBeenLastCalledWith('submissions');
    expect(query.select).toHaveBeenLastCalledWith(listColumns);
    expect(query.eq).toHaveBeenCalledWith('id', 'submission-1');
    // Programs 2..n are added as `answers` (see supabase.answers.spec.ts).
    expect(result.data).toMatchObject({ id: 'submission-1', answers: [] });
  });

  function updateService(result: { data: unknown; error: unknown }) {
    const query = {
      eq: vi.fn(),
      select: vi.fn(),
      maybeSingle: vi.fn().mockResolvedValue(result),
    };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    const update = vi.fn().mockReturnValue(query);
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };
    // Code saves update the page row directly only before the
    // submission_programs table exists; with it they go through
    // save_submission_programs() (supabase.answers.spec.ts).
    service.answersColumnAvailable = false;
    return { service, query, update, from };
  }

  it('saves details only while the row is at the expected revision', async () => {
    const { service, query } = updateService({
      data: { grading_revision: 2 },
      error: null,
    });

    const revision = await service.updateSubmissionDetails(
      'submission-1',
      'Loops',
      'question-1',
      1,
    );

    expect(query.eq.mock.calls).toEqual([
      ['id', 'submission-1'],
      ['grading_revision', 1],
    ]);
    expect(query.select).toHaveBeenCalledWith('grading_revision');
    expect(revision).toBe(2);
  });

  it('reports a details save as a conflict when the row moved on', async () => {
    const { service } = updateService({ data: null, error: null });

    const revision = await service.updateSubmissionDetails(
      'submission-1',
      'Loops',
      'question-1',
      1,
    );

    expect(revision).toBeNull();
  });

  it('saves verified code only while the row is at the expected revision', async () => {
    const { service, query } = updateService({
      data: { grading_revision: 3 },
      error: null,
    });

    const revision = await service.updateSubmissionText(
      'submission-1',
      'verified text',
      undefined,
      2,
    );

    expect(query.eq.mock.calls).toEqual([
      ['id', 'submission-1'],
      ['grading_revision', 2],
    ]);
    expect(revision).toBe(3);
  });

  it('reports a code save as a conflict when the row moved on', async () => {
    const { service } = updateService({ data: null, error: null });

    const revision = await service.updateSubmissionText(
      'submission-1',
      'verified text',
      undefined,
      2,
    );

    expect(revision).toBeNull();
  });

  function gradeService(rpcResult: { data: unknown; error: unknown }) {
    const rpc = vi.fn().mockResolvedValue(rpcResult);
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { rpc: typeof rpc } }).supabase = { rpc };
    return { service, rpc };
  }

  it('saves a grade through the stored-code check and returns the new revision', async () => {
    const { service, rpc } = gradeService({ data: 8, error: null });
    const results = [
      { caseNumber: 1, passed: true },
      { caseNumber: 2, passed: false },
    ];

    const saved = await service.updateSubmissionGrade(
      'submission-1',
      results,
      7,
      'question-1',
      'int main(void) { return 0; }',
    );

    expect(rpc).toHaveBeenCalledWith('save_submission_grade', {
      p_submission_id: 'submission-1',
      p_grading_revision: 7,
      p_question_id: 'question-1',
      p_graded_code: 'int main(void) { return 0; }',
      p_grading_results: results,
    });
    expect(saved).toBe(8);
  });

  it('rejects updateSubmissionText when Supabase returns an error', async () => {
    const error = new Error('permission denied');
    const { service, update, from, query } = updateService({ data: null, error });

    await expect(
      service.updateSubmissionText('submission-1', 'verified text', 'raw ocr text', 0),
    ).rejects.toBe(error);
    expect(from).toHaveBeenCalledWith('submissions');
    expect(update).toHaveBeenCalledWith(expect.objectContaining({
      extracted_text: 'raw ocr text',
      verified_text: 'verified text',
      status: 'verified',
    }));
    expect(query.eq).toHaveBeenCalledWith('id', 'submission-1');
  });

  it('leaves extracted_text untouched when no fresh OCR text is provided', async () => {
    const { service, update } = updateService({
      data: { grading_revision: 0 },
      error: null,
    });

    await service.updateSubmissionText('submission-1', 'verified text', undefined, 0);
    expect(update).toHaveBeenCalledWith(expect.not.objectContaining({
      extracted_text: expect.anything(),
    }));
    expect(update).toHaveBeenCalledWith(expect.objectContaining({
      verified_text: 'verified text',
      status: 'verified',
    }));
  });

  it('rejects updateSubmissionGrade when Supabase returns an error', async () => {
    const error = new Error('grade write failed');
    const { service } = gradeService({ data: null, error });

    await expect(
      service.updateSubmissionGrade(
        'submission-1',
        [{ passed: true }],
        4,
        'question-1',
        'code',
      ),
    ).rejects.toBe(error);
  });

  it('reports a grade that no longer matches the stored inputs as not saved', async () => {
    const { service } = gradeService({ data: null, error: null });

    const saved = await service.updateSubmissionGrade(
      'submission-1',
      [{ passed: true }],
      3,
      'question-1',
      'code that differs from the stored code',
    );

    expect(saved).toBeNull();
  });
});
