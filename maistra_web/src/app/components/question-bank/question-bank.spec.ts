import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from '../../services/supabase';
import {
  BankQuestion,
  NO_SECTION_NAME,
  buildBankGroups,
  countPapers,
  plural,
} from './bank-groups';
import { QuestionBankComponent } from './question-bank';

function question(id: string, name: string, extra: Partial<BankQuestion> = {}): BankQuestion {
  return {
    id,
    question_name: name,
    question_text: `Text for ${name}`,
    question_type: 'program',
    model_answer: 'int main(void) { return 0; }',
    test_cases: [{}, {}, {}],
    ...extra,
  };
}

const sections = [
  { id: 'loops', name: 'Loops', position: 1 },
  { id: 'basic', name: 'Basic', position: 0 },
];

const items = [
  { section_id: 'basic', question_id: 'q-sum', number: 2 },
  { section_id: 'basic', question_id: 'q-hello', number: 1 },
  { section_id: 'loops', question_id: 'q-vowels', number: 1 },
];

const questions = [
  question('q-sum', 'Sum of two numbers', { can_publish: true }),
  question('q-hello', 'Hello world', { test_cases: [{}] }),
  question('q-vowels', 'Count vowels', { question_type: 'function' }),
  question('q-old', 'Skill Test 1A'),
];

describe('plural', () => {
  it('uses the singular for exactly one', () => {
    expect(plural(1, 'question')).toBe('1 question');
    expect(plural(1, 'paper')).toBe('1 paper');
    expect(plural(0, 'test')).toBe('0 tests');
    expect(plural(3, 'test')).toBe('3 tests');
  });
});

describe('countPapers', () => {
  it('counts Program 1 and Programs 2..n, once per paper', () => {
    const counts = countPapers([
      { question_id: 'q-sum', answers: [] },
      { question_id: 'q-hello', answers: [{ code: 'x', question_id: 'q-sum' }] },
      // Same question twice on one paper still counts one paper.
      { question_id: 'q-sum', answers: [{ code: 'y', question_id: 'q-sum' }] },
      { question_id: null },
    ]);
    expect(counts.get('q-sum')).toBe(3);
    expect(counts.get('q-hello')).toBe(1);
  });

  it('works without the answers column', () => {
    expect(countPapers([{ question_id: 'q-sum' }]).get('q-sum')).toBe(1);
  });
});

describe('buildBankGroups', () => {
  const groups = buildBankGroups(questions, sections, items, [
    { question_id: 'q-sum' },
    { question_id: 'q-sum' },
  ]);

  it('orders sections by position and questions by number', () => {
    expect(groups.map((g) => g.name)).toEqual(['Basic', 'Loops', NO_SECTION_NAME]);
    expect(groups[0].rows.map((r) => r.number)).toEqual([1, 2]);
  });

  it('puts unsectioned questions last under "No section yet"', () => {
    const last = groups[groups.length - 1];
    expect(last.sectionId).toBeNull();
    expect(last.rows.map((r) => r.question.question_name)).toEqual(['Skill Test 1A']);
    expect(last.rows[0].number).toBeNull();
  });

  it('fills in test count, paper count and validated state', () => {
    const sum = groups[0].rows.find((r) => r.question.id === 'q-sum')!;
    expect(sum.testCount).toBe(3);
    expect(sum.paperCount).toBe(2);
    expect(sum.validated).toBe(true);

    const hello = groups[0].rows.find((r) => r.question.id === 'q-hello')!;
    expect(hello.testCount).toBe(1);
    expect(hello.paperCount).toBe(0);
    expect(hello.validated).toBe(false);
  });

  it('searches names and question text across all sections', () => {
    const byName = buildBankGroups(questions, sections, items, [], 'VOWEL');
    expect(byName.map((g) => g.name)).toEqual(['Loops']);

    const byText = buildBankGroups(questions, sections, items, [], 'text for hello');
    expect(byText[0].rows.map((r) => r.question.id)).toEqual(['q-hello']);

    expect(buildBankGroups(questions, sections, items, [], 'nothing matches')).toEqual([]);
  });

  it('keeps an empty section visible when not searching', () => {
    const withEmpty = buildBankGroups(
      questions,
      [...sections, { id: 'arrays', name: 'Arrays', position: 2 }],
      items,
      [],
    );
    expect(withEmpty.find((g) => g.name === 'Arrays')?.rows).toEqual([]);
  });

  it('lists everything under "No section yet" when there are no sections', () => {
    const none = buildBankGroups(questions, [], [], []);
    expect(none).toHaveLength(1);
    expect(none[0].rows).toHaveLength(4);
  });
});

describe('QuestionBankComponent', () => {
  function createComponent(overrides: Record<string, unknown> = {}) {
    const supabase = {
      getQuestions: vi.fn().mockResolvedValue({ data: questions, error: null }),
      getQuestionSections: vi.fn().mockResolvedValue({ data: sections, error: null }),
      getSectionItems: vi.fn().mockResolvedValue({ data: items, error: null }),
      getQuestionPaperLinks: vi.fn().mockResolvedValue({ data: [], error: null }),
      getGateResults: vi.fn().mockResolvedValue(new Map()),
      ...overrides,
    };
    const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
    return new QuestionBankComponent(supabase as unknown as SupabaseService, cdr);
  }

  it('groups the loaded questions', async () => {
    const component = createComponent();
    await component.ngOnInit();

    expect(component.isLoading).toBe(false);
    expect(component.totalCount).toBe(4);
    expect(component.groups.map((g) => g.name)).toEqual(['Basic', 'Loops', NO_SECTION_NAME]);
    expect(component.sectionsNotice).toBe('');
  });

  it('still lists questions when the section tables are missing', async () => {
    const missing = {
      data: null,
      error: { code: 'PGRST205', message: "Could not find the table 'public.question_sections'" },
    };
    const component = createComponent({
      getQuestionSections: vi.fn().mockResolvedValue(missing),
      getSectionItems: vi.fn().mockResolvedValue(missing),
    });
    await component.ngOnInit();

    expect(component.errorMessage).toBe('');
    expect(component.sectionsNotice).toContain('No section yet');
    expect(component.groups).toHaveLength(1);
    expect(component.groups[0].rows).toHaveLength(4);
  });

  it('shows an error when questions cannot be loaded', async () => {
    const component = createComponent({
      getQuestions: vi.fn().mockResolvedValue({ data: null, error: { message: 'offline' } }),
    });
    await component.ngOnInit();

    expect(component.errorMessage).toBe('Could not load questions: offline');
  });

  it('opens a question page and goes back to the list', async () => {
    const component = createComponent();
    await component.ngOnInit();

    component.openQuestion('q-sum');
    expect(component.openQuestionData?.question_name).toBe('Sum of two numbers');
    expect(component.openQuestionPlace).toEqual({
      sectionId: 'basic',
      sectionName: 'Basic',
      sectionPosition: 0,
      number: 2,
    });

    component.closeQuestion();
    expect(component.openQuestionData).toBeNull();
  });

  it('collapses a section, but shows every match while searching', async () => {
    const component = createComponent();
    await component.ngOnInit();
    const basic = component.groups[0];

    component.toggleGroup(basic);
    expect(component.isCollapsed(basic)).toBe(true);

    component.search = 'sum';
    expect(component.isCollapsed(component.groups[0])).toBe(false);
  });
});
