import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from './supabase';

describe('SupabaseService', () => {
  function createService(from: ReturnType<typeof vi.fn>): SupabaseService {
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };
    return service;
  }

  it('rejects updateSubmissionText when Supabase returns an error', async () => {
    const error = new Error('permission denied');
    const eq = vi.fn().mockResolvedValue({ error });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;

    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };

    await expect(
      service.updateSubmissionText(
        'submission-1',
        'verified text',
        'raw ocr text',
      ),
    ).rejects.toBe(error);
    expect(from).toHaveBeenCalledWith('submissions');
    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({
        extracted_text: 'raw ocr text',
        verified_text: 'verified text',
        status: 'verified',
      }),
    );
    expect(eq).toHaveBeenCalledWith('id', 'submission-1');
  });

  it('leaves extracted_text untouched when no fresh OCR text is provided', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;

    (service as unknown as { supabase: { from: typeof from } }).supabase = {
      from,
    };

    await service.updateSubmissionText('submission-1', 'verified text');
    expect(update).toHaveBeenCalledWith(
      expect.not.objectContaining({
        extracted_text: expect.anything(),
      }),
    );
    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({
        verified_text: 'verified text',
        status: 'verified',
      }),
    );
  });

  it('selects comparison IDs and display relationships with submissions', async () => {
    const order = vi.fn().mockResolvedValue({ data: [], error: null });
    const select = vi.fn().mockReturnValue({ order });
    const from = vi.fn().mockReturnValue({ select });
    const service = createService(from);

    await service.getSubmissions();

    const selection = select.mock.calls[0][0] as string;
    expect(selection).toContain('assessment_id');
    expect(selection).toContain('student_id');
    expect(selection).toContain('block_section_id');
    expect(selection).toContain('verified_version');
    expect(selection).toContain('is_current');
    expect(selection).toContain('assessment_questions');
    expect(selection).toContain('assessment_roster');
    expect(selection).toContain('assessments');
    expect(selection).toContain('students');
    expect(selection).toContain('block_sections');
  });

  it('loads a selected assessment with its assigned questions and roster', async () => {
    const assessments = [
      {
        id: 'assessment-1',
        name: 'Midterm',
        status: 'closed',
        starts_at: null,
      },
    ];
    const assessmentQuestions = [
      {
        assessment_id: 'assessment-1',
        question_id: 'question-1',
        starter_code: '',
        position: 1,
        questions: { id: 'question-1', question_name: 'Loops' },
      },
    ];
    const roster = [
      {
        assessment_id: 'assessment-1',
        student_id: 'student-1',
        block_section_id: 'section-b',
        students: {
          id: 'student-1',
          student_number: '2026-001',
          display_name: 'Ana',
        },
        block_sections: { id: 'section-b', name: 'BSCS 2B' },
      },
    ];

    const assessmentOr = vi
      .fn()
      .mockResolvedValue({ data: assessments, error: null });
    const assessmentOrder = vi.fn().mockReturnValue({ or: assessmentOr });
    const assessmentSelect = vi
      .fn()
      .mockReturnValue({ order: assessmentOrder });

    const questionOrder = vi.fn().mockResolvedValue({
      data: assessmentQuestions,
      error: null,
    });
    const questionEq = vi.fn().mockReturnValue({ order: questionOrder });
    const questionSelect = vi.fn().mockReturnValue({ eq: questionEq });

    const rosterOrder = vi
      .fn()
      .mockResolvedValue({ data: roster, error: null });
    const rosterEq = vi.fn().mockReturnValue({ order: rosterOrder });
    const rosterSelect = vi.fn().mockReturnValue({ eq: rosterEq });

    const from = vi.fn(
      (table: string) =>
        ({
          assessments: { select: assessmentSelect },
          assessment_questions: { select: questionSelect },
          assessment_roster: { select: rosterSelect },
        })[table],
    );
    const service = createService(from);

    await expect(
      service.getSubmissionContextOptions('assessment-1'),
    ).resolves.toEqual({ assessments, assessmentQuestions, roster });
    expect(assessmentOr).toHaveBeenCalledWith(
      'status.eq.active,id.eq.assessment-1',
    );
    expect(questionEq).toHaveBeenCalledWith('assessment_id', 'assessment-1');
    expect(rosterEq).toHaveBeenCalledWith('assessment_id', 'assessment-1');
  });

  it('does not load unbounded question or roster options without an assessment', async () => {
    const assessmentEq = vi.fn().mockResolvedValue({ data: [], error: null });
    const assessmentOrder = vi.fn().mockReturnValue({ eq: assessmentEq });
    const assessmentSelect = vi
      .fn()
      .mockReturnValue({ order: assessmentOrder });
    const from = vi.fn().mockReturnValue({ select: assessmentSelect });
    const service = createService(from);

    await expect(service.getSubmissionContextOptions()).resolves.toEqual({
      assessments: [],
      assessmentQuestions: [],
      roster: [],
    });
    expect(assessmentEq).toHaveBeenCalledWith('status', 'active');
    expect(from).toHaveBeenCalledTimes(1);
  });

  it('rejects context loading when one of the scoped queries fails', async () => {
    const assessmentOr = vi.fn().mockResolvedValue({ data: [], error: null });
    const assessmentOrder = vi.fn().mockReturnValue({ or: assessmentOr });
    const assessmentSelect = vi
      .fn()
      .mockReturnValue({ order: assessmentOrder });

    const questionOrder = vi.fn().mockResolvedValue({ data: [], error: null });
    const questionEq = vi.fn().mockReturnValue({ order: questionOrder });
    const questionSelect = vi.fn().mockReturnValue({ eq: questionEq });

    const error = new Error('roster unavailable');
    const rosterOrder = vi.fn().mockResolvedValue({ data: null, error });
    const rosterEq = vi.fn().mockReturnValue({ order: rosterOrder });
    const rosterSelect = vi.fn().mockReturnValue({ eq: rosterEq });

    const from = vi.fn(
      (table: string) =>
        ({
          assessments: { select: assessmentSelect },
          assessment_questions: { select: questionSelect },
          assessment_roster: { select: rosterSelect },
        })[table],
    );
    const service = createService(from);

    await expect(
      service.getSubmissionContextOptions('assessment-1'),
    ).rejects.toBe(error);
  });

  it('updates all comparison-group details in one write', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const service = createService(from);
    const details = {
      topic: 'Loops',
      assessment_id: 'assessment-1',
      question_id: 'question-1',
      student_id: 'student-1',
      block_section_id: 'section-b',
    };

    await service.updateSubmissionDetails('submission-1', details);

    expect(update).toHaveBeenCalledWith(details);
    expect(eq).toHaveBeenCalledWith('id', 'submission-1');
  });
});
