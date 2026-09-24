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
  styleUrls: [
    './submissions-list.css',
    './submissions-list.review.css',
    './submissions-list.responsive.css',
  ],
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
  detailsSaveError = '';

  // OCR state
  // Tracked per submission: the modal can switch to another submission while
  // one's save or OCR is still running, and each must stay busy until its own
  // request finishes.
  private extractingIds = new Set<string>();
  private savingIds = new Set<string>();
  extractedText: Record<string, string> = {};
  editableText: Record<string, string> = {};
  extractionError: Record<string, string> = {};
  saveStatus: Record<string, string> = {}; // '' | 'saved' | 'error' | 'conflict'

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
  // The revision each draft started from, for the code editor and the Details
  // form. Saves send it so the database refuses to overwrite a newer change by
  // someone else. It deliberately lags behind live updates while a draft is
  // unsaved: the draft is still built on the older version.
  private codeBaseRevisions = new Map<string, number>();
  private detailsBaseRevisions = new Map<string, number>();
  private dirtyCodeIds = new Set<string>();
  private dirtyQuestionIds = new Set<string>();
  private dirtyTopicIds = new Set<string>();
  private loadGeneration = 0;
  // Orders every fetch (full reload or single row) by when it started, so a
  // slower, older fetch never overwrites a row a newer one already applied.
  private snapshotSequence = 0;
  private rowSnapshots = new Map<string, number>();
  private destroyed = false;

  constructor(
    private supabase: SupabaseService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private judge0Service: Judge0Service,
  ) {}

  async ngOnInit() {
    this.subscription = this.supabase.subscribeToSubmissions((payload) => {
      if (this.destroyed) return;
      // Refetch only the row that changed. A full reload per event re-downloads
      // every submission, including on the echo of this page's own saves.
      const id = payload?.new?.id;
      if (typeof id === 'string') void this.refreshSubmission(id);
      else void this.loadSubmissions();
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
    const snapshot = ++this.snapshotSequence;
    const { data, error } = await this.supabase.getSubmissions();
    if (this.destroyed || generation !== this.loadGeneration) return;
    if (error) {
      console.error(error);
      return;
    }
    this.applySubmissionRows(
      (data ?? []) as unknown as Submission[],
      snapshot,
      true,
    );
  }

  private async refreshSubmission(id: string) {
    const snapshot = ++this.snapshotSequence;
    const { data, error } = await this.supabase.getSubmission(id);
    if (this.destroyed) return;
    if (error) {
      console.error(error);
      return;
    }
    // No row means this page cannot see it (e.g. RLS); leave the list alone.
    if (!data) return;
    this.applySubmissionRows([data as unknown as Submission], snapshot, false);
  }

  // Merges freshly fetched rows into the list. `replaceList` is true for a
  // full reload (the rows are the whole list) and false for a single-row fetch.
  private applySubmissionRows(
    rows: Submission[],
    snapshot: number,
    replaceList: boolean,
  ) {
    // Fetches can land out of order: a snapshot taken before a newer row fetch,
    // or before one of this page's own writes, is older than the local copy.
    // Keep the newer local row rather than regress to the stale one.
    // grading_revision only ever increases, so it also orders our own writes.
    const currentById = new Map(
      this.submissions.map((item) => [item.id, item]),
    );
    const staleIds = new Set<string>();
    const incoming = rows.map((row) => {
      const current = currentById.get(row.id);
      if (
        current &&
        ((this.rowSnapshots.get(row.id) ?? 0) > snapshot ||
          (current.grading_revision ?? 0) > (row.grading_revision ?? 0))
      ) {
        staleIds.add(row.id);
        return current;
      }
      this.rowSnapshots.set(row.id, snapshot);
      return row;
    });

    const selectedId = this.selectedSubmission?.id;
    const refreshed = selectedId
      ? incoming.find((item) => item.id === selectedId)
      : undefined;
    if (selectedId && refreshed) {
      const persisted = this.persistedSubmissions.get(selectedId);
      const persistedTopic = persisted?.topic || 'Uncategorized';
      if (this.editableTopic !== persistedTopic) {
        this.dirtyTopicIds.add(selectedId);
      }
    }

    for (const submission of incoming) {
      if (!staleIds.has(submission.id)) {
        this.rememberPersistedSubmission(submission);
      }
    }

    if (replaceList) {
      const incomingIds = new Set(incoming.map((item) => item.id));
      // Rows fetched on their own after this snapshot was taken (e.g. a new
      // upload) are newer than it, so they stay even though it lacks them.
      const newerRows = this.submissions.filter(
        (item) =>
          !incomingIds.has(item.id) &&
          (this.rowSnapshots.get(item.id) ?? 0) > snapshot,
      );
      this.submissions = newerRows.length
        ? this.byNewestCapture([...newerRows, ...incoming])
        : incoming;
    } else {
      const incomingById = new Map(incoming.map((item) => [item.id, item]));
      this.submissions = this.byNewestCapture([
        ...this.submissions.map((item) => incomingById.get(item.id) ?? item),
        ...incoming.filter((item) => !currentById.has(item.id)),
      ]);
    }

    // Seed the editor with previously saved text so verified/extracted work
    // reappears when the page reloads or a submission is reopened.
    for (const s of incoming) {
      if (this.dirtyCodeIds.has(s.id)) continue;
      const saved = s.verified_text ?? s.extracted_text ?? '';
      this.editableText[s.id] = saved;
      this.codeBaseRevisions.set(s.id, s.grading_revision ?? 0);
    }

    if (selectedId && refreshed) {
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
      } else if (!this.isChecking) {
        // While grading runs, the persisted grade is about to be replaced;
        // restoring it would show stale results next to the in-flight check.
        this.restorePersistedGrade(refreshed);
      }
      if (!topicIsDirty) {
        this.editableTopic = refreshed.topic || 'Uncategorized';
      }
      if (!questionIsDirty && !topicIsDirty) {
        this.detailsBaseRevisions.set(selectedId, refreshed.grading_revision ?? 0);
      }
    }
    this.groupSubmissions();
    this.cdr.detectChanges();
  }

  private byNewestCapture(submissions: Submission[]): Submission[] {
    return [...submissions].sort(
      (a, b) => Date.parse(b.captured_at) - Date.parse(a.captured_at),
    );
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

    const saved = submission.verified_text ?? submission.extracted_text ?? '';
    this.editableText[submission.id] = saved;
    this.detailsSaveError = '';
    this.setBaseRevisions(submission);
  }

  closeModal() {
    if (this.selectedSubmission) {
      const id = this.selectedSubmission.id;
      this.invalidateGrading(id);
      this.restorePersistedSubmission(id);
      this.dirtyCodeIds.delete(id);
      this.dirtyQuestionIds.delete(id);
      this.dirtyTopicIds.delete(id);
      // The draft is discarded, so messages about saving it are stale too.
      this.clearSaveStatusTimer(id);
      this.saveStatus[id] = '';
    }
    this.selectedSubmission = null;
    this.reviewStep = 1;
    this.detailsSaveError = '';
  }

  setReviewStep(step: ReviewStep) {
    // Going back is always allowed; going forward needs the earlier steps saved.
    if (step > this.reviewStep && this.stepBlocker(step)) return;
    this.reviewStep = step;
  }

  // Why a step cannot be opened yet, or '' when it can. Every edit has to be
  // saved before moving on, so grading always runs on exactly what is stored.
  stepBlocker(step: ReviewStep): string {
    const submission = this.selectedSubmission;
    if (!submission || step === 1) return '';
    if (this.hasUnsavedDetails()) return 'Save the topic and question first';
    if (step === 2) return '';
    if (!this.canOpenGradingStep()) return 'Verify code and question first';
    if (this.hasUnsavedCode(submission.id)) return 'Save the code first';
    return '';
  }

  private hasUnsavedDetails(): boolean {
    const submission = this.selectedSubmission;
    if (!submission) return false;
    const saved = this.savedSubmission(submission.id);
    return (
      this.selectedQuestionId !== this.savedQuestionId(submission.id) ||
      this.editableTopic !== (saved?.topic || 'Uncategorized')
    );
  }

  // Describes the editor as it is now, not just the last request: after an
  // edit made during or after a save, the code on screen is not saved yet.
  saveStatusMessage(id: string): string {
    const status = this.saveStatus[id];
    if (status === 'error') return '✕ Save failed—please try again';
    if (status === 'conflict') {
      return 'Someone else changed this submission while you were editing. Save again to keep your code, or close to keep their version.';
    }
    if (status !== 'saved') return '';
    return this.hasUnsavedCode(id)
      ? 'New changes need to be saved.'
      : '✓ Verified code saved';
  }

  // Compares the editor with the stored code rather than tracking edits, so
  // typing the saved text back counts as saved. Code counts as saved only once
  // it is stored as verified_text: OCR output never saved in Review code is not
  // graded.
  hasUnsavedCode(id: string): boolean {
    const savedCode = this.savedSubmission(id)?.verified_text;
    return (
      savedCode === undefined ||
      savedCode === null ||
      this.editableText[id] !== savedCode
    );
  }

  // The submission as last loaded from or saved to Supabase.
  private savedSubmission(id: string): Submission | undefined {
    return (
      this.persistedSubmissions.get(id) ??
      this.submissions.find((item) => item.id === id)
    );
  }

  private savedQuestionId(id: string): string {
    const saved = this.savedSubmission(id);
    if (!saved) return '';
    return saved.question_id || this.getLinkedQuestion(saved)?.id || '';
  }

  async continueFromDetails() {
    const submissionId = this.selectedSubmission?.id;
    if (!submissionId || !this.selectedQuestionId) return;
    // Nothing to write. Saving anyway could only report a conflict about a
    // change this form does not touch, such as another teacher's grade.
    if (!this.hasUnsavedDetails()) {
      this.reviewStep = 2;
      return;
    }

    const saved = await this.saveSubmissionDetails();
    if (
      saved &&
      !this.destroyed &&
      this.selectedSubmission?.id === submissionId &&
      // Edits made while saving are not saved yet; stay so they can be.
      !this.hasUnsavedDetails()
    ) {
      this.reviewStep = 2;
    }
  }

  async saveCodeAndContinue() {
    const submissionId = this.selectedSubmission?.id;
    if (!submissionId || !this.canOpenGradingStep()) return;
    // Same for code that is already stored, unless fresh OCR output still
    // needs recording as extracted_text.
    if (
      !this.hasUnsavedCode(submissionId) &&
      this.extractedText[submissionId] === undefined
    ) {
      if (!this.stepBlocker(3)) this.reviewStep = 3;
      return;
    }

    await this.saveVerifiedText();
    // Code typed while the save was in flight is not saved yet; stay so it can be.
    if (
      this.selectedSubmission?.id === submissionId &&
      this.saveStatus[submissionId] === 'saved' &&
      !this.stepBlocker(3)
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
    const expectedRevision = this.baseRevision(
      this.detailsBaseRevisions,
      submissionId,
    );
    this.savingTopic = true;
    try {
      const gradingRevision = await this.supabase.updateSubmissionDetails(
        submissionId,
        topic,
        questionId,
        expectedRevision,
      );
      if (gradingRevision === null) {
        // Someone else changed the code or question since this form was
        // loaded. Keep the teacher's draft, load the other version, and let a
        // second save replace it knowingly.
        if (this.selectedSubmission?.id === submissionId) {
          this.detailsSaveError =
            'Someone else changed this submission while you were editing. Save again to keep your topic and question, or cancel to keep their version.';
        }
        await this.refreshSubmission(submissionId);
        this.detailsBaseRevisions.set(
          submissionId,
          this.savedSubmission(submissionId)?.grading_revision ??
            expectedRevision,
        );
        return false;
      }
      this.detailsSaveError = '';
      const storedSubmission = this.submissions.find(
        (item) => item.id === submissionId,
      );
      const openSubmission =
        this.selectedSubmission?.id === submissionId
          ? this.selectedSubmission
          : undefined;
      const savedFields: Partial<Submission> = {
        topic,
        question_id: questionId || undefined,
        grading_revision: gradingRevision,
      };
      this.advanceBaseRevisions(submissionId, expectedRevision, gradingRevision);
      this.detailsBaseRevisions.set(submissionId, gradingRevision);
      // Edits the teacher made while this save was in flight are newer than
      // what was saved; they stay as unsaved drafts instead of being replaced.
      const questionDraftChanged =
        !!openSubmission && (this.selectedQuestionId || null) !== questionId;
      const topicDraftChanged =
        !!openSubmission && this.editableTopic !== topic;

      if (storedSubmission) Object.assign(storedSubmission, savedFields);
      if (openSubmission) {
        const draftQuestionId = openSubmission.question_id;
        Object.assign(openSubmission, savedFields);
        if (questionDraftChanged) openSubmission.question_id = draftQuestionId;
      }
      if (!questionDraftChanged) this.dirtyQuestionIds.delete(submissionId);
      if (!topicDraftChanged) this.dirtyTopicIds.delete(submissionId);
      this.rememberPersistedSubmission({
        ...(storedSubmission ?? submission),
        ...savedFields,
      });
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
    this.extractingIds.add(id);
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
      // Closing the modal restored this submission's saved code; a late OCR
      // result must not turn into an unsaved edit nobody is looking at.
      if (this.selectedSubmission?.id !== id) return;
      const text = res?.cleaned_text ?? '';
      this.extractedText[id] = text;
      this.updateSubmissionCode(id, text);
      this.extractionError[id] = '';
    } catch (err) {
      console.error('OCR failed:', err);
      this.extractionError[id] =
        'Failed to extract text. Please try again later.';
    } finally {
      this.extractingIds.delete(id);
      this.cdr.detectChanges();
    }
  }

  async saveVerifiedText() {
    if (!this.selectedSubmission || this.destroyed) return;
    const id = this.selectedSubmission.id;
    const generation = this.startSaveGeneration(id);
    const expectedRevision = this.baseRevision(this.codeBaseRevisions, id);
    this.savingIds.add(id);
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
        expectedRevision,
      );
      if (!this.isCurrentSave(id, generation)) return;
      if (gradingRevision === null) {
        // Someone else changed the code or question since this draft was
        // loaded. Keep the draft (the reload leaves an edited editor alone),
        // load the other version, and let a second save replace it knowingly.
        // If the submission was closed meanwhile, its draft is already gone.
        if (this.selectedSubmission?.id === id) this.saveStatus[id] = 'conflict';
        await this.refreshSubmission(id);
        if (!this.isCurrentSave(id, generation)) return;
        this.codeBaseRevisions.set(
          id,
          this.savedSubmission(id)?.grading_revision ?? expectedRevision,
        );
        return;
      }
      // The draft now descends from this save, even if typed during it.
      this.advanceBaseRevisions(id, expectedRevision, gradingRevision);
      this.codeBaseRevisions.set(id, gradingRevision);

      const s = this.submissions.find((x) => x.id === id);
      if (s) {
        s.verified_text = text;
        if (ocrText !== undefined) s.extracted_text = ocrText;
        s.grading_revision = gradingRevision;
      }
      if (this.selectedSubmission?.id === id) {
        this.selectedSubmission.verified_text = text;
        if (ocrText !== undefined)
          this.selectedSubmission.extracted_text = ocrText;
        this.selectedSubmission.grading_revision = gradingRevision;
      }
      // Edits typed while the save was in flight are still unsaved.
      const savedLatest = this.editableText[id] === text;
      if (savedLatest) this.dirtyCodeIds.delete(id);
      const persisted = this.submissions.find((item) => item.id === id);
      if (persisted) this.rememberPersistedSubmission(persisted);
      this.saveStatus[id] = 'saved';
      // If newer edits are still open, keep the reminder until they are saved.
      // A save that finishes after this submission was closed gets the normal
      // confirmation timer so the message is not stale when it is reopened.
      if (!savedLatest && this.selectedSubmission?.id === id) return;
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
      // A newer save of the same submission is still running; it clears this.
      if (!this.isCurrentSave(id, generation)) return;

      this.savingIds.delete(id);
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
    return this.extractingIds.has(id);
  }

  isSaving(id: string): boolean {
    return this.savingIds.has(id);
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
    // Grade exactly what is stored in Supabase: the saved code, paired with
    // the revision it was saved at. The database re-checks both on the write.
    const saved = this.savedSubmission(submissionId);
    const gradingRevision = saved?.grading_revision ?? 0;

    this.isChecking = true;
    this.checkError = '';
    this.submissionCheckStatus[submission.id] = '';
    this.submissionRunOutput[submission.id] = '';
    this.submissionTestResults[submission.id] = [];

    try {
      const question = this.getSubmissionQuestion(submission);

      if (!question) {
        this.checkError = 'No question is linked to this submission.';
        return;
      }

      if (!this.getStudentCode(submission).trim()) {
        this.checkError = 'No student code found.';
        return;
      }

      if (this.hasUnsavedCode(submissionId)) {
        this.checkError = 'Save the edited code before grading.';
        return;
      }
      const studentCode = saved?.verified_text ?? '';

      const testCases = question.test_cases || [];

      if (testCases.length === 0) {
        this.checkError = 'No test case found for this question.';
        return;
      }

      // Grade only against the saved question assignment. Grading an unsaved
      // selection would run every test case on Judge0 and then fail the
      // database check (which matches on the saved question_id) with a
      // misleading "inputs changed" error.
      if (this.savedQuestionId(submissionId) !== question.id) {
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

      let gradedRevision: number;
      try {
        const newGradingRevision = await this.supabase.updateSubmissionGrade(
          submissionId,
          testResults,
          gradingRevision,
          question.id,
          studentCode,
        );
        if (!this.isCurrentGrading(submissionId, generation)) return;
        if (newGradingRevision === null) {
          this.checkError =
            'Submission inputs changed during grading. Run grading again.';
          this.submissionCheckStatus[submission.id] = 'Error';
          return;
        }
        gradedRevision = newGradingRevision;
        this.advanceBaseRevisions(
          submissionId,
          gradingRevision,
          newGradingRevision,
        );
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
      // A realtime reload during grading replaces the open submission with a
      // fresh copy, so `submission` may no longer be the one on screen.
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
        item.grading_revision = gradedRevision;
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
      restored.verified_text ?? restored.extracted_text ?? '';
    this.selectedQuestionId =
      restored.question_id || this.getLinkedQuestion(restored)?.id || '';
    this.editableTopic = restored.topic || 'Uncategorized';
    this.restorePersistedGrade(restored);
    this.setBaseRevisions(restored);
  }

  private setBaseRevisions(submission: Submission): void {
    const revision = submission.grading_revision ?? 0;
    this.codeBaseRevisions.set(submission.id, revision);
    this.detailsBaseRevisions.set(submission.id, revision);
  }

  // After this page's own write moved the row from `from` to `to`, any draft
  // still based on `from` is based on the latest version, so it must not
  // conflict with the page's own save.
  private advanceBaseRevisions(id: string, from: number, to: number): void {
    for (const bases of [this.codeBaseRevisions, this.detailsBaseRevisions]) {
      if (bases.get(id) === from) bases.set(id, to);
    }
  }

  private baseRevision(bases: Map<string, number>, id: string): number {
    return (
      bases.get(id) ??
      this.savedSubmission(id)?.grading_revision ??
      this.selectedSubmission?.grading_revision ??
      0
    );
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
      this.editableText[submission.id] ??
      submission.verified_text ??
      submission.extracted_text ??
      ''
    );
  }
}
