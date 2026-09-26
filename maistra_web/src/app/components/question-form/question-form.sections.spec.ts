import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { readFileSync } from 'fs';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from '../../services/supabase';
import { Judge0Service } from '../../services/judge0.service';
import { NEW_SECTION, QuestionFormComponent } from './question-form';

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
});
