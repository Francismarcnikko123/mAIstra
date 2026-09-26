import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { readFileSync } from 'fs';
import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from '../../services/supabase';
import { Judge0Service } from '../../services/judge0.service';
import { NEW_SECTION, QuestionFormComponent } from './question-form';

describe('QuestionFormComponent', () => {
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
      ...overrides,
    };
  }

  function createComponent(
    saveQuestion?: ReturnType<typeof vi.fn>,
    supabase = createSupabase(saveQuestion ? { saveQuestion } : {}),
  ) {
    const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
    const judge0 = {} as Judge0Service;

    const component = new QuestionFormComponent(
      supabase as unknown as SupabaseService,
      cdr,
      judge0,
    );
    return { component, supabase };
  }

  /** A form that passes every save rule. */
  async function readyComponent(supabase = createSupabase()) {
    const { component } = createComponent(undefined, supabase);
    await component.ngOnInit();
    component.sectionId = 'sec-basic';
    await component.onSectionChange();
    component.questionNumber = 3;
    component.questionName = 'Count vowels';
    component.questionText = 'Count the vowels in a line of text.';
    component.questionType = 'program';
    component.modelAnswer = 'int main(void) { return 0; }';
    component.canPublish = true;
    return { component, supabase };
  }

  it('resets test cases after a successful save', async () => {
    const { component } = createComponent();
    component.sectionId = 'sec-basic';
    component.sections = [{ id: 'sec-basic', name: 'Basic' }];
    component.questionNumber = 1;
    component.questionName = 'Addition';
    component.questionText = 'Write a C program that adds two numbers.';
    component.questionType = 'program';
    component.modelAnswer = 'int main(void) { return 0; }';
    component.testCases = [
      {
        test_code: '1 1',
        test_input: '1 1',
        expected_output: '2',
        mark: 2,
      },
      {
        test_code: '2 3',
        test_input: '2 3',
        expected_output: '5',
        mark: 3,
      },
    ];
    component.validationResults = [
      {
        passed: true,
        expected: '2',
        actual: '2',
      },
    ];
    component.testRunStatuses = ['passed', 'failed'];
    component.canPublish = true;
    component.collapsedTestCases = { 1: true };

    await component.save();

    expect(component.testCases).toEqual([
      {
        test_code: '',
        test_input: '',
        expected_output: '',
        mark: 2,
      },
    ]);
    expect(component.validationResults).toEqual([]);
    expect(component.testRunStatuses).toEqual([]);
    expect(component.canPublish).toBe(false);
    expect(component.collapsedTestCases).toEqual({});
  });

  it('refuses to save until validation has passed', async () => {
    const { component, supabase } = await readyComponent();
    component.canPublish = false;

    await component.save();

    expect(supabase.saveQuestion).not.toHaveBeenCalled();
    expect(component.errorMessage).toContain('Validate the test cases first');
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
    expect(component.errorMessage).toBe(
      'Q3 is already used in Basic. Pick another number.',
    );
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

    await component.save();

    expect(supabase.saveQuestion).toHaveBeenCalledWith(
      expect.objectContaining({
        question_name: 'Count vowels',
        can_publish: true,
      }),
    );
    expect(supabase.addQuestionToSection).toHaveBeenCalledWith('q-new', 'sec-basic', 3);
    expect(component.successMessage).toBe('Question saved: Basic · Q3 · Count vowels');
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

  it('renders save validation and success messages', async () => {
    const template = readFileSync(
      'src/app/components/question-form/question-form.html',
      'utf8',
    );

    expect(template).toContain('class="error-message"');
    expect(template).toContain('{{ errorMessage }}');
    expect(template).toContain('class="success-message"');
    expect(template).toContain('{{ successMessage }}');
  });
});
