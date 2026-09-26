import '@angular/compiler';
import { describe, expect, it } from 'vitest';
import { BankQuestion, linkedPapers, totalMarks } from './bank-groups';
import { QuestionPageComponent } from './question-page';

const sum: BankQuestion = {
  id: 'q-sum',
  question_name: 'Sum of two numbers',
  question_text: 'Add two numbers.',
  question_type: 'program',
  model_answer: 'int main(void) { return 0; }',
  test_cases: [{ mark: 2 }, { mark: 3 }, { mark: '1' }],
};

const papers = [
  { id: 'p1', question_id: 'q-sum' },
  { id: 'p2', question_id: 'q-other', answers: [{ code: 'x', question_id: 'q-sum' }] },
  { id: 'p3', question_id: 'q-other', answers: [] },
  { id: 'p4', question_id: 'q-sum', answers: [{ code: 'y', question_id: 'q-sum' }] },
];

describe('linkedPapers', () => {
  it('finds Program 1 and Program 2+ links, once per paper', () => {
    expect(linkedPapers('q-sum', papers).map((l) => [l.paper.id, l.program])).toEqual([
      ['p1', 1],
      ['p2', 2],
      ['p4', 1],
    ]);
  });
});

describe('totalMarks', () => {
  it('adds the test-case marks, ignoring missing ones', () => {
    expect(totalMarks(sum)).toBe(6);
    expect(totalMarks({ ...sum, test_cases: [{}, { mark: 4 }] })).toBe(4);
    expect(totalMarks({ ...sum, test_cases: null })).toBe(0);
  });
});

describe('QuestionPageComponent', () => {
  function page(question: BankQuestion) {
    const component = new QuestionPageComponent();
    component.question = question;
    component.papers = papers;
    return component;
  }

  it('labels the question with its section and number', () => {
    const component = page(sum);
    expect(component.label).toBe('Sum of two numbers');
    component.place = { sectionId: 'basic', sectionName: 'Basic', sectionPosition: 0, number: 2 };
    expect(component.label).toBe('Basic · Q2 · Sum of two numbers');
  });

  it('summarises type, tests, marks and papers with correct plurals', () => {
    expect(page(sum).summary).toBe('Program · 3 test cases · 6 marks · used by 3 papers');
    expect(
      page({ ...sum, id: 'lonely', test_cases: [{ mark: 1 }] }).summary,
    ).toBe('Program · 1 test case · 1 mark · used by 0 papers');
  });

  it('flags a question that has not passed validation', () => {
    expect(page(sum).validated).toBe(false);
    expect(page({ ...sum, can_publish: true }).validated).toBe(true);
  });
});
