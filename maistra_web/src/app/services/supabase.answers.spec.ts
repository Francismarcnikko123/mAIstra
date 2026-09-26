import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from './supabase';

// Programs 2..n (submissions.answers) from Nombrado's program tabs and
// pre-extraction, on top of Jayrald's revision-guarded saves. Carried over
// from the pre-extraction branch's supabase.spec.ts when the two merged.

function serviceWith(from: ReturnType<typeof vi.fn>) {
  const service = Object.create(SupabaseService.prototype) as SupabaseService;
  (service as unknown as { supabase: { from: typeof from } }).supabase = { from };
  service.answersColumnAvailable = true;
  return service;
}

/** update().eq('id').eq('grading_revision').select().maybeSingle() */
function updateChain(result = { data: { grading_revision: 5 }, error: null }) {
  const query = {
    eq: vi.fn(),
    select: vi.fn(),
    maybeSingle: vi.fn().mockResolvedValue(result),
  };
  query.eq.mockReturnValue(query);
  query.select.mockReturnValue(query);
  const update = vi.fn().mockReturnValue(query);
  const from = vi.fn().mockReturnValue({ update });
  return { from, update, query };
}

describe('SupabaseService program answers', () => {
  it('registers separate INSERT and UPDATE callbacks when both are given', () => {
    const channel = { on: vi.fn(), subscribe: vi.fn() };
    channel.on.mockReturnValue(channel);
    const createChannel = vi.fn().mockReturnValue(channel);
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { channel: typeof createChannel } }).supabase = {
      channel: createChannel,
    };
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

  it('writes extra programs under the same revision guard', async () => {
    const { from, update, query } = updateChain();
    const answers = [{ code: 'int main() {}', question_id: 'q-2' }];

    const revision = await serviceWith(from).updateSubmissionText(
      'submission-1',
      'verified text',
      undefined,
      4,
      answers,
    );

    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({ verified_text: 'verified text', answers }),
    );
    expect(update).toHaveBeenCalledWith(
      expect.not.objectContaining({ extracted_text: expect.anything() }),
    );
    expect(query.eq).toHaveBeenCalledWith('grading_revision', 4);
    expect(revision).toBe(5);
  });

  it('leaves answers untouched when none are provided', async () => {
    const { from, update } = updateChain();

    await serviceWith(from).updateSubmissionText('submission-1', 'verified text', undefined, 4);

    expect(update).toHaveBeenCalledWith(
      expect.not.objectContaining({ answers: expect.anything() }),
    );
  });

  it('does not write answers while the column is missing', async () => {
    const { from, update } = updateChain();
    const service = serviceWith(from);
    service.answersColumnAvailable = false;

    await service.updateSubmissionText('submission-1', 'verified text', undefined, 4, []);

    expect(update).toHaveBeenCalledWith(
      expect.not.objectContaining({ answers: expect.anything() }),
    );
  });

  it('loads submissions without answers when the column is missing', async () => {
    const order = vi
      .fn()
      .mockResolvedValueOnce({
        data: null,
        error: { code: '42703', message: 'column submissions.answers does not exist' },
      })
      .mockResolvedValueOnce({ data: [{ id: 'a' }], error: null });
    const select = vi.fn().mockReturnValue({ order });
    const service = serviceWith(vi.fn().mockReturnValue({ select }));

    const result = await service.getSubmissions();

    expect(select).toHaveBeenCalledTimes(2);
    expect(select.mock.calls[0][0]).toContain('answers');
    expect(select.mock.calls[1][0]).not.toContain('answers');
    expect(result.data).toEqual([{ id: 'a' }]);
    expect(service.answersColumnAvailable).toBe(false);
  });

  it('keeps the answers column when a different column is missing', async () => {
    const missingTopic = {
      data: null,
      error: { code: '42703', message: 'column submissions.topic does not exist' },
    };
    const select = vi.fn().mockReturnValue({ order: vi.fn().mockResolvedValue(missingTopic) });
    const service = serviceWith(vi.fn().mockReturnValue({ select }));

    const result = await service.getSubmissions();

    expect(select).toHaveBeenCalledTimes(1);
    expect(result.error).toBe(missingTopic.error);
    expect(service.answersColumnAvailable).toBe(true);
  });

  it('reads one submission fresh, including answers while that column exists', async () => {
    const maybeSingle = vi.fn().mockResolvedValue({ data: { id: 'submission-1' }, error: null });
    const eq = vi.fn().mockReturnValue({ maybeSingle });
    const select = vi.fn().mockReturnValue({ eq });
    const service = serviceWith(vi.fn().mockReturnValue({ select }));

    await service.getSubmission('submission-1');
    expect(select.mock.calls[0][0]).toMatch(/^answers, /);
    expect(eq).toHaveBeenCalledWith('id', 'submission-1');

    service.answersColumnAvailable = false;
    await service.getSubmission('submission-1');
    expect(select.mock.calls[1][0]).not.toMatch(/answers/);
  });
});
