# Pending Fixes — Code Review Findings

> **Current pointer (2026-09-24):** This is a dated review log. The optional
> pre-extraction worker and live list badge are on pushed
> `feature/pre-extraction`; the 207-test association count below predates the
> recorded 231/231 OCR and 114/114 web suites. See [docs/README.md](README.md)
> and [TEAM_SYNC.md](TEAM_SYNC.md) for integration status.

> **2026-09-24 review:** 10 more findings (OCR server, cleanup, program tabs), all fixed, with analysis of why they keep appearing: see [`CODE_REVIEW_2026-09-24.md`](CODE_REVIEW_2026-09-24.md). Item 5 below is the root of two of them.

## OCR association follow-up — updated 2026-09-23

**Resolved 2026-09-17 (`7640127`):** the five production expected-failing order
tests now pass. Conservative continuation association is live in
`core/continuation.py`, and the suite has 207 passing tests with zero expected
failures. Items still open, each needing more writers rather than more code:
explicit right-to-left return edges (reserved Example 10 is outside the live
column gate), helper/main block boundaries, and fresh-writer evaluation.
Recognition/filtering loss is a separate problem; never add braces to make a
student program fit. See [session handoff](../ocr_feature/reports/2026-09-14-continuation-session-handoff.md).

No OCR code fix is pending. The next OCR step is importing the incoming bond
paper and yellow pad datasets (see `NEXT_STEPS.md`, 2026-09-23 block).

Findings from a code review of the OCR pipeline and web verification UI. Bugs
1-4 and 6 are fixed; 5 remains an optional web cleanup item.

Status legend: 🔴 not started · 🟡 in progress · ✅ fixed

## Attribution

The confirmed fixes are within John Cale Nombrado's task scope. Checked via
`git blame`:

- **Findings 1 & 3** are in the web save-status feedback feature. The web fix
  also makes `updateSubmissionText` throw returned Supabase errors, preventing
  a failed database update from being displayed as successful.
- **Findings 2 & 4** are in the OCR reading-order feature, committed as
  `94fae71` under John Cale Nombrado's git identity.
- **Findings 5 & 6** concern the web submissions component, not OCR. The
  parallel maps have mixed history; the duplicated status markup was added by
  the web save-status feature.

These are new-feature bugs caught by running a review on freshly-written
code, which is what the review process is for — not something missed by
anyone else on the team.

---

## ✅ 1. Overlapping saves race — fixed
**Severity:** High · **Verdict:** CONFIRMED
**File:** `maistra_web/src/app/components/submissions-list/submissions-list.ts:176`

The `setTimeout` that auto-clears `saveStatus[id]` after 3s has no guard
against a second save happening in between. If the same submission is saved
twice within 3 seconds, the *first* save's timer still fires at its original
mark and unconditionally does `saveStatus[id] = ''` — wiping out the
*second* save's still-fresh "saved" confirmation, or worse, an unread error
message.

**Trigger:** Click Save, then edit and click Save again within 3 seconds.

**Resolution:** the web fix uses a per-submission generation and replaces any
existing timer for that submission. Older requests and timers cannot clear or
overwrite a newer success or error status.

---

## ✅ 2. Reading-order line-merge — fixed
**Severity:** High (touches the project's core "never reshape graded
content" invariant) · **Verdict:** CONFIRMED (traced with concrete numbers)
**File:** `ocr_feature/core/ocr_pipeline.py:118` (`_group_into_reading_order`)

The line-grouping check compares each new detection's y-position against
the *running average* y of the currently-open line, not its first member.
As members accumulate, that average can drift enough to swallow a
genuinely separate next line.

**Traced example:** items at y=10, 11, 12 form one line (median_h=10,
line_tol=6). The running average drifts 10 → 10.5 → 11. A real next line
starting at y=17 is 7 away from the line's first item (would correctly NOT
merge) but only 6 away from the drifted average of 11 (incorrectly DOES
merge, since the comparison uses `<=`).

**Practical impact:** two different handwritten lines' text get concatenated
onto one output line for the teacher to review — changes how graded content
is grouped/read, which is exactly the class of thing this pipeline is
supposed to never do.

**Resolution:** the grouping now predicts each candidate's expected y using a
least-squares y-on-x fit of the current line. This preserves sloped handwritten
lines without allowing a running average to drift into the next line.

---

## ✅ 3. setTimeout cleanup on component destroy — fixed
**Severity:** Medium (real gap, narrower real-world trigger than it looks)
**Verdict:** PLAUSIBLE
**File:** `maistra_web/src/app/components/submissions-list/submissions-list.ts:176`

The same `setTimeout` from #1 is never stored or cleared in `ngOnDestroy()`.
If the component is destroyed while a timer is pending, the callback still
fires afterward and calls `this.cdr.detectChanges()` on a torn-down view.

**Important nuance found during verification:** closing the modal does
*not* destroy this component — `closeModal()` only nulls
`selectedSubmission`. The real trigger requires navigating away from the
whole submissions route within 3 seconds of a save, which is a narrower
window than it first appeared. Whether it actually throws depends on the
Angular version in use.

**Resolution:** pending save-status timers are stored per submission and
cleared in `ngOnDestroy()`. In-flight saves also check the destroyed state
before scheduling UI work.

---

## ✅ 4. Reading-order invariant documentation — fixed
**Severity:** Low-medium (documentation, but directly tied to #2)
**Verdict:** CONFIRMED
**File:** `ocr_feature/core/ocr_pipeline.py:76` (`_group_into_reading_order` docstring)

The helper docstring now records the accurate invariant: grouping can reorder
whole recognized fragments and the caller can insert whitespace when joining
them, but the helper never edits recognized characters.

---

## 🔴 5. Per-submission UI state spread across 4 parallel maps
**Severity:** Low (structural/maintainability, not a bug today)
**File:** `maistra_web/src/app/components/submissions-list/submissions-list.ts:47`

`extractedText`, `editableText`, `extractionError`, and `saveStatus` are all
independent `Record<string, string>` maps keyed by submission id, alongside
`savingId`/`extractingId`. Works today, but every new per-row status adds
another ad-hoc map instead of extending one source of truth, and any future
code that removes/resets a submission has to remember to clear all of them
by hand.

**Likely fix direction (not urgent):** consolidate into one
`Record<string, { text, error, saveStatus, ... }>` or a small state object
per submission.

**2026-09-24:** program tabs (`feature/program-tabs`) added two more
per-submission maps, `extraAnswers` and `extraAnswersError`, following the
existing pattern rather than starting the refactor mid-feature. Include them
if this cleanup is ever done. `submissions-list.ts` is shared with Jayrald, so
coordinate first.

---

## ✅ 6. Duplicated save-status markup — fixed
**Severity:** Low (cosmetic/maintainability)
**File:** `maistra_web/src/app/components/submissions-list/submissions-list.html`

The "✓ Saved successfully" and "✕ Save failed" spans were two near-identical
`*ngIf` blocks differing only in class and text. A future wording/styling
change risked being applied to only one of the two.

**Resolution (found already applied, 2026-08-25 doc audit):** the template
now uses one `<span>` with `[ngClass]="saveStatus[selectedSubmission.id]"`
and a single conditional text expression, exactly the fix direction
originally proposed here. No longer duplicated.

**Update 2026-09-26:** that line under the editor was removed. The save status
now shows once, next to the Save button in the program tab bar
(`.program-save-status`: "✓ All programs saved" / "Save failed, try again").

---

## Remaining work
Finding 5 (per-submission UI state spread across parallel maps) is optional
web cleanup, with no immediate behavioral impact.
