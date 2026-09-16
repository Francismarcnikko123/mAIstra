import { describe, expect, it } from 'vitest';

import { normalizeOutput } from './normalize-output';

describe('normalizeOutput', () => {
  it('normalizes case, repeated whitespace, and colon spacing', () => {
    expect(normalizeOutput('  Sum :   5\n')).toBe('sum:5');
  });

  it('normalizes missing output to an empty string', () => {
    expect(normalizeOutput(undefined)).toBe('');
    expect(normalizeOutput(null)).toBe('');
  });
});
