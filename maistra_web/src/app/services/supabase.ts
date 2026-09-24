import { Injectable } from '@angular/core';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { environment } from '../../environment';

const SUBMISSION_COLUMNS = `
  id,
  image_url,
  captured_at,
  status,
  topic,
  student_name,
  extracted_text,
  verified_text,
  question_id,
  grading_results,
  passed_test_cases,
  total_test_cases,
  score_percent,
  graded_at,
  grading_revision,
  questions (
    id,
    question_name,
    question_type,
    model_answer,
    test_cases
  )
`;

@Injectable({
  providedIn: 'root'
})
export class SupabaseService {
  private supabase: SupabaseClient;

  constructor() {
    this.supabase = createClient(environment.supabaseUrl, environment.supabaseKey);
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
    .select(SUBMISSION_COLUMNS)
    .order('captured_at', { ascending: false });
}

  // One row with the same shape as getSubmissions(), so a realtime event can
  // refresh just the submission that changed instead of the whole list.
  async getSubmission(id: string) {
    return await this.supabase
      .from('submissions')
      .select(SUBMISSION_COLUMNS)
      .eq('id', id)
      .maybeSingle();
  }

  // Both edit saves are compare-and-set on grading_revision, which advances
  // whenever the code, the question or the grade changes. They write only while
  // the row is still at expectedRevision (the version the edit started from) and
  // return the new revision, or null when someone else changed it meanwhile.
  async updateSubmissionDetails(
    id: string,
    topic: string,
    questionId: string | null,
    expectedRevision: number,
  ): Promise<number | null> {
    const { data, error } = await this.supabase
      .from('submissions')
      .update({ topic, question_id: questionId })
      .eq('id', id)
      .eq('grading_revision', expectedRevision)
      .select('grading_revision')
      .maybeSingle();
    if (error) throw error;
    return data?.grading_revision ?? null;
  }

  async updateSubmissionText(
    submissionId: string,
    verifiedText: string,
    extractedText: string | undefined,
    expectedRevision: number,
  ): Promise<number | null> {
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
    const { data, error } = await this.supabase
      .from('submissions')
      .update(update)
      .eq('id', submissionId)
      .eq('grading_revision', expectedRevision)
      .select('grading_revision')
      .maybeSingle();
    if (error) throw error;
    return data?.grading_revision ?? null;
  }

  async updateSubmissionGrade(
    submissionId: string,
    results: ReadonlyArray<{ passed: boolean }>,
    gradingRevision: number,
    questionId: string,
    gradedCode: string,
  ): Promise<number | null> {
    // The database saves the grade only while gradedCode is exactly the stored
    // verified_text and the question and revision are unchanged; it derives
    // the pass counts from the results. Returns null when anything differs.
    const { data, error } = await this.supabase.rpc('save_submission_grade', {
      p_submission_id: submissionId,
      p_grading_revision: gradingRevision,
      p_question_id: questionId,
      p_graded_code: gradedCode,
      p_grading_results: results,
    });
    if (error) throw error;
    return data === null || data === undefined ? null : Number(data);
  }

  subscribeToSubmissions(callback: (payload: any) => void) {
    return this.supabase
      .channel('submissions')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'submissions' }, callback)
      .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'submissions' }, callback)
      .subscribe();
  }
  
}
