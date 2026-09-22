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

  it('returns the new grading revision after submission details change', async () => {
    const query = {
      eq: vi.fn(),
      select: vi.fn(),
      single: vi.fn().mockResolvedValue({
        data: { grading_revision: 2 },
        error: null,
      }),
    };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    const update = vi.fn().mockReturnValue(query);
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;

    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };

    const revision = await service.updateSubmissionDetails(
      'submission-1',
      'Loops',
      'question-1',
    );

    expect(query.select).toHaveBeenCalledWith('grading_revision');
    expect(revision).toBe(2);
  });

  it('returns the new grading revision after verified code changes', async () => {
    const query = {
      eq: vi.fn(),
      select: vi.fn(),
      single: vi.fn().mockResolvedValue({
        data: { grading_revision: 3 },
        error: null,
      }),
    };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    const update = vi.fn().mockReturnValue(query);
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;

    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };

    const revision = await service.updateSubmissionText(
      'submission-1',
      'verified text',
    );

    expect(query.select).toHaveBeenCalledWith('grading_revision');
    expect(revision).toBe(3);
  });

  it('persists a completed grade and marks the submission graded', async () => {
    const query = {
      eq: vi.fn(),
      select: vi.fn(),
      maybeSingle: vi.fn().mockResolvedValue({
        data: { grading_revision: 8 },
        error: null,
      }),
    };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    const update = vi.fn().mockReturnValue(query);
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    const updateSubmissionGrade = (
      service as unknown as {
        updateSubmissionGrade?: (
          id: string,
          results: unknown[],
          gradingRevision: number,
          questionId: string,
        ) => Promise<number | null>;
      }
    ).updateSubmissionGrade;

    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };

    expect(typeof updateSubmissionGrade).toBe('function');

    const results = [
      { caseNumber: 1, passed: true },
      { caseNumber: 2, passed: true },
      { caseNumber: 3, passed: true },
      { caseNumber: 4, passed: false },
    ];
    const saved = await updateSubmissionGrade!.call(
      service,
      'submission-1',
      results,
      7,
      'question-1',
    );

    expect(from).toHaveBeenCalledWith('submissions');
    expect(update).toHaveBeenCalledWith({
      grading_results: results,
      passed_test_cases: 3,
      total_test_cases: 4,
      graded_at: expect.any(String),
      status: 'graded',
    });
    expect(query.eq.mock.calls).toEqual([
      ['id', 'submission-1'],
      ['grading_revision', 7],
      ['question_id', 'question-1'],
    ]);
    expect(query.select).toHaveBeenCalledWith('grading_revision');
    expect(saved).toBe(8);
  });

  it('rejects updateSubmissionText when Supabase returns an error', async () => {
    const error = new Error('permission denied');
    const query = {
      eq: vi.fn(),
      select: vi.fn(),
      single: vi.fn().mockResolvedValue({ data: null, error }),
    };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    const update = vi.fn().mockReturnValue(query);
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;

    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };

    await expect(
      service.updateSubmissionText('submission-1', 'verified text', 'raw ocr text')
    ).rejects.toBe(error);
    expect(from).toHaveBeenCalledWith('submissions');
    expect(update).toHaveBeenCalledWith(expect.objectContaining({
      extracted_text: 'raw ocr text',
      verified_text: 'verified text',
      status: 'verified'
    }));
    expect(query.eq).toHaveBeenCalledWith('id', 'submission-1');
  });

  it('leaves extracted_text untouched when no fresh OCR text is provided', async () => {
    const query = {
      eq: vi.fn(),
      select: vi.fn(),
      single: vi.fn().mockResolvedValue({
        data: { grading_revision: 0 },
        error: null,
      }),
    };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    const update = vi.fn().mockReturnValue(query);
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;

    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };

    await service.updateSubmissionText('submission-1', 'verified text');
    expect(update).toHaveBeenCalledWith(expect.not.objectContaining({
      extracted_text: expect.anything()
    }));
    expect(update).toHaveBeenCalledWith(expect.objectContaining({
      verified_text: 'verified text',
      status: 'verified'
    }));
  });

  it('rejects updateSubmissionGrade when Supabase returns an error', async () => {
    const error = new Error('grade write failed');
    const query = {
      eq: vi.fn(),
      select: vi.fn(),
      maybeSingle: vi.fn().mockResolvedValue({ data: null, error }),
    };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    const update = vi.fn().mockReturnValue(query);
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    const updateSubmissionGrade = (
      service as unknown as {
        updateSubmissionGrade?: (
          id: string,
          results: unknown[],
          gradingRevision: number,
          questionId: string,
        ) => Promise<number | null>;
      }
    ).updateSubmissionGrade;

    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };

    expect(typeof updateSubmissionGrade).toBe('function');
    await expect(
      updateSubmissionGrade!.call(service, 'submission-1', [
        { caseNumber: 1, passed: true },
      ], 4, 'question-1'),
    ).rejects.toBe(error);
  });

  it('rejects a stale grade when the persisted inputs have changed', async () => {
    const query = {
      eq: vi.fn(),
      select: vi.fn(),
      maybeSingle: vi.fn().mockResolvedValue({ data: null, error: null }),
    };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    const update = vi.fn().mockReturnValue(query);
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;

    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };

    const saved = await (
      service.updateSubmissionGrade as unknown as (
        id: string,
        results: unknown[],
        gradingRevision: number,
        questionId: string,
      ) => Promise<number | null>
    ).call(
      service,
      'submission-1',
      [{ caseNumber: 1, passed: true }],
      3,
      'question-1',
    );

    expect(saved).toBeNull();
  });
});
