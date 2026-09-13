# Real handwriting margin validation — 2026-09-13

All three photographs now read the left column top-to-bottom followed by the margin block. A already worked; B/C are fixed by changing **`BAND_GUTTER_MIN_MULTIPLIER` from 1.5 to 0.5**. **`REGION_GAP_MULTIPLIER` remains 0.75**: lowering the trace-seed threshold did not fix either photo. No recognition payload was changed. Brace reassembly still makes no move, despite **16/16 physical braces surviving recognition**.

## Inputs and measurement method

The three original 1536×2048 JPEGs were copied byte-for-byte into ignored `outputs/real_margin_validation/inputs/` as `writerX_marginA.jpg` (switch, supplied `Unknown-3.jpg`), B (for-loop, `Unknown-2.jpg`), and C (nested if/while, `Unknown.jpg`). Original hashes and recognizer weight hash are in the [machine-readable audit](2026-09-13-real-margin-validation.json). No screenshot was submitted to OCR. The screenshots describe intended order; their writing instructions are reference material, not additional task commands or authoritative transcriptions of these photographs.

Both live runs called `core.ocr_pipeline.extract_text_from_image` with the default preprocessing and fine-tuned recognizer. Preprocessing resized each original to **1200×1600**, without a page crop or perspective warp. All fixture boxes below are **processed-image** `[x0,y0,x1,y1]`; multiply any coordinate/distance by **1.28** for its original-photo equivalent. Original-pixel gutter values are scaled detection bounds, not independently segmented ink edges.

Median width follows the actual implementation: `sorted(x1-x0)[len(boxes)//2]` (upper median for even counts), including every retained detection. The global cross-region gap is `min(margin.x0) - max(left.x1)` across the independently identified handwritten columns. Banded gap restricts left detections to those intersecting the margin's entire bounding y-band; it is a different measurement and must not be confused with the full-page gap.

## Confirmed gaps

| Photo | Median width, processed px | Left right edge → margin left edge | Global gap, processed px | Global gap, original px | Global gap / median | Band gap, processed px | Band gap / median |
|---|---:|---:|---:|---:|---:|---:|---:|
| writerX_marginA | 120 | 688 → 845 | 157 | 200.96 | 1.308 | 167 | 1.392 |
| writerX_marginB | 189 | 802 → 869 | 67 | 85.76 | 0.354 | 108 | 0.571 |
| writerX_marginC | 138 | 782 → 830 | 48 | 61.44 | 0.348 | 171 | 1.239 |

Band y-ranges are A `[262,500]`, B `[247,398]`, C `[240,437]`. Band left right edges are 678, 761, 659 px; band gaps in original pixels are **213.76, 138.24, 218.88**. This explains why the tightest full-page gutter C can have a wider band gutter than B: C's longest left line lies below the right block.

**Same-line, within-column gap distribution:** A `n=0`, B `n=0`, C `n=0`; pooled `n=0`. Every surviving handwritten line is one detection box. Consequently min, median, percentiles and max in either pixels or width multiples are **undefined**, not zero. These captures cannot reproduce the positive same-line-vs-cross-region distribution behind the original 0.75 calibration. Distances between different handwritten rows are not same-line gaps. In particular, B's grouped 256px gap from the fabric detection `dd;` to the array line is not a confirmed within-column handwriting gap and is excluded from this measurement (but the detection is retained in output).

## Which mechanism fired

Instrumentation wraps `_group_detection_records` **in `core.layout`**, where `_group_structured_lines` resolves it, and wraps its detector/reassembly call sites. “Accepted” means a detector returned a split; “moved” means the returned sequence/grouping differed. A helper call alone does not count as firing. Full before/after event lists are in the audit JSON.

| Photo | Before: two-column | Before: banded | Before: trace flags | Before: severance moved | Before: brace moved | After: active ordering |
|---|---|---|---:|---|---|---|
| A | Accepted, x=766.5 | Not called | 0 | Not called | No (2 calls) | Two-column, unchanged |
| B | Declined | Declined | 3 detections: 0,2,4 | No | No (1 call) | Banded, x=815.0 |
| C | Declined | Declined | 0 | No | No (1 call) | Banded, x=744.5 |

After calibration, B/C skip severance and each calls brace reassembly twice (once per column), both no-ops with zero flagged lines. B's within-left-column trace is called once and confirms zero detections; C's is not called. `_group_detection_records` reports safe geometry on all six live calls.

The two-column height gate is evaluated against detected content, not the entire 1600px canvas. Right-column center span / detected page span is A **195/357 = 0.546**, B **112/292 = 0.384**, C **149/300 = 0.497**; the minimum is 0.5. The fabric false positive above C's writing increases its detected span. B/C are therefore appropriate partial-height banded cases. Do not lower the full-height gate or remove the fabric detections to make these examples pass.

## Brace survival and remaining recognition errors

| Photo | Physical `{` / `}` | Correctly recognized `{` / `}` | Survival | Detection IDs containing the matching braces |
|---|---|---|---|---|
| A | 2 / 2 | 2 / 2 | 4/4 (100%) | Open: 2,6; close: 5,10 |
| B | 3 / 3 | 3 / 3 | 6/6 (100%) | Open: 3,5,9; close: 5,0,6 |
| C | 3 / 3 | 3 / 3 | 6/6 (100%) | Open: 4,8,10; close: 1,5,9 |

Counts were matched to the physical handwritten lines, not inferred from balanced OCR counts. B includes **both initializer braces** in detection 5; the other four are scope braces. A's first closing brace survives at confidence **0.373**, just above the existing 0.3 recognition floor. No brace was dropped by that filter. A's crossed-out line yielded empty text at score 0 and was filtered by the existing pipeline; another empty background detection was also filtered. B/C dropped no low-confidence detections. This change adds no filtering.

Before calibration, B's trace flags the first three margin detections but not its final closing brace (6). The unflagged final close is merged into the array line, leaving a negative-delta normal line; the brace-reassembly guard declines. C's right block drifts left: its middle closing brace ends exactly at the current right boundary (913px), is treated as left by the existing trace, and collapses the candidate gutter, so no block is flagged. In both, staggered standalone rows interrupt severance's required run of three candidate rows. Lowering the seed does not repair these conditions.

Thus these photos **do demonstrate viable brace recognition**, but **do not demonstrate live brace-based reassembly**. Recognition is necessary but not sufficient for that path. Geometric column ordering fixes these cases without using the recognized braces. OCR spelling errors and the retained `dd;`/`od;` fabric detections remain teacher-verification work; the margin fix does not repair them.

## Detection boxes and exact extraction

IDs are zero-based positions in the committed list-of-`{text,score,box}` fixtures. `L` = handwritten left column, `R` = margin, `F` = outside-paper fabric false positive. The fixture holds full confidence precision; tables round it for readability. Intended row IDs were independently annotated against the photos. Fabric is retained; B's fabric token remains alongside the array line and C's remains first.

### writerX_marginA

[Detection fixture](../tests/fixtures/writerX_marginA_detections.json)

| ID | Region | Box (processed px) | Score | Recognized text, verbatim |
|---:|---|---|---:|---|
| 0 | L | `[276, 271, 542, 311]` | 0.992 | `#include <stdio.h>` |
| 1 | R | `[885, 262, 981, 304]` | 0.979 | `depault` |
| 2 | L | `[336, 315, 557, 346]` | 0.993 | `int main(void) {` |
| 3 | R | `[907, 315, 1120, 373]` | 0.948 | `printf("none\n");` |
| 4 | L | `[409, 357, 548, 384]` | 0.998 | `int n = 2` |
| 5 | R | `[885, 373, 911, 412]` | 0.373 | `}` |
| 6 | L | `[410, 388, 576, 422]` | 0.965 | `swstch (n) {` |
| 7 | R | `[899, 406, 1019, 446]` | 0.956 | `return 0;` |
| 8 | L | `[409, 431, 509, 459]` | 0.918 | `case 1` |
| 9 | L | `[475, 440, 678, 486]` | 0.959 | `printf("onte\n");` |
| 10 | R | `[845, 456, 871, 500]` | 0.726 | `}` |
| 11 | L | `[481, 483, 568, 518]` | 1.000 | `break;` |
| 12 | L | `[410, 524, 518, 553]` | 0.909 | `case 2;` |
| 13 | L | `[477, 525, 688, 582]` | 0.966 | `printf("two\n");` |
| 14 | L | `[484, 579, 571, 619]` | 0.947 | `breask;` |

Before row IDs: `[[0], [2], [4], [6], [8], [9], [11], [12], [13], [14], [1], [3], [5], [7], [10]]`.

Intended and final row IDs: `[[0], [2], [4], [6], [8], [9], [11], [12], [13], [14], [1], [3], [5], [7], [10]]`.

Final raw extraction (unchanged from before):

```text
#include <stdio.h>
  int main(void) {
      int n = 2
      swstch (n) {
      case 1
          printf("onte\n");
          break;
      case 2;
          printf("two\n");
          breask;
  depault

  printf("none\n");
  }
  return 0;
}
```

`cleaned_text` is identical to this raw extraction.
### writerX_marginB

[Detection fixture](../tests/fixtures/writerX_marginB_detections.json)

| ID | Region | Box (processed px) | Score | Recognized text, verbatim |
|---:|---|---|---:|---|
| 0 | R | `[918, 247, 945, 284]` | 0.974 | `}` |
| 1 | L | `[301, 260, 571, 310]` | 0.938 | `# include <stdio.h>` |
| 2 | R | `[919, 275, 1108, 313]` | 0.937 | `printf("%d\n", sunt);` |
| 3 | L | `[333, 311, 557, 351]` | 0.991 | `int main(void) {` |
| 4 | R | `[914, 309, 1032, 351]` | 0.974 | `return 0;` |
| 5 | L | `[415, 346, 761, 402]` | 0.940 | `int a[5] = {2, 4, 6, 8, 70};` |
| 6 | R | `[869, 357, 898, 398]` | 0.705 | `}` |
| 7 | F | `[119, 372, 159, 390]` | 0.689 | `dd;` |
| 8 | L | `[421, 404, 598, 443]` | 0.995 | `int sum = 0;` |
| 9 | L | `[423, 427, 802, 487]` | 0.969 | `for (int i = 0; i < 5; i++) {` |
| 10 | L | `[456, 489, 675, 539]` | 0.982 | `sum + = a[i];` |

Before row IDs: `[[0], [1], [2], [4], [3], [7, 5, 6], [8], [9], [10]]`.

Intended and final row IDs: `[[1], [3], [7, 5], [8], [9], [10], [0], [2], [4], [6]]`.

Before calibration, raw extraction:

```text
                }
        # include <stdio.h>
                printf("%d\n", sunt);
                return 0;
          int main(void) {
dd; int a[5] = {2, 4, 6, 8, 70}; }
              int sum = 0;
              for (int i = 0; i < 5; i++) {

                sum + = a[i];
```

Final raw extraction:

```text
        # include <stdio.h>
          int main(void) {
dd; int a[5] = {2, 4, 6, 8, 70};
              int sum = 0;
              for (int i = 0; i < 5; i++) {
                sum + = a[i];
  }
  printf("%d\n", sunt);
  return 0;
}
```

Final `cleaned_text`:

```text
#include <stdio.h>
          int main(void) {
dd; int a[5] = {2, 4, 6, 8, 70};
              int sum = 0;
              for (int i = 0; i < 5; i++) {
                sum + = a[i];
  }
  printf("%d\n", sunt);
  return 0;
}
```
The `# include` normalization is existing cleanup behavior, not part of this calibration.
### writerX_marginC

[Detection fixture](../tests/fixtures/writerX_marginC_detections.json)

| ID | Region | Box (processed px) | Score | Recognized text, verbatim |
|---:|---|---|---:|---|
| 0 | F | `[33, 217, 71, 241]` | 0.698 | `od;` |
| 1 | R | `[929, 240, 962, 285]` | 1.000 | `}` |
| 2 | L | `[254, 252, 515, 294]` | 0.973 | `# inclde <stdio.h>` |
| 3 | R | `[913, 282, 987, 316]` | 0.997 | `x++;` |
| 4 | L | `[297, 297, 514, 336]` | 0.969 | `int main(void) {` |
| 5 | R | `[876, 306, 913, 353]` | 0.631 | `}` |
| 6 | L | `[349, 346, 487, 377]` | 0.978 | `int x = 1;` |
| 7 | R | `[876, 347, 1005, 388]` | 0.906 | `return 0;` |
| 8 | L | `[358, 376, 571, 420]` | 0.968 | `while (+ <= 3) {` |
| 9 | R | `[830, 386, 861, 437]` | 0.967 | `}` |
| 10 | L | `[411, 418, 659, 467]` | 0.995 | `if (x % 2 == 0) {` |
| 11 | L | `[460, 454, 782, 517]` | 0.924 | `printf("even %d\n", x);` |

Before row IDs: `[[0], [2, 1], [4, 3], [5], [6, 7], [8, 9], [10], [11]]`.

Intended and final row IDs: `[[0], [2], [4], [6], [8], [10], [11], [1], [3], [5], [7], [9]]`.

Before calibration, raw extraction:

```text
od;
          # inclde <stdio.h> }
            int main(void) { x++;
                }
              int x = 1; return 0;
              while (+ <= 3) { }
                if (x % 2 == 0) {
                printf("even %d\n", x);
```

Final raw extraction:

```text
od;
          # inclde <stdio.h>
            int main(void) {
              int x = 1;
              while (+ <= 3) {
                if (x % 2 == 0) {
                printf("even %d\n", x);
    }
    x++;
  }
  return 0;
}
```

`cleaned_text` is identical to this raw extraction.

## Calibration decision and safety gates

- Keep `REGION_GAP_MULTIPLIER=0.75` and `BASELINE_REGION_GAP_MULTIPLIER=6.0`. Frozen replay at region multipliers **0, 0.1, 0.25, 0.5, 0.75, 1, 1.5** produces the same order on all three photographs with the old band setting. At 6.0 B's grouping changes but still interleaves its columns. This knob is not the fix, and there is no measured within-line sample supporting a new seed value.
- Change only `BAND_GUTTER_MIN_MULTIPLIER`: **1.5 → 0.5**. The former required B 283.5px and C 207px despite confirmed band gutters of 108px and 171px. The new thresholds are **94.5px** and **69px**, respectively. The tightest confirmed band ratio is B's 0.571; 0.5 leaves a 13.5px margin. The **60px floor**, **3 distinct rows**, **2.0× x-alignment tolerance**, and uncrossed-band requirement remain.
- Keep `SEVER_GAP_MULTIPLIER=0.8`, `SEVER_X_ALIGN_MULTIPLIER=1.2`, `MIN_SEVER_ROWS=3`, `MIN_COLUMN_LINES=4`, and `MIN_COLUMN_VSPAN_FRACTION=0.5`. B/C are now handled before severance. No detection, recognition, preprocessing, cleanup, character-editing, or submission-flow logic changed.

Frozen comparison of old 1.5 vs new 0.5 across **315 pre-existing debug artifacts (262 distinct detection payloads)** changed **zero complete grouping results**, including text, geometry and indentation metadata. These are artifact counts, not 315 independent writers/pages; the local manifest and its digest are recorded in the audit. The three new captures are excluded from that historical count. Both live photo runs produced identical text/score/box lists, checked against the committed fixtures. The replay tests compare the complete detection multiset, including fabric tokens.

The initial 0.5 trial exposed two subcase failures in `DynamicGutterGroupingTests.test_confirmed_window_respects_line_count_cap`: banded detection intercepted its synthetic 12/13-row cases before the trace under test. The trace-only helper now disables banded detection in addition to its existing brace/severance bypasses. **No cap assertion, input box, or limit was changed**: 12 is still accepted, 13 still rejected. Integration tests separately assert actual two-column/banded paths on all three real photographs with brace reassembly disabled. New boundary tests verify that 59px is rejected / 60px accepted under the pixel floor, and 99px rejected / 100px accepted for median width 200px.

TDD evidence: with the old constant, the new B/C order assertions and B/C mechanism checks fail (four failures/subcases); with the one-constant change all pass. The old setting remains an explicit regression reproduction in the tests. A's assertion also fails when all geometric ordering is disabled. There are **no skipped or expected-failure tests** in the final suite.

Live baseline and calibrated runs both evaluated all 20 held-out samples:

| Metric | Before | After |
|---|---:|---:|
| clean_ws CER | 0.099 | 0.099 |
| clean WER | 0.328 | 0.328 |
| clean token accuracy | 0.716 | 0.716 |
| green_writer10 clean_ws CER | 0.061 | 0.061 |

The complete printed per-file and aggregate evaluator tables match, not only the rounded headline metrics. Full Python suite: **157 passed** (original 148 + 9). No Angular files changed.

Scope limit: these are three controlled scenarios from one pseudonymous writer, with no same-line multi-box samples. The unchanged historical replays and held-out gates support this narrow band adjustment; they do not establish universal separation thresholds or prove brace reassembly on arbitrary handwriting. Keep the existing grade-safe geometry guards and teacher verification.

## Follow-up: brace-assisted missed-candidate fallback

After the validation discussion, the pipeline gained a narrow fallback for the adjacent case these photos exposed: OCR can read the braces correctly while strict geometry still fails to mark the exact continuation block. The A/B/C photos themselves remain geometric successes (A full two-column, B/C banded); the new fallback is for single-column pages where those paths and severance leave the order unchanged.

`_reassemble_margin_candidates` proposes only whole-line right-margin clusters that are visibly right-shifted, x-aligned, and separated by a positive local gutter. It then marks that proposed cluster as `severed_by_gap` and reuses `_reassemble_displaced_regions`; the move is accepted only when exactly one candidate produces a brace-balanced order and preserves the same line identities. Ambiguous tail placement, crossed geometry, missing boxes, no closing-brace signal, or multiple possible moves decline to current behavior.

This still does not correct OCR symbols. If a handwritten `}` is recognized as `)`, the fallback does not edit it into `}` and should not treat the candidate as proven. The added tests cover both sides: readable braces can prove a missed right-margin continuation, while the same layout with a misread closing brace stays in visual order.

Fresh verification after this follow-up: full OCR unit suite **159 passed**; live `evaluate_cer` stayed at clean_ws CER **0.099**, clean WER **0.328**, clean token accuracy **0.716**, and green_writer10 clean_ws **0.061**. A fallback-disabled vs enabled replay over the existing **315 debug artifacts / 262 distinct detection payloads** changed **zero** groupings, so the new path did not affect the stored historical corpus.

## Reproduction

From `ocr_feature/`:

```bash
.venv/bin/python -m unittest tests.test_ocr_pipeline.BraceAssistedMarginCandidateTests -v
.venv/bin/python -m unittest tests.test_real_margin_layout -v
.venv/bin/python -m unittest discover -s tests
PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_cer
```

The fixtures replay without the OCR runtime. For live extraction on local pseudonymous copies, instrument the module owning the call sites (patching an `ocr_pipeline` re-export will not intercept internal layout calls):

```python
from contextlib import ExitStack
from unittest.mock import patch
from core import layout, ocr_pipeline

def trace(name, original):
    def wrapped(*args, **kwargs):
        before = None
        if name in ("_reassemble_displaced_regions", "_sever_displaced_regions"):
            before = [[(m["text"], m["x"], m["y"]) for m in row["members"]]
                      for row in args[0]]
        result = original(*args, **kwargs)
        if before is not None:
            after = [[(m["text"], m["x"], m["y"]) for m in row["members"]]
                     for row in result]
            print(name, "moved:", before != after)
        elif name == "_group_detection_records":
            print(name, "safe:", result[1], "rows:", result[0])
        else:
            print(name, "result:", result)
        return result
    return wrapped

with ExitStack() as stack:
    for name in ("_group_detection_records", "_detect_two_columns",
                 "_detect_banded_column", "_trace_displaced_region",
                 "_reassemble_displaced_regions", "_sever_displaced_regions"):
        stack.enter_context(patch.object(layout, name,
            side_effect=trace(name, getattr(layout, name))))
    for letter in "ABC":
        result = ocr_pipeline.extract_text_from_image(
            f"outputs/real_margin_validation/inputs/writerX_margin{letter}.jpg",
            output_dir="outputs/real_margin_validation/reproduction")
        print(letter, result["raw_text"], result["cleaned_text"], sep="\n")
```

To reproduce the pre-calibration paths, wrap this run in `patch.object(layout, "BAND_GUTTER_MIN_MULTIPLIER", 1.5)`. The original photos and generated preprocessing/debug files remain local and ignored; immutable detection fixtures, this report and its audit JSON are committed. Full local logs use `/tmp/reading-order-{baseline,calibrated}-cer.log`, `/tmp/reading-order-calibrated-tests.log`, and `/tmp/reading-order-calibrated-photos.log`.
