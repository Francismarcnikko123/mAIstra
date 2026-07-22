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
      .select('*')
      .order('captured_at', { ascending: false });
  }

  subscribeToSubmissions(callback: (payload: any) => void) {
    return this.supabase
      .channel('submissions')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'submissions' }, callback)
      .subscribe();
  }
}