/**
 * Section, number and label for questions, shared by the question bank, the
 * question page and the submissions folders.
 */

export interface SectionRow {
  id: string;
  name: string;
  position: number;
}

export interface SectionItemRow {
  section_id: string;
  question_id: string;
  number: number;
}

export interface QuestionPlace {
  sectionId: string;
  sectionName: string;
  sectionPosition: number;
  number: number;
}

/** Where each question sits: question id -> section and number. */
export function indexQuestionPlaces(
  sections: SectionRow[],
  items: SectionItemRow[],
): Map<string, QuestionPlace> {
  const byId = new Map(sections.map((s) => [s.id, s]));
  const places = new Map<string, QuestionPlace>();
  for (const item of items) {
    const section = byId.get(item.section_id);
    if (!section) continue;
    places.set(item.question_id, {
      sectionId: section.id,
      sectionName: section.name,
      sectionPosition: section.position,
      number: item.number,
    });
  }
  return places;
}

/** "Basic · Q2 · Sum of two numbers", or just the name when unsectioned. */
export function questionLabel(name: string, place?: QuestionPlace | null): string {
  return place ? `${place.sectionName} · Q${place.number} · ${name}` : name;
}

export interface GateBadge {
  label: string;
  icon: string;
  tone: 'pass' | 'fixable' | 'retake';
}

/** Photo-quality verdict from the phone, shown as icon + text. */
export function gateBadge(value: string | null | undefined): GateBadge | null {
  switch (value) {
    case 'PASS':
      return { label: 'Photo good', icon: '✓', tone: 'pass' };
    case 'FIXABLE':
      return { label: 'Photo auto-corrected', icon: '✎', tone: 'fixable' };
    case 'RETAKE':
      return { label: 'Photo needs retake', icon: '!', tone: 'retake' };
    default:
      return null;
  }
}

export interface SubmissionFolder {
  key: string;
  name: string;
  /** Sections first (by position), then legacy typed topics, then Uncategorized. */
  rank: [number, number, string];
}

export const UNCATEGORIZED = 'Uncategorized';

/**
 * A paper's folder: its Program 1 question's section. Older papers with no
 * sectioned question keep the topic typed for them, else Uncategorized.
 */
export function submissionFolder(
  questionId: string | null | undefined,
  topic: string | null | undefined,
  places: Map<string, QuestionPlace>,
): SubmissionFolder {
  const place = questionId ? places.get(questionId) : undefined;
  if (place) {
    return {
      key: `section:${place.sectionId}`,
      name: place.sectionName,
      rank: [0, place.sectionPosition, place.sectionName],
    };
  }
  const typed = topic?.trim();
  if (typed && typed !== UNCATEGORIZED) {
    return { key: `topic:${typed}`, name: typed, rank: [1, 0, typed] };
  }
  return { key: 'uncategorized', name: UNCATEGORIZED, rank: [2, 0, ''] };
}

export function compareFolders(a: SubmissionFolder, b: SubmissionFolder): number {
  return (
    a.rank[0] - b.rank[0] ||
    a.rank[1] - b.rank[1] ||
    a.rank[2].localeCompare(b.rank[2])
  );
}
