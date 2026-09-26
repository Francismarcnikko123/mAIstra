import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SupabaseService } from '../../services/supabase';
import { SubmissionsListComponent } from './submissions-list';

function createComponent(options?: {
  getSubmissions?: ReturnType<typeof vi.fn>;
  getSubmission?: ReturnType<typeof vi.fn>;
  updateSubmissionText?: ReturnType<typeof vi.fn>;
  post?: ReturnType<typeof vi.fn>;
}) {
  const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
  const updateSubmissionText =
    options?.updateSubmissionText ?? vi.fn().mockResolvedValue(undefined);
  const supabase = {
    getSubmissions:
      options?.getSubmissions ?? vi.fn().mockResolvedValue({ data: [], error: null }),
    getSubmission:
      options?.getSubmission ?? vi.fn().mockResolvedValue({ data: null, error: null }),
    updateSubmissionText,
    answersColumnAvailable: true,
  } as unknown as SupabaseService;
  const post =
    options?.post ?? vi.fn().mockReturnValue(of({ cleaned_text: 'fresh ocr' }));
  const component = new SubmissionsListComponent(
    supabase,
    { post } as unknown as HttpClient,
    cdr,
    {} as Judge0Service,
  );
  return { component, updateSubmissionText, post, supabase };
}

function select(component: SubmissionsListComponent, id = 'paper-1') {
  component.selectedSubmission = {
    id,
    image_url: 'https://example.test/paper.png',
    captured_at: '2026-09-24T00:00:00.000Z',
  };
  component.selectedQuestionId = 'q-1';
  component.editableText[id] = 'int main() { return 0; }';
}

describe('SubmissionsListComponent program tabs', () => {
  it('adds an empty tab and switches to it', () => {
    const { component } = createComponent();
    select(component);

    component.addExtraAnswer();

    expect(component.getExtraAnswers('paper-1')).toEqual([{ code: '', question_id: null }]);
    expect(component.activeTab).toBe(1);
  });

  it('switches between tabs and closes an open picker', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.questionPickerOpen = true;

    component.selectTab(0);

    expect(component.activeTab).toBe(0);
    expect(component.questionPickerOpen).toBe(false);
  });

  it('links and clears a question on a tab', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();

    component.chooseExtraQuestion(0, 'q-2');
    expect(component.getExtraAnswers('paper-1')[0].question_id).toBe('q-2');

    component.chooseExtraQuestion(0, null);
    expect(component.getExtraAnswers('paper-1')[0].question_id).toBeNull();
  });

  it('refuses a question already linked to another program', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.addExtraAnswer();
    component.chooseExtraQuestion(0, 'q-2');

    component.chooseExtraQuestion(1, 'q-1');
    component.chooseExtraQuestion(1, 'q-2');

    expect(component.getExtraAnswers('paper-1')[1].question_id).toBeNull();
    expect(component.questionOwner('q-1', 1)).toBe(1);
    expect(component.questionOwner('q-2', 1)).toBe(2);
    expect(component.questionOwner('q-3', 1)).toBeNull();
  });

  it('updates tab code without touching Program 1', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();

    component.updateExtraAnswerCode(0, 'int isEven(int n);');

    expect(component.getExtraAnswers('paper-1')[0].code).toBe('int isEven(int n);');
    expect(component.editableText['paper-1']).toBe('int main() { return 0; }');
  });

  it('needs two clicks to remove a tab and frees its question', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.chooseExtraQuestion(0, 'q-2');
    component.addExtraAnswer();

    component.requestRemoveExtraAnswer(0);
    expect(component.getExtraAnswers('paper-1')).toHaveLength(2);
    expect(component.removeConfirmIndex).toBe(0);

    component.requestRemoveExtraAnswer(0);
    expect(component.getExtraAnswers('paper-1')).toEqual([{ code: '', question_id: null }]);
    expect(component.removeConfirmIndex).toBeNull();
    expect(component.questionOwner('q-2', 0)).toBeNull();
  });

  it('moves to the previous tab when the open tab is removed', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.addExtraAnswer();
    expect(component.activeTab).toBe(2);

    component.requestRemoveExtraAnswer(1);
    component.requestRemoveExtraAnswer(1);

    expect(component.activeTab).toBe(1);
  });

  it('loads saved programs for each submission', async () => {
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{
        id: 'paper-1', image_url: 'x', captured_at: 'y', verified_text: 'int main() {}',
        answers: [{ code: 'int f(void) { return 1; }', question_id: 'q-2' }],
      }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions });

    await component.loadSubmissions();

    expect(component.getExtraAnswers('paper-1')).toEqual([
      { code: 'int f(void) { return 1; }', question_id: 'q-2' },
    ]);
  });

  it('does not overwrite unsaved tabs when the list reloads', async () => {
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ id: 'paper-1', image_url: 'x', captured_at: 'y', answers: [] }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions });
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'pasted but not saved');

    await component.loadSubmissions();

    expect(component.getExtraAnswers('paper-1')[0].code).toBe('pasted but not saved');
  });

  it('opens a submission on Program 1', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();

    component.openModal({ id: 'paper-1', image_url: 'x', captured_at: 'y' });

    expect(component.activeTab).toBe(0);
  });

  it('saves every program in the same update as Program 1', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int f(void) { return 1; }');
    component.chooseExtraQuestion(0, 'q-2');

    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledTimes(1);
    // 4th argument: the grading_revision the draft started from (Jayrald's
    // compare-and-set save); the programs follow it.
    expect(updateSubmissionText).toHaveBeenCalledWith(
      'paper-1',
      'int main() { return 0; }',
      undefined,
      0,
      [{ code: 'int f(void) { return 1; }', question_id: 'q-2' }],
    );
    expect(component.saveStatus['paper-1']).toBe('saved');
  });

  it('blocks the save and explains why when a tab breaks a rule', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int x;');

    await component.saveVerifiedText();

    expect(updateSubmissionText).not.toHaveBeenCalled();
    expect(component.extraAnswersError['paper-1']).toBe('Choose a question for Program 2.');
    expect(component.saveStatus['paper-1']).not.toBe('saved');
  });

  it('drops empty tabs when saving', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.addExtraAnswer();

    await component.saveVerifiedText();

    expect(updateSubmissionText.mock.calls[0][4]).toEqual([]);
  });

  it('re-extract on a paper without tabs still replaces Program 1', async () => {
    const { component } = createComponent();
    select(component);
    component.extractedText['paper-1'] = 'int main() { return 0; }';

    await component.extractText();

    expect(component.editableText['paper-1']).toBe('fresh ocr');
    expect(component.ocrPanelOpen).toBe(false);
  });

  it('saves Program 1 and keeps extra programs as a preview while the answers column is missing', async () => {
    const { component, updateSubmissionText, supabase } = createComponent();
    supabase.answersColumnAvailable = false;
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int f(void) { return 1; }');
    component.chooseExtraQuestion(0, 'q-2');

    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledTimes(1);
    expect(component.saveStatus['paper-1']).toBe('saved');
    expect(component.extraAnswersError['paper-1']).toBe(
      "Program 1 was saved. Programs 2 and up can't be saved yet: the database is missing the answers column. Ask Jayrald to apply the migration.",
    );
    expect(component.getExtraAnswers('paper-1')[0].code).toBe('int f(void) { return 1; }');
    expect(component.selectedSubmission?.answers).toBeUndefined();
    // The label beside Save must not claim the extra tabs were stored.
    expect(component.saveStatusLabel('paper-1')).toBe('✓ Program 1 saved');
    expect(component.hasUnsavedPrograms('paper-1')).toBe(true);
  });

  it('the Save label reports a failed save', async () => {
    const updateSubmissionText = vi.fn().mockRejectedValue(new Error('offline'));
    const { component } = createComponent({ updateSubmissionText });
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    select(component);

    await component.saveVerifiedText();

    expect(component.saveStatus['paper-1']).toBe('error');
    expect(component.saveStatusLabel('paper-1')).toBe('Save failed, try again');
  });

  it('keeps the open review in sync with the saved programs', async () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int f(void) { return 1; }');
    component.chooseExtraQuestion(0, 'q-2');

    await component.saveVerifiedText();

    expect(component.selectedSubmission?.answers).toEqual([
      { code: 'int f(void) { return 1; }', question_id: 'q-2' },
    ]);
  });

  it('does not overwrite unsaved Program 1 edits when the list reloads', async () => {
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ id: 'paper-1', image_url: 'x', captured_at: 'y', verified_text: 'saved code' }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions });
    select(component);
    component.updateSubmissionCode('paper-1', 'edited but not saved');

    await component.loadSubmissions();

    expect(component.editableText['paper-1']).toBe('edited but not saved');
  });

  it('gives each tab editor its own identity so a removed tab takes its editor with it', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.addExtraAnswer();
    const [second, third] = component.getExtraAnswers('paper-1');

    component.requestRemoveExtraAnswer(0);
    component.requestRemoveExtraAnswer(0);

    const [remaining] = component.getExtraAnswers('paper-1');
    expect(remaining).toBe(third);
    expect(component.trackByAnswer(0, remaining)).not.toBe(component.trackByAnswer(0, second));
  });

  it('still saves Program 1 alone while the answers column is missing', async () => {
    const { component, updateSubmissionText, supabase } = createComponent();
    supabase.answersColumnAvailable = false;
    select(component);

    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledTimes(1);
    expect(component.saveStatus['paper-1']).toBe('saved');
  });

  it('cancels an armed remove when the teacher clicks elsewhere', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.requestRemoveExtraAnswer(0);
    expect(component.removeConfirmIndex).toBe(0);

    component.cancelPendingRemove();

    expect(component.removeConfirmIndex).toBeNull();
    expect(component.getExtraAnswers('paper-1')).toHaveLength(1);
  });

  it('marks only changed programs as unsaved, and clears the marks after a save', async () => {
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ id: 'paper-1', image_url: 'x', captured_at: 'y', verified_text: 'saved code', answers: [] }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions });
    await component.loadSubmissions();
    component.selectedSubmission = { id: 'paper-1', image_url: 'x', captured_at: 'y' };
    component.selectedQuestionId = 'q-1';
    expect(component.hasUnsavedPrograms('paper-1')).toBe(false);

    component.addExtraAnswer();
    const blank = component.getExtraAnswers('paper-1')[0];
    expect(component.isExtraAnswerUnsaved('paper-1', blank)).toBe(false);
    expect(component.hasUnsavedPrograms('paper-1')).toBe(false);

    component.updateSubmissionCode('paper-1', 'edited');
    component.updateExtraAnswerCode(0, 'int f(void);');
    component.chooseExtraQuestion(0, 'q-2');
    expect(component.isProgram1Unsaved('paper-1')).toBe(true);
    expect(component.isExtraAnswerUnsaved('paper-1', blank)).toBe(true);

    await component.saveVerifiedText();

    expect(component.isProgram1Unsaved('paper-1')).toBe(false);
    expect(component.isExtraAnswerUnsaved('paper-1', blank)).toBe(false);
    expect(component.hasUnsavedPrograms('paper-1')).toBe(false);
  });

  it('closes straight away when nothing is unsaved', async () => {
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ id: 'paper-1', image_url: 'x', captured_at: 'y', verified_text: 'saved code' }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions });
    await component.loadSubmissions();
    component.selectedSubmission = { id: 'paper-1', image_url: 'x', captured_at: 'y' };

    component.requestCloseModal();

    expect(component.selectedSubmission).toBeNull();
    expect(component.closeConfirmOpen).toBe(false);
  });

  it('asks before closing with unsaved programs, and Keep editing stays', () => {
    const { component } = createComponent();
    select(component);

    component.requestCloseModal();
    expect(component.closeConfirmOpen).toBe(true);
    expect(component.selectedSubmission).not.toBeNull();

    component.keepEditing();
    expect(component.closeConfirmOpen).toBe(false);
    expect(component.selectedSubmission).not.toBeNull();
  });

  it('Discard changes goes back to what was last saved, then closes', async () => {
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{
        id: 'paper-1', image_url: 'x', captured_at: 'y', verified_text: 'saved code',
        answers: [{ code: 'saved two', question_id: 'q-2' }],
      }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions });
    await component.loadSubmissions();
    component.selectedSubmission = { id: 'paper-1', image_url: 'x', captured_at: 'y' };
    component.updateSubmissionCode('paper-1', 'edited');
    component.updateExtraAnswerCode(0, 'edited two');
    component.addExtraAnswer();

    component.discardChangesAndClose();

    expect(component.editableText['paper-1']).toBe('saved code');
    expect(component.getExtraAnswers('paper-1')).toEqual([{ code: 'saved two', question_id: 'q-2' }]);
    expect(component.selectedSubmission).toBeNull();
  });

  it('Save keeps the review open on the Code step and clears the unsaved marks', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.reviewStep = 2;
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int x;');
    component.chooseExtraQuestion(0, 'q-2');
    expect(component.hasUnsavedPrograms('paper-1')).toBe(true);

    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledTimes(1);
    // 4th argument: the grading_revision the draft started from (Jayrald's
    // compare-and-set save); the programs follow it.
    expect(updateSubmissionText).toHaveBeenCalledWith(
      'paper-1',
      'int main() { return 0; }',
      undefined,
      0,
      [{ code: 'int x;', question_id: 'q-2' }],
    );
    expect(component.selectedSubmission).not.toBeNull();
    expect(component.reviewStep).toBe(2);
    expect(component.hasUnsavedPrograms('paper-1')).toBe(false);
    expect(component.saveStatus['paper-1']).toBe('saved');
    expect(component.saveStatusLabel('paper-1')).toBe('✓ All programs saved');
  });

  it('Save blocked by a rule shows the reason, writes nothing and stays open', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.reviewStep = 2;
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int x;'); // no question linked yet

    await component.saveVerifiedText();

    expect(updateSubmissionText).not.toHaveBeenCalled();
    expect(component.extraAnswersError['paper-1']).toBeTruthy();
    expect(component.selectedSubmission).not.toBeNull();
    expect(component.reviewStep).toBe(2);
  });

  it('Save on an untouched pre-extracted paper still writes it as verified', async () => {
    // The auto-extract worker saved OCR text; nobody has verified the paper yet.
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{
        id: 'paper-1',
        image_url: 'https://example.test/paper.png',
        captured_at: '2026-09-24T00:00:00.000Z',
        status: 'pending',
        extracted_text: 'int main() { return 0; }',
        verified_text: null,
      }],
      error: null,
    });
    const { component, updateSubmissionText } = createComponent({ getSubmissions });
    await component.loadSubmissions();
    select(component);
    component.reviewStep = 2;
    // It looks saved (the editor matches what was loaded) but was never verified.
    expect(component.hasUnsavedPrograms('paper-1')).toBe(false);

    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledTimes(1);
  });

  it('Cmd/Ctrl+S saves on the Code step and blocks the browser save dialog', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.reviewStep = 2;
    const event = new KeyboardEvent('keydown', { key: 's', metaKey: true });
    const preventDefault = vi.spyOn(event, 'preventDefault');

    component.onSaveShortcut(event);
    await vi.waitFor(() => expect(updateSubmissionText).toHaveBeenCalledTimes(1));

    expect(preventDefault).toHaveBeenCalled();
  });

  it('Cmd/Ctrl+S does nothing outside the Code step, in the close pop-up, or while saving', () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    const press = () => {
      const event = new KeyboardEvent('keydown', { key: 's', ctrlKey: true });
      const preventDefault = vi.spyOn(event, 'preventDefault');
      component.onSaveShortcut(event);
      return preventDefault;
    };

    component.reviewStep = 3;
    expect(press()).not.toHaveBeenCalled();

    component.reviewStep = 2;
    component.closeConfirmOpen = true;
    expect(press()).not.toHaveBeenCalled();

    component.closeConfirmOpen = false;
    vi.spyOn(component, 'isSaving').mockReturnValue(true); // a save is already running
    expect(press()).toHaveBeenCalled(); // still blocks the browser dialog…
    expect(updateSubmissionText).not.toHaveBeenCalled(); // …but does not start a second save

    component.onSaveShortcut(new KeyboardEvent('keydown', { key: 's' })); // no modifier
    expect(updateSubmissionText).not.toHaveBeenCalled();
  });

  it('Cmd/Ctrl+S never saves a paper that has no extracted code yet', () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.reviewStep = 2;
    component.editableText['paper-1'] = ''; // not extracted: the Save button is hidden
    const event = new KeyboardEvent('keydown', { key: 's', metaKey: true });
    const preventDefault = vi.spyOn(event, 'preventDefault');

    component.onSaveShortcut(event);

    expect(preventDefault).toHaveBeenCalled();
    expect(updateSubmissionText).not.toHaveBeenCalled();
  });

  it('the close pop-up offers Keep editing and Discard only', () => {
    const { component } = createComponent();
    select(component);
    component.reviewStep = 2;
    component.editableText['paper-1'] = 'edited';

    component.requestCloseModal();
    expect(component.closeConfirmOpen).toBe(true);
    expect('saveAndClose' in component).toBe(false);

    component.keepEditing();
    expect(component.closeConfirmOpen).toBe(false);
    expect(component.selectedSubmission).not.toBeNull();
    expect(component.reviewStep).toBe(2);
  });

  it('re-extract on a split paper shows the OCR text and leaves every tab alone', async () => {
    const { component, post } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'program two');

    await component.extractText();

    expect(post).toHaveBeenCalledTimes(1);
    expect(component.reextractConfirmId).toBeNull();
    expect(component.editableText['paper-1']).toBe('int main() { return 0; }');
    expect(component.getExtraAnswers('paper-1')[0].code).toBe('program two');
    expect(component.ocrPanelOpen).toBe(true);
    expect(component.getOcrText(component.selectedSubmission!)).toBe('fresh ocr');
  });

  it('shows the saved OCR reading when this session has not extracted', () => {
    const { component } = createComponent();
    const submission = { id: 'paper-9', image_url: 'x', captured_at: 'y', extracted_text: 'saved ocr' };

    expect(component.getOcrText(submission)).toBe('saved ocr');
  });

  it('moves between tabs with the arrow keys, wrapping at both ends', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.selectTab(0);

    component.moveTab(1);
    expect(component.activeTab).toBe(1);
    component.moveTab(1);
    expect(component.activeTab).toBe(0);
    component.moveTab(-1);
    expect(component.activeTab).toBe(1);
  });

  it('finds the question for the open tab, for View question', () => {
    const { component } = createComponent();
    component.questions = [
      { id: 'q-1', question_name: 'One', question_type: 'program', model_answer: 'm', test_cases: [] },
      { id: 'q-2', question_name: 'Two', question_type: 'program', model_answer: 'm', test_cases: [] },
    ];
    select(component);
    expect(component.getActiveTabQuestion()?.id).toBe('q-1');

    component.addExtraAnswer();
    expect(component.getActiveTabQuestion()).toBeNull();
    component.chooseExtraQuestion(0, 'q-2');
    expect(component.getActiveTabQuestion()?.id).toBe('q-2');
  });

  it('re-extracts an untouched pre-extracted paper without asking to discard edits', async () => {
    const { component, post } = createComponent();
    component.selectedSubmission = {
      id: 'paper-1', image_url: 'x', captured_at: 'y', extracted_text: 'worker text',
    };
    component.editableText['paper-1'] = 'worker text';

    await component.extractText();

    expect(component.reextractConfirmId).toBeNull();
    expect(post).toHaveBeenCalledTimes(1);
    expect(component.editableText['paper-1']).toBe('fresh ocr');
  });

  it('still asks before re-extracting over the teacher\'s edits to a pre-extracted paper', async () => {
    const { component, post } = createComponent();
    component.selectedSubmission = {
      id: 'paper-1', image_url: 'x', captured_at: 'y', extracted_text: 'worker text',
    };
    component.editableText['paper-1'] = 'worker text, corrected by the teacher';

    await component.extractText();

    expect(component.reextractConfirmId).toBe('paper-1');
    expect(post).not.toHaveBeenCalled();
  });

  it('picks up OCR text the worker saved after the list loaded, without marking it unsaved', async () => {
    const getSubmission = vi.fn().mockResolvedValue({
      data: { id: 'paper-1', image_url: 'x', captured_at: 'y', extracted_text: 'worker text' },
      error: null,
    });
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ id: 'paper-1', image_url: 'x', captured_at: 'y' }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions, getSubmission });
    await component.loadSubmissions();

    component.openModal({ id: 'paper-1', image_url: 'x', captured_at: 'y' });
    await vi.waitFor(() => expect(component.editableText['paper-1']).toBe('worker text'));

    expect(getSubmission).toHaveBeenCalledWith('paper-1');
    expect(component.selectedSubmission?.extracted_text).toBe('worker text');
    expect(component.hasUnsavedPrograms('paper-1')).toBe(false);
  });

  it('never replaces text the teacher already has when the paper is refreshed', async () => {
    const getSubmission = vi.fn().mockResolvedValue({
      data: { id: 'paper-1', image_url: 'x', captured_at: 'y', extracted_text: 'worker text' },
      error: null,
    });
    const { component } = createComponent({ getSubmission });

    // Closing a review now saves or discards (requestCloseModal), so a draft
    // can only exist while the paper is open: type before the re-read lands.
    component.openModal({ id: 'paper-1', image_url: 'x', captured_at: 'y' });
    component.updateSubmissionCode('paper-1', 'teacher typed this');
    await vi.waitFor(() => expect(getSubmission).toHaveBeenCalled());
    await Promise.resolve();

    expect(component.editableText['paper-1']).toBe('teacher typed this');
  });
});
