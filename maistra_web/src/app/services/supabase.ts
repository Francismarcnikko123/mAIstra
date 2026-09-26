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

// Every verified program on a paper (20260926000600_add_submission_programs).
const PROGRAM_COLUMNS = `
  submission_programs (
    id,
    position,
    question_id,
    verified_text,
    grading_results,
    passed_test_cases,
    total_test_cases,
    score_percent,
    graded_at,
    grading_revision
  )
`;

/** One teacher-verified program on a paper, with its own question and grade. */
export interface SubmissionProgramRow {
  id: string;
  position: number;
  question_id: string;
  verified_text: string;
  grading_results: unknown[];
  passed_test_cases: number | null;
  total_test_cases: number | null;
  score_percent: number | null;
  graded_at: string | null;
  grading_revision: number;
}

type WithPrograms = {
  submission_programs?: Array<
    Pick<SubmissionProgramRow, 'position' | 'question_id' | 'verified_text'>
  > | null;
};

/**
 * Sorts a paper's programs by tab and adds `answers` (Programs 2..n as
 * { code, question_id }), the shape the review screen and the question bank
 * already read, so they need no change for the programs table.
 */
function withAnswers<T extends WithPrograms>(row: T): T & { answers: SubmissionAnswer[] } {
  const programs = [...(row.submission_programs ?? [])].sort(
    (a, b) => a.position - b.position,
  );
  return {
    ...row,
    submission_programs: programs,
    answers: programs
      .filter((program) => program.position > 1)
      .map((program) => ({ code: program.verified_text, question_id: program.question_id })),
  };
}

/** The error PostgREST returns while the submission_programs table is missing. */
function isProgramsTableMissing(error: { code?: string; message?: string } | null): boolean {
  return error?.code === 'PGRST200' && /submission_programs/.test(error.message ?? '');
}

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

  /**
   * Saves an edited question. Jayrald's 20260926000400 migration allows these
   * columns; changing test_cases or question_type clears the grades of papers
   * linked to the question (his trigger).
   */
  async updateQuestion(
    id: string,
    fields: {
      question_name: string;
      question_text: string;
      question_type: string;
      model_answer: string;
      test_cases: unknown[];
      can_publish: boolean;
    },
  ) {
    return await this.supabase
      .from('questions')
      .update(fields)
      .eq('id', id)
      .select('id')
      .single();
  }

  /** Moves an already-sectioned question to another section and/or number. */
  async moveQuestionToSection(questionId: string, sectionId: string, number: number) {
    return await this.supabase
      .from('question_section_items')
      .update({ section_id: sectionId, number })
      .eq('question_id', questionId);
  }

  /**
   * Papers with a grade that editing this question's test cases or type
   * would clear (Jayrald's triggers): graded pages linked as Program 1, plus
   * any program on a page (submission_programs) graded against it. Null when
   * the count can't be read, so the caller warns instead of assuming none.
   */
  async countGradedPapers(questionId: string): Promise<number | null> {
    const papers = new Set<string>();
    const pages = await this.supabase
      .from('submissions')
      .select('id')
      .eq('question_id', questionId)
      .eq('status', 'graded');
    if (pages.error) return null;
    for (const row of (pages.data ?? []) as { id: string }[]) papers.add(row.id);

    const programs = await this.supabase
      .from('submission_programs')
      .select('submission_id, graded_at')
      .eq('question_id', questionId);
    if (programs.error) {
      // PGRST205: the table doesn't exist yet (older database).
      if (programs.error.code !== 'PGRST205') return null;
    } else {
      for (const row of (programs.data ?? []) as { submission_id: string; graded_at: string | null }[]) {
        if (row.graded_at) papers.add(row.submission_id);
      }
    }
    return papers.size;
  }

  /** Every question's section and number, for the question bank. */
  async getSectionItems() {
    return await this.supabase
      .from('question_section_items')
      .select('section_id, question_id, number');
  }

  /**
   * Which questions each paper is linked to, for the bank's paper counts and
   * the question page's linked papers. Programs 2..n come back as `answers`;
   * falls back to Program 1 only while the submission_programs table is
   * missing. (Jayrald: switched from the answers column on 2026-09-26.)
   */
  async getQuestionPaperLinks() {
    const columns = 'id, image_url, captured_at, status, question_id';
    const withPrograms = await this.supabase
      .from('submissions')
      .select(`${columns}, submission_programs (position, question_id, verified_text)`)
      .order('captured_at', { ascending: false });
    if (!isProgramsTableMissing(withPrograms.error)) {
      return { ...withPrograms, data: withPrograms.data?.map(withAnswers) ?? null };
    }
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
   * False once the database reports that the submission_programs table
   * doesn't exist, i.e. its migration hasn't been applied there yet. The list
   * still loads without it; Programs 2..n just can't be saved, and grading
   * falls back to Program 1 on the page row. (The name is from the earlier
   * `answers` column; the review screen reads it.)
   */
  answersColumnAvailable = true;

  async getSubmissions() {
    if (this.answersColumnAvailable !== false) {
      const result = await this.querySubmissions(`${SUBMISSION_COLUMNS}, ${PROGRAM_COLUMNS}`);
      // Only fall back when it's the programs table that is missing; any
      // other error is returned as before.
      if (!isProgramsTableMissing(result.error)) {
        return { ...result, data: (result.data as WithPrograms[] | null)?.map(withAnswers) ?? null };
      }
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
    if (this.answersColumnAvailable !== false) {
      const result = await this.supabase
        .from('submissions')
        .select(`${SUBMISSION_COLUMNS}, ${PROGRAM_COLUMNS}`)
        .eq('id', id)
        .maybeSingle();
      if (!isProgramsTableMissing(result.error)) {
        return { ...result, data: result.data ? withAnswers(result.data as WithPrograms) : null };
      }
      this.answersColumnAvailable = false;
    }
    return this.supabase.from('submissions').select(SUBMISSION_COLUMNS).eq('id', id).maybeSingle();
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
    if (this.answersColumnAvailable !== false) {
      // Every program of the paper in one call, under the page's revision
      // guard. Program 1's question comes from the page (Details step).
      // Without `answers` (a paper with no tabs) only Program 1 is written
      // and Programs 2..n stay exactly as they were.
      const { data, error } = await this.supabase.rpc('save_submission_programs', {
        p_submission_id: submissionId,
        p_grading_revision: expectedRevision,
        p_programs: [
          { verified_text: verifiedText },
          ...(answers ?? []).map((answer) => ({
            verified_text: answer.code,
            question_id: answer.question_id,
          })),
        ],
        p_extracted_text: extractedText ?? null,
        p_replace_all: answers !== undefined,
      });
      if (error) throw error;
      return data === null || data === undefined ? null : Number(data);
    }

    // Before the programs table exists: Program 1 on the page row only.
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

  /**
   * One program's grade, written by the database only while the program's
   * revision, question and stored code all still match (same compare-and-set
   * as updateSubmissionGrade). Returns the program's new revision, or null.
   */
  async saveProgramGrade(
    programId: string,
    gradingRevision: number,
    questionId: string,
    gradedCode: string,
    results: ReadonlyArray<{ passed: boolean }>,
  ): Promise<number | null> {
    const { data, error } = await this.supabase.rpc('save_program_grade', {
      p_program_id: programId,
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
