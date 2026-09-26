import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
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

interface QuestionSection {
  id: string;
  name: string;
}

/** Value of the section dropdown option that creates a new section. */
export const NEW_SECTION = '__new__';

// Postgres unique_violation.
const UNIQUE_VIOLATION = '23505';
interface ValidationResult {
  passed: boolean;
  expected: string;
  actual: string;
  status?: string;
  stderr?: string;
  compile_output?: string;
}
('');

const DEFAULT_TEST_CASE: TestCase = {
  test_code: '',
  test_input: '',
  expected_output: '',
  mark: 2,
};

@Component({
  selector: 'app-question-form',
  standalone: true,
  imports: [CommonModule, FormsModule, CodeEditorComponent],
  templateUrl: './question-form.html',
  styleUrls: ['./question-form.css'],
})
export class QuestionFormComponent implements OnInit {
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
  customInput = '';
  runOutput = '';
  runError = '';
  runStatus = '';
  isRunningModelAnswer = false;

  // Section and number, e.g. Basic · Q3. Stored in question_sections /
  // question_section_items; a question needs both to reach the phone.
  sections: QuestionSection[] = [];
  sectionsError = '';
  sectionId = '';
  newSectionName = '';
  questionNumber: number | null = null;
  takenNumbers: number[] = [];
  readonly NEW_SECTION = NEW_SECTION;

  readonly FUNCTION_TEMPLATE = ``;
  readonly PROGRAM_TEMPLATE = `#include <stdio.h>\n\nint main(void) {\n  return 0;\n}`;

  constructor(
    private supabase: SupabaseService,
    private cdr: ChangeDetectorRef,
    private judge0: Judge0Service,
  ) {}

  async ngOnInit() {
    await this.loadSections();
  }

  async loadSections() {
    const { data, error } = await this.supabase.getQuestionSections();
    if (error) {
      this.sectionsError = 'Could not load sections: ' + error.message;
    } else {
      this.sectionsError = '';
      this.sections = data ?? [];
    }
    this.cdr.detectChanges();
  }

  async onSectionChange() {
    this.takenNumbers = [];
    if (this.sectionId && this.sectionId !== NEW_SECTION) {
      const { data } = await this.supabase.getSectionNumbers(this.sectionId);
      this.takenNumbers = (data ?? [])
        .map((row: { number: number }) => row.number)
        .sort((a: number, b: number) => a - b);
    }
    this.cdr.detectChanges();
  }

  /** Section name as it will be saved, or '' when none is chosen yet. */
  get sectionName(): string {
    if (this.sectionId === NEW_SECTION) return this.newSectionName.trim();
    return this.sections.find((s) => s.id === this.sectionId)?.name ?? '';
  }

  get numberTaken(): boolean {
    return (
      this.questionNumber !== null &&
      this.takenNumbers.includes(this.questionNumber)
    );
  }

  /** "Basic · Q3 · Count vowels" — the label teachers and students see. */
  get labelPreview(): string {
    const parts = [
      this.sectionName,
      this.questionNumber ? `Q${this.questionNumber}` : '',
      this.questionName.trim(),
    ];
    return parts.filter(Boolean).join(' · ');
  }

  /** Why the question can't be saved yet, or '' when it can. */
  saveBlockedReason(): string {
    if (!this.questionName.trim() || !this.questionText.trim() || !this.modelAnswer.trim()) {
      return 'Fill in all required fields.';
    }
    if (!this.sectionName) return 'Choose a section.';
    if (
      this.questionNumber === null ||
      !Number.isInteger(this.questionNumber) ||
      this.questionNumber < 1
    ) {
      return 'Question No. must be a whole number of 1 or more.';
    }
    if (this.numberTaken) {
      return `Q${this.questionNumber} is already used in ${this.sectionName}. Pick another number.`;
    }
    if (!this.canPublish) {
      return 'Validate the test cases first. The question can only be saved once every test passes.';
    }
    return '';
  }

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
    this.testCases.push(this.createDefaultTestCase());

    this.validationResults = [];
    this.canPublish = false;
  }

  removeTestCase(index: number) {
    this.testCases.splice(index, 1);

    this.validationResults = [];
    this.canPublish = false;
  }

  async save() {
    const blocked = this.saveBlockedReason();
    if (blocked) {
      this.errorMessage = blocked;
      this.cdr.detectChanges();
      return;
    }

    this.isSaving = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.cdr.detectChanges();

    try {
      const sectionId = await this.resolveSectionId();
      if (!sectionId) return;
      const label = this.labelPreview;

      const { data, error } = await this.supabase.saveQuestion({
        question_name: this.questionName.trim(),
        question_text: this.questionText,
        question_type: this.questionType,
        model_answer: this.modelAnswer,
        test_cases: this.testCases,
        // save() only gets here after every test case passed.
        can_publish: true,
      });
      if (error) {
        this.errorMessage = 'Error: ' + error.message;
        return;
      }

      const link = await this.supabase.addQuestionToSection(
        data.id,
        sectionId,
        this.questionNumber!,
      );
      if (link.error) {
        // The question itself is saved; it just has no section yet.
        this.errorMessage =
          link.error.code === UNIQUE_VIOLATION
            ? `The question was saved, but Q${this.questionNumber} was taken in ${this.sectionName} in the meantime. It is under "No section yet" until it gets a free number.`
            : `The question was saved, but not added to ${this.sectionName}: ${link.error.message}`;
        await this.onSectionChange();
        return;
      }

      this.successMessage = `Question saved: ${label}`;
      this.resetForm();
      await this.loadSections();
    } finally {
      this.isSaving = false;
      this.cdr.detectChanges();
    }
  }

  /** The chosen section's id, creating the section first if it is new. */
  private async resolveSectionId(): Promise<string | null> {
    if (this.sectionId !== NEW_SECTION) return this.sectionId;

    const name = this.newSectionName.trim();
    const existing = this.sections.find(
      (s) => s.name.toLowerCase() === name.toLowerCase(),
    );
    if (existing) return existing.id;

    const { data, error } = await this.supabase.createQuestionSection(name);
    if (error) {
      this.errorMessage =
        error.code === UNIQUE_VIOLATION
          ? `A section called "${name}" already exists. Choose it from the list.`
          : 'Could not create the section: ' + error.message;
      await this.loadSections();
      return null;
    }
    this.sections = [...this.sections, data];
    this.sectionId = data.id;
    return data.id;
  }

  private resetForm() {
    this.questionName = '';
    this.questionText = '';
    this.questionType = 'program';
    this.modelAnswer = '';
    this.testCases = [this.createDefaultTestCase()];
    this.collapsedTestCases = {};
    // Keep the section so the next question can go straight after this one.
    this.questionNumber = null;
    this.takenNumbers = [];
    this.clearValidationResults();
    if (this.sectionId && this.sectionId !== NEW_SECTION) {
      void this.onSectionChange();
    }
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

  private createDefaultTestCase(): TestCase {
    return { ...DEFAULT_TEST_CASE };
  }
}
