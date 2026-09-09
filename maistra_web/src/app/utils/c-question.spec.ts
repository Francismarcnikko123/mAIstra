import { describe, expect, it } from 'vitest';
import { getFunctionCodeError, getProgramCodeError } from './c-question';

describe('C question structure checks', () => {
  it.each([
    '# include <stdio.h>',
    '# /* comment */ include "stdio.h"',
    '#inc\\\nlude <stdio.h>',
  ])('detects a real include directive: %s', (source) => {
    expect(getFunctionCodeError(source, 'Test Code')).toContain(
      'Remove #include',
    );
  });

  it.each([
    'int main(void) {}',
    'int (main)(void) {}',
    'int ma\\\nin(void) {}',
  ])('detects main: %s', (source) => {
    expect(getFunctionCodeError(source, 'Model Answer')).toContain(
      'Remove main()',
    );
  });

  it.each([
    'int read_value(void) { int value; scanf("%d", &value); return value; }',
    'int value; scanf ("%d", &value);',
  ])('rejects scanf in function code: %s', (source) => {
    expect(getFunctionCodeError(source, 'Model Answer')).toContain(
      'Remove scanf()',
    );
  });

  it('ignores scanf in comments, strings, and longer identifiers', () => {
    const source =
      '// scanf("%d", &value)\nvoid explain(void) { printf("scanf()"); }\nint myscanf(void) { return 1; }';
    expect(getFunctionCodeError(source, 'Model Answer')).toBe('');
  });

  it('ignores continued comments, escaped strings, and identifiers containing main', () => {
    const source =
      '// documentation \\\n#include <stdio.h>\nint domain(int x) { return x; }\nvoid explain(void) { printf("\\\"main()\\\" #include <stdio.h>"); }';
    expect(getFunctionCodeError(source, 'Model Answer')).toBe('');
  });

  it.each([
    'int main() {}',
    'int main(void) {}',
    'int (main)(void) {}',
    'int main(int argc, char **argv) {}',
  ])('accepts a program main definition: %s', (source) => {
    expect(getProgramCodeError(source)).toBe('');
  });
});
