import { readFileSync } from 'fs';
import { describe, expect, it } from 'vitest';

describe('SubmissionsListComponent OCR review template', () => {
  const template = readFileSync(
    'src/app/components/submissions-list/submissions-list.html',
    'utf8',
  );

  it('removes empty finding panels from the DOM instead of visually hiding them', () => {
    expect(template).toContain(
      '*ngIf="structureWarnings(selectedSubmission.id).length"',
    );
    expect(template).toContain(
      '*ngIf="explainedLineFlags(selectedSubmission.id).length"',
    );
    expect(template).not.toContain('[hidden]="!');
  });

  it('labels markers as OCR review aids rather than syntax errors', () => {
    expect(template).toContain('<strong>OCR review</strong>');
    expect(template).toContain(
      'These are OCR review aids, not C syntax diagnostics.',
    );
    expect(template).not.toContain('Likely wrong');
    expect(template).not.toContain('>Confident<');
  });

  it('connects normalized flags and edit invalidation to the editor', () => {
    expect(template).toContain(
      '[lineReviewFlags]="lineReviewFlags[selectedSubmission.id] || []"',
    );
    expect(template).toContain(
      '(reviewEvidenceEdited)="invalidateReviewEvidence(selectedSubmission.id, $event)"',
    );
  });
});
