import {
  Component,
  OnInit,
  OnDestroy,
  ChangeDetectorRef,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { SupabaseService } from '../../services/supabase';
import { CodeEditorComponent } from '../code-editor/code-editor';
import { Judge0, TestCaseResult } from '../judge0/judge0';
import { Judge0Service } from '../../services/judge0.service';
import { firstValueFrom } from 'rxjs';
import { buildCQuestionSource } from '../../utils/c-question';
import { normalizeOutput } from '../../utils/normalize-output';

interface TestCase {
  test_code: string;
  test_input: string;
  expected_output: string;
}
interface SubmissionQuestion {
  id: string;
  question_name: string;
  question_type: 'function' | 'program';
  test_cases: TestCase[];
}

interface Submission {
  id: string;
  image_url: string;
  student_name?: string;
  captured_at: string;
  status?: string;
  extracted_text?: string;
  verified_text?: string;
  topic?: string;
  question_id?: string;
  grading_results?: TestCaseResult[];
  passed_test_cases?: number;
  total_test_cases?: number;
  score_percent?: number;
  graded_at?: string;
  grading_revision?: number;
  questions?: SubmissionQuestion | SubmissionQuestion[];
}

interface TopicGroup {
  topic: string;
  submissions: Submission[];
}

type ReviewStep = 1 | 2 | 3;
type SubmissionFilter = 'all' | 'new' | 'extracted' | 'verified' | 'graded';

@Component({
  selector: 'app-submissions-list',
  standalone: true,
  imports: [CommonModule, FormsModule, CodeEditorComponent, Judge0],
  templateUrl: './submissions-list.html',
  styleUrl: './submissions-list.css',
})
export class SubmissionsListComponent implements OnInit, OnDestroy {
  @ViewChild('codeEditor') codeEditor?: CodeEditorComponent;
  selectedQuestionId = '';
  questions: SubmissionQuestion[] = [];
  submissions: Submission[] = [];
  groupedSubmissions: TopicGroup[] = [];
  collapsedFolders: Record<string, boolean> = {};
  searchQuery = '';
  statusFilter: SubmissionFilter = 'all';

  // Modal state
  selectedSubmission: Submission | null = null;
  reviewStep: ReviewStep = 1;
  editableTopic: string = '';
  savingTopic = false;

  // OCR state
  extractingId: string | null = null;
  savingId: string | null = null;
  extractedText: Record<string, string> = {};
  editableText: Record<string, string> = {};
  extractionError: Record<string, string> = {};
  saveStatus: Record<string, string> = {}; // '' | 'saved' | 'error'

  // code checking state
  isChecking = false;
  checkError = '';
  submissionCheckStatus: Record<string, string> = {};
  submissionRunOutput: Record<string, string> = {};
  submissionTestResults: Record<string, TestCaseResult[]> = {};

  private subscription?: ReturnType<SupabaseService['subscribeToSubmissions']>;
  private saveStatusTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private saveGenerations = new Map<string, number>();
  private gradingGenerations = new Map<string, number>();
  private persistedSubmissions = new Map<string, Submission>();
  private dirtyCodeIds = new Set<string>();
  private dirtyQuestionIds = new Set<string>();
  private dirtyTopicIds = new Set<string>();
  private loadGeneration = 0;
  private destroyed = false;

  constructor(
    private supabase: SupabaseService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private judge0Service: Judge0Service,
  ) {}

  async ngOnInit() {
    this.subscription = this.supabase.subscribeToSubmissions(() => {
      if (!this.destroyed) void this.loadSubmissions();
    });

    await this.loadQuestions();
    if (this.destroyed) return;
    await this.loadSubmissions();
  }

  ngOnDestroy() {
    this.destroyed = true;

    for (const timer of this.saveStatusTimers.values()) {
      clearTimeout(timer);
    }
    this.saveStatusTimers.clear();

    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }

  private clearSaveStatusTimer(id: string) {
    const timer = this.saveStatusTimers.get(id);
    if (timer !== undefined) {
      clearTimeout(timer);
      this.saveStatusTimers.delete(id);
    }
  }

  private startSaveGeneration(id: string): number {
    const generation = (this.saveGenerations.get(id) ?? 0) + 1;
    this.saveGenerations.set(id, generation);
    return generation;
  }

  private isCurrentSave(id: string, generation: number): boolean {
    return !this.destroyed && this.saveGenerations.get(id) === generation;
  }

  private startGradingGeneration(id: string): number {
    const generation = (this.gradingGenerations.get(id) ?? 0) + 1;
    this.gradingGenerations.set(id, generation);
    return generation;
  }

  private invalidateGrading(id: string): void {
    this.startGradingGeneration(id);
    this.isChecking = false;
  }

  private isCurrentGrading(id: string, generation: number): boolean {
    return (
      !this.destroyed && this.gradingGenerations.get(id) === generation
    );
  }

  async loadSubmissions() {
    const generation = ++this.loadGeneration;
    const { data, error } = await this.supabase.getSubmissions();
    if (this.destroyed || generation !== this.loadGeneration) return;
    if (error) {
      console.error(error);
      return;
    }
    const loadedSubmissions = (data ?? []) as unknown as Submission[];
    const selectedId = this.selectedSubmission?.id;
    if (selectedId) {
      const persisted = this.persistedSubmissions.get(selectedId);
      const persistedTopic = persisted?.topic || 'Uncategorized';
      if (this.editableTopic !== persistedTopic) {
        this.dirtyTopicIds.add(selectedId);
      }
    }

    for (const submission of loadedSubmissions) {
      this.rememberPersistedSubmission(submission);
    }

    this.submissions = loadedSubmissions;
    // Seed the editor with previously saved text so verified/extracted work
    // reappears when the page reloads or a submission is reopened.
    for (const s of this.submissions) {
      if (this.dirtyCodeIds.has(s.id)) continue;
      const saved = s.verified_text || s.extracted_text || '';
      this.editableText[s.id] = saved;
    }

    if (selectedId) {
      const refreshed = this.submissions.find((item) => item.id === selectedId);
      if (refreshed) {
        const draftQuestionId = this.selectedSubmission?.question_id;
        const codeIsDirty = this.dirtyCodeIds.has(selectedId);
        const questionIsDirty = this.dirtyQuestionIds.has(selectedId);
        const topicIsDirty = this.dirtyTopicIds.has(selectedId);

        this.selectedSubmission = this.cloneSubmission(refreshed);
        if (questionIsDirty) {
          this.selectedSubmission.question_id = draftQuestionId;
        } else {
          this.selectedQuestionId =
            refreshed.question_id || this.getLinkedQuestion(refreshed)?.id || '';
        }

        if (codeIsDirty || questionIsDirty) {
          this.clearCompletedGrade(selectedId);
        } else {
          this.restorePersistedGrade(refreshed);
        }
        if (!topicIsDirty) {
          this.editableTopic = refreshed.topic || 'Uncategorized';
        }
      }
    }
    this.groupSubmissions();
    this.cdr.detectChanges();
  }

  groupSubmissions() {
    const map = new Map<string, Submission[]>();
    const query = this.searchQuery.trim().toLowerCase();
    const filtered = this.submissions.filter((submission) => {
      const statusMatches =
        this.statusFilter === 'all' ||
        this.getSubmissionStatus(submission) === this.statusFilter;
      const searchMatches =
        !query ||
        [
          submission.student_name,
          submission.topic,
          this.getQuestionName(submission),
        ].some((value) => value?.toLowerCase().includes(query));

      return statusMatches && searchMatches;
    });

    for (const s of filtered) {
      const topic = s.topic?.trim() || 'Uncategorized';
      if (!map.has(topic)) map.set(topic, []);
      map.get(topic)!.push(s);
    }

    this.groupedSubmissions = Array.from(map.entries())
      .sort(([a], [b]) => {
        if (a === 'Uncategorized') return 1;
        if (b === 'Uncategorized') return -1;
        return a.localeCompare(b);
      })
      .map(([topic, submissions]) => ({ topic, submissions }));
  }

  onFiltersChanged() {
    this.groupSubmissions();
  }

  clearFilters() {
    this.searchQuery = '';
    this.statusFilter = 'all';
    this.groupSubmissions();
  }

  toggleFolder(topic: string) {
    this.collapsedFolders[topic] = !this.collapsedFolders[topic];
  }

  openModal(submission: Submission) {
    this.rememberPersistedSubmission(submission);
    this.dirtyCodeIds.delete(submission.id);
    this.dirtyQuestionIds.delete(submission.id);
    this.dirtyTopicIds.delete(submission.id);
    this.selectedSubmission = this.cloneSubmission(submission);
    this.editableTopic = submission.topic || 'Uncategorized';
    const linkedQuestion = this.getLinkedQuestion(submission);
    this.selectedQuestionId =
      submission.question_id || linkedQuestion?.id || '';
    this.reviewStep = 1;

    this.checkError = '';
    this.isChecking = false;
    this.restorePersistedGrade(submission);

    const saved = submission.verified_text || submission.extracted_text || '';
    this.editableText[submission.id] = saved;
  }

  closeModal() {
    if (this.selectedSubmission) {
      const id = this.selectedSubmission.id;
      this.invalidateGrading(id);
      this.restorePersistedSubmission(id);
      this.dirtyCodeIds.delete(id);
      this.dirtyQuestionIds.delete(id);
      this.dirtyTopicIds.delete(id);
    }
    this.selectedSubmission = null;
    this.reviewStep = 1;
  }

  setReviewStep(step: ReviewStep) {
    if (step === 3 && !this.canOpenGradingStep()) return;
    this.reviewStep = step;
  }

  async continueFromDetails() {
    const submissionId = this.selectedSubmission?.id;
    if (!submissionId || !this.selectedQuestionId) return;

    const saved = await this.saveSubmissionDetails();
    if (
      saved &&
      !this.destroyed &&
      this.selectedSubmission?.id === submissionId
    ) {
      this.reviewStep = 2;
    }
  }

  async saveCodeAndContinue() {
    if (!this.canOpenGradingStep()) return;

    await this.saveVerifiedText();
    if (
      this.selectedSubmission &&
      this.saveStatus[this.selectedSubmission.id] === 'saved'
    ) {
      this.reviewStep = 3;
    }
  }

  async saveSubmissionDetails(): Promise<boolean> {
    if (!this.selectedSubmission) return false;
    const submission = this.selectedSubmission;
    const submissionId = submission.id;
    const topic = this.editableTopic;
    const questionId = this.selectedQuestionId || null;
    this.savingTopic = true;
    try {
      const gradingRevision = await this.supabase.updateSubmissionDetails(
        submissionId,
        topic,
        questionId,
      );
      const storedSubmission = this.submissions.find(
        (item) => item.id === submissionId,
      );
      const openSubmission =
        this.selectedSubmission?.id === submissionId
          ? this.selectedSubmission
          : undefined;
      for (const item of new Set([
        submission,
        storedSubmission,
        openSubmission,
      ])) {
        if (!item) continue;
        item.topic = topic;
        item.question_id = questionId || undefined;
        if (typeof gradingRevision === 'number') {
          item.grading_revision = gradingRevision;
        }
      }
      this.dirtyQuestionIds.delete(submissionId);
      this.dirtyTopicIds.delete(submissionId);
      this.rememberPersistedSubmission(storedSubmission ?? submission);
      this.groupSubmissions();
      this.cdr.detectChanges();
      return true;
    } catch (err) {
      console.error('Failed to save submission details:', err);
      return false;
    } finally {
      this.savingTopic = false;
      this.cdr.detectChanges();
    }
  }

  async extractText() {
    if (!this.selectedSubmission) return;
    const id = this.selectedSubmission.id;
    this.extractingId = id;
    this.extractionError[id] = '';
    try {
      const res = await firstValueFrom(
        this.http.post<{ cleaned_text?: string }>(
          'http://localhost:8000/api/ocr/extract-from-url',
          {
            image_url: this.selectedSubmission.image_url,
            submission_id: id,
          },
        ),
      );
      const text = res?.cleaned_text ?? '';
      this.extractedText[id] = text;
      this.updateSubmissionCode(id, text);
      this.extractionError[id] = '';
    } catch (err) {
      console.error('OCR failed:', err);
      this.extractionError[id] =
        'Failed to extract text. Please try again later.';
    } finally {
      this.extractingId = null;
      this.cdr.detectChanges();
    }
  }

  async saveVerifiedText() {
    if (!this.selectedSubmission || this.destroyed) return;
    const id = this.selectedSubmission.id;
    const generation = this.startSaveGeneration(id);
    this.savingId = id;
    this.clearSaveStatusTimer(id);
    this.saveStatus[id] = '';
    try {
      const text = this.editableText[id];
      // The OCR's own output (if extraction ran this session) is saved as
      // extracted_text; the teacher's edits only ever become verified_text.
      const ocrText = this.extractedText[id];
      const gradingRevision = await this.supabase.updateSubmissionText(
        id,
        text,
        ocrText,
      );
      if (!this.isCurrentSave(id, generation)) return;

      const s = this.submissions.find((x) => x.id === id);
      if (s) {
        s.verified_text = text;
        if (ocrText !== undefined) s.extracted_text = ocrText;
        if (typeof gradingRevision === 'number') {
          s.grading_revision = gradingRevision;
        }
      }
      if (this.selectedSubmission?.id === id) {
        this.selectedSubmission.verified_text = text;
        if (ocrText !== undefined)
          this.selectedSubmission.extracted_text = ocrText;
        if (typeof gradingRevision === 'number') {
          this.selectedSubmission.grading_revision = gradingRevision;
        }
      }
      this.dirtyCodeIds.delete(id);
      const persisted = this.submissions.find((item) => item.id === id);
      if (persisted) this.rememberPersistedSubmission(persisted);
      this.saveStatus[id] = 'saved';
      // Auto-clear the confirmation after a few seconds.
      const timer = setTimeout(() => {
        if (!this.isCurrentSave(id, generation)) return;
        this.saveStatusTimers.delete(id);
        this.saveStatus[id] = '';
        this.cdr.detectChanges();
      }, 3000);
      this.saveStatusTimers.set(id, timer);
    } catch (err) {
      if (!this.isCurrentSave(id, generation)) return;

      console.error('Save failed:', err);
      this.saveStatus[id] = 'error';
    } finally {
      if (!this.isCurrentSave(id, generation)) return;

      this.savingId = null;
      this.cdr.detectChanges();
    }
  }

  hasExtractedText(id: string): boolean {
    return !!this.editableText[id];
  }

  canOpenGradingStep(): boolean {
    if (!this.selectedSubmission) return false;
    const question = this.getSubmissionQuestion(this.selectedSubmission);
    return (
      !!this.getStudentCode(this.selectedSubmission).trim() &&
      !!question &&
      (question.test_cases?.length ?? 0) > 0
    );
  }

  getSubmissionStatus(
    submission: Submission,
  ): Exclude<SubmissionFilter, 'all'> {
    const persistedStatus = submission.status?.trim().toLowerCase();
    const checkStatus = this.submissionCheckStatus[submission.id];
    if (
      persistedStatus === 'graded' ||
      this.submissionTestResults[submission.id]?.length ||
      checkStatus === 'Accepted' ||
      checkStatus === 'Wrong Answer'
    ) {
      return 'graded';
    }
    if (persistedStatus === 'verified' || submission.verified_text) {
      return 'verified';
    }
    if (
      persistedStatus === 'extracted' ||
      submission.extracted_text ||
      this.extractedText[submission.id]
    ) {
      return 'extracted';
    }
    return 'new';
  }

  getSubmissionStatusLabel(submission: Submission): string {
    const labels: Record<Exclude<SubmissionFilter, 'all'>, string> = {
      new: 'Needs OCR',
      extracted: 'Needs review',
      verified: 'Ready to grade',
      graded: 'Graded',
    };
    return labels[this.getSubmissionStatus(submission)];
  }

  getSubmissionGradeSummary(submission: Submission | null): string {
    if (
      !submission ||
      submission.passed_test_cases === undefined ||
      submission.total_test_cases === undefined ||
      submission.total_test_cases <= 0
    ) {
      return '';
    }

    const score = Number(
      (
        submission.score_percent ??
        (submission.passed_test_cases / submission.total_test_cases) * 100
      ).toFixed(2),
    );
    return `${submission.passed_test_cases}/${submission.total_test_cases} test cases passed — Score: ${score}%`;
  }

  getQuestionName(submission: Submission): string {
    const selectedOrAssignedId =
      submission.id === this.selectedSubmission?.id
        ? this.selectedQuestionId || submission.question_id
        : submission.question_id;
    const assigned = this.questions.find(
      (question) => question.id === selectedOrAssignedId,
    );
    if (assigned) return assigned.question_name;

    const linked = this.getLinkedQuestion(submission);
    return linked?.question_name || 'No question assigned';
  }

  isExtracting(id: string): boolean {
    return this.extractingId === id;
  }

  isSaving(id: string): boolean {
    return this.savingId === id;
  }

  updateSubmissionCode(id: string, code: string) {
    if (this.editableText[id] === code) return;
    this.editableText[id] = code;
    this.dirtyCodeIds.add(id);
    this.invalidateGrading(id);
    this.clearCompletedGrade(id);
  }

  formatCode() {
    this.codeEditor?.format();
  }

  onSelectedQuestionChange(questionId: string) {
    this.selectedQuestionId = questionId;

    if (!this.selectedSubmission) return;

    this.dirtyQuestionIds.add(this.selectedSubmission.id);
    this.invalidateGrading(this.selectedSubmission.id);
    this.selectedSubmission.question_id = questionId || undefined;

    this.clearCompletedGrade(this.selectedSubmission.id);
    this.cdr.detectChanges();
  }

  async checkSubmission(submission: Submission | null) {
    if (!submission) return;

    const submissionId = submission.id;
    const generation = this.startGradingGeneration(submissionId);
    const gradingRevision = submission.grading_revision ?? 0;

    this.isChecking = true;
    this.checkError = '';
    this.submissionCheckStatus[submission.id] = '';
    this.submissionRunOutput[submission.id] = '';
    this.submissionTestResults[submission.id] = [];

    try {
      const question = this.getSubmissionQuestion(submission);

      const studentCode =
        this.editableText[submission.id] ||
        submission.verified_text ||
        submission.extracted_text ||
        '';

      if (!question) {
        this.checkError = 'No question is linked to this submission.';
        return;
      }

      if (!studentCode.trim()) {
        this.checkError = 'No student code found.';
        return;
      }

      if (this.dirtyCodeIds.has(submissionId)) {
        this.checkError = 'Save the edited code before grading.';
        return;
      }

      const testCases = question.test_cases || [];

      if (testCases.length === 0) {
        this.checkError = 'No test case found for this question.';
        return;
      }

      // Grade only against the persisted question assignment. The step tabs let
      // a teacher change the question dropdown without saving; grading that
      // unsaved selection would run every test case on Judge0 and then fail the
      // persistence guard (which matches on the saved question_id) with a
      // misleading "inputs changed" error. this.submissions holds the last
      // saved value (onSelectedQuestionChange only touches selectedSubmission).
      const persistedSubmission = this.submissions.find(
        (item) => item.id === submissionId,
      );
      if (
        persistedSubmission &&
        persistedSubmission.question_id !== question.id
      ) {
        this.checkError = 'Save the selected question before grading.';
        return;
      }

      const testResults: TestCaseResult[] = [];
      const runResults = await firstValueFrom(
        this.judge0Service.runCCodeBatch(
          testCases.map((testCase) => ({
            sourceCode: buildCQuestionSource(
              question.question_type,
              studentCode,
              testCase.test_code,
            ),
            stdin: this.stdinFor(
              question.question_type,
              testCase.test_input,
            ),
          })),
        ),
      );

      if (!this.isCurrentGrading(submissionId, generation)) return;

      for (const [index, testCase] of testCases.entries()) {
        const runResult = runResults[index];
        const stdin = this.stdinFor(
          question.question_type,
          testCase.test_input,
        );

        const actualOutput = (runResult.stdout || '').trim();
        const expectedOutput = (testCase.expected_output || '').trim();

        // status.id === 3 ("Accepted") already means Judge0 compiled and ran
        // the code without a compile error (status 6) or runtime crash
        // (status 7-12). Don't additionally require stderr/compile_output to
        // be empty — a program can compile with only warnings (e.g. a
        // missing #include) and still run correctly.
        const compilationPassed = runResult.status?.id === 3;

        const normalizedExpected = normalizeOutput(expectedOutput);
        const normalizedActual = normalizeOutput(actualOutput);
        const outputPassed = normalizedExpected === normalizedActual;
        const passed = outputPassed && compilationPassed;

        testResults.push({
          caseNumber: index + 1,
          stdin,
          expectedOutput: normalizedExpected,
          actualOutput: normalizedActual || actualOutput,
          status: passed
            ? 'Accepted'
            : compilationPassed
              ? 'Wrong Answer'
              : runResult.status?.description || 'Error',
          passed,
        });
      }

      if (!this.isCurrentGrading(submissionId, generation)) return;

      try {
        const newGradingRevision = await this.supabase.updateSubmissionGrade(
          submissionId,
          testResults,
          gradingRevision,
          question.id,
        );
        if (!this.isCurrentGrading(submissionId, generation)) return;
        if (newGradingRevision === null) {
          this.checkError =
            'Submission inputs changed during grading. Run grading again.';
          this.submissionCheckStatus[submission.id] = 'Error';
          return;
        }

        submission.grading_revision = newGradingRevision;
        const storedSubmission = this.submissions.find(
          (item) => item.id === submissionId,
        );
        if (storedSubmission) {
          storedSubmission.grading_revision = newGradingRevision;
        }
      } catch {
        if (!this.isCurrentGrading(submissionId, generation)) return;
        this.checkError =
          'Test cases completed, but the grade could not be saved.';
        this.submissionCheckStatus[submission.id] = 'Error';
        return;
      }

      this.submissionTestResults[submission.id] = testResults;
      this.submissionRunOutput[submission.id] =
        testResults.at(-1)?.actualOutput || '';
      this.submissionCheckStatus[submission.id] = testResults.every(
        (result) => result.passed,
      )
        ? 'Accepted'
        : 'Wrong Answer';

      const passedTestCases = testResults.filter((result) => result.passed).length;
      const scorePercent = Number(
        ((passedTestCases / testResults.length) * 100).toFixed(2),
      );
      const gradedAt = new Date().toISOString();
      const storedSubmission = this.submissions.find(
        (item) => item.id === submission.id,
      );
      for (const item of [submission, storedSubmission]) {
        if (!item) continue;
        item.status = 'graded';
        item.grading_results = testResults;
        item.passed_test_cases = passedTestCases;
        item.total_test_cases = testResults.length;
        item.score_percent = scorePercent;
        item.graded_at = gradedAt;
      }
      if (storedSubmission) this.rememberPersistedSubmission(storedSubmission);
    } catch (error) {
      if (!this.isCurrentGrading(submissionId, generation)) return;
      this.checkError = 'Failed to execute test cases.';
      this.submissionCheckStatus[submission.id] = 'Error';
    } finally {
      if (!this.isCurrentGrading(submissionId, generation)) return;
      this.isChecking = false;
      this.cdr.detectChanges();
    }
  }

  async loadQuestions() {
    const { data, error } = await this.supabase.getQuestions();

    if (error) {
      console.error(error);
      return;
    }

    this.questions = data ?? [];
  }

  getSelectedQuestion() {
    return this.questions.find((q) => q.id === this.selectedQuestionId) || null;
  }

  getExecutionSourceCode(submission: Submission | null): string {
    if (!submission) return '';

    const question = this.getSubmissionQuestion(submission);
    const studentCode = this.getStudentCode(submission);
    const firstTestCase = question?.test_cases?.[0];

    if (
      !question ||
      (question.question_type === 'function' && !firstTestCase)
    ) {
      return studentCode;
    }

    return buildCQuestionSource(
      question.question_type,
      studentCode,
      firstTestCase?.test_code,
    );
  }

  getExecutionStdin(submission: Submission | null): string {
    const question = submission ? this.getSubmissionQuestion(submission) : null;
    const firstTestCase = question?.test_cases?.[0];

    return question
      ? this.stdinFor(question.question_type, firstTestCase?.test_input)
      : '';
  }

  getExecutionExpectedOutput(submission: Submission | null): string {
    const question = submission ? this.getSubmissionQuestion(submission) : null;

    return question?.test_cases?.[0]?.expected_output || '';
  }

  hasExecutionQuestion(submission: Submission | null): boolean {
    return !!(submission && this.getSubmissionQuestion(submission));
  }

  private stdinFor(
    questionType: SubmissionQuestion['question_type'],
    input: string | null | undefined,
  ): string {
    return questionType === 'program' ? input || '' : '';
  }

  private clearExecutionResults(id: string) {
    this.checkError = '';
    this.submissionCheckStatus[id] = '';
    this.submissionRunOutput[id] = '';
    this.submissionTestResults[id] = [];
  }

  private cloneSubmission(submission: Submission): Submission {
    return {
      ...submission,
      grading_results: submission.grading_results?.map((result) => ({
        ...result,
      })),
    };
  }

  private rememberPersistedSubmission(submission: Submission): void {
    this.persistedSubmissions.set(
      submission.id,
      this.cloneSubmission(submission),
    );
  }

  private restorePersistedSubmission(id: string): void {
    const snapshot = this.persistedSubmissions.get(id);
    if (!snapshot) return;

    const restored = this.cloneSubmission(snapshot);
    const storedSubmission = this.submissions.find((item) => item.id === id);
    if (storedSubmission) Object.assign(storedSubmission, restored);

    this.editableText[id] =
      restored.verified_text || restored.extracted_text || '';
    this.selectedQuestionId =
      restored.question_id || this.getLinkedQuestion(restored)?.id || '';
    this.editableTopic = restored.topic || 'Uncategorized';
    this.restorePersistedGrade(restored);
  }

  private restorePersistedGrade(submission: Submission): void {
    const persistedResults = Array.isArray(submission.grading_results)
      ? submission.grading_results.map((result) => ({ ...result }))
      : [];
    this.submissionTestResults[submission.id] = persistedResults;
    this.submissionCheckStatus[submission.id] = persistedResults.length
      ? persistedResults.every((result) => result.passed)
        ? 'Accepted'
        : 'Wrong Answer'
      : '';
    this.submissionRunOutput[submission.id] =
      persistedResults.at(-1)?.actualOutput || '';
  }

  private clearCompletedGrade(id: string) {
    this.clearExecutionResults(id);

    const storedSubmission = this.submissions.find((item) => item.id === id);
    for (const submission of [this.selectedSubmission, storedSubmission]) {
      if (!submission || submission.id !== id) continue;
      const hadCompletedGrade =
        submission.status?.trim().toLowerCase() === 'graded' ||
        !!submission.grading_results?.length ||
        !!submission.graded_at;

      submission.grading_results = [];
      submission.passed_test_cases = undefined;
      submission.total_test_cases = undefined;
      submission.score_percent = undefined;
      submission.graded_at = undefined;

      if (hadCompletedGrade) {
        submission.status = submission.verified_text
          ? 'verified'
          : submission.extracted_text
            ? 'extracted'
            : 'pending';
      }
    }
  }

  private getSubmissionQuestion(
    submission: Submission,
  ): SubmissionQuestion | null {
    const selectedQuestion = this.getSelectedQuestion();
    if (selectedQuestion) return selectedQuestion;

    const linkedQuestion = this.getLinkedQuestion(submission);

    return linkedQuestion || null;
  }

  private getLinkedQuestion(submission: Submission): SubmissionQuestion | null {
    if (Array.isArray(submission.questions)) {
      return submission.questions[0] || null;
    }
    return submission.questions || null;
  }

  private getStudentCode(submission: Submission): string {
    return (
      this.editableText[submission.id] ||
      submission.verified_text ||
      submission.extracted_text ||
      ''
    );
  }
}
