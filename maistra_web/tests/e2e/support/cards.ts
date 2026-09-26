import type { Locator, Page } from '@playwright/test';

// Submission cards show the capture time and the question, not the student's
// name (that is the review dialog's title), so tests find a card by its
// capture time as the list renders it in UTC, e.g. 'Sep 26 · 09:30'.
export function submissionCard(page: Page, capturedAt: string): Locator {
  return page.locator('.submission-card').filter({ hasText: capturedAt });
}
