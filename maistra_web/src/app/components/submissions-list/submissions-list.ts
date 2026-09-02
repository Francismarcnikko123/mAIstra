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
import { Judge0, LogicAnalysisResult, TestCaseResult } from '../judge0/judge0';
import { Judge0Service } from '../../services/judge0.service';
import { firstValueFrom } from 'rxjs';

interface TestCase {
  test_code: string;
  test_input: string;
  expected_output: string;
  mark: number;
}
interface SubmissionQuestion {
  id: string;
  question_name: string;
  question_type: 'function' | 'program';
  model_answer: string;
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
  submissionLogicResults: Record<string, LogicAnalysisResult[]> = {};

  private subscription?: ReturnType<
    SupabaseService['subscribeToSubmissions']
  >;
  private saveStatusTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private saveGenerations = new Map<string, number>();
  private destroyed = false;

  constructor(
    private supabase: SupabaseService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private judge0Service: Judge0Service,
  ) {}

  async ngOnInit() {
    await this.loadQuestions();
    await this.loadSubmissions();

    this.subscription = this.supabase.subscribeToSubmissions(() => {
      void this.loadSubmissions();
    });
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

  async loadSubmissions() {
    const { data, error } = await this.supabase.getSubmissions();
    if (error) {
      console.error(error);
      return;
    }
    this.submissions = (data ?? []) as unknown as Submission[];
    // Seed the editor with previously saved text so verified/extracted work
    // reappears when the page reloads or a submission is reopened.
    for (const s of this.submissions) {
      const saved = s.verified_text || s.extracted_text || '';
      if (saved) this.editableText[s.id] = saved;
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
    this.selectedSubmission = { ...submission };
    this.editableTopic = submission.topic || 'Uncategorized';
    const linkedQuestion = this.getLinkedQuestion(submission);
    this.selectedQuestionId = submission.question_id || linkedQuestion?.id || '';
    this.reviewStep = 1;

    this.checkError = '';
    this.isChecking = false;
    this.submissionCheckStatus[submission.id] = '';
    this.submissionTestResults[submission.id] = [];
    this.submissionLogicResults[submission.id] = [];

    const saved = submission.verified_text || submission.extracted_text || '';
    if (saved && !this.editableText[submission.id]) {
      this.editableText[submission.id] = saved;
    }
  }

  closeModal() {
    this.selectedSubmission = null;
    this.reviewStep = 1;
  }

  setReviewStep(step: ReviewStep) {
    if (step === 3 && !this.canOpenGradingStep()) return;
    this.reviewStep = step;
  }

  async continueFromDetails() {
    if (!this.selectedQuestionId) return;

    const saved = await this.saveSubmissionDetails();
    if (saved) this.reviewStep = 2;
  }

  async saveCodeAndContinue() {
    if (!this.canOpenGradingStep()) return;

    await this.saveVerifiedText();
    if (this.selectedSubmission && this.saveStatus[this.selectedSubmission.id] === 'saved') {
      this.reviewStep = 3;
    }
  }

  async saveSubmissionDetails(): Promise<boolean> {
    if (!this.selectedSubmission) return false;
    this.savingTopic = true;
    try {
      await this.supabase.updateSubmissionDetails(
        this.selectedSubmission.id,
        this.editableTopic,
        this.selectedQuestionId || null,
      );
      const s = this.submissions.find(
        (x) => x.id === this.selectedSubmission!.id,
      );
      if (s) {
        s.topic = this.editableTopic;
        s.question_id = this.selectedQuestionId || undefined;
      }
      this.selectedSubmission.topic = this.editableTopic;
      this.selectedSubmission.question_id = this.selectedQuestionId || undefined;
      this.groupSubmissions();
      this.cdr.detectChanges();
      return true;
    } catch (err) {
      console.error('Failed to save submission details:', err);
      return false;
    } finally {
      this.savingTopic = false;
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
      this.editableText[id] = text;
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
      await this.supabase.updateSubmissionText(id, text, ocrText);
      if (!this.isCurrentSave(id, generation)) return;

      const s = this.submissions.find((x) => x.id === id);
      if (s) {
        s.verified_text = text;
        if (ocrText !== undefined) s.extracted_text = ocrText;
      }
      if (this.selectedSubmission?.id === id) {
        this.selectedSubmission.verified_text = text;
        if (ocrText !== undefined)
          this.selectedSubmission.extracted_text = ocrText;
      }
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
    return (
      !!this.getStudentCode(this.selectedSubmission).trim() &&
      !!this.getSubmissionQuestion(this.selectedSubmission)
    );
  }

  getSubmissionStatus(submission: Submission): Exclude<SubmissionFilter, 'all'> {
    const persistedStatus = submission.status?.trim().toLowerCase();
    if (
      persistedStatus === 'graded' ||
      this.submissionTestResults[submission.id]?.length ||
      this.submissionCheckStatus[submission.id]
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
    this.editableText[id] = code;
  }

  formatCode() {
    this.codeEditor?.format();
  }

  onSelectedQuestionChange(questionId: string) {
    this.selectedQuestionId = questionId;

    if (!this.selectedSubmission) return;

    this.selectedSubmission.question_id = questionId || undefined;

    this.clearExecutionResults(this.selectedSubmission.id);
    this.cdr.detectChanges();
  }

  async checkSubmission(submission: Submission | null) {
    if (!submission) return;

    this.isChecking = true;
    this.checkError = '';
    this.submissionCheckStatus[submission.id] = '';
    this.submissionRunOutput[submission.id] = '';
    this.submissionTestResults[submission.id] = [];
    this.submissionLogicResults[submission.id] = [];

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

      if (!question.model_answer?.trim()) {
        this.checkError = 'No model answer found.';
        return;
      }

      const testCases = question.test_cases || [];

      if (testCases.length === 0) {
        this.checkError = 'No test case found for this question.';
        return;
      }

      const testResults: TestCaseResult[] = [];
      let logicResults: LogicAnalysisResult[] | null = null;

      for (const [index, testCase] of testCases.entries()) {
        const sourceCode =
          question.question_type === 'function'
            ? `#include <stdio.h>

${studentCode}

int main() {
${testCase.test_code}

  return 0;
}`
            : studentCode;

        const stdin =
          question.question_type === 'program' ? testCase.test_input || '' : '';

        const runResult = await firstValueFrom(
          this.judge0Service.runCCode(sourceCode, stdin),
        );

        const actualOutput = (runResult.stdout || '').trim();
        const expectedOutput = (testCase.expected_output || '').trim();

        const compilationPassed =
          !runResult.stderr &&
          !runResult.compile_output &&
          runResult.status?.id === 3;

        const result = await firstValueFrom(
          this.judge0Service.gradeSubmission({
            model_code: question.model_answer,
            student_code: studentCode,
            expected_output: expectedOutput,
            actual_output: actualOutput,
            compilation_passed: compilationPassed,
          }),
        );

        const passed = result.output_details.passed && compilationPassed;
        logicResults ??= result.logic_details;

        testResults.push({
          caseNumber: index + 1,
          stdin,
          expectedOutput: result.output_details.expected_normalized,
          actualOutput: result.output_details.actual_normalized || actualOutput,
          status: passed
            ? 'Accepted'
            : compilationPassed
              ? 'Wrong Answer'
              : runResult.status?.description || 'Error',
          passed,
        });
      }

      this.submissionTestResults[submission.id] = testResults;
      this.submissionLogicResults[submission.id] = logicResults ?? [];
      this.submissionRunOutput[submission.id] =
        testResults.at(-1)?.actualOutput || '';
      this.submissionCheckStatus[submission.id] = testResults.every(
        (result) => result.passed,
      )
        ? 'Accepted'
        : 'Wrong Answer';
    } catch (error) {
      this.checkError = 'Failed to check logic and output.';
      this.submissionCheckStatus[submission.id] = 'Error';
    } finally {
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

    if (!question || question.question_type === 'program' || !firstTestCase) {
      return studentCode;
    }

    return `#include <stdio.h>

${studentCode}

int main() {
${firstTestCase.test_code}

  return 0;
}`;
  }

  getExecutionStdin(submission: Submission | null): string {
    const question = submission ? this.getSubmissionQuestion(submission) : null;
    const firstTestCase = question?.test_cases?.[0];

    return question?.question_type === 'program'
      ? firstTestCase?.test_input || ''
      : '';
  }

  getExecutionExpectedOutput(submission: Submission | null): string {
    const question = submission ? this.getSubmissionQuestion(submission) : null;

    return question?.test_cases?.[0]?.expected_output || '';
  }

  hasExecutionQuestion(submission: Submission | null): boolean {
    return !!(submission && this.getSubmissionQuestion(submission));
  }

  private clearExecutionResults(id: string) {
    this.checkError = '';
    this.submissionCheckStatus[id] = '';
    this.submissionRunOutput[id] = '';
    this.submissionTestResults[id] = [];
    this.submissionLogicResults[id] = [];
  }

  private getSubmissionQuestion(
    submission: Submission,
  ): SubmissionQuestion | null {
    const selectedQuestion = this.getSelectedQuestion();
    if (selectedQuestion) return selectedQuestion;

    const linkedQuestion = this.getLinkedQuestion(submission);

    return linkedQuestion || null;
  }

  private getLinkedQuestion(
    submission: Submission,
  ): SubmissionQuestion | null {
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
