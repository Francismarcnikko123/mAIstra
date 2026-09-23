import '@angular/compiler';
import { describe, expect, it, vi } from 'vitest';

import { CodeEditorComponent } from './code-editor';

// reindent is a private static, whitespace-only formatter. Access it directly;
// it needs no Ace editor or Angular TestBed.
const reindent = (src: string): string =>
  (CodeEditorComponent as unknown as { reindent(s: string): string }).reindent(
    src,
  );

// Strip each line's leading whitespace -- the grade-safety invariant is that
// reindent changes ONLY leading whitespace, so this must be identical in and out.
const stripLeading = (s: string): string =>
  s
    .split('\n')
    .map((l) => l.replace(/^[ \t]+/, ''))
    .join('\n');

describe('CodeEditorComponent.reindent', () => {
  it('rule 1: indents by brace depth (regression, unchanged)', () => {
    const input = ['int main(){', 'int x;', 'if(x){', 'printf("hi");', '}', '}'].join(
      '\n',
    );
    const expected = [
      'int main(){',
      '  int x;',
      '  if(x){',
      '    printf("hi");',
      '  }',
      '}',
    ].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('rule 2: switch/case -- labels at block level, bodies one deeper', () => {
    const input = [
      'switch(x){',
      'case 1:',
      'foo();',
      'break;',
      'default:',
      'bar();',
      '}',
    ].join('\n');
    const expected = [
      'switch(x){',
      '  case 1:',
      '    foo();',
      '    break;',
      '  default:',
      '    bar();',
      '}',
    ].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('rule 2: a nested block inside a case still nests correctly', () => {
    const input = [
      'switch(x){',
      'case 1:',
      'if(y){',
      'bar();',
      '}',
      'break;',
      '}',
    ].join('\n');
    const expected = [
      'switch(x){',
      '  case 1:',
      '    if(y){',
      '      bar();',
      '    }',
      '    break;',
      '}',
    ].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('rule 2: Allman switch (brace on its own line) is still a switch body', () => {
    const input = ['switch (x)', '{', 'case 1:', 'foo();', '}'].join('\n');
    const expected = [
      'switch (x)',
      '{',
      '  case 1:',
      '    foo();',
      '}',
    ].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('rule 3: line continuation (unbalanced parens) indents one deeper', () => {
    const input = ['foo(a,', 'b);'].join('\n');
    const expected = ['foo(a,', '  b);'].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('rule 4: a goto label sits one level out', () => {
    const input = ['int main(){', 'goto retry;', 'retry:', 'return 0;', '}'].join(
      '\n',
    );
    const expected = [
      'int main(){',
      '  goto retry;',
      'retry:',
      '  return 0;',
      '}',
    ].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('rule 5: preprocessor directives go to column 0 regardless of depth', () => {
    const input = [
      '#include <stdio.h>',
      'int main(){',
      '#define N 5',
      'return 0;',
      '}',
    ].join('\n');
    const expected = [
      '#include <stdio.h>',
      'int main(){',
      '#define N 5',
      '  return 0;',
      '}',
    ].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('braces inside strings and comments do not shift indentation', () => {
    const input = [
      'int main(){',
      'printf("}");',
      '// a } in a comment',
      'return 0;',
      '}',
    ].join('\n');
    const expected = [
      'int main(){',
      '  printf("}");',
      '  // a } in a comment',
      '  return 0;',
      '}',
    ].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('grade-safety: only leading whitespace changes (content byte-identical)', () => {
    const fixtures = [
      'int main(){\nint x;\nswitch(x){\ncase 1:\nfoo();\nbreak;\n}\nreturn 0;\n}',
      '#include <stdio.h>\nint f(int a,\nint b){\nreturn a+b;\n}',
      'void g(){\ngoto end;\nend:\nreturn;\n}',
    ];
    for (const src of fixtures) {
      expect(stripLeading(reindent(src))).toBe(stripLeading(src));
    }
  });

  it('is idempotent: formatting already-formatted text is a no-op', () => {
    const input = [
      'switch(x){',
      'case 1:',
      'foo();',
      'break;',
      '}',
    ].join('\n');
    const once = reindent(input);
    expect(reindent(once)).toBe(once);
  });

  it('preserves trailing and internal whitespace (only leading changes)', () => {
    const input = ['int main(){', 'int x =  5;   ', '}'].join('\n');
    const expected = ['int main(){', '  int x =  5;   ', '}'].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('blank lines are preserved', () => {
    const input = ['int main(){', '', 'return 0;', '}'].join('\n');
    const expected = ['int main(){', '', '  return 0;', '}'].join('\n');
    expect(reindent(input)).toBe(expected);
  });

  it('never throws on unbalanced braces and stays whitespace-only', () => {
    const input = ['}', '}', 'int x;', '{'].join('\n');
    const out = reindent(input);
    expect(stripLeading(out)).toBe(stripLeading(input));
  });
});

describe('CodeEditorComponent.refresh', () => {
  it('asks Ace to re-measure after the editor was hidden', () => {
    const component = Object.create(CodeEditorComponent.prototype) as CodeEditorComponent;
    const resize = vi.fn();
    (component as unknown as { editor: { resize: typeof resize } }).editor = { resize };

    component.refresh();

    expect(resize).toHaveBeenCalledWith(true);
  });

  it('does nothing before the editor exists', () => {
    const component = Object.create(CodeEditorComponent.prototype) as CodeEditorComponent;
    expect(() => component.refresh()).not.toThrow();
  });
});
