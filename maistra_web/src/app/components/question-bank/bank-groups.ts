import { parseAnswers } from '../submissions-list/extra-answers';

export interface BankQuestion {
  id: string;
  question_name: string;
  question_text: string;
  question_type: string;
  model_answer: string;
  test_cases: unknown[] | null;
  /** Missing until the validated flag exists in the database. */
  can_publish?: boolean | null;
}

export interface BankSection {
  id: string;
  name: string;
  position: number;
}

export interface BankSectionItem {
  section_id: string;
  question_id: string;
  number: number;
}

/** The part of a submission row the bank needs to count linked papers. */
export interface PaperLink {
  id?: string;
  image_url?: string;
  captured_at?: string;
  status?: string | null;
  question_id: string | null;
  answers?: unknown;
}

export interface LinkedPaper {
  paper: PaperLink;
  /** 1 when the question is the paper's Program 1, otherwise 2, 3, ... */
  program: number;
}

export interface BankRow {
  question: BankQuestion;
  /** Null for a question with no section yet. */
  number: number | null;
  testCount: number;
  paperCount: number;
  validated: boolean;
}

export interface BankGroup {
  /** Null for the "No section yet" group. */
  sectionId: string | null;
  name: string;
  rows: BankRow[];
}

export const NO_SECTION_NAME = 'No section yet';

/** "1 question", "2 questions". */
export function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`;
}

export function typeLabel(questionType: string): string {
  return questionType === 'function' ? 'Function' : 'Program';
}

/**
 * Papers linked to each question. A paper counts once per question, whether
 * the question is its Program 1 (`question_id`) or one of Programs 2..n
 * (`answers`).
 */
export function countPapers(links: PaperLink[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const link of links) {
    const ids = new Set<string>();
    if (link.question_id) ids.add(link.question_id);
    for (const answer of parseAnswers(link.answers)) {
      if (answer.question_id) ids.add(answer.question_id);
    }
    for (const id of ids) counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  return counts;
}

/**
 * Papers that answer [questionId], newest first as given. A paper where the
 * question is Program 1 lists as Program 1 even if a later tab repeats it.
 */
export function linkedPapers(questionId: string, links: PaperLink[]): LinkedPaper[] {
  const result: LinkedPaper[] = [];
  for (const paper of links) {
    if (paper.question_id === questionId) {
      result.push({ paper, program: 1 });
      continue;
    }
    const index = parseAnswers(paper.answers).findIndex(
      (answer) => answer.question_id === questionId,
    );
    if (index >= 0) result.push({ paper, program: index + 2 });
  }
  return result;
}

/** Sum of the test cases' marks. */
export function totalMarks(question: BankQuestion): number {
  if (!Array.isArray(question.test_cases)) return 0;
  return question.test_cases.reduce<number>((sum, tc) => {
    const mark = Number((tc as { mark?: unknown })?.mark);
    return sum + (Number.isFinite(mark) ? mark : 0);
  }, 0);
}

function matches(question: BankQuestion, search: string): boolean {
  if (!search) return true;
  const haystack = `${question.question_name} ${question.question_text}`.toLowerCase();
  return haystack.includes(search);
}

/**
 * Sections in order (position, then name), questions sorted by number, and
 * unsectioned questions last under "No section yet". Empty sections are
 * shown only when not searching.
 */
export function buildBankGroups(
  questions: BankQuestion[],
  sections: BankSection[],
  items: BankSectionItem[],
  links: PaperLink[],
  search = '',
): BankGroup[] {
  const term = search.trim().toLowerCase();
  const papers = countPapers(links);
  const itemByQuestion = new Map(items.map((i) => [i.question_id, i]));

  const toRow = (question: BankQuestion): BankRow => ({
    question,
    number: itemByQuestion.get(question.id)?.number ?? null,
    testCount: Array.isArray(question.test_cases) ? question.test_cases.length : 0,
    paperCount: papers.get(question.id) ?? 0,
    validated: question.can_publish === true,
  });

  const sectionIds = new Set(sections.map((s) => s.id));
  const bySection = new Map<string, BankRow[]>();
  const unsectioned: BankRow[] = [];

  for (const question of questions) {
    if (!matches(question, term)) continue;
    const item = itemByQuestion.get(question.id);
    if (item && sectionIds.has(item.section_id)) {
      const rows = bySection.get(item.section_id) ?? [];
      rows.push(toRow(question));
      bySection.set(item.section_id, rows);
    } else {
      unsectioned.push(toRow(question));
    }
  }

  const ordered = [...sections].sort(
    (a, b) => a.position - b.position || a.name.localeCompare(b.name),
  );
  const groups: BankGroup[] = ordered
    .map((section) => ({
      sectionId: section.id,
      name: section.name,
      rows: (bySection.get(section.id) ?? []).sort(
        (a, b) => (a.number ?? 0) - (b.number ?? 0),
      ),
    }))
    .filter((group) => !term || group.rows.length > 0);

  if (unsectioned.length > 0) {
    unsectioned.sort((a, b) =>
      a.question.question_name.localeCompare(b.question.question_name),
    );
    groups.push({ sectionId: null, name: NO_SECTION_NAME, rows: unsectioned });
  }
  return groups;
}
