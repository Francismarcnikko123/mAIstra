import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from './supabase';

describe('SupabaseService', () => {
  /** A PostgREST query builder that records every filter. */
  function recordingQuery(result: unknown) {
    const calls: Array<[string, ...unknown[]]> = [];
    const query: any = {};
    for (const method of ['update', 'eq', 'is', 'not', 'select']) {
      query[method] = (...args: unknown[]) => {
        calls.push([method, ...args]);
        return method === 'select' ? Promise.resolve(result) : query;
      };
    }
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: unknown }).supabase = { from: vi.fn().mockReturnValue(query) };
    return { service, calls };
  }

  const stored = {
    question_name: 'Sum',
    question_text: 'Add.',
    question_type: 'program',
    model_answer: 'int main(void) { return 0; }',
    test_cases: [{ test_input: '2 3', expected_output: '5', mark: 5 }],
  };

  it('updates a question only while it still holds what the form loaded (#2)', async () => {
    const { service, calls } = recordingQuery({ data: [{ id: 'q1' }], error: null });

    const result = await service.updateQuestion('q1', { question_name: 'Sum 2' }, stored);

    expect(result).toEqual({ error: null, conflict: false });
    expect(calls).toContainEqual(['update', { question_name: 'Sum 2' }]);
    expect(calls).toContainEqual(['eq', 'id', 'q1']);
    expect(calls).toContainEqual(['eq', 'question_name', 'Sum']);
    expect(calls).toContainEqual(['eq', 'test_cases', JSON.stringify(stored.test_cases)]);
  });

  it('reports a question update that matched no row as a conflict (#2)', async () => {
    const { service } = recordingQuery({ data: [], error: null });

    const result = await service.updateQuestion('q1', { question_name: 'Sum 2' }, stored);

    expect(result.conflict).toBe(true);
  });

  it('marks validated only the content that was validated (#2)', async () => {
    const { service, calls } = recordingQuery({ data: [{ id: 'q1' }], error: null });

    await service.markQuestionValidated('q1', {
      model_answer: stored.model_answer,
      test_cases: stored.test_cases,
      question_type: 'program',
    });

    expect(calls).toContainEqual(['update', { can_publish: true }]);
    expect(calls).toContainEqual(['eq', 'model_answer', stored.model_answer]);
    expect(calls).toContainEqual(['eq', 'question_type', 'program']);
  });

  it('counts graded papers with both queries at once, asking only for graded programs (#9)', async () => {
    const pages = { data: [{ id: 'p1' }], error: null };
    const programs = { data: [{ submission_id: 'p1' }, { submission_id: 'p2' }], error: null };
    const order: string[] = [];
    const query = (table: string, result: unknown) => {
      const q: any = {};
      q.select = () => q;
      q.not = (...args: unknown[]) => {
        order.push(`not ${args.join(' ')}`);
        return q;
      };
      q.eq = () => q;
      q.then = (resolve: (value: unknown) => void) => {
        order.push(`resolved ${table}`);
        return Promise.resolve(result).then(resolve);
      };
      order.push(`started ${table}`);
      return q;
    };
    const from = vi.fn((table: string) => query(table, table === 'submissions' ? pages : programs));
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: unknown }).supabase = { from };

    expect(await service.countGradedPapers('q1')).toBe(2);
    expect(order.indexOf('started submission_programs')).toBeLessThan(order.indexOf('resolved submissions'));
    expect(order).toContain('not graded_at is ');
  });

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
