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

    const isShortFragment =
      value.length <= 3 && // very short
      /[A-Za-z0-9]/.test(value) && // has some content (not a lone bracket)
      !/[;{}:]$/.test(value) && // not a finished statement or label
      !/^[{}()[\];]+$/.test(value); // not pure punctuation (handled by balance)

    if (isShortFragment) {
      issues.push({
        line: index + 1,
        text: value,
        reason:
          'short fragment — compare it with a brace, number, or punctuation on the paper',
      });
    } else if (/\bcase\b[^:{\n]*\{/.test(value)) {
      issues.push({
        line: index + 1,
        text: value,
        reason: '“case … {” — compare it with “case … :” on the paper',
      });
    }
  });

  issues.push(...detectBracketMismatches(text));
  return issues;
}

const OPENERS: Record<string, string> = { ')': '(', ']': '[', '}': '{' };
const PAIR_NAME: Record<string, string> = {
  '(': 'parenthesis )',
  '[': 'bracket ]',
  '{': 'brace }',
};

/**
 * Stack-based bracket scan across the whole text (literals/comments skipped).
 * Flags the exact line where a closer has no opener, or closes the wrong kind
 * of opener — e.g. `&num5]` where a `)` was expected. This pinpoints the line
 * the whole-document balance banner can only summarize. A missing closer at
 * the very end is intentionally NOT pinned to a line (its true location is
 * ambiguous); the balance banner covers that case.
 */
function detectBracketMismatches(text: string): OcrLineIssue[] {
  const issues: OcrLineIssue[] = [];
  const stack: { ch: string; line: number }[] = [];
  const seen = new Set<number>();
  let line = 1;
  let inString: string | null = null;
  let inBlock = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (ch === '\n') {
      line++;
      continue;
    }
    if (inBlock) {
      if (ch === '*' && next === '/') {
        inBlock = false;
        i++;
      }
      continue;
    }
    if (inString) {
      if (ch === '\\') i++;
      else if (ch === inString) inString = null;
      continue;
    }
    if (ch === '/' && next === '/') {
      while (i < text.length && text[i] !== '\n') i++;
      i--;
      continue;
    }
    if (ch === '/' && next === '*') {
      inBlock = true;
      i++;
      continue;
    }
    if (ch === '"' || ch === "'") {
      inString = ch;
      continue;
    }
    if (ch === '(' || ch === '[' || ch === '{') {
      stack.push({ ch, line });
    } else if (ch === ')' || ch === ']' || ch === '}') {
      const top = stack[stack.length - 1];
      const mismatched = !top || top.ch !== OPENERS[ch];
      if (mismatched && !seen.has(line)) {
        seen.add(line);
        issues.push({
          line,
          text: ch,
          reason: top
            ? `“${ch}” closes a ${PAIR_NAME[top.ch]} that was opened — the pair may be misread`
            : `“${ch}” has no matching opener — a bracket may be missing or misread`,
        });
      }
      // On a mismatch, still pop the innermost opener (assume it was the
      // intended target, just misread as the wrong bracket type) so one bad
      // character doesn't cascade into false flags for the rest of the file.
      if (top) stack.pop();
    }
  }

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
