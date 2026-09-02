import { Injectable } from '@angular/core';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { environment } from '../../environment';

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
    .select(`
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
    `)
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
    extractedText?: string
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
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'submissions' }, callback)
      .subscribe();
  }
  
}
