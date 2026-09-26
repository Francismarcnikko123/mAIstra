import { test as base, expect, type Locator, type Page } from '@playwright/test';
import { submissionCard } from './support/cards';
import { FakeBackend, type QuestionRow } from './support/fake-backend';
import {
  SUM_TEST_CASES,
  evaluateSumProgram,
  program,
} from './support/sum-program';

// Nikko's question linking on the web: questions grouped by section and
// number, the question page, editing saved questions, and a phone upload
// filed into its question's section folder.

const test = base.extend<{ backend: FakeBackend }>({
  backend: async ({ page }, use) => {
    const backend = new FakeBackend();
    backend.judge0 = evaluateSumProgram;
    await backend.install(page);
    await use(backend);
    expect(backend.unexpected, 'requests the fake backend did not expect').toEqual([]);
  },
});

const SUM_ID = '11111111-1111-4111-8111-111111111111';
const HELLO_ID = '22222222-2222-4222-8222-222222222222';
const OLD_ID = '33333333-3333-4333-8333-333333333333';
const PHONE_PAPER_ID = '44444444-4444-4444-8444-444444444444';
const PHONE_CARD_TIME = 'Sep 26 · 11:24';

/** Basic (Q1 Hello, Q2 Sum), an empty Loops section, one unsectioned question. */
function seedBank(backend: FakeBackend) {
  const sumQuestion = (overrides: Partial<QuestionRow> = {}) => ({
    question_type: 'program' as const,
    question_text: 'Read two integers and print their sum.',
    model_answer: program('a + b'),
    test_cases: SUM_TEST_CASES,
    ...overrides,
  });
  backend.addQuestion({ id: SUM_ID, question_name: 'Sum of Two Integers', can_publish: true, ...sumQuestion() });
  backend.addQuestion({ id: HELLO_ID, question_name: 'Hello, name', can_publish: true, ...sumQuestion() });
  backend.addQuestion({ id: OLD_ID, question_name: 'adds two integer', can_publish: false, ...sumQuestion() });
  const basic = backend.addSection('Basic', 0);
  backend.addSection('Loops', 1);
  backend.addSectionItem(basic.id, HELLO_ID, 1);
  backend.addSectionItem(basic.id, SUM_ID, 2);
  // A paper uploaded from the phone for Basic · Q2.
  backend.addSubmission({
    id: PHONE_PAPER_ID,
    captured_at: '2026-09-26T11:24:00Z',
    question_id: SUM_ID,
    gate_result: 'PASS',
  });
  return { basic };
}

async function openBank(page: Page) {
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: 'Question bank' }).click();
  await expect(page.getByRole('heading', { name: 'Question bank' })).toBeVisible();
}

function group(page: Page, name: string): Locator {
  return page.locator('.bank-group').filter({ has: page.locator('.group-name', { hasText: name }) });
}

function row(page: Page, name: string): Locator {
  return page.locator('.bank-row').filter({ hasText: name });
}

async function openQuestionPage(page: Page, name: string) {
  await row(page, name).click();
  await expect(page.locator('app-question-page')).toBeVisible();
}

async function openEdit(page: Page, name: string): Promise<Locator> {
  await openQuestionPage(page, name);
  return clickEdit(page);
}

/** Edit on the question page that is already open. */
async function clickEdit(page: Page): Promise<Locator> {
  await page.locator('app-question-page').getByRole('button', { name: 'Edit' }).click();
  const form = page.locator('app-question-form');
  await expect(form.getByRole('heading', { name: 'Edit question' })).toBeVisible();
  return form;
}

test('the bank groups questions by section and number, with unsectioned ones last', async ({ page, backend }) => {
  seedBank(backend);
  await openBank(page);

  const names = page.locator('.bank-group .group-name');
  await expect(names).toHaveText(['Basic', 'Loops', 'No section yet']);

  const basic = group(page, 'Basic');
  await expect(basic.locator('.row-number')).toHaveText(['Q1', 'Q2']);
  await expect(basic.locator('.row-name')).toHaveText(['Hello, name', 'Sum of Two Integers']);
  await expect(group(page, 'Loops')).toContainText('No questions in this section yet.');

  await expect(row(page, 'Sum of Two Integers')).toContainText('✓ Validated');
  await expect(row(page, 'Sum of Two Integers')).toContainText('1 paper');
  await expect(row(page, 'adds two integer')).toContainText('! Not validated');
  await expect(row(page, 'adds two integer').locator('.row-number')).toHaveText('—');

  // Search looks across every section.
  await page.getByLabel('Search questions by name or text').fill('hello');
  await expect(page.locator('.bank-row')).toHaveCount(1);
  await expect(page.locator('.bank-row')).toContainText('Hello, name');
});

test('the question page shows the label, test cases and papers linked from the phone', async ({ page, backend }) => {
  seedBank(backend);
  await openBank(page);
  await openQuestionPage(page, 'Sum of Two Integers');

  const questionPage = page.locator('app-question-page');
  await expect(questionPage.getByRole('heading', { name: 'Basic · Q2 · Sum of Two Integers' })).toBeVisible();
  await expect(questionPage).toContainText('Program · 2 test cases · used by 1 paper');
  await expect(questionPage.locator('.tc-table tbody tr')).toHaveCount(2);
  await expect(questionPage.locator('.papers-header .count-pill')).toHaveText('1');
  await expect(questionPage.locator('.paper-card')).toContainText('✓ Photo good');
  // Validated, so no warning; and only one action: Edit.
  await expect(questionPage.locator('.warning-strip')).toHaveCount(0);
  await expect(questionPage.locator('.page-actions button')).toHaveText(['Edit']);
});

test('a phone upload lands in its question section folder', async ({ page, backend }) => {
  seedBank(backend);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Submissions' })).toBeVisible();

  const basicFolder = page.locator('.folder').filter({ has: page.locator('.folder-name', { hasText: 'Basic' }) });
  const card = submissionCard(page, PHONE_CARD_TIME);
  await expect(basicFolder).toContainText(PHONE_CARD_TIME);
  await expect(card).toContainText('Basic · Q2 · Sum of Two Integers');
  await expect(card.locator('.gate-badge')).toContainText('Photo good');
});

test('editing an unsectioned question: section and number, then validation, before saving', async ({ page, backend }) => {
  const { basic } = seedBank(backend);
  await openBank(page);
  await openQuestionPage(page, 'adds two integer');
  await expect(page.locator('app-question-page .warning-strip')).toContainText('Use Edit to validate it');

  const form = await clickEdit(page);
  const save = form.getByRole('button', { name: 'Save changes' });
  await expect(form.getByLabel('Question Name')).toHaveValue('adds two integer');
  await expect(save).toBeDisabled();
  await expect(form.locator('.save-hint')).toHaveText('Choose a section.');

  await form.getByLabel('Section *', { exact: true }).selectOption({ label: 'Basic' });
  await expect(form.locator('.field-hint')).toContainText('Already used: 1, 2');
  await form.getByLabel('Question No.').fill('2');
  await expect(form.locator('.field-error')).toContainText('Q2 is already used in Basic.');
  await form.getByLabel('Question No.').fill('3');
  // Never validated: Save waits for Validate Test Cases.
  await expect(form.locator('.save-hint')).toContainText('Validate the test cases first');
  await form.getByRole('button', { name: 'Validate Test Cases' }).click();
  await expect(save).toBeEnabled();
  await save.click();

  await expect(page.getByRole('heading', { name: 'Question bank' })).toBeVisible();
  await expect(group(page, 'Basic').locator('.row-name')).toHaveText([
    'Hello, name',
    'Sum of Two Integers',
    'adds two integer',
  ]);
  expect(backend.sectionItems).toContainEqual({ section_id: basic.id, question_id: OLD_ID, number: 3 });
  expect(backend.questions.find((q) => q.id === OLD_ID)?.can_publish).toBe(true);
});

test('editing a validated question: renaming saves at once, changing a test case locks Save', async ({ page, backend }) => {
  seedBank(backend);
  await openBank(page);
  const form = await openEdit(page, 'Hello, name');
  const save = form.getByRole('button', { name: 'Save changes' });

  // Already validated and nothing that runs has changed.
  await expect(save).toBeEnabled();
  await form.locator('.test-case-card').first().locator('textarea').first().fill('999');
  await expect(save).toBeDisabled();
  await expect(form.locator('.save-hint')).toContainText('Validate the test cases first');

  // Cancel leaves the question as it was.
  await form.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('heading', { name: 'Question bank' })).toBeVisible();
  expect(backend.requestsTo('PATCH', '/rest/v1/questions')).toHaveLength(0);

  const again = await openEdit(page, 'Hello, name');
  await again.getByLabel('Question Name').fill('Hello, your name');
  await again.getByRole('button', { name: 'Save changes' }).click();
  await expect(row(page, 'Hello, your name')).toBeVisible();
  // Content, then can_publish on its own (Jayrald's reset trigger).
  expect(backend.requestsTo('PATCH', '/rest/v1/questions')).toHaveLength(2);
  await expect(row(page, 'Hello, your name')).toContainText('✓ Validated');
  expect(backend.requestsTo('PATCH', '/rest/v1/question_section_items')).toHaveLength(0);
});

test('changing test cases on a question with graded papers warns before saving', async ({ page, backend }) => {
  seedBank(backend);
  backend.addSubmission({
    id: '55555555-5555-4555-8555-555555555555',
    captured_at: '2026-09-25T08:00:00Z',
    question_id: SUM_ID,
    status: 'graded',
    verified_text: program('a + b'),
  });
  await openBank(page);
  const form = await openEdit(page, 'Sum of Two Integers');

  // A new test case the model answer passes: 3 + 4 = 7.
  await form.getByRole('button', { name: '+ Add' }).click();
  const added = form.locator('.test-case-card').last();
  await added.locator('textarea').first().fill('7');
  await added.getByPlaceholder('Input passed to scanf').fill('3 4');
  await form.getByRole('button', { name: 'Validate Test Cases' }).click();
  await form.getByRole('button', { name: 'Save changes' }).click();

  await expect(form.locator('.grade-warning')).toContainText('1 graded paper uses this question');
  expect(backend.requestsTo('PATCH', '/rest/v1/questions')).toHaveLength(0);

  await form.getByRole('button', { name: 'Save and clear grades' }).click();
  await expect(page.getByRole('heading', { name: 'Question bank' })).toBeVisible();
  expect(backend.questions.find((q) => q.id === SUM_ID)?.test_cases).toHaveLength(3);
  // Test cases changed, and the question is still validated afterwards.
  expect(backend.questions.find((q) => q.id === SUM_ID)?.can_publish).toBe(true);
});
