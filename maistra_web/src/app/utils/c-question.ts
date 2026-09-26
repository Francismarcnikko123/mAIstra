/** Lightweight authoring checks; Judge0 remains responsible for C compilation. */
function structuralCode(source: string): string {
  // C joins continued lines before interpreting comments and directives.
  return source
    .replace(/\\\r?\n/g, '')
    .replace(
      /\/\*[\s\S]*?(?:\*\/|$)|\/\/[^\r\n]*|"(?:\\[\s\S]|[^"\\])*"|'(?:\\[\s\S]|[^'\\])*'/g,
      (token) => token.replace(/[^\r\n]/g, ' '),
    );
}

export function getFunctionCodeError(source: string, field: string): string {
  const code = structuralCode(source);
  if (!code.trim()) return `${field} is required.`;

  const errors: string[] = [];
  if (/^\s*#\s*include\b/m.test(code)) {
    errors.push(
      `Remove #include from ${field}. The system supplies #include <stdio.h>.`,
    );
  }
  if (/\bmain\s*(?:\)\s*)*\(/.test(code)) {
    errors.push(
      `Remove main() from ${field}. The system supplies main() for function tests.`,
    );
  }
  if (/\bscanf\s*\(/.test(code)) {
    errors.push(
      `Remove scanf() from ${field}. Function inputs must be received through parameters and assigned in Test Code.`,
    );
  }
  return errors.join(' ');
}

export function getProgramCodeError(source: string): string {
  const code = structuralCode(source);
  // A declaration or a mention in a comment/string does not define main.
  if (!/\bmain\s*(?:\)\s*)*\([^;{}]*\)\s*\{/.test(code)) {
    return 'Model Answer must define main() for Write a Program. The system supplies #include <stdio.h>.';
  }
  return '';
}

export function buildCQuestionSource(
  questionType: string,
  answer: string,
  testCode = '',
): string {
  const source = `#include <stdio.h>\n\n${answer}`;
  if (questionType !== 'function') return source;

  return `${source}\n\nint main(void) {\n${testCode}\n\n  return 0;\n}`;
}
