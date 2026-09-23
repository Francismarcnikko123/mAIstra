/**
 * One extra program the teacher separated out of a student's paper.
 * Program 1 lives in submissions.verified_text / question_id; these are
 * Programs 2..n, stored in submissions.answers under the same submission id.
 */
export interface SubmissionAnswer {
  code: string;
  question_id: string | null;
}

/**
 * Reads the `answers` column defensively. Anything that isn't a list of
 * objects becomes an empty list, so a malformed row can't break the review.
 */
export function parseAnswers(raw: unknown): SubmissionAnswer[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(
      (item): item is Record<string, unknown> =>
        !!item && typeof item === 'object',
    )
    .map((item) => ({
      code: typeof item['code'] === 'string' ? item['code'] : '',
      question_id:
        typeof item['question_id'] === 'string' && item['question_id']
          ? item['question_id']
          : null,
    }));
}

/** A tab with no code and no question: an accidental "+" click. */
export function isBlankAnswer(answer: SubmissionAnswer): boolean {
  return answer.code.trim() === '' && answer.question_id === null;
}

/**
 * What is written back. Blank tabs are dropped. Code is saved verbatim:
 * this is a grading app, so the teacher's text is never trimmed.
 */
export function answersToSave(answers: SubmissionAnswer[]): SubmissionAnswer[] {
  return answers
    .filter((answer) => !isBlankAnswer(answer))
    .map((answer) => ({ code: answer.code, question_id: answer.question_id }));
}

/**
 * question_id -> program number (1 = Program 1 from Details, 2.. = tabs)
 * for every linked question except the tab at `exceptIndex`. The picker uses
 * it to grey out questions another program already holds.
 */
export function takenQuestionIds(
  primaryQuestionId: string | null,
  answers: SubmissionAnswer[],
  exceptIndex: number,
): Map<string, number> {
  const taken = new Map<string, number>();
  if (primaryQuestionId) taken.set(primaryQuestionId, 1);
  answers.forEach((answer, index) => {
    if (index === exceptIndex || !answer.question_id) return;
    if (!taken.has(answer.question_id)) taken.set(answer.question_id, index + 2);
  });
  return taken;
}

/**
 * Save rules, checked before any database write. Returns teacher-facing
 * messages in tab order; an empty list means the tabs can be saved.
 */
export function answerProblems(
  primaryQuestionId: string | null,
  answers: SubmissionAnswer[],
): string[] {
  const problems: string[] = [];
  const seen = new Map<string, number>();
  if (primaryQuestionId) seen.set(primaryQuestionId, 1);

  answers.forEach((answer, index) => {
    if (isBlankAnswer(answer)) return;
    const program = index + 2;

    if (!answer.question_id) {
      problems.push(`Choose a question for Program ${program}.`);
      return;
    }
    if (answer.code.trim() === '') {
      problems.push(
        `Program ${program} is linked to a question but has no code. Paste its program or clear the question.`,
      );
    }
    const earlier = seen.get(answer.question_id);
    if (earlier !== undefined) {
      problems.push(
        `Program ${program} uses the same question as Program ${earlier}. Each question can only be linked to one program.`,
      );
    } else {
      seen.set(answer.question_id, program);
    }
  });

  return problems;
}

/** One program on a paper, linked to the question it answers. */
export interface GradableProgram {
  /** 1 = Program 1 (verified_text); 2.. = answers[program - 2]. */
  program: number;
  code: string;
  question_id: string;
}

/**
 * Hand-off for grading: every program on a paper, each with the question
 * whose model answer and test cases it should be graded against. Program 1
 * comes from verified_text + question_id, Programs 2..n from the saved
 * `answers` column (passed raw, straight from the submission row). Entries
 * without code or without a question are left out: they can't be graded.
 */
export function programsForGrading(
  verifiedText: string | null | undefined,
  questionId: string | null | undefined,
  answers: unknown,
): GradableProgram[] {
  const programs: GradableProgram[] = [];
  if (verifiedText?.trim() && questionId) {
    programs.push({ program: 1, code: verifiedText, question_id: questionId });
  }
  parseAnswers(answers).forEach((answer, index) => {
    if (answer.code.trim() && answer.question_id) {
      programs.push({ program: index + 2, code: answer.code, question_id: answer.question_id });
    }
  });
  return programs;
}
