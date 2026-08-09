import { Component, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SupabaseService } from '../../services/supabase';
import { CodeEditorComponent } from '../code-editor/code-editor';
import { firstValueFrom } from 'rxjs';
import { Judge0Service } from '../../services/judge0.service';

interface TestCase {
  test_code: string;
  test_input: string;
  expected_output: string;
  mark: number;
}

type TestRunStatus = 'idle' | 'running' | 'passed' | 'failed';
interface ValidationResult {
  passed: boolean;
  expected: string;
  actual: string;
  status?: string;
  stderr?: string;
  compile_output?: string;
}
('');
@Component({
  selector: 'app-question-form',
  standalone: true,
  imports: [CommonModule, FormsModule, CodeEditorComponent],
  templateUrl: './question-form.html',
  styleUrls: ['./question-form.css'],
})
export class QuestionFormComponent {
  testRunStatuses: TestRunStatus[] = [];
  collapsedTestCases: Record<number, boolean> = {};
  questionName = '';
  questionText = '';
  questionType = 'function';
  modelAnswer = '';
 testCases: TestCase[] = [
  {
    test_code: '',
    test_input: '',
    expected_output: '',
    mark: 2,
  },
];
  validationResults: ValidationResult[] = [];
  isValidating = false;
  canPublish = false;
  isSaving = false;
  successMessage = '';
  errorMessage = '';
  customInput = '';
  runOutput = '';
  runError = '';
  runStatus = '';
  isRunningModelAnswer = false;

  readonly FUNCTION_TEMPLATE = ``;
  readonly PROGRAM_TEMPLATE = `#include <stdio.h>\n\nint main(void) {\n  return 0;\n}`;
   
  constructor(
    private supabase: SupabaseService,
    private cdr: ChangeDetectorRef,
    private judge0: Judge0Service,
  ) {}
  toggleTestCase(index: number) {
  this.collapsedTestCases[index] = !this.collapsedTestCases[index];
}
async validateModelAnswer() {
  this.isValidating = true;
  this.canPublish = false;

  this.testRunStatuses = this.testCases.map((_, i) =>
    this.validationResults[i]?.passed ? 'passed' : 'idle',
  );

  this.cdr.detectChanges();

  try {
    const validationPromises = this.testCases.map(async (tc, i) => {
      if (this.validationResults[i]?.passed) {
        this.testRunStatuses[i] = 'passed';
        return this.validationResults[i];
      }

      this.testRunStatuses[i] = 'running';
      this.cdr.detectChanges();

      try {
        const sourceCode =
          this.questionType === 'function'
            ? `#include <stdio.h>
            

${this.modelAnswer}

int main() {
${tc.test_code}

  return 0;
}`
            : this.modelAnswer;

        const stdin = this.questionType === 'program' ? tc.test_input : '';

        const result = await firstValueFrom(
          this.judge0.runCCode(sourceCode, stdin),
        );

        const actual = (result.stdout || '').trim();
        const expected = tc.expected_output.trim();
        const passed = actual === expected;

        this.validationResults[i] = {
          passed,
          expected,
          actual,
          status: result.status?.description,
          stderr: result.stderr,
          compile_output: result.compile_output,
        };

        this.testRunStatuses[i] = passed ? 'passed' : 'failed';

        return this.validationResults[i];
      } catch (error) {
        this.validationResults[i] = {
          passed: false,
          expected: tc.expected_output.trim(),
          actual: '',
          status: 'Validation request failed',
          stderr: 'Unable to validate this test case.',
          compile_output: '',
        };

        this.testRunStatuses[i] = 'failed';

        return this.validationResults[i];
      } finally {
        this.cdr.detectChanges();
      }
    });

    const results = await Promise.all(validationPromises);
    this.validationResults = results;

    this.canPublish =
      this.validationResults.length === this.testCases.length &&
      this.validationResults.every((result) => result.passed);
  } finally {
    this.isValidating = false;
    this.cdr.detectChanges();
  }
}
  
  async runModelAnswer() {
    this.isRunningModelAnswer = true;
    this.runOutput = '';
    this.runError = '';
    this.runStatus = '';

    try {
      const result = await firstValueFrom(
        this.judge0.runCCode(this.modelAnswer, this.testCases[0].test_code),
      );

      this.runOutput = result.stdout || '';
      this.runError =
        result.stderr || result.compile_output || result.message || '';
      this.runStatus = result.status?.description || '';
    } finally {
      this.isRunningModelAnswer = false;
      this.cdr.detectChanges();
    }
  }

onTypeChange() {
  this.modelAnswer =
    this.questionType === 'program'
      ? this.PROGRAM_TEMPLATE
      : this.FUNCTION_TEMPLATE;

  this.clearValidationResults();
  this.cdr.detectChanges();
}

  addTestCase() {
      this.testCases.push({
    test_code: '',
    test_input: '',
    expected_output: '',
    mark: 2,
  });

  this.validationResults = [];
  this.canPublish = false;
  }

  removeTestCase(index: number) {
    this.testCases.splice(index, 1);

  this.validationResults = [];
  this.canPublish = false;
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

const { data, error } = await this.supabase.saveQuestion({
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
       this.testCases.push({
    test_code: '',
    test_input: '',
    expected_output: '',
    mark: 2,
  });
    }

    this.isSaving = false;
    this.cdr.detectChanges();
  }

  failedTestCount(): number {
    return this.validationResults.filter((result) => !result.passed).length;
  }

  passedAllTests(): boolean {
    return (
      this.validationResults.length > 0 &&
      this.validationResults.every((result) => result.passed)
    );
  }
  isTestCaseCollapsed(index: number): boolean {
  return !!this.collapsedTestCases[index];
}
clearValidationResults() {
  this.validationResults = [];
  this.testRunStatuses = [];
  this.canPublish = false;
}
getTestCaseStatus(index: number): TestRunStatus {
  return this.testRunStatuses[index] || 'idle';
}
}
