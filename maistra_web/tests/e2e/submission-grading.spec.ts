import { test as base, expect, type Locator, type Page } from '@playwright/test';
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

async function openSubmission(page: Page, studentName: string): Promise<Locator> {
  await page.goto('/');
  await page.getByRole('button', { name: new RegExp(studentName) }).click();
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

  // The grade was stored against the verified code, and the OCR text was kept.
  const stored = backend.submissions.get(SUBMISSION_ID)!;
  expect(stored).toMatchObject({
    status: 'graded',
    question_id: QUESTION_ID,
    extracted_text: program('a - b'),
    verified_text: program('a + b'),
    passed_test_cases: 2,
    total_test_cases: 2,
    score_percent: 100,
  });

  // The list reflects the grade once the review is closed.
  await dialog.getByRole('button', { name: 'Finish review' }).click();
  await expect(dialog).toBeHidden();
  const card = page.getByRole('button', { name: /Maria Santos/ });
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
  expect(backend.submissions.get(SUBMISSION_ID)).toMatchObject({
    status: 'graded',
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
    student_name: 'Ana Cruz',
    status: 'verified',
    question_id: QUESTION_ID,
    verified_text: program('a + b'),
  });
  // Another teacher saves new code while this page's Judge0 run is in flight.
  backend.beforeGradeSave = (row) => {
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
  expect(backend.submissions.get(SUBMISSION_ID)).toMatchObject({
    status: 'verified',
    passed_test_cases: null,
  });
});

test('grading reports a failure and saves nothing when Judge0 is down', async ({
  page,
  backend,
}) => {
  backend.addSubmission({
    id: SUBMISSION_ID,
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
  expect(backend.requestsTo('POST', '/rpc/save_submission_grade')).toHaveLength(0);
  expect(backend.submissions.get(SUBMISSION_ID)?.status).toBe('verified');
});
