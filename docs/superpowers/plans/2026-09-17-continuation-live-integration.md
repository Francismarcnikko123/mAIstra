# Conservative Continuation Association Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the five documented reading-order expected failures pass through the live OCR layout pipeline while preserving every recognized detection and abstaining on ambiguous layouts.

**Architecture:** Add a pure `core.continuation` module that accepts immutable detection records plus the current layout order and returns an evidence report and, only for uniquely supported continuation links, a reordered detection-ID sequence. Keep row construction, indentation, and public compatibility in `core.layout`; route every successful full-column, banded, and single-column result through one finalizer so no early return bypasses association. The frozen evaluator prototype remains unchanged as historical evidence.

**Tech Stack:** Python standard library, existing `core.layout` geometry, `unittest`, frozen JSON detection fixtures, existing OCR CER/WER/token evaluator.

---

### Task 1: Convert production acceptance markers into failing tests

**Files:**
- Modify: `ocr_feature/tests/test_continuation_planning.py`
- Modify: `ocr_feature/tests/test_continuation_development.py`

- [ ] **Step 1: Remove the five `@unittest.expectedFailure` decorators**

  Keep the existing exact-order assertions unchanged. Update the column-bypass characterization test to patch `layout._associate_continuation` and assert it is called for a full-column page while banded and legacy brace fallback remain bypassed.

- [ ] **Step 2: Run the focused tests and record the red state**

  Run from `ocr_feature`:

  ```sh
  PYTHONPATH=. .venv/bin/python -m unittest \
    tests.test_continuation_planning \
    tests.test_continuation_development -v
  ```

  Expected: exactly the five intended-order assertions fail before production integration; preservation and frozen-fixture checks pass.

- [ ] **Step 3: Commit the red acceptance tests**

  ```sh
  git add ocr_feature/tests/test_continuation_planning.py \
    ocr_feature/tests/test_continuation_development.py
  git commit -m "test(ocr): require live continuation association"
  ```

### Task 2: Add the pure continuation decision module

**Files:**
- Create: `ocr_feature/core/continuation.py`
- Create: `ocr_feature/tests/test_continuation.py`

- [ ] **Step 1: Add direct unit tests for the decision contract**

  Cover these exact rules with synthetic detections and frozen real fixtures:

  ```python
  result = associate_continuation(records, baseline_ids)
  self.assertEqual(sorted(result["ordered_ids"]), list(range(len(records))))
  self.assertEqual(records, untouched)
  ```

  Required cases: Examples 5/6/8 produce the annotated order; distinct numbered headings are independent; two unnumbered complete functions abstain; a misread closer abstains; braces inside comments/literals do not count; unterminated literals abstain; invalid geometry preserves baseline; scaling does not change decisions; repeated payloads retain distinct IDs; narrow gutters abstain; competing blocks abstain.

- [ ] **Step 2: Run the new tests and verify the module is missing**

  ```sh
  PYTHONPATH=. .venv/bin/python -m unittest tests.test_continuation -v
  ```

  Expected: import failure for `core.continuation`.

- [ ] **Step 3: Implement a layout-independent association function**

  Create `associate_continuation(records, baseline_ids)` with this contract:

  ```python
  {
      "ordered_ids": list[int],
      "baseline_ids": list[int],
      "changed_order": bool,
      "status": "supported" | "ambiguous",
      "blocks": list[dict],
      "relations": list[dict],
      "reasons": list[str],
  }
  ```

  Validate IDs, text, scores, and finite positive boxes before analysis. Discover one unique uncrossed global gutter, split each side into local vertical bands, and require one unique overlapping left target for each right band. Require a local gutter of at least `2.0 * median_box_height`. Distinct recognized question numbers or two recognized `main(` entries support independence. Literal/comment-masked brace evidence may support continuation only when the left block has an open scope, the right block closes scope without underflowing the combined prefix, and there is no competing insertion target. Every invalid, conflicting, or incomplete case returns the supplied baseline order unchanged.

  The module must not import `core.layout`, inspect answer labels, invoke a compiler, or modify text, scores, or boxes.

- [ ] **Step 4: Run direct association tests**

  ```sh
  PYTHONPATH=. .venv/bin/python -m unittest tests.test_continuation -v
  ```

  Expected: all direct association tests pass.

- [ ] **Step 5: Commit the pure decision module**

  ```sh
  git add ocr_feature/core/continuation.py ocr_feature/tests/test_continuation.py
  git commit -m "feat(ocr): add conservative continuation association"
  ```

### Task 3: Integrate association into every live layout path

**Files:**
- Modify: `ocr_feature/core/layout/__init__.py`
- Modify: `ocr_feature/core/layout/reorder.py`
- Modify: `ocr_feature/tests/test_ocr_pipeline.py`
- Modify: `ocr_feature/tests/test_continuation_planning.py`

- [ ] **Step 1: Add finalizer-focused tests**

  Test that the finalizer:

  - maps each internal detection ID exactly once;
  - keeps members of an existing visual row together;
  - applies only a complete permutation returned by association;
  - returns the original rows if IDs are missing, duplicated, or split a visual row;
  - preserves every member dictionary verbatim;
  - calls association from full-column, banded, and single-column success paths.

- [ ] **Step 2: Run the finalizer and five acceptance tests red**

  ```sh
  PYTHONPATH=. .venv/bin/python -m unittest \
    tests.test_continuation_planning \
    tests.test_continuation_development \
    tests.test_ocr_pipeline -v
  ```

  Expected: finalizer/call assertions and the five intended orders fail.

- [ ] **Step 3: Add stable internal IDs and one shared finalizer**

  In `_group_detection_records`, create a local identity map from each member object's `id(...)` to its original recognition index; do not add internal keys to returned member dictionaries. Add `_associate_continuation(rows, original_records, detection_ids_by_member)` which:

  1. flattens current row IDs as the baseline;
  2. calls `associate_continuation`;
  3. verifies the proposed IDs are an exact permutation;
  4. verifies every pre-existing row remains contiguous in the proposal;
  5. sorts whole rows by the proposed rank while retaining x-order inside each row;
  6. returns the original rows on any validation failure.

  Add `_finalize_grouped_lines(lines, median_char_width, original_records, detection_ids_by_member)` to assign indentation, convert line dictionaries to member rows, and invoke `_associate_continuation`. Replace the duplicated finalization in full-column, banded, and single-column branches with this helper. Do not change detector thresholds, returned member dictionaries, or character content.

  Re-export the new package-level helpers from `core/layout/reorder.py` for compatibility. Extend the model-free package loader in `tests/test_ocr_pipeline.py` to load `core.continuation` before `core.layout`.

- [ ] **Step 4: Run focused live integration tests**

  ```sh
  PYTHONPATH=. .venv/bin/python -m unittest \
    tests.test_continuation \
    tests.test_continuation_planning \
    tests.test_continuation_development \
    tests.test_real_margin_layout \
    tests.test_ocr_pipeline -v
  ```

  Expected: all tests pass with no expected failures in the continuation suites.

- [ ] **Step 5: Commit live integration**

  ```sh
  git add ocr_feature/core/layout/__init__.py \
    ocr_feature/core/layout/reorder.py \
    ocr_feature/tests/test_ocr_pipeline.py \
    ocr_feature/tests/test_continuation_planning.py
  git commit -m "feat(ocr): associate margin continuations in live layout"
  ```

### Task 4: Guard independent pages and historical ordering

**Files:**
- Modify: `ocr_feature/tests/test_continuation.py`
- Modify: `ocr_feature/tests/test_real_margin_layout.py`
- Modify: `ocr_feature/tests/test_continuation_development.py`

- [ ] **Step 1: Add live negative-control assertions**

  Replay Examples 1/2/4/9/11 and `green_writer10_detections.json` through live grouping. Assert their exact existing orders remain unchanged. Replay A/B/C margin fixtures and assert their documented left-then-margin orders remain unchanged. Assert the output detection multiset equals the input multiset for every fixture.

- [ ] **Step 2: Run all continuation and real-layout tests**

  ```sh
  PYTHONPATH=. .venv/bin/python -m unittest \
    tests.test_continuation \
    tests.test_continuation_planning \
    tests.test_continuation_development \
    tests.test_continuation_prototype \
    tests.test_real_margin_layout -v
  ```

  Expected: all tests pass and the frozen prototype tests remain unchanged.

- [ ] **Step 3: Commit regression controls**

  ```sh
  git add ocr_feature/tests/test_continuation.py \
    ocr_feature/tests/test_real_margin_layout.py \
    ocr_feature/tests/test_continuation_development.py
  git commit -m "test(ocr): guard continuation association boundaries"
  ```

### Task 5: Run full regression and OCR metric gates

**Files:**
- No source changes unless a gate exposes a defect.

- [ ] **Step 1: Run the full Python suite**

  ```sh
  PYTHONPATH=. .venv/bin/python -m unittest discover -s tests
  ```

  Expected: all tests pass with zero expected failures.

- [ ] **Step 2: Replay the development and frozen reserved evaluators**

  ```sh
  PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_development
  PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_reserved
  ```

  Expected: development Examples 5/6/8 now have exact live order; frozen reserved fixture hashes remain valid; no fixture or frozen prototype file changes.

- [ ] **Step 3: Run live OCR evaluation**

  ```sh
  PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_cer
  ```

  Expected metric gates: clean_ws CER `0.099`, clean WER `0.328`, clean token accuracy `0.716`, and `green_writer10` clean_ws CER `0.061`. Inspect every changed per-page transcription; only detection order may differ.

- [ ] **Step 4: Check patch hygiene**

  ```sh
  git diff --check
  git status --short
  ```

  Expected: no whitespace errors; only intended code, tests, and documentation are changed.

### Task 6: Record the live behavior and its limits

**Files:**
- Modify: `docs/PROJECT_OVERVIEW_AND_CHANGES.md`
- Modify: `ocr_feature/reports/2026-09-14-continuation-association-plan.md`
- Modify: `ocr_feature/reports/2026-09-14-offline-association.md`

- [ ] **Step 1: Update documentation from verified outputs**

  Record the exact test count, zero remaining expected failures, development orders, reserved replay result, and OCR metrics. Explain that continuation association is a conservative reading-order heuristic, does not repair OCR characters, does not grade code, and abstains when evidence is ambiguous. Retain the one-writer limitation and recommend additional-writer evaluation before making broad accuracy claims.

- [ ] **Step 2: Re-run documentation-sensitive checks**

  ```sh
  rg -n "expected failures|not ready for automatic live integration|production behavior remains unchanged" \
    docs/PROJECT_OVERVIEW_AND_CHANGES.md ocr_feature/reports
  git diff --check
  ```

  Expected: historical passages are explicitly dated as historical; current-status passages describe the verified live implementation without contradictory claims.

- [ ] **Step 3: Commit documentation**

  ```sh
  git add docs/PROJECT_OVERVIEW_AND_CHANGES.md \
    ocr_feature/reports/2026-09-14-continuation-association-plan.md \
    ocr_feature/reports/2026-09-14-offline-association.md
  git commit -m "docs(ocr): record live continuation association"
  ```
