/**
 * Makes two outputs comparable when they differ only in ways that don't
 * matter for grading: it trims the ends, lowercases, removes spaces around
 * ':' and turns every run of spaces or newlines into one space.
 *
 *   "Sum : 15\n"  ->  "sum:15"
 *   "SUM:15"      ->  "sum:15"   (so these two count as the same output)
 *
 * Grading and model-answer validation both compare normalized output.
 */
export function normalizeOutput(value: string | null | undefined): string {
  if (value == null) return '';
  return value
    .trim()
    .toLowerCase()
    .replace(/\s*:\s*/g, ':')
    .replace(/\s+/g, ' ');
}
