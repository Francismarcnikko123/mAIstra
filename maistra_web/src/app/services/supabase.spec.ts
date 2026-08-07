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
});
