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
      service.updateSubmissionText('submission-1', 'raw text', 'verified text')
    ).rejects.toBe(error);
    expect(from).toHaveBeenCalledWith('submissions');
    expect(update).toHaveBeenCalledWith(expect.objectContaining({
      extracted_text: 'raw text',
      verified_text: 'verified text',
      status: 'verified'
    }));
    expect(eq).toHaveBeenCalledWith('id', 'submission-1');
  });
});
