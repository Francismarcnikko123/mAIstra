export function normalizeOutput(value: string | null | undefined): string {
  if (value == null) return '';
  return value
    .trim()
    .toLowerCase()
    .replace(/\s*:\s*/g, ':')
    .replace(/\s+/g, ' ');
}
