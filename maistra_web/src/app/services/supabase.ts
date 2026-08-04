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
      .insert([question]);
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
      .select('id, image_url, captured_at, status, topic, student_name, extracted_text, verified_text')
      .order('captured_at', { ascending: false });
  }

  async updateSubmissionTopic(id: string, topic: string): Promise<void> {
    const { error } = await this.supabase
      .from('submissions')
      .update({ topic })
      .eq('id', id);
    if (error) throw error;
  }

  async updateSubmissionText(
    submissionId: string,
    extractedText: string,
    verifiedText: string
  ): Promise<void> {
    const { error } = await this.supabase
      .from('submissions')
      .update({
        extracted_text: extractedText,
        verified_text: verifiedText,
        status: 'verified',
        verified_at: new Date().toISOString(),
      })
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
