import { Component, ChangeDetectorRef, EventEmitter, Input, OnInit, Output } from '@angular/core';
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

interface QuestionSection {
  id: string;
  name: string;
}

/** Value of the section dropdown option that creates a new section. */
export const NEW_SECTION = '__new__';

// Postgres unique_violation.
const UNIQUE_VIOLATION = '23505';

/** A saved question opened for editing from the question page. */
export interface EditQuestionRequest {
  question: {
    id: string;
    question_name: string;
    question_text: string;
    question_type: string;
    model_answer: string;
    test_cases: unknown[] | null;
    can_publish?: boolean | null;
  };
  /** Its current section and number, or null when it has none yet. */
  place: { sectionId: string; number: number } | null;
}
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
export class QuestionFormComponent implements OnInit {
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
  // Lets the page refresh lists that show questions, such as the review
  // dialog's question picker.
  @Output() questionSaved = new EventEmitter<void>();

  // Section and number, e.g. Basic · Q3. Stored in question_sections /
  // question_section_items; a question needs both to reach the phone.
  sections: QuestionSection[] = [];
  sectionsError = '';
  sectionId = '';
  newSectionName = '';
  questionNumber: number | null = null;
  takenNumbers: number[] = [];
  readonly NEW_SECTION = NEW_SECTION;

  // Edit mode: the id of the saved question being edited, or null when
  // creating. Save stays locked until validation passes, as when creating.
  editingId: string | null = null;
  private editOriginal: {
    place: { sectionId: string; number: number } | null;
    testsKey: string;
  } | null = null;
  /** Graded papers an edit to the test cases would clear; null = unknown. */
  gradedPaperCount: number | null = 0;
  gradeWarning = '';
  private gradeResetConfirmed = false;
  /** Tells the page the edit is finished (saved or cancelled). */
  @Output() editDone = new EventEmitter<void>();

  @Input() set editRequest(request: EditQuestionRequest | null | undefined) {
    if (request) void this.startEdit(request);
    else if (this.editingId) this.exitEdit();
  }

  get isEditing(): boolean {
    return this.editingId !== null;
  }

  readonly PROGRAM_TEMPLATE = `int main(void) {\n  return 0;\n}`;

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
      const own = this.editOriginal?.place;
      this.takenNumbers = (data ?? [])
        .map((row: { number: number }) => row.number)
        .filter(
          (n: number) => !(own && own.sectionId === this.sectionId && own.number === n),
        )
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

  /** Missing fields, section or number, or '' when they are all fine. */
  fieldsBlockedReason(): string {
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
    return '';
  }

  /** Why the question can't be saved yet, or '' when it can. */
  saveBlockedReason(): string {
    const fields = this.fieldsBlockedReason();
    if (fields) return fields;
    if (!this.canPublish) {
      return 'Validate the test cases first. The question can only be saved once every test passes.';
    }
    return '';
  }

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
    const fieldsBlocked = this.fieldsBlockedReason();
    if (fieldsBlocked) {
      this.errorMessage = fieldsBlocked;
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

    if (
      this.isEditing &&
      (this.gradedPaperCount === null || this.gradedPaperCount > 0) &&
      this.testsChanged() &&
      !this.gradeResetConfirmed
    ) {
      this.gradeWarning =
        (this.gradedPaperCount === null
          ? "Couldn't check whether papers graded against this question would lose their grades. "
          : `${this.gradedPaperCount === 1 ? '1 graded paper uses' : `${this.gradedPaperCount} graded papers use`} this question. `) +
        'Saving the changed test cases clears their grades, and they will need grading again.';
      this.cdr.detectChanges();
      return;
    }

    this.isSaving = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.gradeWarning = '';
    this.cdr.detectChanges();

    try {
      if (this.isEditing) {
        await this.saveEdit();
        return;
      }
      const sectionId = await this.resolveSectionId();
      if (!sectionId) return;
      const label = this.labelPreview;

      const { data, error } = await this.saveQuestionWithTimeout({
        question_name: this.questionName.trim(),
        question_text: this.questionText,
        question_type: this.questionType,
        model_answer: this.modelAnswer,
        test_cases: this.testCases.map((testCase) => ({
          ...testCase,
          test_input: this.stdinFor(this.questionType, testCase.test_input),
        })),
        // save() only gets here after every test case passed.
        can_publish: true,
      });
      if (error) {
        this.errorMessage = 'Error: ' + error.message;
        return;
      }
      // The question exists now, so lists that show questions can refresh
      // even if linking it to its section fails below.
      this.questionSaved.emit();

      const link = await this.supabase.addQuestionToSection(
        data.id,
        sectionId,
        this.questionNumber!,
      );
      if (link.error) {
        // The question itself is saved; it just has no section yet. Switch
        // to editing it, so saving again updates this question and adds its
        // section instead of inserting a second copy.
        this.editingId = data.id;
        this.editOriginal = { place: null, testsKey: this.testsKey() };
        this.gradedPaperCount = 0;
        this.errorMessage =
          link.error.code === UNIQUE_VIOLATION
            ? `The question was saved, but Q${this.questionNumber} was taken in ${this.sectionName} in the meantime. Pick another number and save again.`
            : `The question was saved, but not added to ${this.sectionName}: ${link.error.message}. Save again to retry.`;
        await this.onSectionChange();
        return;
      }

      this.resetForm();
      this.successMessage = `Question saved: ${label}`;
      await this.loadSections();
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
    this.gradeWarning = '';
    this.gradeResetConfirmed = false;
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

  /** "Save and clear grades" on the graded-papers warning. */
  async confirmGradeReset() {
    this.gradeResetConfirmed = true;
    await this.save();
  }

  /** Opens a saved question in the form, pre-filled. */
  async startEdit(request: EditQuestionRequest) {
    const q = request.question;
    this.editingId = q.id;
    this.questionName = q.question_name ?? '';
    this.questionText = q.question_text ?? '';
    this.questionType = q.question_type === 'function' ? 'function' : 'program';
    this.modelAnswer = q.model_answer ?? '';
    const cases = Array.isArray(q.test_cases) ? q.test_cases : [];
    this.testCases = cases.length
      ? cases.map((tc) => {
          const t = (tc ?? {}) as Record<string, unknown>;
          return {
            test_code: String(t['test_code'] ?? ''),
            test_input: String(t['test_input'] ?? ''),
            expected_output: String(t['expected_output'] ?? ''),
          };
        })
      : [this.createDefaultTestCase()];
    this.collapsedTestCases = {};
    this.hasAttemptedValidation = false;
    this.newSectionName = '';
    this.clearValidationResults();
    this.successMessage = '';
    this.gradedPaperCount = 0;
    this.editOriginal = { place: request.place, testsKey: this.testsKey() };
    this.sectionId = request.place?.sectionId ?? '';
    this.questionNumber = request.place?.number ?? null;
    // A question that already passed keeps counting as validated until its
    // model answer or test cases are edited (which clears this).
    if (q.can_publish === true) {
      this.canPublish = true;
      this.validatedInputs = this.executionInputsKey();
    }
    this.cdr.detectChanges();

    await this.onSectionChange();
    this.gradedPaperCount = await this.supabase.countGradedPapers(q.id);
    this.cdr.detectChanges();
  }

  /** Leave edit mode without saving. */
  cancelEdit() {
    this.exitEdit();
    this.editDone.emit();
  }

  private exitEdit() {
    this.editingId = null;
    this.editOriginal = null;
    this.gradedPaperCount = 0;
    this.resetForm();
    this.successMessage = '';
    this.cdr.detectChanges();
  }

  private async saveEdit() {
    const id = this.editingId!;
    const sectionId = await this.resolveSectionId();
    if (!sectionId) return;
    const label = this.labelPreview;
    const number = this.questionNumber!;

    const { error } = await this.supabase.updateQuestion(id, {
      question_name: this.questionName.trim(),
      question_text: this.questionText,
      question_type: this.questionType,
      model_answer: this.modelAnswer,
      test_cases: this.testCases.map((testCase) => ({
        ...testCase,
        test_input: this.stdinFor(this.questionType, testCase.test_input),
      })),
      // Only reachable after every test case passed.
      can_publish: true,
    });
    if (error) {
      this.errorMessage = 'Error: ' + error.message;
      return;
    }
    this.questionSaved.emit();
    // The question is saved; later failures only concern its section.
    this.editOriginal = { place: this.editOriginal?.place ?? null, testsKey: this.testsKey() };
    this.gradedPaperCount = await this.supabase.countGradedPapers(id);

    const before = this.editOriginal.place;
    if (!before || before.sectionId !== sectionId || before.number !== number) {
      const link = before
        ? await this.supabase.moveQuestionToSection(id, sectionId, number)
        : await this.supabase.addQuestionToSection(id, sectionId, number);
      if (link.error) {
        this.errorMessage =
          link.error.code === UNIQUE_VIOLATION
            ? `The changes were saved, but Q${number} is already used in ${this.sectionName}. Pick another number and save again.`
            : `The changes were saved, but the section couldn't be updated: ${link.error.message}`;
        await this.onSectionChange();
        return;
      }
    }

    this.exitEdit();
    this.successMessage = `Question updated: ${label}`;
    await this.loadSections();
    this.editDone.emit();
  }

  /** Test cases and type as saved; a change clears linked grades. */
  private testsKey(): string {
    return JSON.stringify({
      type: this.questionType,
      cases: this.testCases.map(({ test_code, test_input, expected_output }) => ({
        test_code,
        test_input: this.stdinFor(this.questionType, test_input),
        expected_output,
      })),
    });
  }

  private testsChanged(): boolean {
    return !!this.editOriginal && this.editOriginal.testsKey !== this.testsKey();
  }

  private resetForm() {
    this.questionName = '';
    this.questionText = '';
    this.questionType = 'program';
    this.modelAnswer = '';
    this.testCases = [this.createDefaultTestCase()];
    this.collapsedTestCases = {};
    this.hasAttemptedValidation = false;
    // Keep the section so the next question can go straight after this one.
    this.questionNumber = null;
    this.takenNumbers = [];
    // Also clears errorMessage.
    this.clearValidationResults();
    if (this.sectionId && this.sectionId !== NEW_SECTION) {
      void this.onSectionChange();
    }
  }

  private async saveQuestionWithTimeout(question: {
    question_name: string;
    question_text: string;
    question_type: string;
    model_answer: string;
    test_cases: TestCase[];
    can_publish: boolean;
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
