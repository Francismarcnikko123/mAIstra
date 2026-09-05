import { Injectable } from '@angular/core';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { environment } from '../../environment';
import {
  Assessment,
  AssessmentQuestion,
  AssessmentRosterEntry,
  SubmissionContextOptions,
  SubmissionDetailsUpdate,
} from '../models/submission.models';

@Injectable({
  providedIn: 'root',
})
export class SupabaseService {
  private supabase: SupabaseClient;

  constructor() {
    this.supabase = createClient(
      environment.supabaseUrl,
      environment.supabaseKey,
    );
  }

  // ── QUESTIONS ──────────────────────────────────────────
  async saveQuestion(question: any) {
    return await this.supabase
      .from('questions')
      .insert([question])
      .select()
      .single();
  }

  async getQuestions() {
    return await this.supabase
      .from('questions')
      .select('*')
      .order('created_at', { ascending: false });
  }

  // ── SUBMISSIONS ─────────────────────────────────────────
  async getSubmissions() {
    return await this.supabase
      .from('submissions')
      .select(
        `
        id,
        image_url,
        captured_at,
        status,
        topic,
        student_name,
        extracted_text,
        verified_text,
        verified_version,
        is_current,
        assessment_id,
        question_id,
        student_id,
        block_section_id,
        questions (
          id,
          question_name,
          question_type,
          model_answer,
          test_cases
        ),
        assessment_questions!submissions_assessment_question_fkey (
          assessments (
            id,
            name,
            status,
            starts_at
          )
        ),
        assessment_roster!submissions_assessment_roster_fkey (
          students (
            id,
            student_number,
            display_name
          ),
          block_sections (
            id,
            name
          )
        )
      `,
      )
      .order('captured_at', { ascending: false });
  }

  async getSubmissionContextOptions(
    assessmentId?: string,
  ): Promise<SubmissionContextOptions> {
    const assessmentQuery = this.supabase
      .from('assessments')
      .select('id, name, status, starts_at')
      .order('starts_at', { ascending: false, nullsFirst: false });

    const assessmentRequest = assessmentId
      ? assessmentQuery.or(`status.eq.active,id.eq.${assessmentId}`)
      : assessmentQuery.eq('status', 'active');

    if (!assessmentId) {
      const { data, error } = await assessmentRequest;
      if (error) throw error;
      return {
        assessments: (data ?? []) as Assessment[],
        assessmentQuestions: [],
        roster: [],
      };
    }

    const [assessmentResult, questionResult, rosterResult] = await Promise.all([
      assessmentRequest,
      this.supabase
        .from('assessment_questions')
        .select(
          `
          assessment_id,
          question_id,
          starter_code,
          position,
          questions (
            id,
            question_name,
            question_type,
            model_answer,
            test_cases
          )
        `,
        )
        .eq('assessment_id', assessmentId)
        .order('position', { ascending: true }),
      this.supabase
        .from('assessment_roster')
        .select(
          `
          assessment_id,
          student_id,
          block_section_id,
          students (
            id,
            student_number,
            display_name
          ),
          block_sections (
            id,
            name
          )
        `,
        )
        .eq('assessment_id', assessmentId)
        .order('student_id', { ascending: true }),
    ]);

    for (const result of [assessmentResult, questionResult, rosterResult]) {
      if (result.error) throw result.error;
    }

    return {
      assessments: (assessmentResult.data ?? []) as Assessment[],
      assessmentQuestions: (questionResult.data ??
        []) as unknown as AssessmentQuestion[],
      roster: (rosterResult.data ?? []) as unknown as AssessmentRosterEntry[],
    };
  }

  async updateSubmissionDetails(
    id: string,
    details: SubmissionDetailsUpdate,
  ): Promise<void> {
    const { error } = await this.supabase
      .from('submissions')
      .update(details)
      .eq('id', id);
    if (error) throw error;
  }

  async updateSubmissionText(
    submissionId: string,
    verifiedText: string,
    extractedText?: string,
  ): Promise<void> {
    // extracted_text must keep the OCR's own output (it is the baseline the
    // verified text is compared against), so it is only written when a fresh
    // extraction produced it — never overwritten with the teacher's edits.
    const update: Record<string, unknown> = {
      verified_text: verifiedText,
      status: 'verified',
      verified_at: new Date().toISOString(),
    };
    if (extractedText !== undefined) {
      update['extracted_text'] = extractedText;
    }
    const { error } = await this.supabase
      .from('submissions')
      .update(update)
      .eq('id', submissionId);
    if (error) throw error;
  }

  subscribeToSubmissions(callback: (payload: any) => void) {
    return this.supabase
      .channel('submissions')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'submissions' },
        callback,
      )
      .subscribe();
  }
}
