export type OcrReviewSource =
  'anomaly' | 'suggestion' | 'confidence-low' | 'confidence-medium';

export type OcrReviewStrength = 'strong' | 'soft';

export interface OcrLineIssue {
  line: number;
  text: string;
  reason: string;
}

export interface OcrReviewSuggestion {
  line: number;
  original: string;
  candidate: string;
}

export interface OcrReviewFlag {
  line: number;
  strength: OcrReviewStrength;
  primarySource: OcrReviewSource;
  reasons: string[];
}

export interface BuildOcrReviewFlagsInput {
  text: string;
  confidence: (number | null)[];
  suggestions: OcrReviewSuggestion[];
  dismissedExtractionLines: ReadonlySet<number>;
  extractionMappingValid: boolean;
}

const LOW_CONFIDENCE = 0.7;
const MEDIUM_CONFIDENCE = 0.85;

const PRIORITY: Record<OcrReviewSource, number> = {
  anomaly: 4,
  suggestion: 3,
  'confidence-low': 2,
  'confidence-medium': 1,
};

/**
 * Find unusual extracted-line shapes without claiming that the C syntax is
 * invalid. These checks are intentionally narrow and never edit the text.
 */
export function detectOcrLineIssues(text: string): OcrLineIssue[] {
  const issues: OcrLineIssue[] = [];

  text.split('\n').forEach((raw, index) => {
    const value = raw.trim();
    if (!value) return;

    if (/^[0-9A-Za-z]{1,2}$/.test(value)) {
      issues.push({
        line: index + 1,
        text: value,
        reason:
          'lone token — compare it with a brace or punctuation on the paper',
      });
    } else if (/\bcase\b[^:{\n]*\{/.test(value)) {
      issues.push({
        line: index + 1,
        text: value,
        reason: '“case … {” — compare it with “case … :” on the paper',
      });
    }
  });

  return issues;
}

/**
 * Merge all line-specific OCR review evidence. One marker is returned per
 * line; stronger deterministic evidence wins visually while all distinct
 * teacher-facing reasons are retained.
 */
export function buildOcrReviewFlags(
  input: BuildOcrReviewFlagsInput,
): OcrReviewFlag[] {
  if (!input.text) return [];

  const lineCount = input.text.split('\n').length;
  const byLine = new Map<number, OcrReviewFlag>();

  const add = (
    line: number,
    source: OcrReviewSource,
    strength: OcrReviewStrength,
    reason: string,
  ) => {
    if (!Number.isInteger(line) || line < 1 || line > lineCount) return;

    const current = byLine.get(line);
    if (!current) {
      byLine.set(line, {
        line,
        strength,
        primarySource: source,
        reasons: [reason],
      });
      return;
    }

    if (!current.reasons.includes(reason)) current.reasons.push(reason);
    if (PRIORITY[source] > PRIORITY[current.primarySource]) {
      current.primarySource = source;
      current.strength = strength;
    }
  };

  for (const issue of detectOcrLineIssues(input.text)) {
    add(issue.line, 'anomaly', 'strong', `“${issue.text}” — ${issue.reason}`);
  }

  if (input.extractionMappingValid) {
    for (const suggestion of input.suggestions) {
      if (input.dismissedExtractionLines.has(suggestion.line)) continue;
      add(
        suggestion.line,
        'suggestion',
        'soft',
        `“${suggestion.original}” may be “${suggestion.candidate}” — compare with the paper`,
      );
    }

    input.confidence.forEach((value, index) => {
      const line = index + 1;
      if (
        value == null ||
        !Number.isFinite(value) ||
        input.dismissedExtractionLines.has(line)
      ) {
        return;
      }

      if (value < LOW_CONFIDENCE) {
        add(
          line,
          'confidence-low',
          'soft',
          'low OCR confidence — compare with the paper',
        );
      } else if (value < MEDIUM_CONFIDENCE) {
        add(
          line,
          'confidence-medium',
          'soft',
          'medium OCR confidence — compare with the paper',
        );
      }
    });
  }

  return [...byLine.values()].sort((left, right) => left.line - right.line);
}
