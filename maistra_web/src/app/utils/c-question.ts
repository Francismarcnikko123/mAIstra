/**
 * Lightweight authoring checks; Judge0 remains responsible for C compilation.
 *
 * A question is one of two types:
 * - 'program': the answer is a whole program with its own main(). Each test
 *   case gives stdin text for scanf() and the expected output.
 * - 'function': the answer is only a function. Each test case gives Test Code
 *   that calls it and prints the result; the system wraps that in main().
 */

// Joins backslash-continued lines, then blanks out comments, strings and char
// literals (keeping their line breaks), so the checks below don't match
// `main(` or `scanf(` written inside them.
function structuralCode(source: string): string {
  // C joins continued lines before interpreting comments and directives.
  return source
    .replace(/\\\r?\n/g, '')
    .replace(
      /\/\*[\s\S]*?(?:\*\/|$)|\/\/[^\r\n]*|"(?:\\[\s\S]|[^"\\])*"|'(?:\\[\s\S]|[^'\\])*'/g,
      (token) => token.replace(/[^\r\n]/g, ' '),
    );
}

/**
 * Checks a function question's Model Answer or Test Code. Returns '' when it
 * is fine, else the problems in one message. #include and main() are added by
 * buildCQuestionSource, and inputs come from Test Code, so none may be typed.
 */
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

/** Checks a program question's Model Answer: it must define main(). */
export function getProgramCodeError(source: string): string {
  const code = structuralCode(source);
  // A declaration or a mention in a comment/string does not define main.
  if (!/\bmain\s*(?:\)\s*)*\([^;{}]*\)\s*\{/.test(code)) {
    return 'Model Answer must define main() for Write a Program. The system supplies #include <stdio.h>.';
  }
  return '';
}

/**
 * Builds the complete C file that is sent to Judge0 for one test case.
 * Used for the model answer (question form) and the student code (Step 3).
 *
 * Program question: #include <stdio.h> + the answer.
 *
 * Function question: the answer plus a temporary main() made from the test
 * case's Test Code. For answer `int square(int n) { return n * n; }` and
 * Test Code `printf("%d", square(4));` Judge0 receives:
 *
 *   #include <stdio.h>
 *
 *   int square(int n) { return n * n; }
 *
 *   int main(void) {
 *   printf("%d", square(4));
 *
 *     return 0;
 *   }
 */
export function buildCQuestionSource(
  questionType: string,
  answer: string,
  testCode = '',
): string {
  const source = `#include <stdio.h>\n\n${answer}`;
  if (questionType !== 'function') return source;

  return `${source}\n\nint main(void) {\n${testCode}\n\n  return 0;\n}`;
}
