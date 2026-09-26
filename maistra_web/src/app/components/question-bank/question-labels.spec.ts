import { describe, expect, it } from 'vitest';
import {
  compareFolders,
  gateBadge,
  indexQuestionPlaces,
  questionLabel,
  submissionFolder,
} from './question-labels';

const places = indexQuestionPlaces(
  [
    { id: 'loops', name: 'Loops', position: 1 },
    { id: 'basic', name: 'Basic', position: 0 },
  ],
  [
    { section_id: 'basic', question_id: 'q-sum', number: 2 },
    { section_id: 'loops', question_id: 'q-vowels', number: 1 },
    // An item whose section is gone is ignored.
    { section_id: 'deleted', question_id: 'q-ghost', number: 1 },
  ],
);

describe('question labels', () => {
  it('indexes questions by section and number', () => {
    expect(places.get('q-sum')?.sectionName).toBe('Basic');
    expect(places.has('q-ghost')).toBe(false);
  });

  it('builds the shared label', () => {
    expect(questionLabel('Sum of two numbers', places.get('q-sum'))).toBe(
      'Basic · Q2 · Sum of two numbers',
    );
    expect(questionLabel('Skill Test 1A', null)).toBe('Skill Test 1A');
  });

  it('turns gate results into icon + text badges', () => {
    expect(gateBadge('PASS')?.label).toBe('Photo good');
    expect(gateBadge('FIXABLE')?.tone).toBe('fixable');
    expect(gateBadge('RETAKE')?.icon).toBe('!');
    expect(gateBadge(null)).toBeNull();
    expect(gateBadge('something else')).toBeNull();
  });
});

describe('submissionFolder', () => {
  it("uses the Program 1 question's section", () => {
    expect(submissionFolder('q-sum', 'Old topic', places).name).toBe('Basic');
  });

  it('keeps a typed topic for papers without a sectioned question', () => {
    expect(submissionFolder(null, ' Chapter 3 ', places).name).toBe('Chapter 3');
    expect(submissionFolder('q-unsectioned', 'Loops HW', places).key).toBe('topic:Loops HW');
  });

  it('falls back to Uncategorized', () => {
    expect(submissionFolder(null, '', places).name).toBe('Uncategorized');
    expect(submissionFolder(null, 'Uncategorized', places).key).toBe('uncategorized');
  });

  it('orders sections by position, then topics, then Uncategorized', () => {
    const folders = [
      submissionFolder(null, null, places),
      submissionFolder(null, 'Chapter 3', places),
      submissionFolder('q-vowels', null, places),
      submissionFolder('q-sum', null, places),
    ].sort(compareFolders);
    expect(folders.map((f) => f.name)).toEqual(['Basic', 'Loops', 'Chapter 3', 'Uncategorized']);
  });
});
