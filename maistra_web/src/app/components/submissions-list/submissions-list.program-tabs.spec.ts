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
  updateSubmissionText?: ReturnType<typeof vi.fn>;
  post?: ReturnType<typeof vi.fn>;
}) {
  const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
  const updateSubmissionText =
    options?.updateSubmissionText ?? vi.fn().mockResolvedValue(undefined);
  const supabase = {
    getSubmissions:
      options?.getSubmissions ?? vi.fn().mockResolvedValue({ data: [], error: null }),
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
    expect(updateSubmissionText).toHaveBeenCalledWith(
      'paper-1',
      'int main() { return 0; }',
      undefined,
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

    expect(updateSubmissionText.mock.calls[0][3]).toEqual([]);
  });

  it('re-extract replaces Program 1 only', async () => {
    const { component } = createComponent();
    select(component);
    component.extractedText['paper-1'] = 'int main() { return 0; }';
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'pasted program two');

    await component.extractText();

    expect(component.editableText['paper-1']).toBe('fresh ocr');
    expect(component.getExtraAnswers('paper-1')[0].code).toBe('pasted program two');
  });

  it('blocks saving extra programs while the answers column is missing', async () => {
    const { component, updateSubmissionText, supabase } = createComponent();
    supabase.answersColumnAvailable = false;
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int f(void) { return 1; }');
    component.chooseExtraQuestion(0, 'q-2');

    await component.saveVerifiedText();

    expect(updateSubmissionText).not.toHaveBeenCalled();
    expect(component.extraAnswersError['paper-1']).toBe(
      "Programs 2 and up can't be saved yet: the database is missing the answers column. Ask Jayrald to apply the migration.",
    );
  });

  it('still saves Program 1 alone while the answers column is missing', async () => {
    const { component, updateSubmissionText, supabase } = createComponent();
    supabase.answersColumnAvailable = false;
    select(component);

    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledTimes(1);
    expect(component.saveStatus['paper-1']).toBe('saved');
  });
});
