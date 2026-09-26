import { test as base, expect, type Locator, type Page } from '@playwright/test';
import { submissionCard } from './support/cards';
import { FakeBackend } from './support/fake-backend';
import {
  SUM_TEST_CASES,
  evaluateSumProgram,
  program,
  replaceEditorCode,
} from './support/sum-program';

// The teacher's path for one handwritten submission: assign it a question,
// verify the OCR'd code, run a sample, then submit it against every test case
// and save the grade.

const QUESTION_ID = '11111111-1111-4111-8111-111111111111';
const SUBMISSION_ID = '22222222-2222-4222-8222-222222222222';
const CAPTURED_AT = '2026-09-20T08:30:00Z';
// How the list shows CAPTURED_AT (tests run in UTC).
const CARD_TIME = 'Sep 20 · 08:30';

const test = base.extend<{ backend: FakeBackend }>({
  backend: async ({ page }, use) => {
    const backend = new FakeBackend();
    backend.addQuestion({
      id: QUESTION_ID,
      question_name: 'Sum of two numbers',
      question_type: 'program',
      model_answer: program('a + b'),
      test_cases: SUM_TEST_CASES,
    });
    backend.judge0 = evaluateSumProgram;
    await backend.install(page);
    await use(backend);
    expect(backend.unexpected, 'requests the fake backend did not expect').toEqual([]);
  },
});

// Opens the submission captured at CAPTURED_AT; its dialog is titled with the
// student's name.
async function openSubmission(page: Page, studentName: string): Promise<Locator> {
  await page.goto('/');
  await submissionCard(page, CARD_TIME).click();
  const dialog = page.getByRole('dialog', { name: studentName });
  await expect(dialog).toBeVisible();
  return dialog;
}

test('teacher assigns a question, fixes the OCR code and grades it', async ({
  page,
  backend,
}) => {
  // OCR misread the student's `+` as `-`.
  backend.addSubmission({
    id: SUBMISSION_ID,
    captured_at: CAPTURED_AT,
    student_name: 'Maria Santos',
    topic: 'Loops',
    status: 'extracted',
    extracted_text: program('a - b'),
  });

  const dialog = await openSubmission(page, 'Maria Santos');

  // Step 1: details. Continuing is blocked until a question is chosen.
  const continueButton = dialog.getByRole('button', { name: 'Save and review code' });
  await expect(continueButton).toBeDisabled();
  await dialog.getByRole('combobox').selectOption({ label: 'Sum of two numbers' });
  await continueButton.click();

  // Step 2: the OCR result is editable; fix the misread operator and save.
  await expect(dialog.getByRole('heading', { name: 'Review extracted code' })).toBeVisible();
  await replaceEditorCode(dialog.locator('app-code-editor'), program('a + b'));
  await dialog.getByRole('button', { name: 'Continue to grading' }).click();

  // Step 3: a sample run checks only the first test case.
  await expect(dialog.getByRole('heading', { name: 'Run and grade' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Run Sample' }).click();
  await expect(dialog.getByText('First Test Case Passed')).toBeVisible();

  await dialog.getByRole('button', { name: 'Submit Code' }).click();
  await expect(
    dialog.getByText('2/2 test cases passed — Score: 100%'),
  ).toBeVisible();
  await expect(dialog.locator('.testcase-card.passed')).toHaveCount(2);

  // Judge0 received the saved code, with the header the grader adds, once per case.
  const [batch] = backend.requestsTo('POST', '/run-batch');
  expect(batch.body.runs).toEqual([
    { source_code: `#include <stdio.h>\n\n${program('a + b')}`, stdin: '2 2' },
    { source_code: `#include <stdio.h>\n\n${program('a + b')}`, stdin: '2 3' },
  ]);

  // The grade was stored on the program, against the verified code, and the
  // OCR text was kept on the page.
  expect(backend.submissions.get(SUBMISSION_ID)).toMatchObject({
    status: 'graded',
    question_id: QUESTION_ID,
    extracted_text: program('a - b'),
    verified_text: program('a + b'),
  });
  expect(backend.programsOf(SUBMISSION_ID)).toEqual([
    expect.objectContaining({
      position: 1,
      question_id: QUESTION_ID,
      verified_text: program('a + b'),
      passed_test_cases: 2,
      total_test_cases: 2,
      score_percent: 100,
    }),
  ]);

  // The list reflects the grade once the review is closed.
  await dialog.getByRole('button', { name: 'Finish review' }).click();
  await expect(dialog).toBeHidden();
  const card = submissionCard(page, CARD_TIME);
  await expect(card).toContainText('Graded');
  await expect(card).toContainText('2/2 test cases passed — Score: 100%');
});

test('code that passes only some test cases gets partial credit', async ({
  page,
  backend,
}) => {
  // Already verified and assigned, so the teacher goes straight to grading.
  backend.addSubmission({
    id: SUBMISSION_ID,
    captured_at: CAPTURED_AT,
    student_name: 'Jose Reyes',
    status: 'verified',
    question_id: QUESTION_ID,
    extracted_text: program('a * b'),
    verified_text: program('a * b'),
  });

  const dialog = await openSubmission(page, 'Jose Reyes');
  await dialog.getByRole('button', { name: 'Save and review code' }).click();
  await dialog.getByRole('button', { name: 'Continue to grading' }).click();
  await dialog.getByRole('button', { name: 'Submit Code' }).click();

  // 2*2 happens to equal 2+2, but 2*3 does not.
  await expect(dialog.getByText('1/2 test cases passed — Score: 50%')).toBeVisible();
  const cases = dialog.locator('.testcase-card');
  await expect(cases.nth(0)).toHaveClass(/passed/);
  await expect(cases.nth(0)).toContainText('1/1 point');
  await expect(cases.nth(1)).toHaveClass(/failed/);
  await expect(cases.nth(1)).toContainText('Wrong Answer');
  await expect(cases.nth(1)).toContainText('0/1 point');

  // Nothing needed saving, so the only write is the grade itself.
  expect(backend.requestsTo('PATCH', '/rest/v1/submissions')).toHaveLength(0);
  expect(backend.requestsTo('POST', '/rpc/save_submission_programs')).toHaveLength(0);
  expect(backend.submissions.get(SUBMISSION_ID)?.status).toBe('graded');
  expect(backend.programsOf(SUBMISSION_ID)[0]).toMatchObject({
    passed_test_cases: 1,
    total_test_cases: 2,
    score_percent: 50,
  });
});

test('a grade is not saved when the submission changed during grading', async ({
  page,
  backend,
}) => {
  backend.addSubmission({
    id: SUBMISSION_ID,
    captured_at: CAPTURED_AT,
    student_name: 'Ana Cruz',
    status: 'verified',
    question_id: QUESTION_ID,
    verified_text: program('a + b'),
  });
  // Another teacher saves new code while this page's Judge0 run is in flight.
  backend.beforeProgramGradeSave = (row) => {
    row.verified_text = program('a - b');
    row.grading_revision += 1;
  };

  const dialog = await openSubmission(page, 'Ana Cruz');
  await dialog.getByRole('button', { name: 'Save and review code' }).click();
  await dialog.getByRole('button', { name: 'Continue to grading' }).click();
  await dialog.getByRole('button', { name: 'Submit Code' }).click();

  await expect(
    dialog.getByText('Submission inputs changed during grading. Run grading again.'),
  ).toBeVisible();
  await expect(dialog.getByText(/test cases passed/)).toHaveCount(0);
  expect(backend.submissions.get(SUBMISSION_ID)?.status).toBe('verified');
  expect(backend.programsOf(SUBMISSION_ID)[0]).toMatchObject({
    graded_at: null,
    passed_test_cases: null,
  });
});

test('grading reports a failure and saves nothing when Judge0 is down', async ({
  page,
  backend,
}) => {
  backend.addSubmission({
    id: SUBMISSION_ID,
    captured_at: CAPTURED_AT,
    student_name: 'Luis Garcia',
    status: 'verified',
    question_id: QUESTION_ID,
    verified_text: program('a + b'),
  });
  backend.judge0FailureStatus = 502;

  const dialog = await openSubmission(page, 'Luis Garcia');
  await dialog.getByRole('button', { name: 'Save and review code' }).click();
  await dialog.getByRole('button', { name: 'Continue to grading' }).click();
  await dialog.getByRole('button', { name: 'Submit Code' }).click();

  await expect(dialog.getByText('Failed to execute test cases.')).toBeVisible();
  // The button is usable again so the teacher can retry once Judge0 is back.
  await expect(dialog.getByRole('button', { name: 'Submit Code' })).toBeEnabled();
  expect(backend.requestsTo('POST', '/rpc/save_program_grade')).toHaveLength(0);
  expect(backend.submissions.get(SUBMISSION_ID)?.status).toBe('verified');
});

test('each program on a paper is graded against its own question', async ({
  page,
  backend,
}) => {
  const PRODUCT_ID = '55555555-5555-4555-8555-555555555555';
  backend.addQuestion({
    id: PRODUCT_ID,
    question_name: 'Product of two numbers',
    question_type: 'program',
    model_answer: program('a * b'),
    test_cases: [
      { test_code: '', test_input: '2 2', expected_output: '4' },
      { test_code: '', test_input: '2 3', expected_output: '6' },
    ],
  });
  // One photographed page with two programs, already verified.
  backend.addSubmission({
    id: SUBMISSION_ID,
    captured_at: CAPTURED_AT,
    student_name: 'Rosa Lim',
    status: 'verified',
    question_id: QUESTION_ID,
    verified_text: program('a + b'),
  });
  backend.addExtraProgram(SUBMISSION_ID, 2, PRODUCT_ID, program('a * b'));

  const dialog = await openSubmission(page, 'Rosa Lim');
  await dialog.getByRole('button', { name: 'Save and review code' }).click();
  await dialog.getByRole('button', { name: 'Continue to grading' }).click();

  // Step 3 lists both programs; the first ungraded one is selected.
  const programs = dialog.getByRole('tablist', { name: 'Programs to grade' });
  const first = programs.getByRole('tab', { name: /Program 1/ });
  const second = programs.getByRole('tab', { name: /Program 2/ });
  await expect(first).toHaveAttribute('aria-selected', 'true');
  await expect(dialog.locator('.grading-context')).toContainText('Sum of two numbers');

  await dialog.getByRole('button', { name: 'Submit Code' }).click();
  await expect(first).toContainText('✓ 2/2');
  // One of two programs graded: the paper is not graded yet.
  expect(backend.submissions.get(SUBMISSION_ID)?.status).toBe('verified');

  await second.click();
  await expect(dialog.locator('.grading-context')).toContainText('Product of two numbers');
  await dialog.getByRole('button', { name: 'Submit Code' }).click();
  await expect(second).toContainText('✓ 2/2');

  // Judge0 ran each program with its own question's inputs.
  const batches = backend.requestsTo('POST', '/run-batch').map((request) => request.body.runs);
  expect(batches).toEqual([
    [
      { source_code: `#include <stdio.h>

${program('a + b')}`, stdin: '2 2' },
      { source_code: `#include <stdio.h>

${program('a + b')}`, stdin: '2 3' },
    ],
    [
      { source_code: `#include <stdio.h>

${program('a * b')}`, stdin: '2 2' },
      { source_code: `#include <stdio.h>

${program('a * b')}`, stdin: '2 3' },
    ],
  ]);
  expect(backend.submissions.get(SUBMISSION_ID)?.status).toBe('graded');
  expect(backend.programsOf(SUBMISSION_ID).map((row) => row.passed_test_cases)).toEqual([2, 2]);

  // The card shows one score per program.
  await dialog.getByRole('button', { name: 'Finish review' }).click();
  const card = submissionCard(page, CARD_TIME);
  await expect(card).toContainText('Graded');
  await expect(card).toContainText('Program 1 2/2 · Program 2 2/2');
});

test('a question changed on Details is the one Program 1 is graded against', async ({
  page,
  backend,
}) => {
  const PRODUCT_ID = '55555555-5555-4555-8555-555555555555';
  backend.addQuestion({
    id: PRODUCT_ID,
    question_name: 'Product of two numbers',
    question_type: 'program',
    model_answer: program('a * b'),
    test_cases: [
      { test_code: '', test_input: '2 2', expected_output: '4' },
      { test_code: '', test_input: '2 3', expected_output: '6' },
    ],
  });
  // Graded 1/2 against the wrong question (Sum) before the teacher noticed.
  backend.addSubmission({
    id: SUBMISSION_ID,
    captured_at: CAPTURED_AT,
    student_name: 'Tomas Diaz',
    status: 'graded',
    question_id: QUESTION_ID,
    verified_text: program('a * b'),
    grading_results: [{ passed: true }, { passed: false }],
    passed_test_cases: 1,
    total_test_cases: 2,
    score_percent: 50,
    graded_at: '2026-09-26T08:00:00Z',
  });

  const dialog = await openSubmission(page, 'Tomas Diaz');
  await dialog.getByRole('combobox').selectOption({ label: 'Product of two numbers' });
  await dialog.getByRole('button', { name: 'Save and review code' }).click();
  // The code is unchanged, so this goes straight to grading without a save.
  await dialog.getByRole('button', { name: 'Continue to grading' }).click();

  await expect(dialog.locator('.grading-context')).toContainText('Product of two numbers');
  await dialog.getByRole('button', { name: 'Submit Code' }).click();
  await expect(dialog.getByText('2/2 test cases passed — Score: 100%')).toBeVisible();

  const [batch] = backend.requestsTo('POST', '/run-batch');
  expect(batch.body.runs.map((run: { stdin: string }) => run.stdin)).toEqual(['2 2', '2 3']);
  expect(backend.programsOf(SUBMISSION_ID)).toEqual([
    expect.objectContaining({ question_id: PRODUCT_ID, passed_test_cases: 2, total_test_cases: 2 }),
  ]);
});
