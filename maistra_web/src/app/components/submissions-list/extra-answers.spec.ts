import { describe, expect, it } from 'vitest';
import {
  answerProblems,
  programsForGrading,
  answersToSave,
  parseAnswers,
  takenQuestionIds,
} from './extra-answers';

describe('parseAnswers', () => {
  it('returns an empty list for anything that is not an array', () => {
    expect(parseAnswers(null)).toEqual([]);
    expect(parseAnswers(undefined)).toEqual([]);
    expect(parseAnswers('[]')).toEqual([]);
    expect(parseAnswers({ code: 'x' })).toEqual([]);
  });

  it('keeps order and code exactly as stored, including whitespace', () => {
    const raw = [
      { code: 'int main() {\n  return 0;\n}\n', question_id: 'q-2' },
      { code: '  void f(void) {}', question_id: null },
    ];
    expect(parseAnswers(raw)).toEqual(raw);
  });

  it('coerces malformed entries instead of throwing', () => {
    expect(parseAnswers([{ code: 5 }, null, 'text', { question_id: '' }])).toEqual([
      { code: '', question_id: null },
      { code: '', question_id: null },
    ]);
  });
});

describe('answersToSave', () => {
  it('drops tabs with neither code nor a question', () => {
    expect(
      answersToSave([
        { code: '', question_id: null },
        { code: ' \n', question_id: null },
      ]),
    ).toEqual([]);
  });

  it('keeps other tabs with code exactly as typed', () => {
    const code = '\n  int main() {}  \n';
    expect(answersToSave([{ code, question_id: 'q-2' }])).toEqual([
      { code, question_id: 'q-2' },
    ]);
  });
});

describe('takenQuestionIds', () => {
  it('maps each linked question to its program number, skipping one tab', () => {
    const taken = takenQuestionIds(
      'q-1',
      [
        { code: 'a', question_id: 'q-2' },
        { code: 'b', question_id: null },
        { code: 'c', question_id: 'q-3' },
      ],
      2,
    );
    expect([...taken.entries()]).toEqual([
      ['q-1', 1],
      ['q-2', 2],
    ]);
  });

  it('ignores a missing Program 1 question', () => {
    const taken = takenQuestionIds(null, [{ code: 'a', question_id: 'q-2' }], -1);
    expect([...taken.entries()]).toEqual([['q-2', 2]]);
  });
});

describe('answerProblems', () => {
  it('accepts linked programs and ignores fully blank tabs', () => {
    expect(
      answerProblems('q-1', [
        { code: 'int f(void);', question_id: 'q-2' },
        { code: '', question_id: null },
      ]),
    ).toEqual([]);
  });

  it('asks for a question when a tab has code but no question', () => {
    expect(answerProblems('q-1', [{ code: 'int x;', question_id: null }])).toEqual([
      'Choose a question for Program 2.',
    ]);
  });

  it('asks for code when a tab has a question but no code', () => {
    expect(answerProblems('q-1', [{ code: '  ', question_id: 'q-2' }])).toEqual([
      'Program 2 is linked to a question but has no code. Paste its program or clear the question.',
    ]);
  });

  it('rejects a tab that reuses Program 1 question', () => {
    expect(answerProblems('q-1', [{ code: 'x', question_id: 'q-1' }])).toEqual([
      'Program 2 uses the same question as Program 1. Each question can only be linked to one program.',
    ]);
  });

  it('rejects two extra tabs with the same question', () => {
    expect(
      answerProblems(null, [
        { code: 'x', question_id: 'q-2' },
        { code: 'y', question_id: 'q-2' },
      ]),
    ).toEqual([
      'Program 3 uses the same question as Program 2. Each question can only be linked to one program.',
    ]);
  });
});

describe('programsForGrading', () => {
  it('lists Program 1 then every saved tab, each with its question', () => {
    expect(
      programsForGrading('int main() {}', 'q-1', [
        { code: 'int f(void);', question_id: 'q-2' },
        { code: 'int g(void);', question_id: 'q-3' },
      ]),
    ).toEqual([
      { program: 1, code: 'int main() {}', question_id: 'q-1' },
      { program: 2, code: 'int f(void);', question_id: 'q-2' },
      { program: 3, code: 'int g(void);', question_id: 'q-3' },
    ]);
  });

  it('reads the saved answers column and skips blank or unlinked entries', () => {
    expect(
      programsForGrading('int main() {}', 'q-1', [
        { code: '', question_id: null },
        { code: 'int f(void);', question_id: null },
        { code: 'int g(void);', question_id: 'q-3' },
      ]),
    ).toEqual([
      { program: 1, code: 'int main() {}', question_id: 'q-1' },
      { program: 4, code: 'int g(void);', question_id: 'q-3' },
    ]);
  });

  it('leaves out Program 1 when it has no code or no question', () => {
    expect(programsForGrading('', 'q-1', [])).toEqual([]);
    expect(programsForGrading('int main() {}', null, [])).toEqual([]);
  });
});
