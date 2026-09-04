import { describe, expect, it } from 'vitest';
import {
  buildOcrReviewFlags,
  detectOcrLineIssues,
  type OcrReviewSuggestion,
} from './ocr-review-flags';

describe('OCR review flags', () => {
  it('detects unusual current-text lines', () => {
    expect(detectOcrLineIssues('switch (n) {\ncase 1 {\n3\n}')).toEqual([
      {
        line: 2,
        text: 'case 1 {',
        reason: '“case … {” — compare it with “case … :” on the paper',
      },
      {
        line: 3,
        text: '3',
        reason:
          'lone token — compare it with a brace or punctuation on the paper',
      },
    ]);
  });

  it('uses the documented confidence thresholds', () => {
    const flags = buildOcrReviewFlags({
      text: 'a();\nb();\nc();',
      confidence: [0.69, 0.7, 0.85],
      suggestions: [],
      dismissedExtractionLines: new Set(),
      extractionMappingValid: true,
    });

    expect(
      flags.map(({ line, primarySource }) => ({ line, primarySource })),
    ).toEqual([
      { line: 1, primarySource: 'confidence-low' },
      { line: 2, primarySource: 'confidence-medium' },
    ]);
  });

  it('ignores invalid and out-of-range suggestion lines', () => {
    const suggestions: OcrReviewSuggestion[] = [
      { line: 0, original: 'x', candidate: 'y' },
      { line: 3, original: 'x', candidate: 'y' },
      { line: 1, original: 'printe', candidate: 'printf' },
    ];
    const flags = buildOcrReviewFlags({
      text: 'printe("Hi");\nreturn 0;',
      confidence: [],
      suggestions,
      dismissedExtractionLines: new Set(),
      extractionMappingValid: true,
    });

    expect(flags).toHaveLength(1);
    expect(flags[0].line).toBe(1);
    expect(flags[0].reasons).toContain(
      '“printe” may be “printf” — compare with the paper',
    );
  });

  it('renders one strong flag when an anomaly overlaps weaker evidence', () => {
    const flags = buildOcrReviewFlags({
      text: '3',
      confidence: [0.2],
      suggestions: [{ line: 1, original: '3', candidate: '}' }],
      dismissedExtractionLines: new Set(),
      extractionMappingValid: true,
    });

    expect(flags).toHaveLength(1);
    expect(flags[0]).toMatchObject({
      line: 1,
      strength: 'strong',
      primarySource: 'anomaly',
    });
    expect(flags[0].reasons).toHaveLength(3);
  });

  it('dismisses edited extraction evidence but keeps current-text anomalies', () => {
    const flags = buildOcrReviewFlags({
      text: '3\nvalid();',
      confidence: [0.2, 0.2],
      suggestions: [{ line: 2, original: 'valid', candidate: 'value' }],
      dismissedExtractionLines: new Set([1, 2]),
      extractionMappingValid: true,
    });

    expect(flags).toEqual([
      expect.objectContaining({ line: 1, primarySource: 'anomaly' }),
    ]);
  });

  it('drops extraction-era evidence after the line mapping changes', () => {
    expect(
      buildOcrReviewFlags({
        text: 'valid();',
        confidence: [0.2],
        suggestions: [{ line: 1, original: 'valid', candidate: 'value' }],
        dismissedExtractionLines: new Set(),
        extractionMappingValid: false,
      }),
    ).toEqual([]);
  });

  it('returns no flags for empty text or unusable confidence values', () => {
    expect(
      buildOcrReviewFlags({
        text: '',
        confidence: [0.1, Number.NaN, Number.POSITIVE_INFINITY],
        suggestions: [],
        dismissedExtractionLines: new Set(),
        extractionMappingValid: true,
      }),
    ).toEqual([]);
  });
});
