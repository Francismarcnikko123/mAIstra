import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from '../../services/supabase';
import { Judge0Service } from '../../services/judge0.service';
import { of, Subject, throwError } from 'rxjs';
import { QuestionFormComponent } from './question-form';

describe('QuestionFormComponent', () => {
  function createComponent(
    saveQuestion = vi.fn().mockResolvedValue({ data: {}, error: null }),
    runCCode = vi.fn().mockReturnValue(of({ stdout: '2', status: { id: 3 } })),
  ) {
    const supabase = { saveQuestion } as unknown as SupabaseService;
    const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
    const judge0 = { runCCode } as unknown as Judge0Service;

    return new QuestionFormComponent(supabase, cdr, judge0);
  }

  it('resets test cases after a successful save', async () => {
    const saveQuestion = vi.fn().mockResolvedValue({ data: {}, error: null });
    const runCCode = vi
      .fn()
      .mockReturnValueOnce(of({ stdout: '2', status: { id: 3 } }))
      .mockReturnValueOnce(of({ stdout: '5', status: { id: 3 } }));
    const component = createComponent(saveQuestion, runCCode);
    component.questionName = 'Addition';
    component.questionText = 'Write a C program that adds two numbers.';
    component.questionType = 'program';
    component.modelAnswer = 'int main(void) { return 0; }';
    component.testCases = [
      {
        test_code: '1 1',
        test_input: '1 1',
        expected_output: '2',
      },
      {
        test_code: '2 3',
        test_input: '2 3',
        expected_output: '5',
      },
    ];
    await component.validateModelAnswer();
    component.collapsedTestCases = { 1: true };

    await component.save();

    expect(
      saveQuestion.mock.calls[0][0].test_cases.every(
        (testCase: object) => !('mark' in testCase),
      ),
    ).toBe(true);
    expect(component.testCases).toEqual([
      {
        test_code: '',
        test_input: '',
        expected_output: '',
      },
    ]);
    expect(component.validationResults).toEqual([]);
    expect(component.testRunStatuses).toEqual([]);
    expect(component.canPublish).toBe(false);
    expect(component.collapsedTestCases).toEqual({});
  });

  function validationFixture(
    runCCode = vi
      .fn()
      .mockReturnValue(
        of({ stdout: '5\n', status: { id: 3, description: 'Accepted' } }),
      ),
  ) {
    const saveQuestion = vi.fn().mockResolvedValue({ data: {}, error: null });
    const component = createComponent(saveQuestion, runCCode);
    component.questionName = 'Addition';
    component.questionText = 'Return the sum.';
    component.modelAnswer = 'int add(int a, int b) { return a + b; }';
    component.testCases = [
      {
        test_code: 'printf("%d", add(2, 3));',
        test_input: '',
        expected_output: '5',
      },
    ];
    return { component, runCCode, saveQuestion };
  }

  it.each([
    [
      'model',
      '#include <stdio.h>\nint add(int a, int b) { return a + b; }',
      '#include',
    ],
    ['model', 'int main(void) { return 0; }', 'main()'],
    [
      'model',
      'int read(void) { int x; scanf("%d", &x); return x; }',
      'scanf()',
    ],
    ['test', '#include <stdio.h>\nprintf("%d", add(2, 3));', '#include'],
    ['test', 'int main(void) { printf("%d", add(2, 3)); }', 'main()'],
    ['test', 'int x; scanf("%d", &x); printf("%d", add(x, 3));', 'scanf()'],
  ])(
    'rejects forbidden %s code before Judge0: %s',
    async (field, code, token) => {
      const { component, runCCode, saveQuestion } = validationFixture();
      if (field === 'model') component.modelAnswer = code;
      else component.testCases[0].test_code = code;

      await component.validateModelAnswer();
      await component.save();

      expect(runCCode).not.toHaveBeenCalled();
      expect(saveQuestion).not.toHaveBeenCalled();
      expect(component.canPublish).toBe(false);
      expect(component.validationResults[0]).toMatchObject({
        passed: false,
        status: 'Invalid code structure',
      });
      expect(component.validationResults[0].message).toContain(token);
      expect(
        field === 'model'
          ? component.modelAnswerError
          : component.getTestCodeError(0),
      ).toContain(token);
    },
  );

  it('ignores forbidden words in C comments and string literals', async () => {
    const { component, runCCode } = validationFixture();
    component.modelAnswer =
      '// #include <stdio.h>, main(), and scanf() are discussed here\nint add(int a, int b) { return a+b; }';
    component.testCases[0].test_code =
      '/* main() and scanf() */ printf("#include <stdio.h> main() scanf() %d", add(2, 3));';
    await component.validateModelAnswer();
    expect(runCCode).toHaveBeenCalledOnce();
    expect(component.canPublish).toBe(true);
  });

  it('runs function test statements in a single main without Standard Input', async () => {
    const { component, runCCode } = validationFixture();
    component.testCases[0].test_input = '2 3';
    await component.validateModelAnswer();
    const [source, stdin] = runCCode.mock.calls[0];
    expect(source).toContain('#include <stdio.h>');
    expect(source).toContain(component.modelAnswer);
    expect(source).toContain(component.testCases[0].test_code);
    expect(source.match(/\bmain\s*\(/g)).toHaveLength(1);
    expect(stdin).toBe('');
    expect(component.canPublish).toBe(true);
  });

  it.each(['', '#include <stdio.h>\n'])(
    'supplies stdio for a program with header %j',
    async (header) => {
      const { component, runCCode } = validationFixture();
      component.questionType = 'program';
      component.modelAnswer =
        header + 'int main(void) { printf("5"); return 0; }';
      component.testCases[0].test_input = '2 3';
      await component.validateModelAnswer();
      const [source, stdin] = runCCode.mock.calls[0];
      expect(source).toMatch(/^#include <stdio.h>/);
      expect(source).toContain(component.modelAnswer);
      expect(source.match(/\bmain\s*\(/g)).toHaveLength(1);
      expect(stdin).toBe('2 3');
      expect(component.canPublish).toBe(true);
    },
  );

  it.each([
    'int add(int a, int b) { return a + b; }',
    'int main(void);',
    '// int main(void) {}',
  ])('rejects a program without a main definition: %s', async (source) => {
    const { component, runCCode } = validationFixture();
    component.questionType = 'program';
    component.modelAnswer = source;
    await component.validateModelAnswer();
    expect(runCCode).not.toHaveBeenCalled();
    expect(component.modelAnswerError).toContain('main()');
    expect(component.canPublish).toBe(false);
  });

  it.each(['function', 'program'])(
    'fails empty stdout for %s without erasing expected output',
    async (type) => {
      const runCCode = vi
        .fn()
        .mockReturnValue(
          of({ stdout: ' \n\t', status: { id: 3, description: 'Accepted' } }),
        );
      const { component } = validationFixture(runCCode);
      component.questionType = type;
      if (type === 'program')
        component.modelAnswer = 'int main(void) { return 0; }';
      await component.validateModelAnswer();
      expect(component.canPublish).toBe(false);
      expect(component.testCases[0].expected_output).toBe('5');
      expect(component.validationResults[0]).toMatchObject({
        passed: false,
        status: 'No output',
      });
      expect(component.validationResults[0].message).toContain('printf');
    },
  );

  it('keeps a manual expected output and fails when actual output differs', async () => {
    const { component } = validationFixture(
      vi.fn().mockReturnValue(
        of({
          stdout: '7\n',
          compile_output: 'warning: unused variable',
          status: { id: 3 },
        }),
      ),
    );
    await component.validateModelAnswer();
    expect(component.testCases[0].expected_output).toBe('5');
    expect(component.validationResults[0]).toMatchObject({
      passed: false,
      expected: '5',
      actual: '7',
      status: 'Wrong Answer',
      compile_output: 'warning: unused variable',
    });
    expect(component.canPublish).toBe(false);
  });

  it('accepts a normalized match without changing the manual expected output', async () => {
    const { component } = validationFixture(
      vi.fn().mockReturnValue(
        of({
          stdout: '  HELLO:world\n',
          status: { id: 3, description: 'Accepted' },
        }),
      ),
    );
    component.testCases[0].expected_output = 'hello : world';
    await component.validateModelAnswer();
    expect(component.validationResults[0]).toMatchObject({
      passed: true,
      expected: 'hello : world',
      actual: 'HELLO:world',
    });
    expect(component.testCases[0].expected_output).toBe('hello : world');
    expect(component.canPublish).toBe(true);
  });

  it('saves a function question without hidden legacy Standard Input', async () => {
    const { component, saveQuestion } = validationFixture();
    component.testCases[0].test_input = 'legacy input';
    await component.validateModelAnswer();
    await component.save();
    expect(saveQuestion).toHaveBeenCalledWith(
      expect.objectContaining({
        question_type: 'function',
        test_cases: [
          expect.objectContaining({
            test_input: '',
            expected_output: '5',
          }),
        ],
      }),
    );
  });

  it('requires Expected Output before sending any validation request', async () => {
    const { component, runCCode } = validationFixture();
    component.testCases[0].expected_output = '   ';
    await component.validateModelAnswer();
    expect(runCCode).not.toHaveBeenCalled();
    expect(component.canPublish).toBe(false);
    expect(component.validationResults[0]).toMatchObject({
      passed: false,
      status: 'Missing expected output',
    });
    expect(component.validationResults[0].message).toContain('Expected Output');
  });

  it.each([
    {
      stdout: '',
      compile_output: 'error: invalid C',
      status: { id: 6, description: 'Compilation Error' },
    },
    {
      stdout: 'partial output',
      stderr: 'crashed',
      message: 'SIGSEGV',
      status: { id: 11, description: 'Runtime Error (SIGSEGV)' },
    },
  ])(
    'preserves Judge0 diagnostics on a failed run: $status.description',
    async (result) => {
      const { component } = validationFixture(
        vi.fn().mockReturnValue(of(result)),
      );
      await component.validateModelAnswer();
      expect(component.canPublish).toBe(false);
      expect(component.testCases[0].expected_output).toBe('5');
      expect(component.validationResults[0]).toMatchObject({
        passed: false,
        actual: result.stdout,
        status: result.status.description,
        message: result.message,
      });
    },
  );

  it('shows the API error when Judge0 is unavailable', async () => {
    const { component } = validationFixture(
      vi
        .fn()
        .mockReturnValue(
          throwError(() => ({ error: { detail: 'Judge0 is unreachable.' } })),
        ),
    );
    await component.validateModelAnswer();
    expect(component.validationResults[0].message).toBe(
      'Judge0 is unreachable.',
    );
    expect(component.canPublish).toBe(false);
    expect(component.isValidating).toBe(false);
  });

  it.each(['model', 'test', 'cases'])(
    'rejects empty %s instead of passing',
    async (field) => {
      const { component, runCCode } = validationFixture();
      if (field === 'model') component.modelAnswer = ' /* empty */ ';
      if (field === 'test') component.testCases[0].test_code = ' // empty ';
      if (field === 'cases') component.testCases = [];
      await component.validateModelAnswer();
      expect(runCCode).not.toHaveBeenCalled();
      expect(component.canPublish).toBe(false);
      expect(component.errorMessage).not.toBe('');
    },
  );

  it('does not reapply a passed result after editing during execution', async () => {
    const response = new Subject<{ stdout: string; status: { id: number } }>();
    const { component } = validationFixture(vi.fn().mockReturnValue(response));
    const validation = component.validateModelAnswer();
    component.modelAnswer = 'int main(void) {}';
    component.clearValidationResults();
    component.testCases[0].expected_output = 'edited';
    response.next({ stdout: 'old result', status: { id: 3 } });
    await validation;
    expect(component.canPublish).toBe(false);
    expect(component.validationResults).toEqual([]);
    expect(component.testCases[0].expected_output).toBe('edited');
  });

  it('does not publish after the last test is removed during validation', async () => {
    const response = new Subject<{ stdout: string; status: { id: number } }>();
    const { component } = validationFixture(vi.fn().mockReturnValue(response));
    const validation = component.validateModelAnswer();
    component.removeTestCase(0);
    response.next({ stdout: '5', status: { id: 3 } });
    await validation;
    expect(component.canPublish).toBe(false);
    expect(component.validationResults).toEqual([]);
  });

  it('requires validation of the current inputs at save time', async () => {
    const { component, saveQuestion } = validationFixture();
    await component.validateModelAnswer();
    component.testCases[0].expected_output = 'changed without an event';
    await component.save();
    expect(saveQuestion).not.toHaveBeenCalled();
  });

  it('does not report all tests passed while an earlier test is still running', async () => {
    const response = new Subject<{ stdout: string; status: { id: number } }>();
    const runCCode = vi
      .fn()
      .mockReturnValueOnce(response)
      .mockReturnValueOnce(of({ stdout: '7', status: { id: 3 } }));
    const { component } = validationFixture(runCCode);
    component.testCases.push({
      ...component.testCases[0],
      test_code: 'printf("%d", add(3, 4));',
      expected_output: '7',
    });
    const validation = component.validateModelAnswer();
    await Promise.resolve();
    const prematurelyPassed = component.passedAllTests();
    response.next({ stdout: '5', status: { id: 3 } });
    await validation;
    expect(prematurelyPassed).toBe(false);
    expect(component.passedAllTests()).toBe(true);
    expect(component.testCases.map((tc) => tc.expected_output)).toEqual([
      '5',
      '7',
    ]);
  });

});
