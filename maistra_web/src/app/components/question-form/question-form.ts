import { Component, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SupabaseService } from '../../services/supabase';
import { CodeEditorComponent } from '../code-editor/code-editor';
import { firstValueFrom } from 'rxjs';
import { Judge0Service, Judge0RunResult } from '../../services/judge0.service';
import {
  buildCQuestionSource,
  getFunctionCodeError,
  getProgramCodeError,
} from '../../utils/c-question';
import { normalizeOutput } from '../../utils/normalize-output';

interface TestCase {
  test_code: string;
  test_input: string;
  expected_output: string;
}

type TestRunStatus = 'idle' | 'running' | 'passed' | 'failed';
interface ValidationResult {
  passed: boolean;
  expected: string;
  actual: string;
  status?: string;
  stderr?: string;
  compile_output?: string;
  message?: string;
}

const DEFAULT_TEST_CASE: TestCase = {
  test_code: '',
  test_input: '',
  expected_output: '',
};

@Component({
  selector: 'app-question-form',
  standalone: true,
  imports: [CommonModule, FormsModule, CodeEditorComponent],
  templateUrl: './question-form.html',
  styleUrls: ['./question-form.css'],
})
export class QuestionFormComponent {
  private readonly saveTimeoutMs = 15000;
  private validationVersion = 0;
  private validatedInputs = '';
  private hasAttemptedValidation = false;

  testRunStatuses: TestRunStatus[] = [];
  collapsedTestCases: Record<number, boolean> = {};
  questionName = '';
  questionText = '';
  questionType = 'function';
  modelAnswer = '';
  testCases: TestCase[] = [this.createDefaultTestCase()];
  validationResults: ValidationResult[] = [];
  isValidating = false;
  canPublish = false;
  isSaving = false;
  successMessage = '';
  errorMessage = '';

  readonly PROGRAM_TEMPLATE = `int main(void) {\n  return 0;\n}`;

  constructor(
    private supabase: SupabaseService,
    private cdr: ChangeDetectorRef,
    private judge0: Judge0Service,
  ) {}
  toggleTestCase(index: number) {
    this.collapsedTestCases[index] = !this.collapsedTestCases[index];
  }
  async validateModelAnswer() {
    if (this.isValidating) return;
    this.clearValidationResults();
    this.hasAttemptedValidation = true;
    this.successMessage = '';

    if (this.testCases.length === 0) {
      this.errorMessage = 'Add at least one test case before validating.';
      this.cdr.detectChanges();
      return;
    }

    const modelError = this.modelAnswerError;
    const codeErrors = this.testCases.map((_, i) =>
      [modelError, this.getTestCodeError(i)].filter(Boolean).join(' '),
    );
    const expectedErrors = this.testCases.map((_, i) =>
      this.getExpectedOutputError(i),
    );
    const errors = codeErrors.map((error, i) =>
      [error, expectedErrors[i]].filter(Boolean).join(' '),
    );
    if (errors.some(Boolean)) {
      this.errorMessage = codeErrors.some(Boolean)
        ? 'Fix the code errors below, then validate again.'
        : 'Enter the Expected Output for every test case, then validate again.';
      this.validationResults = this.testCases.map((tc, i) => ({
        passed: false,
        expected: tc.expected_output.trim(),
        actual: '',
        status: codeErrors[i]
          ? 'Invalid code structure'
          : expectedErrors[i]
            ? 'Missing expected output'
            : 'Not run',
        message:
          errors[i] || 'Fix the other code errors before running this test.',
      }));
      this.testRunStatuses = errors.map((error) => (error ? 'failed' : 'idle'));
      this.cdr.detectChanges();
      return;
    }

    const version = this.validationVersion;
    const inputKey = this.executionInputsKey();
    const isCurrent = () =>
      version === this.validationVersion &&
      inputKey === this.executionInputsKey();
    const type = this.questionType;
    const answer = this.modelAnswer;
    const testCases = this.testCases.map((tc) => ({ ...tc }));
    this.isValidating = true;
    this.testRunStatuses = testCases.map(() => 'running');
    this.cdr.detectChanges();

    try {
      let results: ValidationResult[];
      try {
        // Settled, so one slow or failed run does not hide the other results.
        const outcomes = await firstValueFrom(
          this.judge0.runCCodeBatchSettled(
            testCases.map((testCase) => ({
              sourceCode: buildCQuestionSource(
                type,
                answer,
                testCase.test_code,
              ),
              stdin: this.stdinFor(type, testCase.test_input),
            })),
          ),
        );
        results = testCases.map((testCase, index) => {
          const outcome = outcomes[index];
          return 'error' in outcome
            ? this.requestFailedValidation(testCase.expected_output, outcome)
            : this.executionValidation(outcome, testCase.expected_output, type);
        });
      } catch (error) {
        results = testCases.map((testCase) =>
          this.requestFailedValidation(testCase.expected_output, error),
        );
      }

      if (!isCurrent()) {
        this.clearValidationResults();
        return;
      }
      this.validationResults = results;
      this.testRunStatuses = results.map((result) =>
        result.passed ? 'passed' : 'failed',
      );
      this.canPublish = results.every((result) => result.passed);
      this.validatedInputs = this.canPublish ? this.executionInputsKey() : '';
    } finally {
      this.isValidating = false;
      this.cdr.detectChanges();
    }
  }

  onTypeChange() {
    this.modelAnswer =
      this.questionType === 'program' ? this.PROGRAM_TEMPLATE : '';

    this.hasAttemptedValidation = false;
    this.clearValidationResults();
    this.cdr.detectChanges();
  }

  addTestCase() {
    this.testCases.push(this.createDefaultTestCase());

    this.clearValidationResults();
  }

  removeTestCase(index: number) {
    this.testCases.splice(index, 1);

    this.clearValidationResults();
  }

  async save() {
    if (!this.questionName || !this.questionText || !this.modelAnswer) {
      this.errorMessage = 'Fill in all required fields.';
      this.cdr.detectChanges();
      return;
    }

    if (
      this.isValidating ||
      !this.canPublish ||
      this.validatedInputs !== this.executionInputsKey()
    ) {
      this.canPublish = false;
      this.errorMessage =
        'Click "Validate Test Cases" and make sure every test case passes before saving. ' +
        'This confirms the expected output actually comes from running the model answer in Judge0.';
      this.cdr.detectChanges();
      return;
    }

    this.isSaving = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.cdr.detectChanges();

    try {
      const { error } = await this.saveQuestionWithTimeout({
        question_name: this.questionName,
        question_text: this.questionText,
        question_type: this.questionType,
        model_answer: this.modelAnswer,
        test_cases: this.testCases.map((testCase) => ({
          ...testCase,
          test_input: this.stdinFor(this.questionType, testCase.test_input),
        })),
      });

      if (error) {
        this.errorMessage = 'Error: ' + error.message;
      } else {
        this.successMessage = 'Question saved!';
        this.questionName = '';
        this.questionText = '';
        this.questionType = 'program';
        this.modelAnswer = '';
        this.testCases = [this.createDefaultTestCase()];
        this.collapsedTestCases = {};
        this.hasAttemptedValidation = false;
        this.clearValidationResults();
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unable to save question.';
      this.errorMessage = 'Error: ' + message;
    } finally {
      this.isSaving = false;
      this.cdr.detectChanges();
    }
  }

  failedTestCount(): number {
    return this.validationResults.filter((result) => !result.passed).length;
  }

  passedAllTests(): boolean {
    return (
      this.canPublish &&
      !this.isValidating &&
      this.validationResults.length > 0 &&
      this.validationResults.every((result) => result.passed)
    );
  }
  isTestCaseCollapsed(index: number): boolean {
    return !!this.collapsedTestCases[index];
  }
  clearValidationResults() {
    this.validationVersion++;
    this.validatedInputs = '';
    this.validationResults = [];
    this.testRunStatuses = [];
    this.canPublish = false;
    this.errorMessage = '';
  }
  getTestCaseStatus(index: number): TestRunStatus {
    return this.testRunStatuses[index] || 'idle';
  }

  get modelAnswerError(): string {
    if (!this.modelAnswer.trim() && !this.hasAttemptedValidation) return '';
    return this.questionType === 'function'
      ? getFunctionCodeError(this.modelAnswer, 'Model Answer')
      : getProgramCodeError(this.modelAnswer);
  }

  getTestCodeError(index: number): string {
    if (this.questionType !== 'function') return '';
    const code = this.testCases[index]?.test_code || '';
    if (!code.trim() && !this.hasAttemptedValidation) return '';
    return getFunctionCodeError(code, 'Test Code');
  }

  getExpectedOutputError(index: number): string {
    const expected = this.testCases[index]?.expected_output || '';
    if (!expected.trim() && !this.hasAttemptedValidation) return '';
    return expected.trim() ? '' : 'Expected Output is required.';
  }

  private executionInputsKey(): string {
    return JSON.stringify({
      type: this.questionType,
      answer: this.modelAnswer,
      cases: this.testCases.map(
        ({ test_code, test_input, expected_output }) => ({
          test_code,
          test_input: this.stdinFor(this.questionType, test_input),
          expected_output,
        }),
      ),
    });
  }

  private executionValidation(
    result: Judge0RunResult,
    expected: string,
    type: string,
  ): ValidationResult {
    const actual = (result.stdout || '').trim();
    const expectedOutput = expected.trim();
    const ranSuccessfully = result.status?.id === 3;
    const noOutput = ranSuccessfully && !actual;
    const outputMatches =
      normalizeOutput(actual) === normalizeOutput(expectedOutput);
    const passed = ranSuccessfully && !noOutput && outputMatches;
    return {
      passed,
      expected: expectedOutput,
      actual,
      status: noOutput
        ? 'No output'
        : ranSuccessfully && !outputMatches
          ? 'Wrong Answer'
          : result.status?.description || 'Unknown execution status',
      message: noOutput
        ? type === 'function'
          ? 'No output was produced. Test Code must call the function and print the result, for example with printf().'
          : 'No output was produced. The program must print a result, for example with printf(), so this test can grade submissions.'
        : ranSuccessfully && !outputMatches
          ? 'The model answer output does not match the manually entered Expected Output.'
          : result.message,
      stderr: result.stderr,
      compile_output: result.compile_output,
    };
  }

  private stdinFor(type: string, input: string): string {
    return type === 'program' ? input : '';
  }

  private requestFailedValidation(
    expected: string,
    error: unknown,
  ): ValidationResult {
    return {
      passed: false,
      expected: expected.trim(),
      actual: '',
      status: 'Validation request failed',
      message: this.validationRequestError(error),
    };
  }

  // Reads `error.detail` from both an HttpErrorResponse and a settled batch
  // run's { error: { detail } } outcome.
  private validationRequestError(error: unknown): string {
    const detail = (error as { error?: { detail?: unknown } } | null)?.error
      ?.detail;
    return typeof detail === 'string'
      ? detail
      : 'Unable to validate this test case. Check the Judge0 connection and try again.';
  }

  private createDefaultTestCase(): TestCase {
    return { ...DEFAULT_TEST_CASE };
  }

  private async saveQuestionWithTimeout(question: {
    question_name: string;
    question_text: string;
    question_type: string;
    model_answer: string;
    test_cases: TestCase[];
  }) {
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const timeout = new Promise<never>((_, reject) => {
      timeoutId = setTimeout(() => {
        reject(
          new Error('Saving question timed out. Check Supabase connection.'),
        );
      }, this.saveTimeoutMs);
    });

    try {
      return await Promise.race([
        this.supabase.saveQuestion(question),
        timeout,
      ]);
    } finally {
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId);
      }
    }
  }
}
