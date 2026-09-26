import { test as base, expect, type Locator, type Page } from '@playwright/test';
import { submissionCard } from './support/cards';
import { FakeBackend, PLACEHOLDER_IMAGE } from './support/fake-backend';
import {
  SUM_TEST_CASES,
  evaluateSumProgram,
  program,
  replaceEditorCode,
} from './support/sum-program';

// The whole teacher workflow on one page, in the order it happens in class:
// author a question, receive a student's photo from the mobile app, extract
// the handwritten code with OCR, verify it, then grade it with Judge0.

const NEW_SUBMISSION_ID = '33333333-3333-4333-8333-333333333333';
// Capture times as the list shows them (tests run in UTC).
const NEW_CARD_TIME = 'Sep 26 · 09:30';
const OLD_CARD_TIME = 'Sep 1 · 08:00';

const test = base.extend<{ backend: FakeBackend }>({
  backend: async ({ page }, use) => {
    const backend = new FakeBackend();
    backend.judge0 = evaluateSumProgram;
    await backend.install(page);
    await use(backend);
    expect(backend.unexpected, 'requests the fake backend did not expect').toEqual([]);
  },
});

async function openApp(page: Page, backend: FakeBackend) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Submissions' })).toBeVisible();
  // Uploads only reach the page once its realtime channel has joined.
  await expect.poll(() => backend.realtimeSubscribed).toBe(true);
}

// The question form is its own page, opened from the question bank.
async function openQuestionForm(page: Page): Promise<Locator> {
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: 'Question bank' }).click();
  await page.getByRole('button', { name: '+ Create question' }).click();
  const form = page.locator('app-question-form');
  await expect(form.getByRole('heading', { name: 'Create Question' })).toBeVisible();
  return form;
}

async function fillSumQuestion(form: Locator, expectedOutputs: string[]) {
  // Every question belongs to a section and has a number in it.
  await form.getByLabel('Section *', { exact: true }).selectOption({ label: '+ New section' });
  await form.getByLabel('New section name').fill('Skill Test 1A');
  await form.getByLabel('Question No.').fill('1');
  await form.getByLabel('Question Name').fill('Sum of two numbers');
  await form.getByRole('radio', { name: 'Write a Program' }).check();
  await form
    .getByPlaceholder('Describe the problem...')
    .fill('Read two integers and print their sum.');
  await replaceEditorCode(form.locator('app-code-editor').first(), program('a + b'));

  for (const [index, testCase] of SUM_TEST_CASES.entries()) {
    if (index > 0) await form.getByRole('button', { name: '+ Add' }).click();
    const card = form.locator('.test-case-card').nth(index);
    // In a program question the textareas are Expected Output, then stdin.
    await card.locator('textarea').first().fill(expectedOutputs[index]);
    await card.getByPlaceholder('Input passed to scanf').fill(testCase.test_input);
  }
}

test('teacher creates a question, then extracts, verifies and grades a new upload', async ({
  page,
  backend,
}) => {
  // An earlier, already graded submission, to check the list filters.
  backend.addSubmission({
    id: '44444444-4444-4444-8444-444444444444',
    student_name: 'Ben Tan',
    topic: 'Week 1',
    status: 'graded',
    captured_at: '2026-09-01T08:00:00Z',
    verified_text: program('a + b'),
    passed_test_cases: 2,
    total_test_cases: 2,
    score_percent: 100,
  });
  await openApp(page, backend);

  await test.step('author a question and validate it against Judge0', async () => {
    const form = await openQuestionForm(page);
    await fillSumQuestion(form, ['4', '5']);
    const save = form.getByRole('button', { name: 'Save Question' });
    // Saving is locked until Judge0 confirms every expected output.
    await expect(save).toBeDisabled();

    await form.getByRole('button', { name: 'Validate Test Cases' }).click();
    await expect(form.getByText('Passed all tests')).toBeVisible();
    await save.click();
    await expect(form.getByText('Question saved: Skill Test 1A · Q1 · Sum of two numbers')).toBeVisible();

    const [insert] = backend.requestsTo('POST', '/rest/v1/questions');
    expect(insert.body).toEqual([
      {
        question_name: 'Sum of two numbers',
        question_text: 'Read two integers and print their sum.',
        question_type: 'program',
        model_answer: program('a + b'),
        test_cases: SUM_TEST_CASES,
        // Saving is only possible once validation passed.
        can_publish: true,
      },
    ]);
    // The new section was created and the question placed in it as Q1.
    expect(backend.sections.map((section) => section.name)).toEqual(['Skill Test 1A']);
    expect(backend.sectionItems).toEqual([
      {
        section_id: backend.sections[0].id,
        question_id: backend.questions[0].id,
        number: 1,
      },
    ]);

    await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: 'Submissions' }).click();
  });

  await test.step('a photo uploaded from the mobile app appears live', async () => {
    backend.pushInsert({
      id: NEW_SUBMISSION_ID,
      student_name: 'Maria Santos',
      topic: 'Week 2',
      status: 'pending',
      image_url: PLACEHOLDER_IMAGE,
      captured_at: '2026-09-26T09:30:00Z',
    });
    const card = submissionCard(page, NEW_CARD_TIME);
    await expect(card).toBeVisible();
    await expect(card).toContainText('Needs OCR');

    await page.getByLabel('Status').selectOption({ label: 'Needs OCR' });
    await expect(card).toBeVisible();
    await expect(submissionCard(page, OLD_CARD_TIME)).toBeHidden();
    await page.getByRole('button', { name: 'Clear filters' }).click();
  });

  const dialog = page.getByRole('dialog', { name: 'Maria Santos' });

  await test.step('assign the new question', async () => {
    await submissionCard(page, NEW_CARD_TIME).click();
    await dialog
      .getByRole('combobox')
      .selectOption({ label: 'Sum of two numbers' });
    await dialog.getByRole('button', { name: 'Save and review code' }).click();
    await expect(
      dialog.getByRole('heading', { name: 'Review extracted code' }),
    ).toBeVisible();
  });

  await test.step('extract the handwritten code with OCR and correct it', async () => {
    // OCR misreads the student's `+` as `-`.
    backend.ocr = () => program('a - b');
    await expect(dialog.getByText('Not extracted yet')).toBeVisible();
    const saveAndContinue = dialog.getByRole('button', {
      name: 'Continue to grading',
    });
    await expect(saveAndContinue).toBeDisabled();

    await dialog.getByRole('button', { name: 'Extract now' }).click();
    const editor = dialog.locator('app-code-editor');
    await expect(editor).toContainText('printf("%d", a - b);');
    const [ocrRequest] = backend.requestsTo('POST', '/extract-from-url');
    expect(ocrRequest.body).toEqual({
      image_url: PLACEHOLDER_IMAGE,
      submission_id: NEW_SUBMISSION_ID,
    });

    await replaceEditorCode(editor, program('a + b'));
    await saveAndContinue.click();
    await expect(dialog.getByRole('heading', { name: 'Run and grade' })).toBeVisible();
  });

  await test.step('run a sample, then grade every test case', async () => {
    await dialog.getByRole('button', { name: 'Run Sample' }).click();
    await expect(dialog.getByText('First Test Case Passed')).toBeVisible();

    await dialog.getByRole('button', { name: 'Submit Code' }).click();
    await expect(
      dialog.getByText('2/2 test cases passed — Score: 100%'),
    ).toBeVisible();
    await dialog.getByRole('button', { name: 'Finish review' }).click();
    await expect(dialog).toBeHidden();
  });

  await test.step('the graded submission is stored and findable', async () => {
    expect(backend.submissions.get(NEW_SUBMISSION_ID)).toMatchObject({
      status: 'graded',
      question_id: backend.questions[0].id,
      // The OCR's own output is kept apart from the teacher's correction.
      extracted_text: program('a - b'),
      verified_text: program('a + b'),
    });
    // The grade is stored on the paper's one program.
    expect(backend.programsOf(NEW_SUBMISSION_ID)).toEqual([
      expect.objectContaining({
        position: 1,
        question_id: backend.questions[0].id,
        verified_text: program('a + b'),
        passed_test_cases: 2,
        total_test_cases: 2,
        score_percent: 100,
      }),
    ]);

    await page.getByLabel('Status').selectOption({ label: 'Graded' });
    await page.getByPlaceholder('Search student, topic, or question').fill('maria');
    const card = submissionCard(page, NEW_CARD_TIME);
    await expect(card).toContainText('Graded');
    // Cards label the question with its section and number.
    await expect(card).toContainText('Skill Test 1A · Q1 · Sum of two numbers');
    await expect(submissionCard(page, OLD_CARD_TIME)).toBeHidden();
  });
});

test('a question whose expected output disagrees with the model answer cannot be saved', async ({
  page,
  backend,
}) => {
  await openApp(page, backend);
  const form = await openQuestionForm(page);

  // 2 + 3 is 5, not 6.
  await fillSumQuestion(form, ['4', '6']);
  await form.getByRole('button', { name: 'Validate Test Cases' }).click();

  await expect(form.getByText('Failed 1 test(s)')).toBeVisible();
  await expect(
    form.getByText(
      'The model answer output does not match the manually entered Expected Output.',
    ),
  ).toBeVisible();
  await expect(form.getByRole('button', { name: 'Save Question' })).toBeDisabled();
  expect(backend.requestsTo('POST', '/rest/v1/questions')).toHaveLength(0);
});

test('a failed OCR extraction tells the teacher and keeps grading locked', async ({
  page,
  backend,
}) => {
  backend.addQuestion({
    id: '11111111-1111-4111-8111-111111111111',
    question_name: 'Sum of two numbers',
    question_type: 'program',
    test_cases: SUM_TEST_CASES,
  });
  backend.addSubmission({
    id: NEW_SUBMISSION_ID,
    student_name: 'Maria Santos',
    status: 'pending',
    question_id: '11111111-1111-4111-8111-111111111111',
    captured_at: '2026-09-26T09:30:00Z',
  });
  backend.ocr = () => null;
  await openApp(page, backend);

  await submissionCard(page, NEW_CARD_TIME).click();
  const dialog = page.getByRole('dialog', { name: 'Maria Santos' });
  await dialog.getByRole('button', { name: 'Save and review code' }).click();
  await dialog.getByRole('button', { name: 'Extract now' }).click();

  await expect(
    dialog.getByText('Failed to extract text. Please try again later.'),
  ).toBeVisible();
  // The teacher can retry, but cannot move on to grading without code.
  await expect(dialog.getByRole('button', { name: 'Extract now' })).toBeEnabled();
  await expect(
    dialog.getByRole('button', { name: 'Continue to grading' }),
  ).toBeDisabled();
  expect(backend.requestsTo('PATCH', '/rest/v1/submissions')).toHaveLength(0);
});
