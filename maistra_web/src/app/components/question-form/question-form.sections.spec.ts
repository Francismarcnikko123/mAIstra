import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { readFileSync } from 'fs';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from '../../services/supabase';
import { Judge0Service } from '../../services/judge0.service';
import { EditQuestionRequest, NEW_SECTION, QuestionFormComponent } from './question-form';

// Section and question number (Nikko). Validation and saving rules are
// covered in question-form.spec.ts.

describe('QuestionFormComponent sections', () => {
  function createSupabase(overrides: Record<string, unknown> = {}) {
    return {
      saveQuestion: vi.fn().mockResolvedValue({ data: { id: 'q-new' }, error: null }),
      getQuestionSections: vi.fn().mockResolvedValue({
        data: [{ id: 'sec-basic', name: 'Basic', position: 0 }],
        error: null,
      }),
      createQuestionSection: vi.fn().mockResolvedValue({
        data: { id: 'sec-loops', name: 'Loops', position: 0 },
        error: null,
      }),
      getSectionNumbers: vi.fn().mockResolvedValue({ data: [], error: null }),
      addQuestionToSection: vi.fn().mockResolvedValue({ error: null }),
      updateQuestion: vi.fn().mockResolvedValue({ data: { id: 'q-sum' }, error: null }),
      moveQuestionToSection: vi.fn().mockResolvedValue({ error: null }),
      countGradedPapers: vi.fn().mockResolvedValue(0),
      ...overrides,
    };
  }

  /** A program question whose one test case passes in a fake Judge0. */
  async function readyComponent(supabase = createSupabase(), validate = true) {
    const judge0 = {
      runCCodeBatchSettled: vi
        .fn()
        .mockReturnValue(of([{ stdout: '5', status: { id: 3, description: 'Accepted' } }])),
    };
    const component = new QuestionFormComponent(
      supabase as unknown as SupabaseService,
      { detectChanges: vi.fn() } as unknown as ChangeDetectorRef,
      judge0 as unknown as Judge0Service,
    );
    await component.ngOnInit();
    component.sectionId = 'sec-basic';
    await component.onSectionChange();
    component.questionNumber = 3;
    component.questionName = 'Count vowels';
    component.questionText = 'Count the vowels in a line of text.';
    component.questionType = 'program';
    component.modelAnswer = 'int main(void) { printf("5"); return 0; }';
    component.testCases = [{ test_code: '', test_input: 'hello', expected_output: '5' }];
    if (validate) await component.validateModelAnswer();
    return { component, supabase };
  }

  it('is ready to save once validation passes', async () => {
    const { component } = await readyComponent();
    expect(component.canPublish).toBe(true);
    expect(component.saveBlockedReason()).toBe('');
  });

  it('refuses to save until validation has passed', async () => {
    const { component, supabase } = await readyComponent(createSupabase(), false);

    expect(component.saveBlockedReason()).toContain('Validate the test cases first');
    await component.save();

    expect(supabase.saveQuestion).not.toHaveBeenCalled();
  });

  it('refuses a question number already used in the section', async () => {
    const supabase = createSupabase({
      getSectionNumbers: vi.fn().mockResolvedValue({
        data: [{ number: 3 }, { number: 1 }],
        error: null,
      }),
    });
    const { component } = await readyComponent(supabase);

    expect(component.takenNumbers).toEqual([1, 3]);
    expect(component.numberTaken).toBe(true);
    await component.save();

    expect(supabase.saveQuestion).not.toHaveBeenCalled();
    expect(component.errorMessage).toBe('Q3 is already used in Basic. Pick another number.');
  });

  it('requires a section and a whole question number', async () => {
    const { component } = await readyComponent();
    component.sectionId = '';
    expect(component.saveBlockedReason()).toBe('Choose a section.');

    component.sectionId = 'sec-basic';
    component.questionNumber = 0;
    expect(component.saveBlockedReason()).toContain('whole number of 1 or more');

    component.questionNumber = 2.5;
    expect(component.saveBlockedReason()).toContain('whole number of 1 or more');
  });

  it('previews the label teachers will see', async () => {
    const { component } = await readyComponent();
    expect(component.labelPreview).toBe('Basic · Q3 · Count vowels');
  });

  it('saves a validated question and links it to its section and number', async () => {
    const { component, supabase } = await readyComponent();
    const saved = vi.fn();
    component.questionSaved.subscribe(saved);

    await component.save();

    expect(supabase.saveQuestion).toHaveBeenCalledWith(
      expect.objectContaining({ question_name: 'Count vowels', can_publish: true }),
    );
    expect(supabase.addQuestionToSection).toHaveBeenCalledWith('q-new', 'sec-basic', 3);
    expect(component.successMessage).toBe('Question saved: Basic · Q3 · Count vowels');
    expect(saved).toHaveBeenCalledOnce();
    // The section stays chosen for the next question; the number clears.
    expect(component.sectionId).toBe('sec-basic');
    expect(component.questionNumber).toBeNull();
  });

  it('creates a new section before saving into it', async () => {
    const { component, supabase } = await readyComponent();
    component.sectionId = NEW_SECTION;
    component.newSectionName = '  Loops ';

    await component.save();

    expect(supabase.createQuestionSection).toHaveBeenCalledWith('Loops');
    expect(supabase.addQuestionToSection).toHaveBeenCalledWith('q-new', 'sec-loops', 3);
  });

  it('reuses an existing section when a new one has the same name', async () => {
    const { component, supabase } = await readyComponent();
    component.sectionId = NEW_SECTION;
    component.newSectionName = 'basic';

    await component.save();

    expect(supabase.createQuestionSection).not.toHaveBeenCalled();
    expect(supabase.addQuestionToSection).toHaveBeenCalledWith('q-new', 'sec-basic', 3);
  });

  it('explains when the number was taken between checking and saving', async () => {
    const supabase = createSupabase({
      addQuestionToSection: vi.fn().mockResolvedValue({
        error: { code: '23505', message: 'duplicate key' },
      }),
    });
    const { component } = await readyComponent(supabase);

    await component.save();

    expect(component.errorMessage).toContain('was taken in Basic in the meantime');
    expect(component.errorMessage).toContain('No section yet');
    expect(component.successMessage).toBe('');
  });

  it('shows the section, number and label preview in the template', () => {
    const template = readFileSync('src/app/components/question-form/question-form.html', 'utf8');
    expect(template).toContain('New section name');
    expect(template).toContain('Question No.');
    expect(template).toContain('Teachers will see:');
  });

  describe('editing a saved question', () => {
    const saved = (overrides: Partial<EditQuestionRequest['question']> = {}) => ({
      id: 'q-sum',
      question_name: 'Sum of Two Integers',
      question_text: 'Read two integers and print their sum.',
      question_type: 'program',
      model_answer: 'int main(void) { printf("5"); return 0; }',
      test_cases: [{ test_code: '', test_input: 'hello', expected_output: '5' }],
      can_publish: true,
      ...overrides,
    });

    async function editing(
      request: Partial<EditQuestionRequest> = {},
      supabase = createSupabase({
        getSectionNumbers: vi.fn().mockResolvedValue({ data: [{ number: 1 }, { number: 2 }], error: null }),
      }),
    ) {
      const { component } = await readyComponent(supabase, false);
      const done = vi.fn();
      component.editDone.subscribe(done);
      await component.startEdit({
        question: saved(),
        place: { sectionId: 'sec-basic', number: 1 },
        ...request,
      });
      return { component, supabase, done };
    }

    it('opens pre-filled, still validated, and its own number is not "taken"', async () => {
      const { component } = await editing();

      expect(component.isEditing).toBe(true);
      expect(component.questionName).toBe('Sum of Two Integers');
      expect(component.questionType).toBe('program');
      expect(component.testCases).toEqual([
        { test_code: '', test_input: 'hello', expected_output: '5' },
      ]);
      expect(component.sectionId).toBe('sec-basic');
      expect(component.questionNumber).toBe(1);
      expect(component.takenNumbers).toEqual([2]);
      expect(component.saveBlockedReason()).toBe('');
    });

    it('locks Save again once the model answer is edited', async () => {
      const { component } = await editing();

      component.modelAnswer = 'int main(void) { return 1; }';
      component.clearValidationResults(); // what the editor's valueChange does

      expect(component.saveBlockedReason()).toContain('Validate the test cases first');
    });

    it('a question that never passed must be validated before saving', async () => {
      const { component } = await editing({ question: saved({ can_publish: false }) });
      expect(component.saveBlockedReason()).toContain('Validate the test cases first');

      await component.validateModelAnswer();
      expect(component.saveBlockedReason()).toBe('');
    });

    it('"Validate test cases" on the question page validates as the form opens', async () => {
      const { component } = await editing({ question: saved({ can_publish: false }), validate: true });
      expect(component.canPublish).toBe(true);
    });

    it('saves the question in place without touching its section when that is unchanged', async () => {
      const { component, supabase, done } = await editing();
      component.questionName = 'Sum of two integers';

      await component.save();

      expect(supabase.updateQuestion).toHaveBeenCalledWith(
        'q-sum',
        expect.objectContaining({ question_name: 'Sum of two integers', can_publish: true }),
      );
      expect(supabase.saveQuestion).not.toHaveBeenCalled();
      expect(supabase.moveQuestionToSection).not.toHaveBeenCalled();
      expect(supabase.addQuestionToSection).not.toHaveBeenCalled();
      expect(done).toHaveBeenCalledOnce();
      expect(component.isEditing).toBe(false);
    });

    it('moves the question when its number changes', async () => {
      const { component, supabase } = await editing();
      component.questionNumber = 3;

      await component.save();

      expect(supabase.moveQuestionToSection).toHaveBeenCalledWith('q-sum', 'sec-basic', 3);
    });

    it('gives an unsectioned question its first section and number', async () => {
      const { component, supabase } = await editing({ place: null });
      expect(component.saveBlockedReason()).toBe('Choose a section.');

      component.sectionId = 'sec-basic';
      await component.onSectionChange();
      component.questionNumber = 3;
      await component.save();

      expect(supabase.addQuestionToSection).toHaveBeenCalledWith('q-sum', 'sec-basic', 3);
      expect(supabase.moveQuestionToSection).not.toHaveBeenCalled();
    });

    it('warns before clearing grades when test cases change on a graded question', async () => {
      const supabase = createSupabase({ countGradedPapers: vi.fn().mockResolvedValue(2) });
      const { component } = await editing({}, supabase);
      // A changed test input is a test-case change (the fake Judge0 still passes it).
      component.testCases = [{ test_code: '', test_input: 'hello again', expected_output: '5' }];
      component.clearValidationResults();
      await component.validateModelAnswer();

      await component.save();
      expect(supabase.updateQuestion).not.toHaveBeenCalled();
      expect(component.gradeWarning).toContain('2 graded papers use this question');

      await component.confirmGradeReset();
      expect(supabase.updateQuestion).toHaveBeenCalledOnce();
    });

    it('no warning when only the name changes on a graded question', async () => {
      const supabase = createSupabase({ countGradedPapers: vi.fn().mockResolvedValue(2) });
      const { component } = await editing({}, supabase);
      component.questionName = 'Renamed';

      await component.save();

      expect(component.gradeWarning).toBe('');
      expect(supabase.updateQuestion).toHaveBeenCalledOnce();
    });

    it('Cancel leaves edit mode without saving', async () => {
      const { component, supabase, done } = await editing();

      component.cancelEdit();

      expect(component.isEditing).toBe(false);
      expect(component.questionName).toBe('');
      expect(supabase.updateQuestion).not.toHaveBeenCalled();
      expect(done).toHaveBeenCalledOnce();
    });
  });
});
