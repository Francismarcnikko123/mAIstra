import {
  Component,
  OnInit,
  OnDestroy,
  ChangeDetectorRef,
  ElementRef,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { SupabaseService } from '../../services/supabase';
import { CodeEditorComponent } from '../code-editor/code-editor';
import { Judge0, LogicAnalysisResult, TestCaseResult } from '../judge0/judge0';
import { Judge0Service } from '../../services/judge0.service';
import { firstValueFrom } from 'rxjs';
import {
  SubmissionAnswer,
  answerProblems,
  answersToSave,
  isBlankAnswer,
  parseAnswers,
  takenQuestionIds,
} from './extra-answers';

interface TestCase {
  test_code: string;
  test_input: string;
  expected_output: string;
  mark: number;
}
interface SubmissionQuestion {
  id: string;
  question_name: string;
  question_text?: string;
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
  answers?: unknown;
  topic?: string;
  question_id?: string;
  questions?: SubmissionQuestion | SubmissionQuestion[];
}

interface TopicGroup {
  topic: string;
  submissions: Submission[];
}

type ReviewStep = 1 | 2 | 3;

const EXTRA_PROGRAMS_UNSAVABLE =
  "Program 1 was saved. Programs 2 and up can't be saved yet: the database is missing the answers column. Ask Jayrald to apply the migration.";
type SubmissionFilter = 'all' | 'new' | 'extracted' | 'verified' | 'graded';

@Component({
  selector: 'app-submissions-list',
  standalone: true,
  imports: [CommonModule, FormsModule, CodeEditorComponent, Judge0],
  templateUrl: './submissions-list.html',
  styleUrls: ['./submissions-list.css', './program-tabs.css'],
})
export class SubmissionsListComponent implements OnInit, OnDestroy {
  @ViewChild('codeEditor') codeEditor?: CodeEditorComponent;
  @ViewChildren('extraEditor') extraEditors?: QueryList<CodeEditorComponent>;
  @ViewChild('tabList') tabList?: ElementRef<HTMLElement>;
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
  // Submission id whose re-extract confirmation dialog is open, or null.
  reextractConfirmId: string | null = null;

  // Program tabs. Program 1 is editableText; Programs 2..n are extraAnswers,
  // saved to submissions.answers under the same submission id.
  extraAnswers: Record<string, SubmissionAnswer[]> = {};
  // 0 = Program 1; n = extraAnswers[id][n - 1].
  activeTab = 0;
  // Index (into extraAnswers) of the tab whose × awaits a second click.
  removeConfirmIndex: number | null = null;
  questionPickerOpen = false;
  extraAnswersError: Record<string, string> = {};
  // Read-only question details (prompt + test cases) for the open tab.
  questionPeekOpen = false;
  // Read-only OCR reading shown beside the photo.
  ocrPanelOpen = false;
  // "Some programs aren't saved yet" prompt when leaving the review.
  closeConfirmOpen = false;
  // What was last loaded or saved, to mark unsaved tabs and back "Discard".
  private savedProgram1: Record<string, string> = {};
  private savedExtras: Record<string, SubmissionAnswer[]> = {};

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
      // Seed once. This also runs on every realtime INSERT, and must not
      // replace unsaved edits in a review that is open.
      if (saved && this.editableText[s.id] === undefined) this.editableText[s.id] = saved;
      if (this.savedProgram1[s.id] === undefined) this.savedProgram1[s.id] = saved;
      // Seed saved program tabs once. Never replace a loaded list: the teacher
      // may have pasted programs that aren't saved yet.
      if (!this.extraAnswers[s.id]) {
        this.extraAnswers[s.id] = parseAnswers(s.answers);
        this.savedExtras[s.id] = parseAnswers(s.answers);
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
    this.selectedSubmission = { ...submission };
    this.editableTopic = submission.topic || 'Uncategorized';
    const linkedQuestion = this.getLinkedQuestion(submission);
    this.selectedQuestionId = submission.question_id || linkedQuestion?.id || '';
    this.reviewStep = 1;
    this.activeTab = 0;
    this.removeConfirmIndex = null;
    this.questionPickerOpen = false;
    this.questionPeekOpen = false;
    this.ocrPanelOpen = false;
    this.closeConfirmOpen = false;
    this.extraAnswersError[submission.id] = '';

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
    this.closeConfirmOpen = false;
  }

  /** Close, or first ask when some program on this paper isn't saved. */
  requestCloseModal() {
    if (this.selectedSubmission && this.hasUnsavedPrograms(this.selectedSubmission.id)) {
      this.closeConfirmOpen = true;
      return;
    }
    this.closeModal();
  }

  keepEditing() {
    this.closeConfirmOpen = false;
  }

  /** Back to what was last loaded or saved for this paper, then close. */
  discardChangesAndClose() {
    if (this.selectedSubmission) {
      const id = this.selectedSubmission.id;
      this.editableText[id] = this.savedProgram1[id] ?? '';
      this.extraAnswers[id] = (this.savedExtras[id] ?? []).map((answer) => ({ ...answer }));
      delete this.extractedText[id];
      this.extraAnswersError[id] = '';
    }
    this.closeModal();
  }

  /** Save with the usual rules; close only if the save went through. */
  async saveAndClose() {
    this.closeConfirmOpen = false;
    const id = this.selectedSubmission?.id;
    await this.saveVerifiedText();
    if (id && this.saveStatus[id] === 'saved') {
      this.closeModal();
    } else if (this.selectedSubmission) {
      // Show the reason (a save rule or a failed save) where the tabs are.
      this.reviewStep = 2;
    }
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

    // Guard against silently discarding the teacher's work. Re-extracting
    // overwrites the editor with a fresh OCR result; if the current editor
    // content differs from the last extraction (the teacher has made
    // corrections, or a previously-saved verified text was loaded), ask for
    // confirmation via the in-app dialog first. A first extraction (no editor
    // content yet) or a re-extract with no edits since the last one runs
    // straight through without prompting.
    // Once the paper is split into tabs, a whole-page reading can't go back
    // into Program 1 without duplicating the other programs. Show it beside
    // the photo instead; the teacher copies what they need into a tab.
    if (this.getExtraAnswers(id).length) {
      await this.performExtract(id, { replaceProgram1: false });
      return;
    }

    const current = this.editableText[id];
    const lastExtraction = this.extractedText[id];
    const hasEdits = !!current && current !== lastExtraction;
    if (hasEdits) {
      this.reextractConfirmId = id;
      this.cdr.detectChanges();
      return;
    }

    await this.performExtract(id);
  }

  /** Confirm handler for the re-extract dialog: proceed with the extraction. */
  confirmReextract() {
    const id = this.reextractConfirmId;
    this.reextractConfirmId = null;
    if (id) this.performExtract(id);
  }

  /** Cancel handler for the re-extract dialog: keep the teacher's edits. */
  cancelReextract() {
    this.reextractConfirmId = null;
  }

  private async performExtract(id: string, options = { replaceProgram1: true }) {
    if (!this.selectedSubmission) return;
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
      if (options.replaceProgram1) {
        this.editableText[id] = text;
      } else {
        this.ocrPanelOpen = true;
      }
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

    // Save rules for Programs 2..n are checked before any database write,
    // so a blocked save never touches the generation/timer guards below.
    const problems = answerProblems(
      this.selectedQuestionId || null,
      this.getExtraAnswers(id),
    );
    if (problems.length) {
      this.extraAnswersError[id] = problems[0];
      this.saveStatus[id] = '';
      this.cdr.detectChanges();
      return;
    }
    // Until the answers migration is applied, Programs 2..n have nowhere to
    // go. Program 1 still saves; the extra tabs stay on screen as a preview
    // and the teacher is told they weren't saved.
    const extrasUnsaved =
      !this.extraProgramsSavable && answersToSave(this.getExtraAnswers(id)).length > 0;
    this.extraAnswersError[id] = '';

    const generation = this.startSaveGeneration(id);
    this.savingId = id;
    this.clearSaveStatusTimer(id);
    this.saveStatus[id] = '';
    try {
      const text = this.editableText[id];
      // The OCR's own output (if extraction ran this session) is saved as
      // extracted_text; the teacher's edits only ever become verified_text.
      const ocrText = this.extractedText[id];
      const extras = answersToSave(this.getExtraAnswers(id));
      await this.supabase.updateSubmissionText(id, text, ocrText, extras);
      if (!this.isCurrentSave(id, generation)) return;

      const s = this.submissions.find((x) => x.id === id);
      if (s) {
        s.verified_text = text;
        if (ocrText !== undefined) s.extracted_text = ocrText;
        if (!extrasUnsaved) s.answers = extras;
      }
      if (this.selectedSubmission?.id === id) {
        this.selectedSubmission.verified_text = text;
        if (ocrText !== undefined)
          this.selectedSubmission.extracted_text = ocrText;
        if (!extrasUnsaved) this.selectedSubmission.answers = extras;
      }
      if (extrasUnsaved) this.extraAnswersError[id] = EXTRA_PROGRAMS_UNSAVABLE;
      this.savedProgram1[id] = text;
      if (!extrasUnsaved) this.savedExtras[id] = extras.map((answer) => ({ ...answer }));
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

  /** False while the database lacks submissions.answers (migration pending). */
  get extraProgramsSavable(): boolean {
    return this.supabase.answersColumnAvailable !== false;
  }

  getExtraAnswers(id: string): SubmissionAnswer[] {
    return this.extraAnswers[id] ?? [];
  }

  getActiveExtraAnswer(): SubmissionAnswer | undefined {
    if (this.activeTab === 0) return undefined;
    return this.getSelectedExtraAnswer(this.activeTab - 1);
  }

  addExtraAnswer() {
    if (!this.selectedSubmission) return;
    const id = this.selectedSubmission.id;
    const answers = [...this.getExtraAnswers(id), { code: '', question_id: null }];
    this.extraAnswers[id] = answers;
    this.selectTab(answers.length);
  }

  selectTab(tab: number) {
    this.activeTab = tab;
    this.removeConfirmIndex = null;
    this.questionPickerOpen = false;
    this.questionPeekOpen = false;
    // Show the tab first, then let Ace re-measure the now-visible editor.
    this.cdr.detectChanges();
    this.getActiveEditor()?.refresh();
  }

  /** Left/right arrow on a tab: move to the previous/next tab, wrapping. */
  moveTab(step: 1 | -1, event?: Event) {
    if (!this.selectedSubmission) return;
    event?.preventDefault();
    const count = this.getExtraAnswers(this.selectedSubmission.id).length + 1;
    this.selectTab((this.activeTab + step + count) % count);
    const tabs = this.tabList?.nativeElement.querySelectorAll<HTMLElement>('[role="tab"]');
    tabs?.[this.activeTab]?.focus();
  }

  /** Program 1 differs from what was last loaded or saved. */
  isProgram1Unsaved(id: string): boolean {
    return (this.editableText[id] ?? '') !== (this.savedProgram1[id] ?? '');
  }

  /** Tab has content that isn't in the saved programs. Blank tabs never count. */
  isExtraAnswerUnsaved(id: string, answer: SubmissionAnswer): boolean {
    if (isBlankAnswer(answer)) return false;
    return !(this.savedExtras[id] ?? []).some(
      (saved) => saved.code === answer.code && saved.question_id === answer.question_id,
    );
  }

  /** Anything on this paper that a close would lose, including removed tabs. */
  hasUnsavedPrograms(id: string): boolean {
    return (
      this.isProgram1Unsaved(id) ||
      JSON.stringify(answersToSave(this.getExtraAnswers(id))) !==
        JSON.stringify(this.savedExtras[id] ?? [])
    );
  }

  /** The question linked to the open tab, for the read-only "View question". */
  getActiveTabQuestion(): SubmissionQuestion | null {
    if (!this.selectedSubmission) return null;
    if (this.activeTab === 0) return this.getSubmissionQuestion(this.selectedSubmission);
    const questionId = this.getActiveExtraAnswer()?.question_id;
    return this.questions.find((question) => question.id === questionId) ?? null;
  }

  /** The OCR reading shown beside the photo: this session's, else the saved one. */
  getOcrText(submission: Submission): string {
    return this.extractedText[submission.id] ?? submission.extracted_text ?? '';
  }

  extraTabPlaceholder(index: number): string {
    return `Paste Program ${index + 2}'s code here, then choose its question above.`;
  }

  updateExtraAnswerCode(index: number, code: string) {
    const answer = this.getSelectedExtraAnswer(index);
    // Mutate in place: replacing the object would re-render the Ace editor
    // on every keystroke and lose the teacher's cursor.
    if (answer) answer.code = code;
    this.clearExtraAnswersError();
  }

  /** Program number already holding this question (other than tab `index`), or null. */
  questionOwner(questionId: string, index: number): number | null {
    if (!this.selectedSubmission) return null;
    return (
      takenQuestionIds(
        this.selectedQuestionId || null,
        this.getExtraAnswers(this.selectedSubmission.id),
        index,
      ).get(questionId) ?? null
    );
  }

  /** Links (or with null, clears) a tab's question. Taken questions are refused. */
  chooseExtraQuestion(index: number, questionId: string | null) {
    const answer = this.getSelectedExtraAnswer(index);
    if (!answer) return;
    if (questionId !== null && this.questionOwner(questionId, index) !== null) return;
    answer.question_id = questionId;
    this.questionPickerOpen = false;
    this.clearExtraAnswersError();
  }

  /** First click arms the tab's ×; the second click on the same tab removes it. */
  requestRemoveExtraAnswer(index: number) {
    if (!this.selectedSubmission) return;
    if (this.removeConfirmIndex !== index) {
      this.removeConfirmIndex = index;
      return;
    }
    const id = this.selectedSubmission.id;
    this.extraAnswers[id] = this.getExtraAnswers(id).filter((_, i) => i !== index);
    const removedTab = index + 1;
    const nextTab =
      this.activeTab === removedTab
        ? removedTab - 1
        : this.activeTab > removedTab
          ? this.activeTab - 1
          : this.activeTab;
    this.clearExtraAnswersError();
    this.selectTab(nextTab);
  }

  /** Any click outside a tab's × disarms a pending "Remove?". */
  cancelPendingRemove() {
    this.removeConfirmIndex = null;
  }

  getQuestionTitle(questionId: string): string {
    return (
      this.questions.find((question) => question.id === questionId)?.question_name ||
      'Unknown question'
    );
  }

  questionPreview(question: SubmissionQuestion): string {
    const text = (question.question_text ?? '').trim();
    return text.length > 70 ? `${text.slice(0, 70)}…` : text;
  }

  onPickerFocusOut(event: FocusEvent) {
    const next = event.relatedTarget as Node | null;
    const picker = event.currentTarget as HTMLElement;
    if (!next || !picker.contains(next)) this.questionPickerOpen = false;
  }

  trackByIndex(index: number): number {
    return index;
  }

  /**
   * Editors track their own tab object, so removing a tab destroys its
   * editor instead of handing that editor (and its undo history) to the
   * next tab. Tab objects are mutated in place, so the identity is stable.
   */
  trackByAnswer(_index: number, answer: SubmissionAnswer): SubmissionAnswer {
    return answer;
  }

  private getSelectedExtraAnswer(index: number): SubmissionAnswer | undefined {
    if (!this.selectedSubmission) return undefined;
    return this.getExtraAnswers(this.selectedSubmission.id)[index];
  }

  private getActiveEditor(): CodeEditorComponent | undefined {
    return this.activeTab === 0
      ? this.codeEditor
      : this.extraEditors?.get(this.activeTab - 1);
  }

  private clearExtraAnswersError() {
    if (this.selectedSubmission) this.extraAnswersError[this.selectedSubmission.id] = '';
  }

  /** Formats the open tab only. */
  formatCode() {
    this.getActiveEditor()?.format();
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
