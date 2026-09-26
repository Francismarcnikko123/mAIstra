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

  // ── QUESTION SECTIONS (Nikko) ───────────────────────────
  // Tables from supabase/migrations/20260926000100_add_question_sections.sql.

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

  /**
   * One row with the same shape as getSubmissions(), fresh from the database.
   * A realtime event refreshes just the submission that changed, and opening
   * a paper picks up OCR text the auto-extract worker saved after the list
   * was loaded.
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
    answers?: SubmissionAnswer[],
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
    // Programs 2..n from the review tabs, saved in the same update so they
    // share Program 1's save guards, including the revision check.
    if (answers !== undefined && this.answersColumnAvailable !== false) {
      update['answers'] = answers;
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

  /** New rows go to onInsert; changed rows go to onUpdate, or to onInsert when only one handler is given. */
  subscribeToSubmissions(
    onInsert: (payload: any) => void,
    onUpdate: (payload: any) => void = onInsert,
  ) {
    return this.supabase
      .channel('submissions')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'submissions' }, onInsert)
      .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'submissions' }, onUpdate)
      .subscribe();
  }
}
