import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from './supabase';

describe('SupabaseService', () => {
  it('rejects updateSubmissionText when Supabase returns an error', async () => {
    const error = new Error('permission denied');
    const eq = vi.fn().mockResolvedValue({ error });
    const update = vi.fn().mockReturnValue({ eq });
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
    expect(eq).toHaveBeenCalledWith('id', 'submission-1');
  });

  it('leaves extracted_text untouched when no fresh OCR text is provided', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
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

  it('writes extra programs when they are provided', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };

    const answers = [{ code: 'int main() {}', question_id: 'q-2' }];
    await service.updateSubmissionText('submission-1', 'verified text', undefined, answers);

    expect(update).toHaveBeenCalledWith(expect.objectContaining({
      verified_text: 'verified text',
      answers,
    }));
    expect(update).toHaveBeenCalledWith(expect.not.objectContaining({
      extracted_text: expect.anything(),
    }));
  });

  it('leaves answers untouched when none are provided', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };

    await service.updateSubmissionText('submission-1', 'verified text');

    expect(update).toHaveBeenCalledWith(expect.not.objectContaining({
      answers: expect.anything(),
    }));
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
    const from = vi.fn().mockReturnValue({ select });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };
    service.answersColumnAvailable = true;

    const result = await service.getSubmissions();

    expect(select).toHaveBeenCalledTimes(2);
    expect(select.mock.calls[0][0]).toContain('answers');
    expect(select.mock.calls[1][0]).not.toContain('answers');
    expect(result.data).toEqual([{ id: 'a' }]);
    expect(service.answersColumnAvailable).toBe(false);
  });

  it('does not write answers while the column is missing', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };
    service.answersColumnAvailable = false;

    await service.updateSubmissionText('submission-1', 'verified text', undefined, []);

    expect(update).toHaveBeenCalledWith(expect.not.objectContaining({
      answers: expect.anything(),
    }));
  });

  it('keeps the answers column when a different column is missing', async () => {
    const missingTopic = {
      data: null,
      error: { code: '42703', message: 'column submissions.topic does not exist' },
    };
    const order = vi.fn().mockResolvedValue(missingTopic);
    const select = vi.fn().mockReturnValue({ order });
    const from = vi.fn().mockReturnValue({ select });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };
    service.answersColumnAvailable = true;

    const result = await service.getSubmissions();

    expect(select).toHaveBeenCalledTimes(1);
    expect(result.error).toBe(missingTopic.error);
    expect(service.answersColumnAvailable).toBe(true);
  });

  it('reads one submission fresh, including answers while that column exists', async () => {
    const maybeSingle = vi.fn().mockResolvedValue({ data: { id: 'submission-1' }, error: null });
    const eq = vi.fn().mockReturnValue({ maybeSingle });
    const select = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ select });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };

    service.answersColumnAvailable = true;
    await service.getSubmission('submission-1');
    expect(select.mock.calls[0][0]).toMatch(/^answers, /);
    expect(eq).toHaveBeenCalledWith('id', 'submission-1');

    service.answersColumnAvailable = false;
    await service.getSubmission('submission-1');
    expect(select.mock.calls[1][0]).not.toMatch(/answers/);
  });
});
