# Web Frontend Guide — Nombrado's Work in `maistra_web/`

## Current addition — 2026-09-24

On pushed `feature/pre-extraction`, `subscribeToSubmissions(onInsert,
onUpdate?)` also listens for UPDATEs. The optional callback preserves existing
INSERT callers. The list checks the OCR server's `GET /` health field on load,
every 30 seconds and after list reloads. An eligible new unread paper shows
**Extracting…**, then **Needs review** when `extracted_text` arrives. The
`applyFreshSubmission(row)` helper is shared by the realtime callback and
opening a paper; it fills empty OCR/editor fields and updates status without
replacing teacher edits, verified text or program tabs. See the
[pre-extraction plan](../superpowers/plans/2026-09-24-pre-extraction-on-arrival.md).

Companion to [`ocr/CODEBASE_GUIDE.md`](../ocr/CODEBASE_GUIDE.md), same
purpose: a systematic, file-by-file walkthrough of the *current* code,
not a chronological bug log (that's [`VERIFICATION_UI.md`](VERIFICATION_UI.md)
— read it for *why* each fix exists and what broke before it; read this for
*how the code works now*).

**Attribution boundary**, carried over from `VERIFICATION_UI.md`: the
folder/topic grouping and modal shell in `submissions-list.*` were built by
a teammate (Nikko). What's documented here as Nombrado's work is: the
`code-editor` component in full (predates the rewrite, original work), and
the OCR-extraction / save / feedback logic layered into `submissions-list.ts`
and `services/supabase.ts` — the parts that make the teacher-verification
loop actually work and stay data-safe. Where a file is shared with the
teammate's UI code, only the relevant methods are covered, not the whole
file.

---

## 1. The shape of this slice in one picture

```
 submissions-list.html (teammate's shell + Nombrado's OCR controls)
        |
        v
 submissions-list.ts
   extractText() ---> POST http://localhost:8000/api/ocr/extract-from-url
                       (ocr_feature backend -- see CODEBASE_GUIDE.md)
        |
        v
 app-code-editor (code-editor.ts, Nombrado's component)
   [(value)]="editableText[id]"  <-- two-way bound
        |
        v
 saveVerifiedText() ---> supabase.ts: updateSubmissionText()
                          writes verified_text (+ extracted_text, once)
                          to the `submissions` table
```

The teacher never edits `extracted_text` directly — they edit
`editableText[id]` (seeded from whichever of `verified_text` /
`extracted_text` exists), and only `saveVerifiedText()` decides what gets
written where.

---

## 2. `code-editor/code-editor.ts` — the Ace wrapper (fully original work)

### 2.1 Why it exists at all

The extracted C code needs to be *editable* (a teacher corrects OCR
mistakes) and *readable* (syntax highlighting beats a plain `<textarea>` for
scanning handwritten-code output for errors). `CodeEditorComponent` wraps
the third-party Ace editor (`ace-builds`) behind a small, two-way-bindable
Angular component so it drops into the template exactly where a plain
`<textarea [(ngModel)]>` used to sit.

### 2.2 The two-way binding contract

```ts
@Input() value = '';
@Output() valueChange = new EventEmitter<string>();
```

Angular's `[(value)]` banana-in-a-box syntax requires exactly this pair —
an `@Input() value` and an `@Output() valueChange`. `ngOnChanges` pushes
external updates (e.g. a fresh OCR result arriving) into the Ace buffer only
when they actually differ from what's already there, so it never clobbers
text the teacher is mid-typing:

```ts
ngOnChanges(changes: SimpleChanges): void {
  if (this.editor && changes['value'] && this.value !== this.editor.getValue()) {
    this.editor.setValue(this.value ?? '', -1);
  }
}
```

The `-1` cursor position on `setValue` puts the cursor at document start
rather than selecting everything, which is what Ace does by default.

### 2.3 `format()` and `reindent()` — brace-depth re-indentation

**The problem it solves:** OCR extraction deliberately outputs a *flat*
transcription — `" ".join(parts)` in the backend strips leading whitespace,
because inferring nesting depth from a handwritten glyph's horizontal
position on the page would mean guessing structure instead of reading what's
actually there. That's the right call for extraction accuracy, but it makes
the raw output hard for a teacher to visually scan. `format()` fills that
readability gap **at the display layer only**.

**The boundary that makes this safe:** `reindent()` is a pure string
function — feed it text, get back the same text with only leading whitespace
changed. It never touches any other character, and the whole document is
replaced as one edit (`session.replace(...)`) so `Ctrl+Z` undoes it in one
step. It's wired to the conventional `Shift-Alt-F` "format document" chord,
and to a visible Format button in the template — both **teacher-triggered**,
never automatic on load or on OCR result arrival. That matters for the same
reason the backend's cleanup layer (`c_code_cleanup.py`) never touches braces
or string content: the teacher should see the faithful raw extraction first,
and formatting is an opt-in convenience, not something that could be mistaken
for what OCR actually read off the page.

**The reindent algorithm** (private static, so it's testable independent of
Ace):
- Walks the buffer line by line, tracking brace `depth`.
- A line whose first non-whitespace character is `}` is dedented by one level
  *before* being printed (the closing brace sits at its block's outer level).
- Within each line, a second pass walks character-by-character to update
  `depth` for subsequent lines — but skips characters inside string/char
  literals (`"..."`, `'...'`, with `\`-escape handling) and `//`/`/* */`
  comments, so e.g. `printf("{}")` doesn't shift the indent level.
- Blank lines pass through untouched (no re-indentation applied to nothing).

**Known, deliberate limitation:** the reindenter trusts whatever braces are
literally in the buffer. OCR frequently misreads `}` as a digit or other
glyph (documented separately as the project's brace error-recall problem),
so `format()` only produces *correct* indentation once the teacher has fixed
the braces — on raw, brace-misread OCR text it will under/over-indent in a
traceable, brace-count-consistent way. This was verified directly (same
program formats correctly after brace fixes, predictably-wrong before) and
is treated as expected behavior, not a bug to chase further. A brace-count
mismatch *warning* was proposed and explicitly declined ("can I just leave
it?") — not built.

**Explicitly out of scope by design, not by omission:**
- Auto-correcting misread braces (e.g. guessing a misread `d` was meant to be
  `{`) — would mean silently altering extracted content based on a guess,
  defeating the entire point of showing raw text for teacher review.
- Any structural/grammar parsing (that's a downstream teammate's tree-sitter
  stage, for a different purpose — checking logic/structure rules, not
  display formatting). This component implements no tree-sitter and has no
  dependency on it.
- Preserving blank-line vertical spacing from the original handwriting — OCR
  has no signal for "there was a blank line here" (no detection = no output
  line), so there's nothing to preserve; `format()` only keeps blank lines
  the teacher already typed.

### 2.4 Reused beyond `submissions-list` (as of the `judge0-integration` merge)

**Updated 2026-09-02** — the component's editing/formatting logic above is
unchanged, but its reach in the app has grown. `app-code-editor` originally
had exactly one caller (`submissions-list.html`, the teacher-verification
widget this doc's §1 diagram describes). It's now also embedded in:

- `question-form.html` (Diwa's question-authoring form) — twice: once for
  the model-answer source, once for a test case's code, so a question
  author gets the same Ace/syntax-highlighting experience.
- `judge0.html` (Tajanlangit's Judge0 test-run component) — for the
  submitted-code view during grading.

This reuse is what motivated the one styling change made to the component
itself, committed `5ccd5e9` ("Enhance code editor styling for layout
flexibility"):

```diff
- .ace-host {
+ :host {
+   display: block;
+ }
+
+ .ace-host {
    width: 100%;
-   height: 300px;
+   height: var(--code-editor-height, 300px);
    border: 1px solid #ccc;
    border-radius: 6px;
+   box-sizing: border-box;
  }
```

- `height` is now a CSS custom property (`--code-editor-height`) with the
  original `300px` kept as the fallback, so a fixed-height caller (the
  original `submissions-list` usage) needs no changes, while a caller that
  wants the editor to fill its container can set the variable — e.g.
  `submissions-list.css:533` sets `--code-editor-height: 100%` on a
  flex/grid ancestor for its modal layout.
- `:host { display: block; }` was added because Angular components default
  to `display: inline` on their host element, which silently breaks
  `width: 100%`/height-driven layouts in a flex or grid container —
  necessary once the component started appearing in different layout
  contexts, not just its original fixed-size slot.
- `box-sizing: border-box` keeps the 1px border from pushing the rendered
  box past `width: 100%`/`height: 100%`, which matters more once the height
  is externally controlled instead of a hardcoded pixel value.

**Nothing else changed.** The `[(value)]` two-way binding contract, the
`format()`/`reindent()` logic, and `ngOnChanges`'s guard against clobbering
in-progress edits are identical to what §2.1–2.3 describe — this was a
pure CSS/layout change to make the existing component embeddable elsewhere,
not a behavioral rewrite.

---

## 3. `submissions-list.ts` — the OCR-integration and save-safety logic

(Folder/topic grouping methods — `groupSubmissions()`, `toggleFolder()`,
`openModal()`/`closeModal()`'s core shape — are the teammate's rewrite and
not covered here beyond what's needed for context.)

### 3.1 `extractText()` / `performExtract()` — calling the OCR backend, with a re-extract guard

**Updated 2026-09-04.** The extraction path was split into a *guard* and the
*actual call* when the button became re-runnable (a teammate relabeled it
"Re-extract code" once text exists, commit `aca278e`). The unconditional
overwrite that was safe for a one-time "Extract" became a footgun for a
re-runnable button — clicking it silently discarded the teacher's corrections.
So `extractText()` (what the button calls) now guards first:

```ts
const current = this.editableText[id];
const lastExtraction = this.extractedText[id];
const hasEdits = !!current && current !== lastExtraction;
if (hasEdits) {
  this.reextractConfirmId = id;   // opens the in-app confirmation dialog
  return;
}
await this.performExtract(id);     // no edits to lose -> extract straight away
```

`hasEdits` is true when the editor content differs from the last OCR output —
i.e. the teacher has typed corrections, **or** a previously-saved `verified_text`
was loaded into the editor. In either case a styled confirmation dialog opens
(`reextractConfirmId` drives a `*ngIf` overlay in the template; `confirmReextract()`
proceeds, `cancelReextract()` keeps the edits). A first extraction (editor empty)
or a re-extract with no edits since the last one skips the dialog entirely.

`performExtract()` is the actual network call (unchanged logic, just moved out
of `extractText`):

```ts
const res = await firstValueFrom(this.http.post(
  'http://localhost:8000/api/ocr/extract-from-url',
  { image_url: this.selectedSubmission.image_url, submission_id: id },
));
```

Sends the submission's already-known `image_url` (the image itself is never
re-fetched by the frontend — it's already displayed via a direct `<img
[src]>` binding) to the OCR backend's `extract-from-url` endpoint (see
`ocr/CODEBASE_GUIDE.md` §4 for what happens server-side). The component uses
`cleaned_text` for the editable buffer and now also consumes `line_details`
and `review_suggestions` as submission-scoped OCR-review evidence. It combines
their confidence/suggestion signals with narrow deterministic checks, then
passes one prioritized flag per line to the Ace wrapper.

**Defense scope note:** this OCR-review layer is outside the defended scope
(extract → save raw/verified text → display for teacher editing) and stays
unmerged on the experiment branches — future work, not a feature to lead
with in the walkthrough.

The markers are violet OCR-review aids, not syntax diagnostics. Empty finding
panels do not render, and an unmarked line is not claimed to be correct.
Editing a row dismisses extraction-era evidence for that row; inserting or
removing lines invalidates stale row mappings. The original OCR, editable, and
verified text remain separate. See
`../superpowers/specs/2026-09-05-ocr-review-highlighting-design.md`.

**Updated 2026-09-05 (same-day follow-on, after live testing against a real
garbled page surfaced four lines the checks above still missed):**
- The deterministic "unusual line" check in `ocr-review-flags.ts` widened from
  an exact 1–2 alphanumeric-character token to any short (≤3 char) fragment
  that isn't a finished statement/label/pure punctuation — catches dangling
  garbage like `s%d` that the narrower rule couldn't match.
- `detectBracketMismatches()` (same file) now walks the whole text with a
  bracket stack and flags the *exact line* where a `)`/`]`/`}` doesn't match
  what's open — e.g. `&num5]` where a `)` was expected — instead of the old
  behavior of only reporting a whole-document open/close count with no
  location. An opener left unclosed at end-of-document still can't be pinned
  to one line and stays in the whole-document banner; only mismatched/orphaned
  *closers* are now locatable.
- The backend (`c_code_suggestions.py`) gained `_literal_word_suggestions()` —
  flags a likely-misread word *inside* a printed message (e.g.
  `valind`→`valid`) against a small curated word list, one edit-distance only.
  This is the one place the original design correctly kept out of scope for
  *correction* (message text is student-authored) but had left with *no
  flagging coverage at all* — the fix flags without ever asserting whether OCR
  or the student is the source of the misspelling. (`c_code_suggestions.py`
  and this reasoning were later removed 2026-09-12 from
  `feature/reading-order-reassembly` as unused on that branch — see
  `../ocr/OCR_REVIEW_SUGGESTION_AB.md`'s banner.)

The production backend's exact suggestion table still misses variants such as
`scainf` → `scanf` (a *function-call* misspelling, unrelated to the message-text
check above). A guarded matcher has been A/B tested but is not yet
implemented; see `../ocr/OCR_REVIEW_SUGGESTION_AB.md`.

On success it seeds *two* separate fields:
```ts
this.extractedText[id] = text;   // the OCR's own output, kept as the baseline
this.editableText[id] = text;    // what the teacher will actually edit
```
This split is what makes Bug 5's fix (below) possible — `extractedText` never
gets overwritten by the teacher's subsequent edits to `editableText` — and it's
also exactly what the re-extract guard above compares against to detect edits.

On failure, the error goes to a dedicated `extractionError[id]` field, and
**`editableText` is left untouched** — the editor either stays hidden (first
attempt) or keeps showing whatever real content a previous successful
extraction/save already put there. This is deliberate: an error message must
never become something that's editable and savable as if it were real
content (see `VERIFICATION_UI.md` Bug 3 for the incident this prevents).

### 3.2 `saveVerifiedText()` — the race-safe save path

Three problems this method solves simultaneously:

**(a) `extracted_text` vs `verified_text` must never collapse into one
value.** The OCR's own output must survive as a permanent baseline for
measuring teacher-correction rate and building fine-tuning training pairs;
the teacher's edits must only ever land in `verified_text`. So:
```ts
const ocrText = this.extractedText[id];   // undefined if no extraction ran this session
await this.supabase.updateSubmissionText(id, text, ocrText);
```
`ocrText` is `undefined` unless an extraction actually ran in this browser
session — `updateSubmissionText` (in `supabase.ts`, below) only writes
`extracted_text` when a real value is passed, so re-saving edits to an
already-extracted submission never overwrites its baseline with the
teacher's text (see `VERIFICATION_UI.md` Bug 5 — this whole split exists
because the previous version wrote the same string into both columns,
silently destroying every OCR-vs-teacher comparison in the database).

**(b) A stale async save must not clobber UI state from a newer one.** If a
teacher clicks Save twice in quick succession, or navigates while a save is
in flight, an older `await` resolving after a newer one could otherwise
overwrite fresher state. Guarded with a per-submission generation counter:
```ts
const generation = this.startSaveGeneration(id);   // increments and returns
...
if (!this.isCurrentSave(id, generation)) return;    // bail if superseded
```
checked after every `await` boundary and again at the top of the delayed
`setTimeout` that auto-clears the "✓ Saved" message, so an in-flight stale
save can't resurrect a status message for a save that's no longer current.

**(c) The component must not touch Angular state after it's destroyed.**
`this.destroyed` is set in `ngOnDestroy()` and checked alongside the
generation check, so a save that's still in flight when the user navigates
away doesn't throw or silently mutate a torn-down component's fields.

### 3.3 Save-status feedback (`saveStatus[id]`)

`'saved'` or `'error'`, rendered inline next to the Save button
(`✓ Saved successfully` / `✕ Save failed — please try again`), auto-clearing
after 3 seconds via a tracked `setTimeout` (cleared/replaced correctly if a
new save starts before the old timeout fires — see `clearSaveStatusTimer()`).
Exists because the pre-fix version gave zero feedback on save success *or*
failure — a failed save was indistinguishable from a successful one from the
teacher's point of view (`VERIFICATION_UI.md` Bug 4).

---

## 4. `services/supabase.ts` — the submission-write contract

Only the submission-related methods are Nombrado's; `saveQuestion`/
`getQuestions` predate this work and are unrelated.

### 4.1 `getSubmissions()`

```ts
const SUBMISSION_COLUMNS = `id, image_url, captured_at, status, topic, student_name,
  extracted_text, verified_text, question_id,
  questions (id, question_name, question_type, model_answer, test_cases)`;
// getSubmissions() first tries `answers, ${SUBMISSION_COLUMNS}`
```
**Missing-column fallback (2026-09-24, program tabs):** if Postgres returns
`42703` (undefined column) and the message names `answers`, the service sets
`answersColumnAvailable = false` and re-queries with `SUBMISSION_COLUMNS` alone.
The list still loads before the `answers` migration is applied. Any other
missing column is returned as an error, as before. The flag resets on page load,
so the fallback stops as soon as the column exists.

Explicit column list, not `select('*')` — this was itself the fix for Bug 1
(a rewrite had dropped `extracted_text`/`verified_text`/`student_name` from
an equivalent explicit list, making previously-saved work appear to vanish
on reload). If a new column is ever added to the `submissions` table and
needs to reach the UI, it must be added here explicitly — `select('*')` was
deliberately not restored, since an explicit list is what caught this bug
being reproducible/verifiable in the first place.

### 4.2 `updateSubmissionText()` — the write-safety contract

```ts
async updateSubmissionText(
  submissionId: string,
  verifiedText: string,
  extractedText?: string,
  answers?: SubmissionAnswer[],   // 2026-09-24: Programs 2..n
): Promise<void> {
  const update: Record<string, unknown> = {
    verified_text: verifiedText,
    status: 'verified',
    verified_at: new Date().toISOString(),
  };
  if (extractedText !== undefined) {
    update['extracted_text'] = extractedText;
  }
  ...
}
```
`extracted_text` is conditionally included in the update payload — omitted
entirely (not set to `undefined` or `null` inside the object, which
Supabase would still send) when the caller didn't pass a fresh OCR result.
This is the actual mechanism behind the `extracted_text`/`verified_text`
separation described in §3.2(a). A spec (`supabase.spec.ts`) asserts this
field is absent from the update payload when no OCR text is given, so a
regression here would fail a test, not just get caught by inspection.

`answers` follows the same rule: it's only in the payload when the caller
passes it **and** `answersColumnAvailable` is not false. The component never
calls this with extra programs while the column is missing; it blocks the save
with a message first (see "Program tabs" below).

### 4.3 `subscribeToSubmissions()`

Realtime Postgres-changes subscription (`INSERT` on `submissions`), used by
`submissions-list.ts`'s `ngOnInit()` to refresh the list when a new
submission arrives from the mobile app, without a manual reload. Cleaned up
in `ngOnDestroy()` via `subscription.unsubscribe()`.

---

## 5. Testing

`submissions-list.spec.ts` and `supabase.spec.ts` cover the save-safety
logic specifically: the `extracted_text`-omitted-when-absent contract
(§4.2), and (per the spec file size added in `263b6d7`) the race-safety
behavior in `saveVerifiedText()`. Run with `npx ng test --watch=false` from
`maistra_web/` (Vitest via `@angular/build:unit-test`). The 89-test count was
the first program-tabs checkpoint; after pre-extraction the recorded suite was
114/114, and after the 2026-09-26 Save-next-to-the-tabs change it is 121/121.
The program-tab tests are listed at the end of this guide.

---

## 6. What this component does *not* do

- **Manual extraction does not write immediately** — `extractText()` only calls the OCR
  backend and updates local component state (`extractedText`/
  `editableText`). Nothing is persisted until the teacher explicitly saves on
  Step 2: the **Save** button next to the program tabs (or Cmd/Ctrl+S), or
  **Continue to grading**, which saves first (since 2026-09-26; before that
  the only buttons were "Save and continue to grading" and the close prompt's
  "Save and close", and originally "Save Verified Text"). The separate OCR-server worker now saves
  `extracted_text` for eligible new papers when `AUTO_EXTRACT=true`; it does
  not save `verified_text` or the teacher's edits. See
  `superpowers/plans/2026-09-24-pre-extraction-on-arrival.md`.
- **No structural code parsing** — `code-editor.ts` does syntax
  highlighting and brace-depth display formatting only; it makes no claims
  about whether the code is logically correct C (that's a separate,
  downstream stage owned by a teammate).
- **No indentation inference in extraction itself** — that boundary is
  enforced on the `ocr_feature` side (see `ocr/CODEBASE_GUIDE.md`), not
  here; this guide's `format()` section (§2.3) explains why the frontend
  doesn't try to work around it either.

## Program tabs in Review Code (2026-09-24, branch `feature/program-tabs`)

One paper can hold several programs. Step 2 shows browser-style tabs above the editor.

- **Program 1** is the existing editor (`editableText`). Its question comes from Details.
- **Programs 2..n** live in `extraAnswers[submissionId]` as `{ code, question_id }` and are saved to `submissions.answers` (jsonb) under the same submission id.
- **`extra-answers.ts`** holds the pure rules:
  - `parseAnswers` reads the column defensively.
  - `answersToSave` drops fully blank tabs and keeps code verbatim.
  - `takenQuestionIds` maps each question to the program holding it, for the "In Program N" greying.
  - `answerProblems` returns save-rule messages: code without a question, a question without code, or a duplicate question including Program 1's.
  - `programsForGrading(verified_text, question_id, answers)` is the **grading hand-off for Jayrald**. It returns `[{ program, code, question_id }]`, Program 1 first, skipping entries without code or a question. The review never calls it; grading will.
- **Component state:**
  - `activeTab` is 0 for Program 1 and n for `extraAnswers[n-1]`.
  - `removeConfirmIndex` backs the two-click ×. `cancelPendingRemove()`, bound to a click anywhere in the workspace, disarms a pending "Remove?".
  - `questionPickerOpen` controls the custom picker menu.
  - `extraAnswersError` holds the save-rule message.
- **Tab marks:** an orange `!` means no question is linked yet. Dots mark tabs with unsaved changes.
- **Save path:** `saveVerifiedText()` checks `answerProblems` before the save generation starts. A blocked save makes no DB call and shows the first message. The extras go in the same `updateSubmissionText(id, text, ocrText, answersToSave(extras))` update, and on success both the list row and the open `selectedSubmission` get the saved `answers`. If the `answers` column is missing (`extraProgramsSavable` false), Program 1 still saves (the service drops `answers`), the tabs stay on screen unsaved, and `EXTRA_PROGRAMS_UNSAVABLE` says "Program 1 was saved. Programs 2 and up can't be saved yet…" (changed 2026-09-24; it used to block the whole save).
- **Reload safety:** `loadSubmissions()` seeds `editableText` only once per submission, so a realtime INSERT can't replace unsaved Program 1 edits (fixed 2026-09-24).
- **Editor identity:** the extra editors use `trackByAnswer` (the tab object), so removing a tab destroys its Ace editor rather than handing it, and its undo history, to the next tab.
- **Preview-only note:** while the column is missing, Step 2 shows "Preview only: Programs 2 and up can't be saved until the database has the answers column." under the editor. The footer says "Every program is saved with this paper. Only Program 1 is graded for now."
- **Editors:** every tab keeps its own `CodeEditorComponent`. Inactive ones are `[hidden]`, which the CSS forces to `display: none` because `:host { display: block }` would win otherwise. `selectTab()` runs change detection, then `refresh()`, so Ace re-measures.
- **Format** acts on the open tab only.
- **Styles** live in `program-tabs.css`, which the component uses via `styleUrls`. `submissions-list.css` alone was already near the 12 kB `anyComponentStyle` error budget.
- **Tests:**
  - `extra-answers.spec.ts` (15)
  - `submissions-list.program-tabs.spec.ts` (17)
  - `supabase.spec.ts` (+5)
  - `code-editor.spec.ts` (+2)
  - 42 new in total; 92/92 overall after the 2026-09-24 code-review fixes; 102/102 after the review aids below.
- **Review aids (2026-09-24, same branch):**
  - `savedProgram1` / `savedExtras` hold what was last loaded or saved.
  - `isProgram1Unsaved`, `isExtraAnswerUnsaved` (blank tabs never count) and `hasUnsavedPrograms` (also catches removed tabs) drive the tab dots and the close prompt.
  - `requestCloseModal()` replaces direct `closeModal()` calls from ✕, the overlay, Cancel and Finish review. Its prompt offers `keepEditing()` (primary) and `discardChangesAndClose()` (restores the snapshots and drops this session's `extractedText`). `saveAndClose()` was removed on 2026-09-26; see "Save next to the tabs" below.
  - `extractText()` on a paper with tabs calls `performExtract(id, { replaceProgram1: false })`, which only updates `extractedText` and opens the OCR panel. It skips the re-extract confirmation because nothing is overwritten.
  - OCR panel: `ocrPanelOpen` plus `getOcrText()` (this session's `extractedText`, else the saved `extracted_text`). `.ocr-layout.with-ocr-text` puts photo and text side by side and the editor full width below.
  - `getActiveTabQuestion()` feeds the read-only "View question" peek.
  - `moveTab(±1)` handles the ←/→ keys and focuses the tab through `#tabList`.
  - `CodeEditorComponent` gained `@Input() placeholder` (Ace `placeholder` option) for the empty-tab guide text.
  - Styles: `program-tabs.css` (about 7 kB).
- **Proposed next** (mocked, not built): move selection to a new tab, unsaved dots with a close prompt, an "N programs" badge, arrow keys, and tooltips. Details are in the plan's "Nombrado: optional and future work".
- **Save next to the tabs (2026-09-26, branch `feature/program-tabs-save`):**
  - **Why:** Step 2 had no plain Save. Saving meant going to grading or closing the paper (✕ → "Save and close"), so a teacher who saved and closed had to reopen the paper to grade.
  - **Markup:** the tab row is wrapped in `.program-tabs-bar`. Inside it, `.program-tabs` (`role="tablist"`, `#tabList`) keeps the tabs and **+**, takes the free width (`flex: 1; min-width: 0`) and scrolls sideways; `.program-save` sits after it, *outside* the tablist so screen readers still see only tabs there, and stays pinned right (`flex: none`).
  - **Save button:** `(click)="saveVerifiedText()"`, `[disabled]="isSaving(id)"` (no double saves), label "Saving…" while `savingId` is set. `.program-save-status` shows `saveStatusLabel(id)`: "Save failed, try again" on error, "✓ Program 1 saved" when `extraAnswersError[id]` is `EXTRA_PROGRAMS_UNSAVABLE` (no `answers` column), otherwise "✓ All programs saved" (it replaced the old `.save-status` line under the editor; `saveVerifiedText()` still clears it after 3 s). Rule errors still show under the editor via `extraAnswersError`.
  - **Shortcut:** `onSaveShortcut(event)` is a `@HostListener('document:keydown')`. It acts only on Cmd/Ctrl+S, only with a paper open on Step 2 and the close prompt shut; it then always calls `preventDefault()`, and saves only if `hasExtractedText(id)` (same condition as the button being shown) and no save is running.
  - **Footer:** the label is "Continue to grading"; `saveCodeAndContinue()` is unchanged apart from `cdr.detectChanges()` after `reviewStep = 3` (the app is zoneless; same fix as Jayrald's `8e20fd5`). `continueFromDetails()` got the same call after `reviewStep = 2`.
  - **Close prompt:** Discard changes (danger) + Keep editing (primary). `saveAndClose()` is gone.
  - **Save still runs when nothing looks changed**, on purpose: an untouched pre-extracted paper has `savedProgram1 = extracted_text`, so it has no dots, but it is still `pending` with no `verified_text`.
  - **Tests** (`submissions-list.program-tabs.spec.ts`): Save keeps Step 2 open and clears the dots; a rule-blocked Save writes nothing; Save verifies an untouched pre-extracted paper; Cmd/Ctrl+S saves and blocks the browser dialog; the shortcut does nothing outside Step 2, in the prompt, without a modifier, while saving, or with no extracted code; the prompt has no save action; the label says "Program 1 saved" when the column is missing and "Save failed" on error. `submissions-list.spec.ts`: Continue to grading renders Step 3. Suite: 121/121.
