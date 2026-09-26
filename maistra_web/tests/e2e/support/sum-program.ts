import type { Locator } from '@playwright/test';
import { accepted, compileError, type Judge0Run } from './fake-backend';

// The sample question used across the specs: read two integers and print
// their sum. Test cases pick inputs where a wrong operator still passes some
// of them (2*2 == 2+2), so partial credit is observable.

export const SUM_TEST_CASES = [
  { test_code: '', test_input: '2 2', expected_output: '4' },
  { test_code: '', test_input: '2 3', expected_output: '5' },
];

export const program = (expression: string) =>
  `int main(void) {\nint a, b;\nscanf("%d %d", &a, &b);\nprintf("%d", ${expression});\nreturn 0;\n}`;

// Stands in for gcc: finds `a <op> b` in the program and applies it to the
// two numbers on stdin, so each test's code decides which cases pass.
export function evaluateSumProgram(run: Judge0Run) {
  const operator = run.source_code.match(/printf\("%d", a\s*([-+*])\s*b\)/)?.[1];
  if (!operator) return compileError('error: expected expression');
  const [a, b] = run.stdin.trim().split(/\s+/).map(Number);
  const value = operator === '+' ? a + b : operator === '-' ? a - b : a * b;
  return accepted(String(value));
}

// Types into an Ace editor the way a teacher would: select all, then replace.
export async function replaceEditorCode(editor: Locator, code: string) {
  await editor.locator('.ace_content').click();
  await editor.page().keyboard.press('ControlOrMeta+A');
  await editor.page().keyboard.insertText(code);
}
