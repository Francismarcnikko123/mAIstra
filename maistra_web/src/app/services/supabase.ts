import { Injectable } from '@angular/core';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { environment } from '../../environment';
import { SubmissionAnswer } from '../components/submissions-list/extra-answers';

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
  /**
   * False once the database reports that submissions.answers doesn't exist,
   * i.e. the program-tabs migration hasn't been applied to it yet. The list
   * still loads without the column; Programs 2..n just can't be saved.
   */
  answersColumnAvailable = true;

  async getSubmissions() {
    if (this.answersColumnAvailable !== false) {
      const result = await this.querySubmissions(`answers, ${SUBMISSION_COLUMNS}`);
      // 42703 = undefined column. Only fall back when it's `answers` that is
      // missing (migration not applied); any other missing column is a real
      // error and is returned as before.
      const answersMissing =
        result.error?.code === '42703' && /\banswers\b/.test(result.error.message ?? '');
      if (!answersMissing) return result;
      this.answersColumnAvailable = false;
    }
    return this.querySubmissions(SUBMISSION_COLUMNS);
  }

  /**
   * One submission, fresh from the database. The review uses it when a paper
   * is opened, to pick up OCR text the auto-extract worker saved after the
   * list was loaded.
   */
  async getSubmission(id: string) {
    const columns: string =
      this.answersColumnAvailable !== false ? `answers, ${SUBMISSION_COLUMNS}` : SUBMISSION_COLUMNS;
    return this.supabase.from('submissions').select(columns).eq('id', id).maybeSingle();
  }

  private querySubmissions(columns: string) {
    return this.supabase
      .from('submissions')
      .select(columns)
      .order('captured_at', { ascending: false });
  }

  async updateSubmissionDetails(
    id: string,
    topic: string,
    questionId: string | null,
  ): Promise<void> {
    const { error } = await this.supabase
      .from('submissions')
      .update({ topic, question_id: questionId })
      .eq('id', id);
    if (error) throw error;
  }

  async updateSubmissionText(
    submissionId: string,
    verifiedText: string,
    extractedText?: string,
    answers?: SubmissionAnswer[],
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
    // Programs 2..n from the review tabs, saved in the same update so they
    // share Program 1's save guards.
    if (answers !== undefined && this.answersColumnAvailable !== false) {
      update['answers'] = answers;
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
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'submissions' }, callback)
      .subscribe();
  }
  
}
