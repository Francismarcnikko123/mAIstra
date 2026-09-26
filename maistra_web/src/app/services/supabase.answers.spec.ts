import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from './supabase';

// Programs 2..n from Nombrado's program tabs. Since 20260926000600 every
// program on a paper is a submission_programs row; this service maps the
// rows back to the `answers` shape ({ code, question_id }) the review
// screen reads, and saves through save_submission_programs().

function serviceWith(client: Record<string, unknown>) {
  const service = Object.create(SupabaseService.prototype) as SupabaseService;
  (service as unknown as { supabase: unknown }).supabase = client;
  service.answersColumnAvailable = true;
  return service;
}

const program = (position: number, questionId: string, code: string) => ({
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
});

const MISSING_PROGRAMS = {
  code: 'PGRST200',
  message:
    "Could not find a relationship between 'submissions' and 'submission_programs' in the schema cache",
};

describe('SupabaseService programs on a paper', () => {
  it('registers separate INSERT and UPDATE callbacks when both are given', () => {
    const channel = { on: vi.fn(), subscribe: vi.fn() };
    channel.on.mockReturnValue(channel);
    const createChannel = vi.fn().mockReturnValue(channel);
    const service = serviceWith({ channel: createChannel });
    const onInsert = vi.fn();
    const onUpdate = vi.fn();

    service.subscribeToSubmissions(onInsert, onUpdate);

    expect(channel.on).toHaveBeenCalledWith(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'submissions' },
      onInsert,
    );
    expect(channel.on).toHaveBeenCalledWith(
      'postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'submissions' },
      onUpdate,
    );
  });

  it('loads every program and hands Programs 2..n to the review as answers', async () => {
    const rows = [
      {
        id: 'paper-1',
        // Out of order on purpose: the database does not sort embedded rows.
        submission_programs: [
          program(3, 'q-3', 'third'),
          program(1, 'q-1', 'first'),
          program(2, 'q-2', 'second'),
        ],
      },
    ];
    const order = vi.fn().mockResolvedValue({ data: rows, error: null });
    const select = vi.fn().mockReturnValue({ order });
    const service = serviceWith({ from: vi.fn().mockReturnValue({ select }) });

    const result = await service.getSubmissions();

    expect(select.mock.calls[0][0]).toContain('submission_programs');
    const [paper] = result.data as Array<Record<string, any>>;
    expect(paper['submission_programs'].map((p: { position: number }) => p.position)).toEqual([
      1, 2, 3,
    ]);
    expect(paper['answers']).toEqual([
      { code: 'second', question_id: 'q-2' },
      { code: 'third', question_id: 'q-3' },
    ]);
  });

  it('loads submissions without programs while the table is missing', async () => {
    const order = vi
      .fn()
      .mockResolvedValueOnce({ data: null, error: MISSING_PROGRAMS })
      .mockResolvedValueOnce({ data: [{ id: 'a' }], error: null });
    const select = vi.fn().mockReturnValue({ order });
    const service = serviceWith({ from: vi.fn().mockReturnValue({ select }) });

    const result = await service.getSubmissions();

    expect(select).toHaveBeenCalledTimes(2);
    expect(select.mock.calls[1][0]).not.toContain('submission_programs');
    expect(result.data).toEqual([{ id: 'a' }]);
    expect(service.answersColumnAvailable).toBe(false);
  });

  it('keeps loading programs when a different error happens', async () => {
    const otherError = { code: '42703', message: 'column submissions.topic does not exist' };
    const select = vi
      .fn()
      .mockReturnValue({ order: vi.fn().mockResolvedValue({ data: null, error: otherError }) });
    const service = serviceWith({ from: vi.fn().mockReturnValue({ select }) });

    const result = await service.getSubmissions();

    expect(select).toHaveBeenCalledTimes(1);
    expect(result.error).toBe(otherError);
    expect(service.answersColumnAvailable).toBe(true);
  });

  it('reads one submission fresh, with its programs while the table exists', async () => {
    const maybeSingle = vi.fn().mockResolvedValue({
      data: { id: 'paper-1', submission_programs: [program(2, 'q-2', 'second')] },
      error: null,
    });
    const eq = vi.fn().mockReturnValue({ maybeSingle });
    const select = vi.fn().mockReturnValue({ eq });
    const service = serviceWith({ from: vi.fn().mockReturnValue({ select }) });

    const result = await service.getSubmission('paper-1');
    expect(select.mock.calls[0][0]).toContain('submission_programs');
    expect(eq).toHaveBeenCalledWith('id', 'paper-1');
    expect((result.data as Record<string, unknown>)['answers']).toEqual([
      { code: 'second', question_id: 'q-2' },
    ]);

    service.answersColumnAvailable = false;
    await service.getSubmission('paper-1');
    expect(select.mock.calls[1][0]).not.toContain('submission_programs');
  });

  it('saves every tab in one guarded call', async () => {
    const rpc = vi.fn().mockResolvedValue({ data: 5, error: null });
    const answers = [{ code: 'int main() {}', question_id: 'q-2' }];

    const revision = await serviceWith({ rpc }).updateSubmissionText(
      'paper-1',
      'program one',
      undefined,
      4,
      answers,
    );

    expect(rpc).toHaveBeenCalledWith('save_submission_programs', {
      p_submission_id: 'paper-1',
      p_grading_revision: 4,
      p_programs: [
        { verified_text: 'program one' },
        { verified_text: 'int main() {}', question_id: 'q-2' },
      ],
      p_extracted_text: null,
      p_replace_all: true,
    });
    expect(revision).toBe(5);
  });

  it('saves only Program 1 when the paper has no tabs, keeping the others', async () => {
    const rpc = vi.fn().mockResolvedValue({ data: 7, error: null });

    await serviceWith({ rpc }).updateSubmissionText('paper-1', 'program one', 'raw OCR', 6);

    expect(rpc).toHaveBeenCalledWith('save_submission_programs', {
      p_submission_id: 'paper-1',
      p_grading_revision: 6,
      p_programs: [{ verified_text: 'program one' }],
      p_extracted_text: 'raw OCR',
      p_replace_all: false,
    });
  });

  it('reports a stale save as null', async () => {
    const rpc = vi.fn().mockResolvedValue({ data: null, error: null });

    const revision = await serviceWith({ rpc }).updateSubmissionText('paper-1', 'x', undefined, 1);

    expect(revision).toBeNull();
  });

  it('saves Program 1 on the page row while the programs table is missing', async () => {
    const query = { eq: vi.fn(), select: vi.fn(), maybeSingle: vi.fn() };
    query.eq.mockReturnValue(query);
    query.select.mockReturnValue(query);
    query.maybeSingle.mockResolvedValue({ data: { grading_revision: 5 }, error: null });
    const update = vi.fn().mockReturnValue(query);
    const rpc = vi.fn();
    const service = serviceWith({ from: vi.fn().mockReturnValue({ update }), rpc });
    service.answersColumnAvailable = false;

    const revision = await service.updateSubmissionText('paper-1', 'program one', undefined, 4, [
      { code: 'lost', question_id: 'q-2' },
    ]);

    expect(rpc).not.toHaveBeenCalled();
    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({ verified_text: 'program one', status: 'verified' }),
    );
    expect(update).toHaveBeenCalledWith(
      expect.not.objectContaining({ answers: expect.anything() }),
    );
    expect(query.eq).toHaveBeenCalledWith('grading_revision', 4);
    expect(revision).toBe(5);
  });

  it('saves one program grade with its own revision guard', async () => {
    const rpc = vi.fn().mockResolvedValue({ data: 3, error: null });
    const results = [{ passed: true }, { passed: false }];

    const revision = await serviceWith({ rpc }).saveProgramGrade(
      'program-2',
      2,
      'q-2',
      'second',
      results,
    );

    expect(rpc).toHaveBeenCalledWith('save_program_grade', {
      p_program_id: 'program-2',
      p_grading_revision: 2,
      p_question_id: 'q-2',
      p_graded_code: 'second',
      p_grading_results: results,
    });
    expect(revision).toBe(3);
  });

  it('links papers to every program question for the question bank', async () => {
    const order = vi.fn().mockResolvedValue({
      data: [{ id: 'paper-1', question_id: 'q-1', submission_programs: [
        { position: 2, question_id: 'q-2', verified_text: 'second' },
      ] }],
      error: null,
    });
    const select = vi.fn().mockReturnValue({ order });
    const service = serviceWith({ from: vi.fn().mockReturnValue({ select }) });

    const result = await service.getQuestionPaperLinks();

    expect(select.mock.calls[0][0]).toContain('submission_programs');
    expect((result.data as Array<Record<string, unknown>>)[0]['answers']).toEqual([
      { code: 'second', question_id: 'q-2' },
    ]);
  });
});
