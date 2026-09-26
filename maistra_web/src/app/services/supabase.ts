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

  // ── QUESTION SECTIONS (Nikko) ───────────────────────────
  // Tables from supabase/migrations/20260924000000_add_question_sections.sql.

  async getQuestionSections() {
    return await this.supabase
      .from('question_sections')
      .select('id, name, position')
      .order('position')
      .order('name');
  }

  async createQuestionSection(name: string) {
    return await this.supabase
      .from('question_sections')
      .insert([{ name }])
      .select('id, name, position')
      .single();
  }

  /** Question numbers already used in one section. */
  async getSectionNumbers(sectionId: string) {
    return await this.supabase
      .from('question_section_items')
      .select('number')
      .eq('section_id', sectionId);
  }

  async addQuestionToSection(questionId: string, sectionId: string, number: number) {
    return await this.supabase
      .from('question_section_items')
      .insert([{ section_id: sectionId, question_id: questionId, number }]);
  }

  /** Every question's section and number, for the question bank. */
  async getSectionItems() {
    return await this.supabase
      .from('question_section_items')
      .select('section_id, question_id, number');
  }

  /**
   * Which questions each paper is linked to, for the bank's paper counts and
   * the question page's linked papers. Falls back to Program 1 only while
   * submissions.answers is missing.
   */
  async getQuestionPaperLinks() {
    const columns = 'id, image_url, captured_at, status, question_id';
    const withAnswers = await this.supabase
      .from('submissions')
      .select(`${columns}, answers`)
      .order('captured_at', { ascending: false });
    if (withAnswers.error?.code !== '42703') return withAnswers;
    return await this.supabase
      .from('submissions')
      .select(columns)
      .order('captured_at', { ascending: false });
  }

  /**
   * Quality-gate verdict per submission id ('PASS' | 'FIXABLE' | 'RETAKE').
   * Read separately from getSubmissions() so a missing gate_result column
   * (migration not applied yet) gives an empty map instead of breaking the
   * submissions list.
   */
  async getGateResults(): Promise<Map<string, string>> {
    const { data, error } = await this.supabase
      .from('submissions')
      .select('id, gate_result');
    const results = new Map<string, string>();
    if (error) return results;
    for (const row of (data ?? []) as { id: string; gate_result: string | null }[]) {
      if (row.gate_result) results.set(row.id, row.gate_result);
    }
    return results;
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
