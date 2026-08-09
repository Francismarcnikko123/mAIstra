import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { SupabaseService } from '../../services/supabase';
import { CodeEditorComponent } from '../code-editor/code-editor';
import { Judge0 } from '../judge0/judge0';
import { Judge0Service, GradingResult } from '../../services/judge0.service';
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
  questions?: SubmissionQuestion;
}

interface CodeCheckResult {
  logicSimilar: boolean;
  outputSame: boolean;
  compilationPassed: boolean;
  overallMatched: boolean;
  expectedOutput: string;
  actualOutput: string;
  logicDetails: GradingResult['logic_details'];
}

interface TopicGroup {
  topic: string;
  submissions: Submission[];
}

@Component({
  selector: 'app-submissions-list',
  standalone: true,
  imports: [CommonModule, FormsModule, CodeEditorComponent, Judge0],
  templateUrl: './submissions-list.html',
  styleUrl: './submissions-list.css',
})
export class SubmissionsListComponent implements OnInit, OnDestroy {
  selectedQuestionId = '';
  questions: any[] = [];
  submissions: Submission[] = [];
  groupedSubmissions: TopicGroup[] = [];
  collapsedFolders: Record<string, boolean> = {};

  // Modal state
  selectedSubmission: Submission | null = null;
  editableTopic: string = '';
  savingTopic = false;

  // OCR state
  extractingId: string | null = null;
  savingId: string | null = null;
  extractedText: Record<string, string> = {};
  editableText: Record<string, string> = {};
  extractionError: Record<string, string> = {};
  saveStatus: Record<string, string> = {}; // '' | 'saved' | 'error'
  showCodeExecutionEditor: Record<string, boolean> = {};

  // code checking state
  checkResult: CodeCheckResult | null = null;
  checkedSubmissionId: string | null = null;
  isChecking = false;
  checkError = '';

  private subscription: any;
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

    this.subscription = this.supabase.subscribeToSubmissions((payload: any) => {
      this.loadSubmissions();
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
    for (const s of this.submissions) {
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

  toggleFolder(topic: string) {
    this.collapsedFolders[topic] = !this.collapsedFolders[topic];
  }

  openModal(submission: Submission) {
    this.selectedSubmission = { ...submission };
    this.editableTopic = submission.topic || 'Uncategorized';

    this.checkResult = null;
    this.checkError = '';
    this.isChecking = false;
    this.checkedSubmissionId = null;

    const saved = submission.verified_text || submission.extracted_text || '';
    if (saved && !this.editableText[submission.id]) {
      this.editableText[submission.id] = saved;
    }
  }

  closeModal() {
    this.selectedSubmission = null;
  }

  async saveTopic() {
    if (!this.selectedSubmission) return;
    this.savingTopic = true;
    try {
      await this.supabase.updateSubmissionTopic(
        this.selectedSubmission.id,
        this.editableTopic,
      );
      const s = this.submissions.find(
        (x) => x.id === this.selectedSubmission!.id,
      );
      if (s) s.topic = this.editableTopic;
      this.selectedSubmission.topic = this.editableTopic;
      this.groupSubmissions();
      this.cdr.detectChanges();
    } catch (err) {
      console.error('Failed to save topic:', err);
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
      const res: any = await this.http
        .post('http://localhost:8000/api/ocr/extract-from-url', {
          image_url: this.selectedSubmission.image_url,
          submission_id: id,
        })
        .toPromise();
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
      this.showCodeExecutionEditor[id] = true;
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

  isExtracting(id: string): boolean {
    return this.extractingId === id;
  }

  isSaving(id: string): boolean {
    return this.savingId === id;
  }

  async checkSubmission(submission: Submission | null) {
    if (!submission) return;

    this.isChecking = true;
    this.checkError = '';
    this.checkResult = null;
    this.checkedSubmissionId = submission.id;

    try {
      const linkedQuestion = Array.isArray(submission.questions)
        ? submission.questions[0]
        : submission.questions;

      const selectedQuestion = this.getSelectedQuestion();
      const question = linkedQuestion || selectedQuestion;

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

      const firstTestCase = question.test_cases?.[0];

      if (!firstTestCase) {
        this.checkError = 'No test case found for this question.';
        return;
      }

      const sourceCode =
        question.question_type === 'function'
          ? `#include <stdio.h>

${studentCode}

int main() {
${firstTestCase.test_code}

  return 0;
}`
          : studentCode;

      const stdin =
        question.question_type === 'program'
          ? firstTestCase.test_input || ''
          : '';

      const runResult = await firstValueFrom(
        this.judge0Service.runCCode(sourceCode, stdin),
      );

      const actualOutput = (runResult.stdout || '').trim();
      const expectedOutput = (firstTestCase.expected_output || '').trim();

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

      const logicSimilar = result.logic_details.every((check) => check.passed);
      const outputSame = result.output_details.passed;

      this.checkResult = {
        logicSimilar,
        outputSame,
        compilationPassed,
        overallMatched: logicSimilar && outputSame && compilationPassed,
        expectedOutput: result.output_details.expected_normalized,
        actualOutput: result.output_details.actual_normalized,
        logicDetails: result.logic_details,
      };

      this.checkedSubmissionId = submission.id;
    } catch (error) {
      this.checkError = 'Failed to check logic and output.';
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

}
