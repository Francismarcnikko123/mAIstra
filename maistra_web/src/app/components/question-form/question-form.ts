import { Component, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SupabaseService } from '../../services/supabase';

interface TestCase {
  test_code: string;
  expected_output: string;
  mark: number;
}

@Component({
  selector: 'app-question-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './question-form.html',
})
export class QuestionFormComponent {
  questionName = '';
  questionText = '';
  questionType = 'program';
  modelAnswer = '';
  testCases: TestCase[] = [{ test_code: '', expected_output: '', mark: 2 }];
  isSaving = false;
  successMessage = '';
  errorMessage = '';

  readonly FUNCTION_TEMPLATE = `#include <stdio.h>\n\nint main(void) {\n    // insert function call here\n    return 0;\n}`;

  constructor(private supabase: SupabaseService, private cdr: ChangeDetectorRef) {}

  onTypeChange() {
    this.modelAnswer = this.questionType === 'function' ? this.FUNCTION_TEMPLATE : '';
  }

  addTestCase() {
    this.testCases.push({ test_code: '', expected_output: '', mark: 2 });
  }

  removeTestCase(index: number) {
    this.testCases.splice(index, 1);
  }

  async save() {
    if (!this.questionName || !this.questionText || !this.modelAnswer) {
      this.errorMessage = 'Fill in all required fields.';
      this.cdr.detectChanges();
      return;
    }

    this.isSaving = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.cdr.detectChanges();

    const { error } = await this.supabase.saveQuestion({
      question_name: this.questionName,
      question_text: this.questionText,
      question_type: this.questionType,
      model_answer: this.modelAnswer,
      test_cases: this.testCases,
    });

    if (error) {
      this.errorMessage = 'Error: ' + error.message;
    } else {
      this.successMessage = 'Question saved!';
      this.questionName = '';
      this.questionText = '';
      this.questionType = 'program';
      this.modelAnswer = '';
      this.testCases = [{ test_code: '', expected_output: '', mark: 2 }];
    }

    this.isSaving = false;
    this.cdr.detectChanges();
  }
}