import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SupabaseService } from '../../services/supabase';

interface Question {
  id: string;
  question_name: string;
  question_text: string;
  question_type: string;
  model_answer: string;
  test_cases: any[];
  created_at: string;
}

@Component({
  selector: 'app-question-bank',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './question-bank.html',
  styleUrls: ['./question-bank.css'],
})
export class QuestionBankComponent implements OnInit {
  questions: Question[] = [];
  isLoading = true;
  errorMessage = '';
  expandedId: string | null = null;

  constructor(
    private supabase: SupabaseService,
    private cdr: ChangeDetectorRef,
  ) {}

  async ngOnInit() {
    const { data, error } = await this.supabase.getQuestions();
    if (error) {
      this.errorMessage = 'Failed to load questions.';
    } else {
      this.questions = data ?? [];
    }
    this.isLoading = false;
    this.cdr.detectChanges();
  }

  toggle(id: string) {
    this.expandedId = this.expandedId === id ? null : id;
  }

  isExpanded(id: string) {
    return this.expandedId === id;
  }
}
