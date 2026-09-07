# Non-linear layout reading-order reassembly — design

## Problem

The OCR pipeline's line-grouping (`core/ocr_pipeline.py`,
`_group_detection_records`) assumes a standard single-column, top-to-bottom,
left-to-right handwriting layout: detections are swept top-to-bottom, and a
candidate joins the current line if its vertical center falls within
tolerance and it doesn't overlap heavily in x with existing members.

A real, expected student behavior breaks this assumption: writing a
structurally later piece of code (e.g., a `switch` case's body) into unused
margin space elsewhere on the page — because the space directly below is
needed for other code — rather than in linear sequence. Two concrete examples
(the thesis adviser's prompt, reproduced by the user) were traced by hand
this session:

- A struct definition sits top-left.
- A dangling code fragment (the eventual case body, ending in several closing
  braces) sits far to the right of it, roughly the same height.
- Below, the actual function definition opens (`function → control structure
  → switch`) and stops mid-structure, immediately after a `case N:` label.

Today's grouping either (a) wrongly fuses the same-height fragments into one
garbled line (since there is no maximum-horizontal-gap check, only an
x-overlap check), or (b) if vertical tolerance is exceeded, inserts the
fragment as its own line at the wrong position in the sequence — either way,
the extracted text does not represent the student's intended program.

## Goals

- Stop the worst failure mode: unrelated same-height fragments being fused
  into one nonsensical line.
- For the specific, well-determined case demonstrated by the two examples
  (exactly one dangling open structural point, exactly one candidate fragment
  that resolves it to a globally consistent state) — reconstruct the correct
  line order automatically.
- Never assert a reordering when more than one candidate plausibly fits, or
  when the page's overall brace balance is inconclusive. Fall back to
  original geometric order, unchanged from today's behavior.
- Reuse existing, already-validated infrastructure (`core/c_literals.py`'s
  literal-shielding) for brace counting, rather than re-implementing
  brace/string/comment detection from scratch.
- Zero behavior change on ordinary, linear-layout pages — this is strictly
  additive and must be a no-op unless it is confident.

## Non-goals

- **Not a general-purpose reading-order solver.** This does not attempt to
  handle arbitrary non-linear layouts, multi-column printed documents, or
  cases without a clean, unique brace-depth match. Genuinely ambiguous pages
  still require human verification, same as today.
- **Not mid-sequence reassembly or semantic scope inference.** Reassembly
  remains end-of-sequence only. Consider a self-contained struct followed
  geometrically by a severed margin block `work(); }`, then main-column lines
  `void f() {`, `switch (x) {`, `case 0:`, `after_switch();`, `}`. The intended
  order puts `work();` inside the switch, its displaced `}` next, and
  `after_switch();` outside the switch before the function's final `}`.
  Appending the two-line block instead puts `after_switch();` inside the
  switch and `work();` outside it. Both orders have the same cumulative
  depths (`0, 1, 2, 2, 2, 1, 1, 0`); a unique brace-well-formed end candidate
  therefore does not establish the intended scopes.

  A conservative guard now rejects a unique winning candidate if any line
  in its normal partition has a negative brace delta. The check runs only
  **after** the existing block-length search establishes uniqueness; it does
  not filter candidates or resolve ambiguity. The partition depends on the
  selected block length, since unmarked lines can belong to the displaced
  block. In this counter-example, the winning length is 2 and its normal
  partition still contains the final `}`: the guard returns the original
  input rather than a brace-well-formed but semantically wrong reordering.

  The supported pattern leaves scopes open in the main text and supplies
  their closing lines from the margin. This restriction also rejects valid
  end-of-sequence layouts whose normal partition contains a negative-delta
  closing line from an earlier completed scope, such as a completed for-loop
  before a displaced switch body. Those pages require human verification.
  The guard is a safe fallback for this failure class, not a general proof
  of semantic correctness.
- **Not indentation/formatting.** Output stays flat (line content and order
  only), consistent with the existing design principle that raw extraction
  is a faithful, unformatted transcription. The existing Ace Editor "Format"
  button remains the separate, teacher-triggered step — and becomes more
  trustworthy once this feature has resolved brace structure correctly.
- **Not evaluating PP-StructureV3** (PaddleOCR's own multi-column
  reading-order module). Researched this session and deprioritized: it's
  built for printed multi-column documents (magazines/newspapers), has no
  understanding of C syntax, and would not resolve which structural point a
  fragment belongs to. Noted here only so it isn't independently proposed
  later without this context.
- **Not training a machine-learning reading-order model** (e.g., the
  graph-convolutional approaches found in the literature search). No labeled
  training data exists for this layout class, and building it is out of
  scope for a thesis timeline. The brace-depth heuristic is chosen
  specifically because it needs no training data — it works because C is a
  formally bracket-delimited language, a domain-specific signal general
  document-layout research doesn't have access to.

## Design

### Phase 1 — Region separation (modify existing merge rule)

In `_group_detection_records`, the same-line join condition currently checks
only x-overlap (`MAX_SAME_LINE_X_OVERLAP = 0.3`) once the vertical-tolerance
gate passes. Add a horizontal-gap check: if the gap between a line's
rightmost member and a candidate's leftmost x exceeds a threshold derived
from median character/word spacing (mirroring how `line_tol` is already
derived from median box height), reject the merge and start a new region
instead of joining.

This is a narrow, additive change to an existing, well-tested function.
Existing behavior (joining genuine side-by-side fragments of one physical
row, e.g. `int main()` + a trailing `{`) must be unaffected — the new gap
threshold needs to sit clearly above normal inter-word/inter-token spacing
and clearly below the kind of gap seen in the motivating examples, calibrated
against real measurements the same way `MAX_SAME_LINE_X_OVERLAP` was
(`docs/ocr/LINE_MERGE_INVESTIGATION.md`'s 30% cutoff came from a measured gap
between confirmed same-row and confirmed different-row cases — this
threshold needs the same evidence-based derivation, not a guessed constant).

### Phase 2 — Brace-depth region reassembly (new function)

After Phase 1 produces geometrically-separated regions (each region = one or
more grouped lines that stayed together under the tightened rule), a new
function computes each region's brace-depth trajectory:

- Entry depth: the brace depth at the start of the region, computed by
  walking all *prior* regions in default geometric order.
- Exit depth / "open" status: whether the region's own content leaves it
  balanced (exit depth === entry depth, self-contained) or leaves it
  "dangling" (ends mid-structure, most commonly right after a `case N:`
  label or an unclosed opener).

Braces inside string/char literals or comments must not count — reuse
`core/c_literals.py`'s existing shielding logic (already used by
`c_code_cleanup.py`) rather than re-parsing literals independently.

For every region left "open," search the remaining not-yet-placed regions
for one whose entry-depth requirement matches and whose own content, if
inserted there, is internally consistent (its own braces resolve without
going negative, and inserting it moves the overall page toward a fully
balanced final state — ideally depth 0 with no other open regions left,
since nothing should remain dangling at the true end of a page).

**Matching rule:** if exactly one remaining region satisfies the match,
insert it. If zero or more than one region satisfies it, do nothing — leave
all regions in original geometric order. No scoring, no "best guess" — a
match must be unique to be applied.

### Fallback / safety

- Any region whose own brace count doesn't resolve cleanly (should not
  normally happen if OCR read the braces correctly, but OCR error is
  expected) aborts reassembly for the whole page, falling back to original
  order. Reassembly must never run on data it can't verify internally.
- Ambiguous matches (as above) leave the page in original order.
- This is consistent with the project's existing discipline elsewhere
  (`is_suspected_unedited()`, `literal_provenance_issues()`, the suggestion
  layer): stay silent rather than assert something unverifiable. A
  confident-looking wrong reorder is a worse failure than today's flat
  merge/misorder, since it invites less scrutiny from the teacher during
  verification.

## Testing

- The two examples from this session (RBNode `rotate_rb`, Compressor
  `pack_flags`) become the first real fixtures — exact regression tests for
  correct reassembly end-to-end.
- User-provided handwriting photos of this same scenario (pending) — real
  captures, gate-framed per the discussion above, run through the full
  pipeline rather than only unit-level fixtures.
- Synthetic variants: different struct/switch shapes; at least one ordinary
  page with no split layout at all (confirms zero behavior change); at least
  one deliberately ambiguous case (two candidate regions equally fit the same
  open depth) to confirm the fallback correctly declines to reorder.
- Full regression run against the existing `test_ocr_pipeline.py` suite
  (currently part of the 93-test full suite) — this feature must not change
  any currently-passing case.
- `evaluate_cer` before/after on the real `samples/` set — expected to show
  no regression (feature is a no-op there, no split-layout pages currently
  exist in that set) but confirms nothing else broke.

## Rollout

1. Implement Phase 1 (region separation) first — smaller, lower-risk, and a
   real improvement on its own even before Phase 2 exists (stops garbled
   fusion).
2. Add tests for Phase 1 using the two example fixtures — confirm regions
   are correctly separated (not yet correctly reordered).
3. Implement Phase 2 (brace-depth reassembly) on top.
4. Add the full fixture set (examples + synthetic + ambiguous case) and
   confirm correct reassembly on the two motivating examples.
5. Run full regression (`run_tests.py`) and `evaluate_cer` — confirm zero
   change on all currently-passing cases.
6. Once user-provided real handwriting photos arrive, run them through the
   full pipeline (not just unit fixtures) and record real results —
   including honest reporting if real handwriting proves messier than the
   clean typed-out examples (e.g., ambiguous or partially-legible brace
   characters triggering the fallback more often than the fixtures suggest).
