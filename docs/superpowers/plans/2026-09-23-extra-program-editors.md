# Program Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Implemented 2026-09-24 on `feature/program-tabs`** (Tasks 1–8, then two additions).
> **Later integration:** the pushed `feature/pre-extraction` branch now includes
> this work via merge `d9df182`; it also adds the optional OCR worker and live
> list badge. The verification counts below are the earlier program-tabs
> checkpoint (the later recorded counts are OCR 231/231 and web 114/114).
> - **Stylesheet deviation:** tab styles live in `submissions-list/program-tabs.css` via `styleUrls`, because appending them to `submissions-list.css` broke the 12 kB component-style budget.
> - **Missing-column fallback:** the app keeps working before the `answers` migration. It loads without the column, Program 1 saves, and extra tabs are preview-only.
> - **Grading hand-off:** `programsForGrading()` is the hand-off for Jayrald.
> - **Verification:** 89/89 tests (50 existing + 39 new); app and spec type checks and `ng build` clean; tabs, picker, "In Program 1" greying, preview note and click-elsewhere cancel all checked in the running app against the cloud database. Saving extra tabs end to end waits on the migration.
> - **Before merging anything:** read "Merge and integration notes" at the end. It has branch-by-branch conflict results and open questions for Jayrald.
> - **Next for Jayrald and Nikko:** see "For the team" at the end.

> **Revised 2026-09-24** to match the agreed mock (since removed; the built feature is now the reference). The changes from the first draft:
> - Browser-style tabs replace stacked editors.
> - A custom question picker replaces the native `<select>`, with no free-text name field.
> - Each question can be linked to only one tab.
> - Save rules are stricter.

**Goal:** In Step 2 (Review Code), let the teacher split one student's paper into several program tabs. They press **+**, move each program's code into its own tab, and link each tab to a question from the bank. Every program is saved separately under the same submission ID.

**Architecture:**
- **Program 1 is the existing editor, unchanged:** `verified_text`, with its question from Details (`question_id`).
- **Programs 2..n** are `{ code, question_id }` entries in a new `answers jsonb` column on the same `submissions` row. They are written by the existing guarded `saveVerifiedText()` in one database update.
- **Pure helpers** (`extra-answers.ts`) own parsing, the one-question-per-tab rule and the save rules, so those rules are unit-tested without Angular.
- **OCR is untouched.** `extracted_text` is never modified, and Re-extract only replaces Program 1.

**Tech Stack:** Angular 21 (standalone components, template-driven forms), Ace via the existing `CodeEditorComponent`, Supabase (Postgres + supabase-js), Vitest via `@angular/build:unit-test`.

---

## Agreed design (from the mock)

| Element | Behavior |
|---|---|
| Tab bar | Browser-style tabs above the editor: `Program 1 · <question>`, `Program 2 · <question>`, …, then **+** |
| **+** | Adds an empty tab and switches to it |
| Program 1 | Can't be removed; its question comes from Details and is shown as "set in Details" |
| Tabs 2..n | Two-click remove: × becomes "Remove?", and clicking anywhere else cancels. A tab with no question shows **!** |
| Question picker | A custom menu, since a native `<select>` can't be styled in Safari. Each row shows the question name, a prompt preview and its test-case count. The chosen row shows ✓, and "Clear question" appears when one is chosen |
| One question per tab | Questions linked to another tab are greyed with "In Program N" and can't be picked. Program 1's question counts. A question is freed by clearing it or removing that tab |
| Editor | Fixed height. Each tab keeps its own Ace instance (hidden when inactive) so cursor and undo stay per program |
| Format | Formats the active tab only |
| Hint | "Move each program into its own tab. Each question can be linked to one tab." |

**Save rules** (checked before any database call):

| Tab state | Result |
|---|---|
| Code + question | Saved |
| Code, no question | Blocked: "Choose a question for Program N." |
| Question, no code | Blocked: "Program N is linked to a question but has no code. Paste its program or clear the question." |
| Same question as another program (e.g. changed in Details afterwards) | Blocked: "Program N uses the same question as Program M. Each question can only be linked to one program." |
| No code, no question | Dropped silently (an accidental **+**) |

## Scope

**In scope:** everything in the two tables above, plus saving and reloading.

**Out of scope, with owners:**
- Grading Programs 2..n. Step 3 still grades Program 1 only (Jayrald, follow-up).
- Automatic splitting by OCR. Its consistency is unmeasured; this is future work that needs evaluation.
- Question numbering, quiz grouping and a question-bank list screen. These are question-bank changes for Nikko. The picker only **reads** the existing `questions` rows.

## Project rules this plan keeps (`AGENTS.md`)

- The review stays inside `SubmissionsListComponent`. The tabs and picker are template markup in that component, and the editors reuse `CodeEditorComponent`. The user explicitly requested these extra editors.
- Original OCR output stays separate: nothing writes `extracted_text`, and Re-extract replaces Program 1 only.
- Save-generation, timer and destroy protections are kept. Programs 2..n are saved inside the existing guarded save.
- Judge0 results stay keyed by submission ID. Grading is untouched.
- A selected question and verified code are still required before grading. `canOpenGradingStep()` is unchanged.
- No service-role key in browser code.

## File structure

| File | Action | Responsibility |
|---|---|---|
| `supabase/migrations/20260923000000_add_submission_answers.sql` | Create | `answers jsonb` column |
| `maistra_web/src/app/components/submissions-list/extra-answers.ts` | Create | Type, parsing, taken-question map, save rules (pure) |
| `maistra_web/src/app/components/submissions-list/extra-answers.spec.ts` | Create | Helper tests |
| `maistra_web/src/app/services/supabase.ts` | Modify | Select and write `answers` |
| `maistra_web/src/app/services/supabase.spec.ts` | Modify | Service tests |
| `maistra_web/src/app/components/code-editor/code-editor.ts` | Modify | `refresh()` to re-measure a previously hidden editor |
| `maistra_web/src/app/components/code-editor/code-editor.spec.ts` | Modify | `refresh()` test |
| `maistra_web/src/app/components/submissions-list/submissions-list.ts` | Modify | Tab state, picker, guard, load, save |
| `maistra_web/src/app/components/submissions-list/submissions-list.program-tabs.spec.ts` | Create | Component tests |
| `maistra_web/src/app/components/submissions-list/submissions-list.html` | Modify | Tabs, picker, editors |
| `maistra_web/src/app/components/submissions-list/submissions-list.css` | Modify | Tab and picker styles |
| `docs/PROJECT_OVERVIEW_AND_CHANGES.md` | Modify | Team record (tracked, own `docs:` commit) |
| `docs/web/WEB_CODEBASE_GUIDE.md` | Modify | Local guide (gitignored, never committed) |

---

### Task 0: Team gate (no code)

- [ ] **Step 1:** Share this plan and the mock with Jayrald. Agree on:
  - the `answers jsonb` column and its entry shape `{ code: string, question_id: uuid | null }`
  - who applies the migration to the **cloud** project
  - Programs 2..n are saved but not graded in this version
- [ ] **Step 2:** Optionally pass Nikko the question-bank notes: no question number, no quiz grouping, and no screen that lists existing questions. These are not blockers for this plan.
- [ ] **Step 3:** Branch off the team's web base branch (confirm which with Jayrald):

```bash
git switch <base-branch>
git pull
git switch -c feature/program-tabs
```

- [ ] **Step 4:** Record the test baseline before changing anything:

```bash
cd maistra_web
npx ng test --watch=false
```

Note the exact pass/fail counts; the overview records one known unrelated red `submissions-list` OCR-error test. If native Rollup/esbuild packages fail because `node_modules` came from another OS, report it and only run `npm ci` with the user's permission.

---

### Task 1: Database column

**Files:** Create `supabase/migrations/20260923000000_add_submission_answers.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Programs 2..n that a teacher separates out of one handwritten paper.
-- Program 1 stays in verified_text / question_id. Each entry is
-- {"code": text, "question_id": uuid-or-null}, in tab order.
-- The original OCR output stays in extracted_text and is never written here.
ALTER TABLE public.submissions
  ADD COLUMN IF NOT EXISTS answers jsonb NOT NULL DEFAULT '[]'::jsonb;
```

- [ ] **Step 2: Apply locally and check**

```bash
cd <repo root>
supabase migration up
supabase db dump --local --schema public | grep -n "answers"
```

Expected: a line containing `"answers" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL`. See `docs/setup/SUPABASE_LOCAL_SETUP.md` if the local stack isn't running.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260923000000_add_submission_answers.sql
git commit -m "feat(db): add submissions.answers for program tabs"
```

> **Deploy order:** after Task 3, `getSubmissions()` selects `answers`. If the cloud database lacks the column, the submissions list fails to load. **Apply the cloud migration before deploying the web change.**

---

### Task 2: Pure helpers

**Files:**
- Create: `maistra_web/src/app/components/submissions-list/extra-answers.ts`
- Test: `maistra_web/src/app/components/submissions-list/extra-answers.spec.ts`

- [ ] **Step 1: Write the failing tests**

```ts
import { describe, expect, it } from 'vitest';
import {
  answerProblems,
  answersToSave,
  parseAnswers,
  takenQuestionIds,
} from './extra-answers';

describe('parseAnswers', () => {
  it('returns an empty list for anything that is not an array', () => {
    expect(parseAnswers(null)).toEqual([]);
    expect(parseAnswers(undefined)).toEqual([]);
    expect(parseAnswers('[]')).toEqual([]);
    expect(parseAnswers({ code: 'x' })).toEqual([]);
  });

  it('keeps order and code exactly as stored, including whitespace', () => {
    const raw = [
      { code: 'int main() {\n  return 0;\n}\n', question_id: 'q-2' },
      { code: '  void f(void) {}', question_id: null },
    ];
    expect(parseAnswers(raw)).toEqual(raw);
  });

  it('coerces malformed entries instead of throwing', () => {
    expect(parseAnswers([{ code: 5 }, null, 'text', { question_id: '' }])).toEqual([
      { code: '', question_id: null },
      { code: '', question_id: null },
    ]);
  });
});

describe('answersToSave', () => {
  it('drops tabs with neither code nor a question', () => {
    expect(
      answersToSave([
        { code: '', question_id: null },
        { code: ' \n', question_id: null },
      ]),
    ).toEqual([]);
  });

  it('keeps other tabs with code exactly as typed', () => {
    const code = '\n  int main() {}  \n';
    expect(answersToSave([{ code, question_id: 'q-2' }])).toEqual([
      { code, question_id: 'q-2' },
    ]);
  });
});

describe('takenQuestionIds', () => {
  it('maps each linked question to its program number, skipping one tab', () => {
    const taken = takenQuestionIds(
      'q-1',
      [
        { code: 'a', question_id: 'q-2' },
        { code: 'b', question_id: null },
        { code: 'c', question_id: 'q-3' },
      ],
      2,
    );
    expect([...taken.entries()]).toEqual([
      ['q-1', 1],
      ['q-2', 2],
    ]);
  });

  it('ignores a missing Program 1 question', () => {
    const taken = takenQuestionIds(null, [{ code: 'a', question_id: 'q-2' }], -1);
    expect([...taken.entries()]).toEqual([['q-2', 2]]);
  });
});

describe('answerProblems', () => {
  it('accepts linked programs and ignores fully blank tabs', () => {
    expect(
      answerProblems('q-1', [
        { code: 'int f(void);', question_id: 'q-2' },
        { code: '', question_id: null },
      ]),
    ).toEqual([]);
  });

  it('asks for a question when a tab has code but no question', () => {
    expect(answerProblems('q-1', [{ code: 'int x;', question_id: null }])).toEqual([
      'Choose a question for Program 2.',
    ]);
  });

  it('asks for code when a tab has a question but no code', () => {
    expect(answerProblems('q-1', [{ code: '  ', question_id: 'q-2' }])).toEqual([
      'Program 2 is linked to a question but has no code. Paste its program or clear the question.',
    ]);
  });

  it('rejects a tab that reuses Program 1 question', () => {
    expect(answerProblems('q-1', [{ code: 'x', question_id: 'q-1' }])).toEqual([
      'Program 2 uses the same question as Program 1. Each question can only be linked to one program.',
    ]);
  });

  it('rejects two extra tabs with the same question', () => {
    expect(
      answerProblems(null, [
        { code: 'x', question_id: 'q-2' },
        { code: 'y', question_id: 'q-2' },
      ]),
    ).toEqual([
      'Program 3 uses the same question as Program 2. Each question can only be linked to one program.',
    ]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd maistra_web
npx ng test --watch=false --include='src/app/components/submissions-list/extra-answers.spec.ts'
```

Expected: FAIL, because `./extra-answers` cannot be resolved.

- [ ] **Step 3: Implement**

```ts
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
```

- [ ] **Step 4: Run to verify it passes**

Same command as Step 2. Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add maistra_web/src/app/components/submissions-list/extra-answers.ts maistra_web/src/app/components/submissions-list/extra-answers.spec.ts
git commit -m "feat(web): add program-tab parse, guard and save-rule helpers"
```

---

### Task 3: Supabase service reads and writes `answers`

**Files:**
- Modify: `maistra_web/src/app/services/supabase.ts`
- Test: `maistra_web/src/app/services/supabase.spec.ts`

- [ ] **Step 1: Write the failing tests** (inside the existing `describe('SupabaseService', …)`)

```ts
  it('writes extra programs when they are provided', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };

    const answers = [{ code: 'int main() {}', question_id: 'q-2' }];
    await service.updateSubmissionText('submission-1', 'verified text', undefined, answers);

    expect(update).toHaveBeenCalledWith(expect.objectContaining({
      verified_text: 'verified text',
      answers,
    }));
    expect(update).toHaveBeenCalledWith(expect.not.objectContaining({
      extracted_text: expect.anything(),
    }));
  });

  it('leaves answers untouched when none are provided', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const service = Object.create(SupabaseService.prototype) as SupabaseService;
    (service as unknown as { supabase: { from: typeof from } }).supabase = { from };

    await service.updateSubmissionText('submission-1', 'verified text');

    expect(update).toHaveBeenCalledWith(expect.not.objectContaining({
      answers: expect.anything(),
    }));
  });
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd maistra_web
npx ng test --watch=false --include='src/app/services/supabase.spec.ts'
```

Expected: FAIL. Either `answers` is missing from the payload, or TypeScript rejects the 4th argument.

- [ ] **Step 3: Implement** in `supabase.ts`

Add the import:

```ts
import { SubmissionAnswer } from '../components/submissions-list/extra-answers';
```

In `getSubmissions()`, add `answers,` after `verified_text,`:

```ts
      extracted_text,
      verified_text,
      answers,
      question_id,
```

Replace `updateSubmissionText` with:

```ts
  async updateSubmissionText(
    submissionId: string,
    verifiedText: string,
    extractedText?: string,
    answers?: SubmissionAnswer[],
  ): Promise<void> {
    // extracted_text must keep the OCR's own output (it is the baseline the
    // verified text is compared against), so it is only written when a fresh
    // extraction produced it — never overwritten with the teacher's edits.
    const update: Record<string, unknown> = {
      verified_text: verifiedText,
      status: 'verified',
      verified_at: new Date().toISOString(),
    };
    if (extractedText !== undefined) {
      update['extracted_text'] = extractedText;
    }
    // Programs 2..n from the review tabs, saved in the same update so they
    // share Program 1's save guards.
    if (answers !== undefined) {
      update['answers'] = answers;
    }
    const { error } = await this.supabase
      .from('submissions')
      .update(update)
      .eq('id', submissionId);
    if (error) throw error;
  }
```

- [ ] **Step 4: Run to verify it passes.** Same command; all `SupabaseService` tests pass.

- [ ] **Step 5: Commit**

```bash
git add maistra_web/src/app/services/supabase.ts maistra_web/src/app/services/supabase.spec.ts
git commit -m "feat(web): read and write submissions.answers"
```

---

### Task 4: `CodeEditorComponent.refresh()`

Inactive tabs keep their Ace editor mounted but hidden, so each program keeps its own cursor and undo history. Ace measures size when shown, so a tab needs a re-measure after it becomes visible.

**Files:**
- Modify: `maistra_web/src/app/components/code-editor/code-editor.ts`
- Test: `maistra_web/src/app/components/code-editor/code-editor.spec.ts`

- [ ] **Step 1: Write the failing test** (append at the end of the file; add `vi` to the vitest import)

```ts
describe('CodeEditorComponent.refresh', () => {
  it('asks Ace to re-measure after the editor was hidden', () => {
    const component = Object.create(CodeEditorComponent.prototype) as CodeEditorComponent;
    const resize = vi.fn();
    (component as unknown as { editor: { resize: typeof resize } }).editor = { resize };

    component.refresh();

    expect(resize).toHaveBeenCalledWith(true);
  });

  it('does nothing before the editor exists', () => {
    const component = Object.create(CodeEditorComponent.prototype) as CodeEditorComponent;
    expect(() => component.refresh()).not.toThrow();
  });
});
```

Change the import line to: `import { describe, expect, it, vi } from 'vitest';`

- [ ] **Step 2: Run to verify it fails**

```bash
cd maistra_web
npx ng test --watch=false --include='src/app/components/code-editor/code-editor.spec.ts'
```

Expected: FAIL, because `refresh` is not a function.

- [ ] **Step 3: Implement.** Add this method after `format()`:

```ts
  /**
   * Re-measure the editor after its container was hidden (an inactive
   * program tab). Ace sizes itself on show, so without this a tab switched
   * to can render blank until the window resizes.
   */
  refresh(): void {
    this.editor?.resize(true);
  }
```

- [ ] **Step 4: Run to verify it passes.** Same command; the existing reindent tests plus these 2 pass.

- [ ] **Step 5: Commit**

```bash
git add maistra_web/src/app/components/code-editor/code-editor.ts maistra_web/src/app/components/code-editor/code-editor.spec.ts
git commit -m "feat(web): let a hidden code editor re-measure itself"
```

---

### Task 5: Component tab state, picker guard, loading

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Test: `maistra_web/src/app/components/submissions-list/submissions-list.program-tabs.spec.ts`

- [ ] **Step 1: Write the failing tests**

```ts
import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SupabaseService } from '../../services/supabase';
import { SubmissionsListComponent } from './submissions-list';

export function createComponent(options?: {
  getSubmissions?: ReturnType<typeof vi.fn>;
  updateSubmissionText?: ReturnType<typeof vi.fn>;
  post?: ReturnType<typeof vi.fn>;
}) {
  const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
  const updateSubmissionText =
    options?.updateSubmissionText ?? vi.fn().mockResolvedValue(undefined);
  const supabase = {
    getSubmissions:
      options?.getSubmissions ?? vi.fn().mockResolvedValue({ data: [], error: null }),
    updateSubmissionText,
  } as unknown as SupabaseService;
  const post =
    options?.post ?? vi.fn().mockReturnValue(of({ cleaned_text: 'fresh ocr' }));
  const component = new SubmissionsListComponent(
    supabase,
    { post } as unknown as HttpClient,
    cdr,
    {} as Judge0Service,
  );
  return { component, updateSubmissionText, post };
}

export function select(component: SubmissionsListComponent, id = 'paper-1') {
  component.selectedSubmission = {
    id,
    image_url: 'https://example.test/paper.png',
    captured_at: '2026-09-24T00:00:00.000Z',
  };
  component.selectedQuestionId = 'q-1';
  component.editableText[id] = 'int main() { return 0; }';
}

describe('SubmissionsListComponent program tabs', () => {
  it('adds an empty tab and switches to it', () => {
    const { component } = createComponent();
    select(component);

    component.addExtraAnswer();

    expect(component.getExtraAnswers('paper-1')).toEqual([{ code: '', question_id: null }]);
    expect(component.activeTab).toBe(1);
  });

  it('switches between tabs and closes an open picker', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.questionPickerOpen = true;

    component.selectTab(0);

    expect(component.activeTab).toBe(0);
    expect(component.questionPickerOpen).toBe(false);
  });

  it('links and clears a question on a tab', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();

    component.chooseExtraQuestion(0, 'q-2');
    expect(component.getExtraAnswers('paper-1')[0].question_id).toBe('q-2');

    component.chooseExtraQuestion(0, null);
    expect(component.getExtraAnswers('paper-1')[0].question_id).toBeNull();
  });

  it('refuses a question already linked to another program', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.addExtraAnswer();
    component.chooseExtraQuestion(0, 'q-2');

    component.chooseExtraQuestion(1, 'q-1');
    component.chooseExtraQuestion(1, 'q-2');

    expect(component.getExtraAnswers('paper-1')[1].question_id).toBeNull();
    expect(component.questionOwner('q-1', 1)).toBe(1);
    expect(component.questionOwner('q-2', 1)).toBe(2);
    expect(component.questionOwner('q-3', 1)).toBeNull();
  });

  it('updates tab code without touching Program 1', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();

    component.updateExtraAnswerCode(0, 'int isEven(int n);');

    expect(component.getExtraAnswers('paper-1')[0].code).toBe('int isEven(int n);');
    expect(component.editableText['paper-1']).toBe('int main() { return 0; }');
  });

  it('needs two clicks to remove a tab and frees its question', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.chooseExtraQuestion(0, 'q-2');
    component.addExtraAnswer();

    component.requestRemoveExtraAnswer(0);
    expect(component.getExtraAnswers('paper-1')).toHaveLength(2);
    expect(component.removeConfirmIndex).toBe(0);

    component.requestRemoveExtraAnswer(0);
    expect(component.getExtraAnswers('paper-1')).toEqual([{ code: '', question_id: null }]);
    expect(component.removeConfirmIndex).toBeNull();
    expect(component.questionOwner('q-2', 0)).toBeNull();
  });

  it('moves to the previous tab when the open tab is removed', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.addExtraAnswer();
    expect(component.activeTab).toBe(2);

    component.requestRemoveExtraAnswer(1);
    component.requestRemoveExtraAnswer(1);

    expect(component.activeTab).toBe(1);
  });

  it('loads saved programs for each submission', async () => {
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{
        id: 'paper-1', image_url: 'x', captured_at: 'y', verified_text: 'int main() {}',
        answers: [{ code: 'int f(void) { return 1; }', question_id: 'q-2' }],
      }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions });

    await component.loadSubmissions();

    expect(component.getExtraAnswers('paper-1')).toEqual([
      { code: 'int f(void) { return 1; }', question_id: 'q-2' },
    ]);
  });

  it('does not overwrite unsaved tabs when the list reloads', async () => {
    const getSubmissions = vi.fn().mockResolvedValue({
      data: [{ id: 'paper-1', image_url: 'x', captured_at: 'y', answers: [] }],
      error: null,
    });
    const { component } = createComponent({ getSubmissions });
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'pasted but not saved');

    await component.loadSubmissions();

    expect(component.getExtraAnswers('paper-1')[0].code).toBe('pasted but not saved');
  });

  it('opens a submission on Program 1', () => {
    const { component } = createComponent();
    select(component);
    component.addExtraAnswer();

    component.openModal({ id: 'paper-1', image_url: 'x', captured_at: 'y' });

    expect(component.activeTab).toBe(0);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd maistra_web
npx ng test --watch=false --include='src/app/components/submissions-list/submissions-list.program-tabs.spec.ts'
```

Expected: FAIL. TypeScript reports that `addExtraAnswer`, `activeTab` and the other new members do not exist.

- [ ] **Step 3: Implement** in `submissions-list.ts`

Change the Angular import to include `ViewChildren` and `QueryList`:

```ts
import {
  Component,
  OnInit,
  OnDestroy,
  ChangeDetectorRef,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core';
```

Add the helper import below the existing imports:

```ts
import {
  SubmissionAnswer,
  answerProblems,
  answersToSave,
  parseAnswers,
  takenQuestionIds,
} from './extra-answers';
```

In `SubmissionQuestion`, add after `question_name: string;`:

```ts
  question_text?: string;
```

In `Submission`, add after `verified_text?: string;`:

```ts
  answers?: unknown;
```

Below `@ViewChild('codeEditor') codeEditor?: CodeEditorComponent;` add:

```ts
  @ViewChildren('extraEditor') extraEditors?: QueryList<CodeEditorComponent>;
```

Add state after `reextractConfirmId`:

```ts
  // Program tabs. Program 1 is editableText; Programs 2..n are extraAnswers,
  // saved to submissions.answers under the same submission id.
  extraAnswers: Record<string, SubmissionAnswer[]> = {};
  // 0 = Program 1; n = extraAnswers[id][n - 1].
  activeTab = 0;
  // Index (into extraAnswers) of the tab whose × awaits a second click.
  removeConfirmIndex: number | null = null;
  questionPickerOpen = false;
  extraAnswersError: Record<string, string> = {};
```

In `loadSubmissions()`, inside the `for (const s of this.submissions)` loop after the `editableText` line:

```ts
      // Seed saved program tabs once. Never replace a loaded list: the teacher
      // may have pasted programs that aren't saved yet.
      if (!this.extraAnswers[s.id]) {
        this.extraAnswers[s.id] = parseAnswers(s.answers);
      }
```

In `openModal()`, after `this.reviewStep = 1;`:

```ts
    this.activeTab = 0;
    this.removeConfirmIndex = null;
    this.questionPickerOpen = false;
    this.extraAnswersError[submission.id] = '';
```

Replace the existing `formatCode()` with:

```ts
  /** Formats the open tab only. */
  formatCode() {
    this.getActiveEditor()?.format();
  }
```

Add these methods after `updateSubmissionCode()`:

```ts
  getExtraAnswers(id: string): SubmissionAnswer[] {
    return this.extraAnswers[id] ?? [];
  }

  getActiveExtraAnswer(): SubmissionAnswer | undefined {
    if (this.activeTab === 0) return undefined;
    return this.getSelectedExtraAnswer(this.activeTab - 1);
  }

  addExtraAnswer() {
    if (!this.selectedSubmission) return;
    const id = this.selectedSubmission.id;
    const answers = [...this.getExtraAnswers(id), { code: '', question_id: null }];
    this.extraAnswers[id] = answers;
    this.selectTab(answers.length);
  }

  selectTab(tab: number) {
    this.activeTab = tab;
    this.removeConfirmIndex = null;
    this.questionPickerOpen = false;
    // Show the tab first, then let Ace re-measure the now-visible editor.
    this.cdr.detectChanges();
    this.getActiveEditor()?.refresh();
  }

  updateExtraAnswerCode(index: number, code: string) {
    const answer = this.getSelectedExtraAnswer(index);
    // Mutate in place: replacing the object would re-render the Ace editor
    // on every keystroke and lose the teacher's cursor.
    if (answer) answer.code = code;
    this.clearExtraAnswersError();
  }

  /** Program number already holding this question (other than tab `index`), or null. */
  questionOwner(questionId: string, index: number): number | null {
    if (!this.selectedSubmission) return null;
    return (
      takenQuestionIds(
        this.selectedQuestionId || null,
        this.getExtraAnswers(this.selectedSubmission.id),
        index,
      ).get(questionId) ?? null
    );
  }

  /** Links (or with null, clears) a tab's question. Taken questions are refused. */
  chooseExtraQuestion(index: number, questionId: string | null) {
    const answer = this.getSelectedExtraAnswer(index);
    if (!answer) return;
    if (questionId !== null && this.questionOwner(questionId, index) !== null) return;
    answer.question_id = questionId;
    this.questionPickerOpen = false;
    this.clearExtraAnswersError();
  }

  /** First click arms the tab's ×; the second click on the same tab removes it. */
  requestRemoveExtraAnswer(index: number) {
    if (!this.selectedSubmission) return;
    if (this.removeConfirmIndex !== index) {
      this.removeConfirmIndex = index;
      return;
    }
    const id = this.selectedSubmission.id;
    this.extraAnswers[id] = this.getExtraAnswers(id).filter((_, i) => i !== index);
    const removedTab = index + 1;
    const nextTab =
      this.activeTab === removedTab
        ? removedTab - 1
        : this.activeTab > removedTab
          ? this.activeTab - 1
          : this.activeTab;
    this.clearExtraAnswersError();
    this.selectTab(nextTab);
  }

  getQuestionTitle(questionId: string): string {
    return (
      this.questions.find((question) => question.id === questionId)?.question_name ||
      'Unknown question'
    );
  }

  questionPreview(question: SubmissionQuestion): string {
    const text = (question.question_text ?? '').trim();
    return text.length > 70 ? `${text.slice(0, 70)}…` : text;
  }

  onPickerFocusOut(event: FocusEvent) {
    const next = event.relatedTarget as Node | null;
    const picker = event.currentTarget as HTMLElement;
    if (!next || !picker.contains(next)) this.questionPickerOpen = false;
  }

  trackByIndex(index: number): number {
    return index;
  }

  private getSelectedExtraAnswer(index: number): SubmissionAnswer | undefined {
    if (!this.selectedSubmission) return undefined;
    return this.getExtraAnswers(this.selectedSubmission.id)[index];
  }

  private getActiveEditor(): CodeEditorComponent | undefined {
    return this.activeTab === 0
      ? this.codeEditor
      : this.extraEditors?.get(this.activeTab - 1);
  }

  private clearExtraAnswersError() {
    if (this.selectedSubmission) this.extraAnswersError[this.selectedSubmission.id] = '';
  }
```

- [ ] **Step 4: Run to verify it passes.** Same command as Step 2. Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add maistra_web/src/app/components/submissions-list/submissions-list.ts maistra_web/src/app/components/submissions-list/submissions-list.program-tabs.spec.ts
git commit -m "feat(web): add program tab state and one-question-per-tab guard"
```

---

### Task 6: Save with rules; Re-extract leaves tabs alone

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts` (`saveVerifiedText`)
- Test: `maistra_web/src/app/components/submissions-list/submissions-list.program-tabs.spec.ts`

- [ ] **Step 1: Write the failing tests** (append inside the `describe` from Task 5)

```ts
  it('saves every program in the same update as Program 1', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int f(void) { return 1; }');
    component.chooseExtraQuestion(0, 'q-2');

    await component.saveVerifiedText();

    expect(updateSubmissionText).toHaveBeenCalledTimes(1);
    expect(updateSubmissionText).toHaveBeenCalledWith(
      'paper-1',
      'int main() { return 0; }',
      undefined,
      [{ code: 'int f(void) { return 1; }', question_id: 'q-2' }],
    );
    expect(component.saveStatus['paper-1']).toBe('saved');
  });

  it('blocks the save and explains why when a tab breaks a rule', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'int x;');

    await component.saveVerifiedText();

    expect(updateSubmissionText).not.toHaveBeenCalled();
    expect(component.extraAnswersError['paper-1']).toBe('Choose a question for Program 2.');
    expect(component.saveStatus['paper-1']).not.toBe('saved');
  });

  it('drops empty tabs when saving', async () => {
    const { component, updateSubmissionText } = createComponent();
    select(component);
    component.addExtraAnswer();

    await component.saveVerifiedText();

    expect(updateSubmissionText.mock.calls[0][3]).toEqual([]);
  });

  it('re-extract replaces Program 1 only', async () => {
    const { component } = createComponent();
    select(component);
    component.extractedText['paper-1'] = 'int main() { return 0; }';
    component.addExtraAnswer();
    component.updateExtraAnswerCode(0, 'pasted program two');

    await component.extractText();

    expect(component.editableText['paper-1']).toBe('fresh ocr');
    expect(component.getExtraAnswers('paper-1')[0].code).toBe('pasted program two');
  });
```

- [ ] **Step 2: Run to verify it fails**

Same command as Task 5 Step 2. Expected: the first three new tests FAIL. The re-extract test already PASSES; it locks existing behavior.

- [ ] **Step 3: Implement** in `saveVerifiedText()`

Directly after `const id = this.selectedSubmission.id;` insert:

```ts
    // Save rules for Programs 2..n are checked before any database write,
    // so a blocked save never touches the generation/timer guards below.
    const problems = answerProblems(
      this.selectedQuestionId || null,
      this.getExtraAnswers(id),
    );
    if (problems.length) {
      this.extraAnswersError[id] = problems[0];
      this.saveStatus[id] = '';
      this.cdr.detectChanges();
      return;
    }
    this.extraAnswersError[id] = '';
```

Replace:

```ts
      const ocrText = this.extractedText[id];
      await this.supabase.updateSubmissionText(id, text, ocrText);
```

with:

```ts
      const ocrText = this.extractedText[id];
      const extras = answersToSave(this.getExtraAnswers(id));
      await this.supabase.updateSubmissionText(id, text, ocrText, extras);
```

After the existing `if (s) { … }` block that updates the list copy, add:

```ts
      if (s) s.answers = extras;
```

`saveCodeAndContinue()` already advances only when `saveStatus` is `'saved'`, so a blocked save keeps the teacher on Step 2.

- [ ] **Step 4: Run to verify it passes.** Same command: 14 passed. Then prove the existing save protections still hold:

```bash
npx ng test --watch=false --include='src/app/components/submissions-list/**'
```

Expected: the Task 0 baseline plus the new tests. No existing test asserts `updateSubmissionText`'s argument list, so none should change.

- [ ] **Step 5: Commit**

```bash
git add maistra_web/src/app/components/submissions-list/submissions-list.ts maistra_web/src/app/components/submissions-list/submissions-list.program-tabs.spec.ts
git commit -m "feat(web): save program tabs with save rules"
```

---

### Task 7: Template and styles

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.html` (Step 2 `editor-panel`)
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.css`

- [ ] **Step 1: Update the panel header hint.** In `editor-panel-header`, replace the text `Edit OCR mistakes before continuing.` with:

```html
Move each program into its own tab. Each question can be linked to one tab.
```

The existing **Format code** button stays and now formats the open tab (Task 5 changed `formatCode()`).

- [ ] **Step 2: Replace the editor block.** Replace the current `<app-code-editor *ngIf="hasExtractedText(selectedSubmission.id)" #codeEditor …></app-code-editor>` element with:

```html
            <ng-container *ngIf="hasExtractedText(selectedSubmission.id)">
              <div class="program-tabs" role="tablist" aria-label="Programs on this paper">
                <button
                  type="button"
                  role="tab"
                  class="program-tab"
                  [class.active]="activeTab === 0"
                  [attr.aria-selected]="activeTab === 0"
                  (click)="selectTab(0)"
                >
                  <span class="program-tab-label">
                    <strong>Program 1</strong> · {{ getQuestionName(selectedSubmission) }}
                  </span>
                </button>

                <div
                  *ngFor="let answer of getExtraAnswers(selectedSubmission.id); let i = index; trackBy: trackByIndex"
                  role="tab"
                  tabindex="0"
                  class="program-tab"
                  [class.active]="activeTab === i + 1"
                  [attr.aria-selected]="activeTab === i + 1"
                  (click)="selectTab(i + 1)"
                  (keydown.enter)="selectTab(i + 1)"
                >
                  <span class="program-tab-label">
                    <strong>Program {{ i + 2 }}</strong>
                    <ng-container *ngIf="answer.question_id"> · {{ getQuestionTitle(answer.question_id) }}</ng-container>
                  </span>
                  <span class="program-tab-warn" *ngIf="!answer.question_id" aria-label="No question yet">!</span>
                  <button
                    type="button"
                    class="program-tab-close"
                    [class.armed]="removeConfirmIndex === i"
                    [attr.aria-label]="'Remove program ' + (i + 2)"
                    (click)="$event.stopPropagation(); requestRemoveExtraAnswer(i)"
                  >
                    {{ removeConfirmIndex === i ? 'Remove?' : '×' }}
                  </button>
                </div>

                <button
                  type="button"
                  class="program-tab-add"
                  aria-label="Add program"
                  title="Add another program from this paper"
                  (click)="addExtraAnswer()"
                >
                  +
                </button>
              </div>

              <div class="program-panel" role="tabpanel">
                <div class="program-question">
                  <span>Question</span>

                  <span class="question-locked" *ngIf="activeTab === 0">
                    {{ getQuestionName(selectedSubmission) }} · set in Details
                  </span>

                  <div
                    class="question-picker"
                    *ngIf="getActiveExtraAnswer() as answer"
                    (focusout)="onPickerFocusOut($event)"
                    (keydown.escape)="questionPickerOpen = false"
                  >
                    <button
                      type="button"
                      class="question-picker-button"
                      [class.empty]="!answer.question_id"
                      aria-haspopup="listbox"
                      [attr.aria-expanded]="questionPickerOpen"
                      (click)="questionPickerOpen = !questionPickerOpen"
                    >
                      <span class="question-picker-value">
                        {{ answer.question_id ? getQuestionTitle(answer.question_id) : 'Choose a question…' }}
                      </span>
                      <span aria-hidden="true">▾</span>
                    </button>

                    <div class="question-picker-menu" role="listbox" *ngIf="questionPickerOpen">
                      <p class="question-picker-label">Question bank</p>
                      <button
                        *ngFor="let question of questions"
                        type="button"
                        role="option"
                        class="question-option"
                        [class.selected]="answer.question_id === question.id"
                        [attr.aria-selected]="answer.question_id === question.id"
                        [disabled]="questionOwner(question.id, activeTab - 1) !== null"
                        (click)="chooseExtraQuestion(activeTab - 1, question.id)"
                      >
                        <span class="question-option-text">
                          <strong>{{ question.question_name }}</strong>
                          <small>{{ questionPreview(question) }} · {{ question.test_cases?.length || 0 }} test cases</small>
                        </span>
                        <span class="question-option-used" *ngIf="questionOwner(question.id, activeTab - 1) as owner">
                          In Program {{ owner }}
                        </span>
                        <span class="question-option-check" *ngIf="answer.question_id === question.id" aria-hidden="true">✓</span>
                      </button>
                      <p class="question-picker-empty" *ngIf="!questions.length">
                        No questions in the question bank yet.
                      </p>
                      <button
                        type="button"
                        class="question-option clear"
                        *ngIf="answer.question_id"
                        (click)="chooseExtraQuestion(activeTab - 1, null)"
                      >
                        Clear question
                      </button>
                    </div>
                  </div>
                </div>

                <app-code-editor
                  #codeEditor
                  class="text-editor"
                  [hidden]="activeTab !== 0"
                  [(value)]="editableText[selectedSubmission.id]"
                ></app-code-editor>

                <app-code-editor
                  *ngFor="let answer of getExtraAnswers(selectedSubmission.id); let i = index; trackBy: trackByIndex"
                  #extraEditor
                  class="text-editor"
                  [hidden]="activeTab !== i + 1"
                  [value]="answer.code"
                  (valueChange)="updateExtraAnswerCode(i, $event)"
                ></app-code-editor>
              </div>
            </ng-container>

            <p class="extract-error" *ngIf="extraAnswersError[selectedSubmission.id]">
              {{ extraAnswersError[selectedSubmission.id] }}
            </p>
```

Program 1 keeps `#codeEditor` and `[(value)]`, so re-extract, the save guard and every existing binding behave as before.

- [ ] **Step 3: Footer note.** In the Step 2 footer, before the **Save and continue to grading** button, add:

```html
      <div class="footer-guidance" *ngIf="reviewStep === 2 && hasExtractedText(selectedSubmission.id) && getExtraAnswers(selectedSubmission.id).length">
        Every program is saved with this paper. Only Program 1 is graded for now.
      </div>
```

- [ ] **Step 4: Styles.** Append to `submissions-list.css`:

```css
.text-editor[hidden] {
  display: none !important; /* :host { display: block } would otherwise win over [hidden] */
}

.program-tabs {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  padding: 6px 6px 0;
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-bottom: 0;
  border-radius: 12px 12px 0 0;
  background: #f1f5f9;
}

.program-tab {
  display: flex;
  flex: none;
  align-items: center;
  gap: 6px;
  max-width: 230px;
  height: 38px;
  padding: 0 8px 0 12px;
  border: 1px solid transparent;
  border-bottom: 0;
  border-radius: 9px 9px 0 0;
  color: #475569;
  background: transparent;
  font-size: 13px;
  cursor: pointer;
}

.program-tab:hover {
  background: #e2e8f0;
}

.program-tab.active {
  border-color: #e2e8f0;
  color: #172033;
  background: #fff;
  box-shadow: inset 0 3px 0 #4f46e5;
}

.program-tab-label {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.program-tab-warn {
  color: #b45309;
  font-weight: 800;
}

.program-tab-close {
  min-width: 20px;
  height: 20px;
  padding: 0 4px;
  border: 0;
  border-radius: 6px;
  color: #64748b;
  background: transparent;
}

.program-tab-close:hover {
  background: #cbd5e1;
}

.program-tab-close.armed {
  color: #fff;
  background: #b91c1c;
  font-size: 11px;
  font-weight: 700;
}

.program-tab-add {
  flex: none;
  width: 34px;
  height: 32px;
  margin: 0 4px 3px;
  border: 0;
  border-radius: 8px;
  color: #4f46e5;
  background: transparent;
  font-size: 20px;
}

.program-tab-add:hover {
  background: #e0e7ff;
}

.program-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-top: 0;
  border-radius: 0 0 12px 12px;
  background: #fff;
}

.program-question {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.question-locked {
  flex: 1;
  padding: 8px 10px;
  border-radius: 8px;
  color: #334155;
  background: #f8fafc;
  font-weight: 600;
}

.question-picker {
  position: relative;
  flex: 1;
  min-width: 0;
}

.question-picker-button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 38px;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  color: #172033;
  background: #fff;
  font-size: 13px;
  text-align: left;
}

.question-picker-button:focus-visible {
  border-color: #4f46e5;
  outline: 3px solid rgba(79, 70, 229, 0.12);
}

.question-picker-button.empty {
  border-color: #dc9090;
  color: #b91c1c;
  background: #fffafa;
  font-weight: 600;
}

.question-picker-value {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.question-picker-menu {
  position: absolute;
  z-index: 20;
  top: calc(100% + 6px);
  right: 0;
  left: 0;
  max-height: 320px;
  overflow-y: auto;
  padding: 6px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.16);
}

.question-picker-label {
  margin: 0;
  padding: 6px 10px 4px;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.question-option {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 7px;
  color: #172033;
  background: transparent;
  font-size: 13px;
  text-align: left;
}

.question-option:not(:disabled):hover {
  background: #f1f5f9;
}

.question-option.selected {
  background: #eef2ff;
}

.question-option:disabled {
  color: #94a3b8;
  cursor: not-allowed;
}

.question-option-text {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.question-option-text small {
  overflow: hidden;
  color: #64748b;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.question-option-used {
  flex: none;
  padding: 2px 8px;
  border-radius: 999px;
  color: #64748b;
  background: #f1f5f9;
  font-size: 11px;
  font-weight: 600;
}

.question-option-check {
  color: #4f46e5;
  font-weight: 800;
}

.question-option.clear {
  margin-top: 4px;
  border-top: 1px solid #e2e8f0;
  border-radius: 0 0 7px 7px;
  color: #64748b;
}

.question-picker-empty {
  margin: 0;
  padding: 8px 10px;
  color: #64748b;
  font-size: 12px;
}
```

- [ ] **Step 5: Compile**

```bash
cd maistra_web
npx tsc -p tsconfig.app.json --noEmit
npx ng build
```

Expected: both succeed. `ng build` is the template-compilation check `AGENTS.md` requires.

- [ ] **Step 6: Manual check in the running app** (`npm start`, per `docs/setup/RUNNING_LOCALLY.md`). Check:
  1. Tabs appear only after extraction. Program 1 shows its Details question and has no ×.
  2. **+** opens a new tab. Pasting works, and switching tabs keeps each tab's code, cursor and undo.
  3. The picker greys out the Program 1 question and any question linked on another tab ("In Program N"). Clearing or removing frees it.
  4. × needs two clicks, and clicking elsewhere cancels.
  5. Format changes only the open tab.
  6. The save rules each show their message and block the save. A fully empty tab is ignored.
  7. Saving, closing and reopening restores every tab and question.
  8. Re-extract replaces Program 1 only.
  9. At phone width, the tab row scrolls sideways and nothing overflows the page.

- [ ] **Step 7: Commit**

```bash
git add maistra_web/src/app/components/submissions-list/submissions-list.html maistra_web/src/app/components/submissions-list/submissions-list.css
git commit -m "feat(web): add program tabs and question picker to the review step"
```

---

### Task 8: Final verification and docs

- [ ] **Step 1: Full web verification**

```bash
cd maistra_web
npx tsc -p tsconfig.app.json --noEmit
npx ng build
npx ng test --watch=false
```

Expected: TypeScript and the build are clean. Tests show the Task 0 baseline plus 30 new passing tests:
- 12 helpers
- 2 service
- 2 code editor
- 14 component

- [ ] **Step 2: Team doc.** In `docs/PROJECT_OVERVIEW_AND_CHANGES.md`, add a section before "Code cleanup completed":

```markdown
## Program tabs in Review Code (2026-09-24)

> **Owner:** Nombrado (review editor); schema agreed with Jayrald

- One paper can hold several programs. Step 2 shows browser-style tabs above the editor: Program 1 is the existing editor, whose question comes from Details, and **+** adds Programs 2..n. The teacher moves each program's code into its own tab and links it to a question from the bank.
- Each question can be linked to only one program. The picker greys out questions another tab holds. Saving is blocked for a tab with code but no question, a question but no code, or a duplicate question. Fully empty tabs are ignored.
- Programs 2..n are saved as `{ code, question_id }` in the new `submissions.answers jsonb` column, under the same submission ID and in the same guarded save as Program 1. `extracted_text` is never modified, and Re-extract replaces Program 1 only. No OCR change.
- Programs 2..n are saved but not graded yet; grading them is Jayrald's follow-up.
- The split is manual by design: OCR program-boundary detection exists but its consistency is unmeasured.
- Migration `supabase/migrations/20260923000000_add_submission_answers.sql` must be applied to the cloud project before this web change is deployed.
```

Commit it on its own, staging only the tracked file (`docs/` is gitignored):

```bash
git add -u -- docs/PROJECT_OVERVIEW_AND_CHANGES.md
git commit -m "docs: record program tabs in review code"
```

- [ ] **Step 3: Local guide.** Update `docs/web/WEB_CODEBASE_GUIDE.md` with the helpers, tab state, picker guard and save path. **Do not stage or commit it.**

- [ ] **Step 4:** Push and open a PR **only after the user confirms**. Commit messages and the PR carry no AI attribution.

---

## For the team: what each part needs next

Program tabs are built on `feature/program-tabs` (Nombrado). A teacher can now split one paper into Program 1, 2, 3… and link each program to a question from the bank. The pieces below are **not** Nombrado's to build. They are written down here so each owner knows what their part needs and why.

### Jayrald: database and grading

**1. Add the `answers` column (needed before extra programs can be saved).**
Run `supabase/migrations/20260923000000_add_submission_answers.sql` on the cloud project:

```sql
ALTER TABLE public.submissions
  ADD COLUMN IF NOT EXISTS answers jsonb NOT NULL DEFAULT '[]'::jsonb;
```

It only adds a column with an empty default, so existing rows and other branches are unaffected. Until it runs, the web app still loads normally (it detects the missing column). Program 1 still saves, and extra tabs are shown as preview-only.

**2. Grade every program on a paper, not just Program 1.**
Step 3 currently grades `verified_text` against the one `question_id`. Use the hand-off helper instead:

```ts
import { programsForGrading } from './extra-answers';

const programs = programsForGrading(submission.verified_text, submission.question_id, submission.answers);
// → [{ program: 1, code, question_id }, { program: 2, code, question_id }, …]
```

For each entry, load that `question_id`'s `model_answer` and `test_cases` and run it the same way Program 1 is run today. Programs missing code or a question are already left out, and each question appears at most once per paper.

Decisions for you:
- How per-program results are stored and shown. Judge0 result maps are keyed by submission ID today, so they would need a per-program key such as `submissionId:program`.
- How program scores combine into the paper's grade.

**3. Existing schema gaps (already in the overview).** Migrations for `question_type`, `topic` and `question_id`, and RLS on `submissions`.

### Nikko: question bank identifiers and visibility

**The problem.** Programs are linked to questions from the bank, but today a question can only be told apart by its free-text **Question Name** (placeholder "e.g. Skill Test 1A"):
- **No question number.** Nothing records that a question is "Question 2" of a quiz, so the "2." a student writes on paper has no match in the app.
- **No quiz or assessment grouping.** Every question ever created sits in one flat list, so the picker shows all of them, not just the current quiz's.
- **Model answers and test cases are write-only.** The Create Question form saves them and then clears itself. No screen lists existing questions or shows which model answer and test cases belong to which question, and nothing lets a teacher check or fix them later. Two questions with similar names ("sum of two integers" twice) can't be distinguished, and linking a program to the wrong one means it's graded against the wrong model answer and test cases.

> **Check with Jayrald first.** His unmerged branch `code-similarity/duplicate` (2026-09-05) already adds an `assessments` table and an `assessment_questions` table with a `position` column. That is quiz grouping plus question numbering. If that branch is still the plan, Nikko should build on it rather than design a second version. See "Merge and integration notes" below.

**Suggested additions (your call on the design):**
1. **A quiz/assessment field** on each question (e.g. "Skill Test 1"), plus a **question number** within it (1, 2, 3…).
2. **A question bank list screen** that shows each question with its quiz, number, type, prompt, model answer and test cases, with **view and edit**.
3. **Distinct labels everywhere a question is chosen** ("ST1 · Q2 · Even or odd"), so the Details dropdown and the program-tab picker show the same identifier.

**Why it matters for program tabs.** The tab picker currently shows each question's name, a prompt preview and its test-case count, because that's all the bank stores. Once questions carry a quiz and number, the picker can show "Q2" and list only the current quiz's questions. That change is small on the review side, and Nombrado can do it once the fields exist.

**Until then, a free team convention:** name questions with quiz and number, e.g. `ST1 – Q2: Even or odd`.

### Nombrado: optional and future work
- Mark taken questions in the **Details** dropdown too ("In Program N"). For now, the save rule catches a duplicate chosen there.
- An OCR-suggested split ("This paper looks like 3 programs. Split into tabs?"). Only after measuring its accuracy on multi-program pages from new writers; the split stays manual until then.

**Proposed improvements (mocked 2026-09-24, NOT built yet; waiting on the user's go-ahead).** All are in Nombrado's area:
1. **"Move selection to new tab"** button next to Format code. The teacher highlights a program in the editor and clicks it: the selection is cut from the current tab into a new tab, and the picker opens for it. It replaces cut → **+** → paste → pick. With nothing highlighted, it shows "Highlight a program in the editor first." Button, not drag-and-drop: easier to find and harder to misdrop.
2. **Unsaved-changes dots and a close prompt.** An indigo dot marks each tab changed since the last save, and all dots clear on a successful **Save and continue to grading** (one save covers every tab). Today `closeModal()` ([submissions-list.ts:264](../../../maistra_web/src/app/components/submissions-list/submissions-list.ts)) closes at once, including from an overlay click. With unsaved tabs it would ask "Keep editing / Discard and close / Save and close". Unsaved tabs survive reopening but are lost on a page reload. `closeModal()` is shared review code, so keep the check limited to tabs and note it in TEAM_SYNC.
3. **"N programs" badge** on the submission's row in the list, counted from saved programs.
4. **Arrow keys** move between tabs (standard tablist behaviour); today only Enter works.
5. **Tooltips:** `!` = "No question linked yet" (question only, not code) and dot = "Unsaved changes". The `!` has an aria-label but no visible tooltip.

**Decided 2026-09-24 after mocks:**
- **Dropped for good:** "Move selection to new tab" and its Undo bar. The user wants only human-in-the-loop: nothing that highlights, moves or checks code for the teacher, because it risks grading.
- **Build set (not started, waiting on the go-ahead):**
  - **Clarity:** tooltips, guide text in an empty tab, arrow keys
  - **Question check:** read-only "View question" (prompt and test cases, no model answer); "Change" on Program 1 goes to Details
  - **Don't lose work:** unsaved dots, and a close prompt with Keep editing / Discard changes / Save and close. Program 1 counts as unsaved too.
  - **OCR text beside the photo** (layout B, see below)
- **OCR text beside the photo (layout B):**
  - Photo and a read-only "OCR text" panel sit side by side on top; the tab editor keeps full width underneath.
  - A "Show OCR text" link opens it any time, showing the saved `extracted_text`. "Hide" closes it.
  - **Re-extract on a paper with tabs** only refreshes this panel and never overwrites a tab. On a paper with no tabs, Re-extract works as today.
  - The teacher copies from the panel into tabs. The panel is never edited; `extracted_text` stays the machine's reading, `verified_text` / `answers` stay the teacher's.
  - **Purpose, in the user's words:** side by side lets anyone see that the OCR features work, e.g. continuation lines placed in reading order next to the photo where they were written in the margin. The panel shows the server's output as-is: no extra markers, and no API change.
  - **Demo caveat:** continuation abstains unless its safety checks pass, and both calibration photos can't show a visible success (brace miss). A demo needs a new photo where it fires.
- **Data note:** nothing records which lines of `extracted_text` became which program. Grading doesn't need it; per-program OCR accuracy would, so it's deliberately not added.

**Not adding:** automatic splitting. It would depend on braces and `main(`, and brace recall is the OCR's weakest point.

**After Jayrald/Nikko deliver assessments:** the picker lists only the paper's assessment questions, labelled Q1, Q2…, and each new tab pre-fills in order (Program 2 → Q2), which the teacher only changes for out-of-order answers. Blocked on how a submission links to its assessment (open question for Jayrald).

**Seen in passing (not ours):** the web app sets no global font (`maistra_web/src/styles.css` is empty), so the review screen renders in the browser's default serif. It's shared styling, so mention it to Jayrald rather than fixing it in the tab code.

**Separate proposal: auto-extract on arrival** (historical proposal; implemented later on `feature/pre-extraction`). An earlier design already exists: `docs/superpowers/specs/2026-09-11-pre-extraction-on-submission-design.md`, updated with a 2026-09-24 addendum. That spec is the reference; this is only a summary. A polling worker inside the OCR server (`ocr_feature/main.py`) finds submissions with empty `extracted_text` and `verified_text`. It runs the same pipeline as `/api/ocr/extract-from-url`, then writes `extracted_text` only if both are still empty. It never sets `status`: the web already derives "extracted" from `extracted_text`. After retries it logs and skips, and the paper stays "new" for a manual **Extract now**. The review screen shows **Extract now** with no text and **Re-extract** once there is text, and treats the saved `extracted_text` as the last extraction so the re-extract dialog stays correct. It also re-fetches the row on open. It needs a server-side Supabase key in a local `.env` only: tell Jayrald and get his OK. Log upload→extracted delay for the thesis. Nothing changes for Nikko or for model answers. Build it on its own branch off `feature/reading-order-reassembly`.

---

## Merge and integration notes (checked 2026-09-24)

Written so the merge can be planned with Jayrald. It's not yet known which of his branches is current, so every relevant remote branch was checked. All checks were **simulations** (`git merge-tree`): no branch was merged or changed.

### Current state of `feature/program-tabs`

- **Base:** `feature/reading-order-reassembly` @ `979c7f2`, Nombrado's working branch. Nothing from it or this branch is merged into the team branches yet.
- **Tip:** `a8e8d5b`. Pushed to `origin/feature/program-tabs` (tracking set) on 2026-09-24. Working tree clean.
- **Verification at the tip:** 89/89 web tests (50 existing + 39 new); `tsc -p tsconfig.app.json`, `tsc -p tsconfig.spec.json` and `ng build` all clean. The only build warning, `submissions-list.css` over its 9 kB warning budget at 11.72 kB, existed before this feature.
- **Checked in the running app** against the cloud database (without the `answers` column): 209 submissions load, tabs and picker render with the real question bank, the Program 1 question is greyed "In Program 1", the preview-only note shows, and clicking elsewhere cancels an armed "Remove?". Nothing was saved during testing.

Commits, oldest first:

| Commit | What |
|---|---|
| `83b11ca` | Migration: `submissions.answers jsonb` |
| `4567e85` | Pure helpers: parse, taken-question map, save rules |
| `3939422` | Supabase service reads and writes `answers` |
| `8c112c4` | `CodeEditorComponent.refresh()` for hidden tabs |
| `c60f5cd` | Tab state and one-question-per-tab guard |
| `e2e2c4f` | Save with rules; Re-extract replaces Program 1 only |
| `4d8a431` | Tabs and question picker in the template (`program-tabs.css`) |
| `e6cd79a` | Team doc |
| `aed2a37` | App keeps working before the migration (missing-column fallback) |
| `6681f4f` | Team doc |
| `2e23350` | `programsForGrading()` grading hand-off |
| `21c2cf8` | Team doc |
| `845a75d` | Fallback only when it's the `answers` column that's missing |
| `a49d737` | Clicking elsewhere cancels an armed tab remove |
| `a862e4b` | `docs/TEAM_SYNC.md` added (tracked team doc) |
| `c0c379a` | TEAM_SYNC ownership boundaries and per-person to-do lists |
| `a8e8d5b` | TEAM_SYNC: program tabs marked as pushed |

**Files this feature touches** (the likely merge surface):
- `maistra_web/src/app/components/submissions-list/`: `submissions-list.ts`, `submissions-list.html`, plus the new `extra-answers.ts`, `program-tabs.css`, `submissions-list.program-tabs.spec.ts` and `extra-answers.spec.ts`
- `maistra_web/src/app/services/supabase.ts` and `supabase.spec.ts`
- `maistra_web/src/app/components/code-editor/code-editor.ts` and `code-editor.spec.ts` (one added method)
- `supabase/migrations/20260923000000_add_submission_answers.sql`
- `docs/PROJECT_OVERVIEW_AND_CHANGES.md`

### Simulated merge results, branch by branch

**Pre-existing** conflicts already happen between the base branch and theirs, with or without program tabs. **Added** conflicts are the ones program tabs introduces.

| Remote branch | Tip | Pre-existing conflicts | Added by program tabs |
|---|---|---|---|
| `origin/judge0-integration` | `096dfa3` 2026-09-22 Jayrald, "fix(security): replace legacy Supabase keys and tighten RLS" | `docs/PROJECT_OVERVIEW_AND_CHANGES.md`, `maistra_web/src/environment.ts` | `submissions-list.ts`: 1 block, imports only |
| `origin/codex/supabase-security` | **same commit** `096dfa3` | same as above | same as above |
| `origin/feature/question-bank` | `50fc362` 2026-09-06 Nikko, "added question bank page with slide-in drawer navbar" | `docs/PROJECT_OVERVIEW_AND_CHANGES.md` | `submissions-list.ts`: 1 block, 8 lines in `openModal()` |
| `origin/code-similarity/duplicate` | `39ad170` 2026-09-05 Jayrald, "fix(web): scope similarity updates to active review" | `docs/PROJECT_OVERVIEW_AND_CHANGES.md` | **Large:** `supabase.ts` (3 blocks, ~190 lines), `submissions-list.html` (1 block, ~153 lines), `submissions-list.ts` (3 blocks, ~65 lines) |
| `origin/feature/capture-quality-gate` | 2026-09-17 | `.gitignore`, `maistra_mobile/lib/screens/capture_screen.dart` | none |
| `origin/feature/document-scanner` | 2026-09-07 | `maistra_mobile/lib/screens/capture_screen.dart` | none |

Notes:
- `judge0-integration` and `codex/supabase-security` point at the **same commit**, so resolving one resolves both.
- Neither `code-similarity/duplicate` nor `feature/question-bank` is contained in `judge0-integration`. Both are still separate, unmerged work.
- The `environment.ts` conflict comes from the Supabase key fix on the base branch (`a448198`) versus Jayrald's own key fix (`096dfa3`). Both replaced the disabled legacy key. Keep whichever key is current. It's unrelated to program tabs.

### How to resolve the small conflicts

**`judge0-integration` / `codex/supabase-security`:** both sides added imports in the same place. Keep both:

```ts
import {
  SubmissionAnswer,
  answerProblems,
  answersToSave,
  parseAnswers,
  takenQuestionIds,
} from './extra-answers';
import { buildCQuestionSource } from '../../utils/c-question';
import { normalizeOutput } from '../../utils/normalize-output';
```

**`feature/question-bank`:** both sides added resets in `openModal()`. Keep both:

```ts
    this.activeTab = 0;
    this.removeConfirmIndex = null;
    this.questionPickerOpen = false;
    this.extraAnswersError[submission.id] = '';
    this.detailsSaveStatus = '';
```

After any resolution, rerun `npx ng test --watch=false`, `npx tsc -p tsconfig.app.json --noEmit` and `npx ng build` in `maistra_web`.

### The big one: `code-similarity/duplicate` (a design question, not just a text conflict)

That branch (12 commits on 2026-09-05, about 3,800 lines added) builds assessments, rosters and code-similarity checking. Beyond the text conflicts, it overlaps with program tabs in two ways:

**1. It already has quiz grouping and question numbering.** Migration `20260905010000_add_assessment_roster_similarity_schema.sql` creates:
- `assessments` (`name`, `status` draft/active/closed, `starts_at`)
- `assessment_questions` (`assessment_id`, `question_id`, `starter_code`, **`position`**)

It also adds `submissions.assessment_id`, `student_id`, `block_section_id`, `verified_version` and `is_current`. Migration `20260905000000_add_question_submission_metadata.sql` adds the missing `question_type`, `topic` and `question_id` columns. That covers the "Existing schema gaps" item above and most of the Nikko item.

**2. Its data model is one submission row = one answer to one question.** It has:
- a foreign key `(assessment_id, question_id)` → `assessment_questions`
- a unique index `submissions_one_current_per_student_question_idx` on `(assessment_id, question_id, student_id) WHERE is_current`
- similarity scans (`similarity_scans`) run per `(assessment_id, question_id)`

Program tabs instead keeps Programs 2..n **inside one row's `answers` column**. If both merge unchanged, the similarity checker never compares Programs 2..n, because it only reads each row's `verified_text` for that row's `question_id`.

**Options to decide together** (no code has been written for either):
- **A. Keep `answers` (current design).** Similarity and grading both read `programsForGrading(verified_text, question_id, answers)`, and each entry is compared under its own `question_id`. Smallest change to program tabs; the similarity scan query has to expand each row into its programs.
- **B. One submission row per program.** When the teacher adds a tab, create a new `submissions` row for the same student and photo (same `image_url`, `student_id`, `assessment_id`) with its own `question_id` and `verified_text`. This matches his unique index and similarity model directly. Program tabs would then save tabs as rows instead of into `answers`, and the `answers` column would no longer be needed. The review UI (tabs, picker, guard, save rules) stays the same; only the save/load layer changes.

Either way, the tab picker should then list **only that assessment's questions, ordered by `position`**, and show real numbers ("Q2"). That's a small review-side change once the schema is merged.

### Questions to ask Jayrald

1. Which branch are you actively working on: `judge0-integration` (same commit as `codex/supabase-security`) or `code-similarity/duplicate`?
2. Is `code-similarity/duplicate` still going to be merged? If so, before or after the grading work?
3. For papers with several programs: option A (`answers` column + `programsForGrading`) or option B (one submission row per program)?
4. Who applies migrations to the cloud project, and in what order? Candidates: `20260905*` from his branch and `20260923000000_add_submission_answers.sql` from this one. Under option B the `answers` migration may be unnecessary.
5. Should Nikko wait for `assessments` / `assessment_questions` instead of designing quiz grouping separately?
6. Which branch should `feature/program-tabs` target for its pull request?
7. Once assessments exist, how does a submission link to its assessment (e.g. an `assessment_id` on `submissions`)? The tab picker needs it to list only that paper's questions and pre-fill tabs in order.

### Re-running these checks

From the repo root, after `git fetch origin`. Nothing is modified:

```bash
# files that would conflict if <branch> were merged into program tabs
git merge-tree --write-tree --name-only feature/program-tabs origin/<branch>

# the same for the base branch, to separate pre-existing conflicts
git merge-tree --write-tree --name-only feature/reading-order-reassembly origin/<branch>

# is one branch already contained in another?
git merge-base --is-ancestor origin/<older> origin/<newer> && echo yes || echo no
```
