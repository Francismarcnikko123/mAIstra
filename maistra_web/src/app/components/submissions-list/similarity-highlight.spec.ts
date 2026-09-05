import { describe, expect, it } from 'vitest';
import { highlightSource } from './similarity-highlight';

describe('Similarity evidence fragments', () => {
  it('retains literal HTML as text and merges overlapping ranges', () => {
    const code = '<script>alert(1)</script>';
    const rows = highlightSource(code, [
      { start: { row: 0, column: 8 }, end: { row: 0, column: 13 } },
      { start: { row: 0, column: 10 }, end: { row: 0, column: 16 } },
    ]);
    expect(rows[0].fragments.map((f) => f.text).join('')).toBe(code);
    expect(
      rows[0].fragments
        .filter((f) => f.matched)
        .map((f) => f.text)
        .join(''),
    ).toBe('alert(1)');
  });
  it('converts Tree-sitter UTF-8 byte columns into Unicode character boundaries', () => {
    const rows = highlightSource('é = 4;\nreturn 4;', [
      { start: { row: 0, column: 5 }, end: { row: 1, column: 6 } },
    ]);
    expect(
      rows[0].fragments
        .filter((f) => f.matched)
        .map((f) => f.text)
        .join(''),
    ).toBe('4;');
    expect(
      rows[1].fragments
        .filter((f) => f.matched)
        .map((f) => f.text)
        .join(''),
    ).toBe('return');
    expect(rows[1].number).toBe(2);
  });
});
