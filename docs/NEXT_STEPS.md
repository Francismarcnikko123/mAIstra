# OCR — Current State and Next Steps

## Integration update — 2026-09-24 (supersedes the optional-work note below)

Pre-extraction on arrival is implemented and pushed on `feature/pre-extraction`,
off by default. The web shows **Extracting…** for eligible new papers and
updates to **Needs review** when the worker saves, without a reload. The
phone-photo, server-off and restart catch-up live checks passed. At that
checkpoint OCR tests passed 231/231, web tests passed 114/114, and the OCR
accuracy metrics below were unchanged. The next OCR *accuracy* step remains
new bond and yellow pad datasets. Nikko owns mobile `question_id`; Jayrald
owns the cloud schema/migrations for the complete question-linking flow.
See [the implementation plan](superpowers/plans/2026-09-24-pre-extraction-on-arrival.md)
and [TEAM_SYNC.md](TEAM_SYNC.md).

## Current status — 2026-09-23 (supersedes earlier status blocks)

**Waiting on data, not code.** The OCR pipeline, reading-order/continuation layer
and tests are complete for now: 207 tests pass (zero expected failures) and the
live evaluator shows clean_ws CER 0.099, clean WER 0.328, clean token
accuracy 0.716, `green_writer10` 0.061. **The next step is the incoming bond paper
and yellow pad datasets.**

Why these two paper types: they are the evaluation gap named in
`ocr/LIMITATIONS.md`. Current data (checked 2026-09-23):

| Set | greenbook | bond | yellow | Total |
|---|---|---|---|---|
| `datasets/verified/` (train) | 131 | 20 | 17 | 168 |
| `samples/` (held-out test) | 14 | 2 | 4 | 20 |

Greenbook test writers are writer-disjoint (8/9). The bond (2) and yellow (4)
test pages come from writers also seen in training, so **new-writer CER on bond and
yellow is unmeasured**. The new batches should add *new* writers, ideally with
more varied C constructs (structs, pointers, switch, arrays) as well.

When the datasets arrive, in order:

1. Physically verify each `.txt` against its paper. Use writer pseudonyms only.
   **Naming (user decision 2026-09-23):** continue the existing scheme and never
   rename files that were already trained on:

   | Paper | Existing (leave alone) | New batch starts at |
   |---|---|---|
   | Greenbook | `green_writerN_B1..B3_page`; legacy unbatched `green_writer1/2/3` | `green_writer1_B4_1.jpg`. B4 is next, writer numbers restart at 1 per batch, and batch numbers are never reused |
   | Bond | `bond_writer1..4_page` (no batch) | `bond_writer5_1.jpg`: continue numbering, no batch |
   | Yellow pad | `yellow_writer1..4_page` (no batch) | `yellow_writer5_1.jpg`: continue numbering, no batch |

   Each `writerN` must be a *new* student. A returning student keeps their
   existing number. For greenbook, "the same student" means the same number
   *and* batch.

   **The 7 `dataset_review/deferred_needs_line_exclusion/` pages are EXCLUDED
   from this batch (user decision 2026-09-23).** A read-only check that day found:
   - **No duplicates.** None is a byte copy of any of the 524 images. A visual
     match scored 7–9 matching points against every image, versus 296–1,630 for
     a known photo-to-cropped-copy pair.
   - **All are likely existing writers, not new ones.** Neighboring photos in the
     camera sequence map to B1–B3 writers: `IMG_0308` ≈ `green_writer2_B3`;
     `IMG_0290` ≈ `green_writer13_B2` (**test set**); `IMG_0279` is between
     `writer9_B2` and `writer10_B2` (**test set**); the rest are uncertain.
     Adding them risks leaking test-set writers into training, and they add no
     writer diversity.

   The photos stay where they are, and no per-line exclusion manifest is needed.
   If they are ever used, a person with the physical papers must first confirm
   each page's writer. Test-set writers' pages go to `samples/` or are skipped,
   never to training.
2. Import from `ocr_feature/`:
   `python import_verified_batch.py --verified-by "<name>"`. This populates
   `literal_verified*`. Today, 0 of the 168 existing verified rows have
   provenance, because they predate those columns.
3. Add the deferred `writer_id` column to both `labels.csv` files, for old and new
   rows together. Unbatched files map to B0. Do not rename image files. (Still
   absent in both CSVs as of 2026-09-23.)
4. Earmark some new bond/yellow writers as **test-only** so both paper types get
   a writer-disjoint holdout. Note: `select_holdout.py` currently holds out
   individual bond/yellow *pages*, not whole writers, because there were too few
   writers. It must be updated to whole-writer selection for these types before
   `--apply`. Always dry-run it first.
5. Rebuild crops (`evaluators/build_recognition_dataset.py`), retrain on
   Colab, and compare against the shipped model on the **same** test set. Do not
   compare numbers across different test sets.
6. If new constructs add keywords/symbols, extend the closed vocabulary in
   `core/c_code_cleanup.py` so they are preserved.

**Historical proposal (earlier 2026-09-24; now implemented):** pre-extraction on arrival.
A polling worker next to the OCR server fills `extracted_text` before the teacher
opens a paper. Design: `superpowers/specs/2026-09-11-pre-extraction-on-submission-design.md`
(see its 2026-09-24 addendum). It uses the same pipeline and doesn't change
accuracy numbers. It needs Jayrald's OK for the server-side key, and for any
provenance columns.

## Status — 2026-09-17 (superseded by the block above)

The conservative production derivative of the frozen association prototype is now
active in `core/continuation.py` and the live full/banded column finalizer. FastAPI
and the web app receive this ordering automatically through
`extract_text_from_image`. All eight development pages match their annotated order,
all detections survive, and the five former expected failures now pass. Current
production regression remains clean_ws CER 0.099, clean WER 0.328, clean token
accuracy 0.716, and green_writer10 clean_ws 0.061. The frozen prototype and
`tests/manual_continuation.py` remain available for offline comparison. Reserved
Example 10 is outside the live column gate, and the supplied pages represent one
writer; the next evidence step is evaluation on additional writers without tuning
against the reserved set. Details and measured limits: [session handoff](../ocr_feature/reports/2026-09-14-continuation-session-handoff.md).

Written so anyone (or any AI tool) can pick this up without needing it
explained verbally. Start here, then go to the linked docs for detail.

**Scope note:** this doc covers `ocr_feature` only. For the web verification
widget (`maistra_web`) — including the "Format" button (brace-depth
indentation, committed `9c719f3`, 2026-08-11) — see
[`web/VERIFICATION_UI.md`](web/VERIFICATION_UI.md) (chronological bug log) or
[`web/WEB_CODEBASE_GUIDE.md`](web/WEB_CODEBASE_GUIDE.md) (current-code
reference).

> ## 🔵 CURRENT STATUS 2026-09-08 (read this first — supersedes the 2026-09-06 block below)
>
> - **Reading-order reassembly feature built on `feature/reading-order-reassembly`
>   (branched off `ocr_feature`, not yet merged, not yet pushed).** Addresses a
>   real, adviser-raised scenario: a student writing a `switch`-case body into
>   unused margin space (because the space directly below is filled with the
>   rest of the function) rather than linearly, which today's geometry-only
>   grouping would either fuse into one garbled line or misorder. Six commits:
>   `74ebace` (Phase 1 gap severance), `21121ec` (literal-safe brace-delta
>   helper), `7cbcea0` (reassembly via well-formedness search), `7ec4b24`
>   (wire into `_group_detection_records`), `3e15298` (conservative
>   post-selection guard), `9ad5e22` (design-spec limits documented).
> - **Two-phase design.** Phase 1 severs a same-height fragment when its
>   horizontal gap to the current line exceeds ~6× median box width
>   (provisional threshold, calibrated against real 111-artifact
>   within-line-gap statistics — see `_group_detection_records` for the
>   exact derivation). Phase 2's `_reassemble_displaced_regions` searches
>   every possible block length starting at the first severed line, keeps
>   only the reordering where cumulative brace depth never goes negative
>   and ends at 0, and applies iff exactly one such length is valid. A
>   post-selection guard vetoes any winner whose non-severed partition
>   contains a negative-delta line (a real closer) — a semantic-integrity
>   safeguard against a brace-well-formed but wrong reordering.
> - **Test coverage: 109/109 (was 108).** Fifteen new tests total across
>   the branch: 2 gap-severance, 7 brace-delta, 5 reassembly (both RBNode
>   `rotate_rb` and Compressor `pack_flags` from the adviser's own examples
>   plus ambiguous/unbalanced fixtures), 1 end-to-end wiring, 1 guard
>   counter-example (Codex's post-selection edge case). `evaluate_cer`
>   unchanged from the citable baseline: CER `clean_ws` 0.126, WER `clean`
>   0.351, token-acc `clean` 0.696 — the feature is a proper no-op on
>   ordinary linear-layout pages.
> - **Genuine limitations, honestly named in the design spec's non-goals
>   (`docs/superpowers/specs/2026-09-07-reading-order-reassembly-design.md`).**
>   Not general non-linear layout — only end-of-sequence displacement.
>   Not mid-sequence reassembly (brace math alone can't discriminate
>   correct-mid-insertion from wrong-end-append when depth trajectories
>   match). Not PP-StructureV3 (evaluated, deprioritized — built for printed
>   multi-column, no C-syntax awareness). Not indentation/formatting (that
>   stays the teacher-triggered Format button). The guard trades some
>   legitimate multi-scope pages for safety against wrong reorderings —
>   those pages fall back to human verification, same as any unresolved
>   case.
> - **Explicitly still pending — three real handwriting photos from the
>   user of the exact adviser-raised scenario.** Once those arrive: (a)
>   recalibrate `REGION_GAP_MULTIPLIER` against a confirmed real gap from
>   actual writing, and (b) end-to-end validate the whole pipeline on real
>   OCR output (not just typed-fixture unit tests) — real handwriting can
>   include misread braces that break the brace-count math, and only real
>   photos will reveal how often that happens. Design-spec rollout §6
>   flagged this as follow-up, not part of the shipped algorithm.
> - **Defense scope.** This is squarely inside your defended pipeline
>   (extract → save → display for teacher editing) — reading-order
>   correctness is part of "extract." Explicitly NOT OCR-review
>   highlighting territory (that stays on `confidence-flagging-experiment-backup`,
>   unmerged, future work). If a panelist raises the non-linear-layout
>   scenario your adviser mentioned, this is the honest answer: identified
>   the case, built a domain-specific brace-depth reassembly that handles
>   it, named the remaining limits, added a guard so the algorithm fails
>   safely rather than confidently wrong.

> ## 🔵 STATUS 2026-09-06 (superseded by the block above)
>
> - **`labels.csv` provenance columns + a real overwrite bug fixed.**
>   `export_dataset.py` and `import_verified_batch.py` previously each opened
>   `datasets/verified/labels.csv` in truncating write mode and wrote only
>   their own rows — running one after the other silently destroyed whichever
>   rows the other script had written. Fixed via a new shared module,
>   `evaluators/labels_schema.py`, that partitions rows by ID shape
>   (writer-batch IDs like `bond_writer1_2` vs. Supabase UUIDs) so each
>   script's write merges instead of overwrites.
> - **New columns, additive only, nothing blocked:** `literal_verified`,
>   `literal_verified_by`, `literal_verified_at` (populated by
>   `import_verified_batch.py`'s new required `--verified-by` flag for
>   physically-verified rows; blank for Supabase-sourced rows, which have no
>   per-row physical check) and `correction_edit_distance` (character-level
>   edit distance between OCR output and the teacher's saved text, computed
>   at export time for OCR-sourced rows only). No row is skipped or rejected
>   based on either signal — this is visibility, not a gate, consistent with
>   the decision not to block the ongoing bond/yellow data-collection push.
> - **Real export run against current data:** all 168 existing writer-batch
>   rows in `datasets/verified/labels.csv` preserved correctly (0 lost); 2
>   Supabase submissions found, both skipped (1 missing text/image, 1 caught
>   by the existing unedited-save guard). 0/168 currently show full
>   provenance — expected, since all 168 were imported before these columns
>   existed; the next `import_verified_batch.py --verified-by "<name>"` run
>   populates them. Full numbers: `ocr/DEFENSE_PREP.md` §7 appendix
>   (2026-09-06).
> - **`writer_id` is still deferred, not done by this work.** See the
>   "Planned (next dataset import)" bullet in the 2026-09-01 block below —
>   unchanged, still waiting on real next-batch filenames to design against.
> - **Tests: 93/93 (was 81)** — 8 new for `labels_schema.py`, 2 for the
>   `export_dataset.py` merge fix, 1 for its summary output, 2 for the
>   `import_verified_batch.py` merge fix.
> - **Scope note:** this is dataset/training-pipeline tooling, squarely
>   inside the defended scope (fine-tuning data preparation), unlike the
>   OCR-review-highlighting work below.

> ## 🔵 STATUS 2026-09-05 (superseded by the block above)
>
> - **Defense scope note:** OCR-review highlighting below is outside the
>   defended scope (extract → save raw/verified text → display for teacher
>   editing) and unmerged. It is being held as future work, not presented as
>   a finished feature — the live-testing recall ceiling (some misreads are
>   invisible without the source image) means no amount of extra rules
>   closes the gap; more/diverse training data is the real next step.
> - **OCR-review highlighting is implemented on
>   `confidence-flagging-experiment-backup`.** The existing Review Code editor now
>   merges deterministic line anomalies, backend suggestions, and line
>   confidence into violet strong/soft markers. Empty finding panels are gone;
>   the UI explicitly says these are OCR review aids, not syntax diagnostics,
>   and unmarked text is not claimed to be correct.
> - **Exact suggestion coverage is still narrow.** The production backend
>   recognizes only `printe`/`printt` → `printf` and `scant` → `scanf`, so the
>   observed `scainf` → `scanf` mismatch produced no marker.
> - **A guarded matcher was A/B tested before implementation.** On identical
>   cached OCR output for all 20 held-out pages, current rules emitted 0
>   suggestions; the refined unique one-edit matcher emitted 3, all helpful,
>   with 0 non-improving suggestions. It also catches the separate `scainf`
>   case. After rejecting a naïve variant that falsely flagged three literal
>   `print(...)` calls, the refined candidate emitted 0 alerts across 188
>   literal-transcription negative controls.
> - **Do not overclaim:** 3/3 is a small observed result, not a precision
>   guarantee, the guards were refined after inspecting the same evaluation
>   pool, and this does not measure overall misspelling recall. The candidate
>   is documented but not implemented. Next action is to implement it only in
>   the non-mutating suggestion layer with permanent positive and negative
>   tests, then validate on a new untouched set. Full report:
>   `ocr/OCR_REVIEW_SUGGESTION_AB.md`.
> - **Same-day follow-on (still 2026-09-05): live testing against a real
>   garbled page closed 3 more detection gaps.** A page with `s%d` (dangling
>   fragment), `Pleace`/`valind`/`digt`/`numter` (misread words inside printed
>   messages), and `&num5]` (mismatched bracket) went entirely unflagged
>   despite the highlighting above. Fixed: (1) the "unusual line" check
>   widened from exactly 1–2 alnum characters to any short (≤3 char)
>   unterminated fragment; (2) a bracket-stack scan
>   (`detectBracketMismatches()`) now pins a mismatched/orphaned closer to its
>   exact line instead of only the whole-document balance count (an opener
>   left unclosed at end-of-document still can't be pinned to one line — that
>   part of the original design still holds); (3) a new backend check
>   (`_literal_word_suggestions()` in `c_code_suggestions.py`) flags a
>   likely-misread word inside a printed message against a small curated word
>   list at edit distance 1 — flag-only, never a correction, reason text never
>   claims whether OCR or the student is the source. All four gaps on the
>   motivating page now flag correctly. Tests: 61/61 frontend (was 56), 81/81
>   backend (was 78). Full detail: `docs/CLAUDE.md`,
>   `web/WEB_CODEBASE_GUIDE.md` §3.1, `docs/PROJECT_OVERVIEW_AND_CHANGES.md`.
>   (The `ocr/CODEBASE_GUIDE.md` §5.3 this once pointed to described
>   `c_code_suggestions.py`, removed 2026-09-12 — see
>   `ocr/OCR_REVIEW_SUGGESTION_AB.md`'s banner.)

> ## 🔵 CURRENT STATUS 2026-09-02 (read this first — supersedes older dated blocks below)
>
> - **v1 training dataset RECOVERED (content-faithful reconstruction, not the
>   byte-exact original file — verified 2026-09-04).** The literal morning crops
>   that trained the RELEASED model (`models/fine_tuned_rec/`) were uploaded to
>   Colab and never saved (`datasets/recognition/` is gitignored) — gone. A
>   same-day REBUILD was recovered from Trash at
>   **`~/Downloads/recognition_dataset_v1_release.zip`** (2491/278). Timestamps:
>   model exported **08:58** (morning), zip crops dated **13:30–13:48**
>   (afternoon) — so the zip is a rebuild, not the original upload. **But it's
>   content-identical to the training crops:** the source-image swap (`a8d4bb1`,
>   **22:47**) and builder rework (`aedd444`, **23:14**) were both EVENING —
>   hours after both the morning build and the 13:48 rebuild — so source +
>   builder were provably unchanged between them. Deterministic builder
>   (`RANDOM_SEED=0`) + identical source → identical crops, and the 13:48 rebuild
>   hitting exactly 2491/278 confirms it. Defense framing: "content-faithful
>   deterministic reconstruction — the crops match what trained the model, though
>   the literal original upload wasn't preserved." Do NOT say "byte-exact original
>   file"; DO say "content-faithful reconstruction." Published as a 4th asset on
>   GitHub Release `ocr-rec-v1`. **Do NOT confuse** it with
>   `recognition_dataset_FULL.zip` (2515/283, a later rebuild — NOT what trained
>   v1; the builder changed via `aedd444` after training) or
>   `recognition_dataset_crosswriter.zip` (2292/231, the cross-writer experiment).
> - **Orientation / de-warp / textline-orientation passes measured OFF (were
>   already off; now quantified).** Enabling all three on the 20-image test set
>   made CER WORSE: overall 0.126 → 0.177, **bond 0.005 → 0.455** (the
>   orientation/de-warp models mis-correct already-gated flat pages). Kept off by
>   design — the quality gate handles geometry, so re-correcting clean input
>   costs ~80s/image AND hurts accuracy. Full table + mechanism:
>   `ocr/DEFENSE_PREP.md` §14.1.
> - **Adaptive-denoise is genuinely active on the current test set** — fires on
>   15/20 samples (measured background noise 0.49–4.52; gate CROPS but doesn't
>   smooth paper texture). The old `preprocess.py` comment claiming the branch is
>   "inert on gate input (0.50–2.07)" was stale (older, smoother cohort) and is
>   now corrected in the code.
> - **Skill-test prep added** to `ocr/DEFENSE_PREP.md`: §12 verification-loop
>   preamble (tests → single-image → evaluate_cer → app-vs-paper) and §12.0 a
>   live preprocessing-change walkthrough (adaptive_denoise on/off).
> - **Notebook Part B made robust** — auto-detects whatever `recognition_dataset*.zip`
>   you upload (no rename needed) and documents uploading
>   `recognition_dataset_v1_release.zip` to reproduce v1.
>
> ## 🔵 STATUS 2026-09-01 (superseded by the block above)
>
> - **New-writer generalization confirmed + a writer-identity correction.**
>   Earlier docs implied the held-out `samples/` set was fully same-writer
>   (a miscount that ignored the batch in the filename). **Corrected:** writer
>   identity = paper type + number + **batch** (`green_writer19_B1` ≠
>   `green_writer19_B2` — numbering resets per batch; no-batch files are the
>   first dataset). Under the correct identity, **greenbook is writer-disjoint
>   (8/9 test writers, 13/14 images)** — only bond (2) and yellow (4) are
>   same-writer (too few writers to hold out). So **0.126 is largely a genuine
>   unseen-writer result**, not same-writer. Full detail: `ocr/EVALUATION.md`;
>   memory `test-set-writer-overlap`.
> - **Cross-writer experiment (independent new-writer confirmation).** Retrained
>   a *separate measurement* model with 4 greenbook writers (7/8/20/27) excluded
>   entirely, tested on their 15 never-seen pages: **stock 0.296 → fine-tuned
>   0.123 CER (−58%)**; WER 0.792 → 0.397. Proves the gain transfers to writers
>   the model never saw (generalization, not memorization). Reproducible:
>   `evaluators/build_crosswriter_dataset.py` + `evaluators/crosswriter_eval.py`
>   (model via `MAISTRA_REC_MODEL_DIR` env var; 76MB measurement model in
>   `models/fine_tuned_rec_crosswriter/`, gitignored). **Shipped model
>   (`models/fine_tuned_rec/`) unchanged — trains on ALL writers.**
> - **WER + token-accuracy on the main 20-image set (objective 7):** stock →
>   fine-tuned **WER 0.726 → 0.359 (−51%)**, token-acc 0.487 → 0.701. Improved
>   on every paper type. In `ocr/EVALUATION.md`.
> - **`samples/` reorganized** into `bond/`/`greenbook/`/`yellow_pad/` subfolders
>   (was flat) to mirror `datasets/verified/`; `select_holdout.py` now writes
>   into subfolders and `labels.csv` filenames carry the `<paper_type>/` prefix.
>   Same 20 images, no writer changes — evaluate_cer resolves `samples/<filename>`
>   unchanged.
> - **Notebook dep fix:** the clean Colab notebook's git-clone path needs
>   **`pyclipper`** on top of `lmdb rapidfuzz` (the old paddlex install provided
>   it transitively). Deps line is now `lmdb rapidfuzz pyclipper`.
> - **Planned (next dataset import):** add a `writer_id` column to both
>   `labels.csv` files (no-batch → B0 identity) — disambiguation in metadata,
>   NOT by renaming files. New greenbook keeps batches (next batch = B4+, never
>   reuse an existing batch number); bond/yellow stay casual until writer counts
>   grow. Also: collect more C constructs (structs/pointers/switch/arrays) for
>   vocabulary coverage. Memories: `test-set-writer-overlap`,
>   `dataset-content-diversity-plan`.
>
> ## 🔵 STATUS 2026-08-30 (superseded by the block above)
>
> - **First real fine-tune trained and measured — the thesis payoff result.**
>   `PP-OCRv6_medium_rec` fine-tuned on 2,491 train / 278 val handwritten
>   C-code line crops, 40 epochs (Colab GPU, best checkpoint epoch 39). On the
>   same 20-image held-out `samples/` set, stock vs fine-tuned through the
>   identical pipeline: recognition CER (`clean_ws`) **0.274 → 0.126 (−54%)**,
>   every one of the 20 files improved, zero regressions. Per paper type: bond
>   0.089→0.005, yellow_pad 0.175→0.071, greenbook 0.328→0.159. **Do not cite
>   "0.149 → 0.126"** — the old `0.149` baseline was measured on a different,
>   easier 14-sample set; the only valid comparison is same-test-set
>   `0.274 → 0.126`. Full writeup: `ocr/EVALUATION.md` top banner; memory:
>   `fine-tune-result-2026-08-30`.
> - **The result is INTACT — none of this session's later git/cleanup work
>   changed it.** (Recording this explicitly because the same-day contamination
>   bug + folder deletions + doc churn below can look, in hindsight, like they
>   might have touched the fine-tune. They did not — verified by file
>   timestamps:)
>   - **Model weights** (`models/fine_tuned_rec/inference/inference.pdiparams`)
>     are dated **08:58** (the Colab export). No training job was run this
>     session — all later work *used* the model, committed files, cleaned up
>     folders, and edited docs. The bytes that produced 0.126 are unchanged.
>   - **Training crops** (`datasets/recognition/`) were built **13:48**, zipped
>     for Colab **13:51**. The 20-image test/train contamination (see the
>     import-script bug bullet below) happened in the **evening**, *hours after*
>     both training and crop-building, and `datasets/recognition/` was never
>     rebuilt after 4pm — so the wrongly-copied test images never became crops,
>     never went to Colab, never reached the model.
>   - **Test set** (`samples/`) content is unchanged — this session *committed*
>     those 20 images/labels to git but didn't alter them; the measurement ran
>     against exactly that set.
>   - Honest nuance: the model was exported (08:58) before the local crops were
>     last rebuilt (13:48), so the on-disk crops may not be byte-identical to
>     the exact build that trained the model. That's a reproducibility detail,
>     not a result-affecting one — the builder is deterministic (`RANDOM_SEED=0`,
>     reads the same `datasets/verified/`), so it regenerates equivalent crops.
>   - **Bottom line: the 0.274→0.126 result stands as measured. This session
>     made it reproducible (committed the data + methodology) without changing
>     it.**
> - **Dataset provenance — one pipeline, two views (a triage staging area
>   and its verified output), not separate competing batches.** (Earlier
>   versions of this bullet mis-described this twice: once claiming a third
>   separate "unverified `submission_*` batch" that turned out to be the same
>   verified data renamed, and once claiming `dataset_review/` was unused when
>   its `usable/` folder actually fed the fine-tune. Both corrected below;
>   corrections kept visible rather than silently deleted.)
>   1. **`dataset_review/`** (148 raw `IMG_XXXX.jpg` photos) — a manual
>      triage stage: photos sorted by hand into `usable/` (137) /
>      `usable_if_cropped/` (3) / `deferred_needs_line_exclusion/` (7) /
>      `not_usable/` (1), per `docs/CLAUDE.md` and
>      `dataset_review/VERDICTS.md`. **This is a staging/triage view, not a
>      separate unused batch** — the `usable/` folder (137 photos, mostly
>      greenbook) DID feed the 2026-08-30 fine-tune: after review these were
>      run through the quality-gate crop/de-warp, transcribed + physically
>      verified, renamed to the `writer<N>` convention (mostly
>      `green_writer*`), and are the source of the greenbook portion of the
>      verified training set in batch 2 below (which is why verified greenbook
>      is by far the largest paper type, 131 images). The `IMG_XXXX` files
>      here are the pre-gate/pre-rename originals kept for audit.
>
>      **Full data lineage (sequential stages of ONE pipeline):**
>      `dataset_review/usable/` (raw, triaged as qualified) → **quality-gate
>      crop/de-warp** → `image_to_transcribe/` (gate-cropped, ready to
>      transcribe) → transcribe + verify against physical paper + rename to
>      `writer<N>` → `~/Downloads/image_to_transcribe_verified/` → import via
>      `import_verified_batch.py` → `datasets/verified/` (committed training
>      set, `a8d4bb1`). Only `usable/` takes this path; the
>      `deferred_needs_line_exclusion/` 7 pages did NOT go through the gate and
>      are **still genuinely pending** — they need the per-line exclusion
>      manifest before their readable lines can be added (see
>      `docs/ocr/PER_LINE_EXCLUSION_HANDOFF.md`). `not_usable/` (1) is excluded
>      by design.
>
>      (Earlier versions of this bullet wrongly said dataset_review was "not
>      transcribed, not used in any fine-tune" — wrong for `usable/`, which is
>      the greenbook source. And the gate-cropped `image_to_transcribe/`
>      intermediate stage was briefly mistaken for a separate unverified batch
>      — it was just this pipeline's middle step.)
>   2. **The writer-pseudonym batch**, source of truth
>      **`~/Downloads/image_to_transcribe_verified/`** (`bond_writer1_2`,
>      `green_writer10_B2_1`, `yellow_writer1_1`, etc.) — **physically
>      verified against the real papers**, split into `datasets/verified/`
>      (train, imported via `ocr_feature/import_verified_batch.py`) and
>      `samples/` (test, selected via `select_holdout.py`). **This is the
>      actual data behind the fine-tune**: the 2,491/278 train/val crops and
>      the 20-image held-out test set below both come from this batch. It
>      fully replaced the old `submission_*`-named `samples/` set (the one
>      behind the retired `0.149` baseline) this session. Committed to git as
>      `a8d4bb1` (168 train images + `labels.csv`).
>
>   **Correction (2026-08-30, same day):** a `~/Desktop/image_to_transcribe/`
>   folder (189 `submission_<id>`-named photos, matching the old
>   `VERIFICATION_INSTRUCTIONS.md` transcription workflow) was initially
>   mistaken for a *third, still-unverified* batch, purely because its
>   filenames didn't match the `writerN` convention. **Verified by md5 hash
>   comparison, not assumption**: every one of its 189 photos was
>   byte-identical to a file already in the verified batch above (188 direct
>   matches; the 189th was a confirmed duplicate capture of an already-included
>   page, correctly not re-added). It was the same physically-verified content
>   under its pre-rename Supabase export name — not separate, not pending,
>   nothing missing. **Deleted** after this was confirmed (redundant with the
>   verified batch, and its ambiguous near-identical name to the verified
>   folder was actively causing confusion). **Lesson:** a filename convention
>   (`submission_*` vs `writer<N>`) is not proof of verification status by
>   itself — check file content, not just names, before concluding two
>   folders hold different data.
>
> - **Import-script bug found and fixed while wiring up the renamed source
>   above.** `import_verified_batch.py` had no awareness of `samples/` (the
>   test set) and would copy any writer-named image it found in its source
>   folder into `datasets/verified/` (train) — including the 20 images
>   `select_holdout.py` had deliberately held out as the test set, violating
>   the hard "samples/ = test, datasets/verified/ = train, never overlap"
>   rule. Caught immediately via a sanity check added to the same script
>   (diffs new import rows against the current `labels.csv` instead of
>   silently overwriting); fixed with a `_holdout_stems()` guard that reads
>   `samples/`'s filenames and skips any match. The 20 wrongly-copied files
>   were deleted and `labels.csv` regenerated correctly (168 rows) before
>   anything downstream (`datasets/recognition/`, the actual fine-tune) was
>   touched — no contamination reached the shipped model. Committed as
>   `5749a7a`.
> - **Colab install path was broken on Python 3.13 — worked around, not
>   fixed upstream.** `paddlex --install PaddleOCR -y` cannot resolve its
>   bundled dependency set on Colab's current runtime (`tokenizers==0.19.1`
>   has no py3.13 wheel; `albumentations==1.4.10+pdx` hard-conflicts with
>   `numpy>=2`) — unfixable by patching pins. Working bypass: skip the plugin
>   installer entirely and run PaddleOCR's native `tools/train.py` directly
>   against a native (non-PaddleX) YAML config, since the plugin's only
>   necessary side effect (cloning the PaddleOCR repo) always succeeded
>   anyway. New doc: **`ocr/COLAB_SETUP_WORKING.md`** — the actual working
>   sequence. `ocr/COLAB_FINE_TUNING_GUIDE.md` now has a warning banner on
>   its install section pointing here; its data-prep parts are still correct.
>   Cleaned/reproducible notebook: `notebooks/finetune_ppocrv6_rec_colab.ipynb`.
> - **Fine-tuned model is the committed, required default.**
>   `core/ocr_pipeline.py`'s `PaddleOCR(...)` call points the recognizer at
>   `text_recognition_model_dir="models/fine_tuned_rec/inference"` (three
>   exported files: `inference.json` architecture, `inference.pdiparams`
>   weights ~76MB, `inference.yml` config/character-dict) instead of the
>   named stock model — this one line is the entire integration; PaddleOCR's
>   own model loader does the rest. Committed `0ab6a1b` (no stock fallback —
>   see next bullet). Verified live end-to-end via a standalone tester page
>   and the real Angular app's extract flow.
> - **Model distribution: done, live, and verified end-to-end.** The 76MB
>   weights file isn't committed to git (`.gitignore`: `models/*` /
>   `!models/README.md`) and is instead distributed via a **published GitHub
>   Release** (`ocr-rec-v1`, on `ocr_feature`, commit `0ab6a1b`) with
>   `models/README.md` documenting install for both macOS/Linux/Git-Bash and
>   Windows PowerShell. **No stock-model fallback** — an earlier
>   `Path.exists()`-based fallback was deliberately removed; `ocr_pipeline.py`
>   now requires the fine-tuned model and raises a clear `FileNotFoundError`
>   pointing at the README if it's missing, so the result the thesis measured
>   is never silently swapped for something weaker. Verified for real: moved
>   the local model aside, downloaded the actual zip from the published
>   Release, followed the README's own steps, confirmed the pipeline loads it
>   (a real gap was caught and fixed doing this — the original instructions'
>   `unzip -d` failed on a directory that doesn't exist on a fresh clone).
>   All of this is committed and pushed (`0ab6a1b`, `10e37f9`, `246a13a`).
> - **Capture-convention decision: one photo per notebook page, portrait —
>   not a landscape two-page spread.** Full investigation, root cause, real
>   test evidence (before/after OCR output on an actual landscape training
>   photo), and the commercial-scanner-app comparison that informed the
>   live-capture decision: **`docs/ocr/LANDSCAPE_SPREAD_INVESTIGATION.md`**.
>   Summary: the offline crop builder's gutter-split (`_split_landscape_page`,
>   committed `aedd444`) is done and verified working — safe there because
>   ground truth catches a bad split. The live quality gate does NOT have
>   this fix and is NOT getting the same fix — gutter-splitting was
>   considered and rejected as too fragile for live input (no ground truth
>   to catch a bad split there); the decision is to reject/flag landscape
>   spreads at capture instead. **Not yet implemented in the quality gate**
>   — awaiting the gate owner (see item 1 in "Immediate next steps"). (An
>   earlier version of this bullet wrongly said landscape handling was "not
>   yet implemented anywhere in code" — it's implemented in the offline
>   builder; only live-gate enforcement is outstanding.)
> - **Clarified (not a bug): OCR does not reliably skip scribbled/crossed-out
>   lines.** The detector has no notion of "this is scribbled out" — it boxes
>   whatever looks stroke-like and the recognizer reads whatever's in the
>   box, producing hallucinated garbled text rather than cleanly skipping it
>   (confirmed on two real review-screen examples). This is why the project's
>   existing `deferred_needs_line_exclusion` human-reviewed manifest
>   (`docs/CLAUDE.md`) exists — a person marks unrecoverable scribble lines
>   explicitly; no automatic scribble-detection is planned, since reliably
>   telling scribble apart from genuinely messy-but-legible handwriting is
>   its own unsolved classification problem with an asymmetric failure cost.
>
> ---
>
> ## 🔵 STATUS 2026-08-28 (superseded by the 2026-08-30 block above)
>
> **Update (2026-08-30, later same day):** this block describes
> `~/Desktop/image_to_transcribe/` (`submission_*`-named) as pending
> physical-paper verification. That framing is now confirmed **stale, not
> current** — this same batch was physically verified and renamed to the
> `writerN` convention sometime after this 2026-08-28 snapshot, becoming the
> verified batch in `~/Downloads/image_to_transcribe_verified/` that the
> fine-tune actually used (confirmed via md5 hash match, not assumption —
> see the "dataset batches" bullet above). The `~/Desktop/` copy was the
> stale pre-verification leftover and has been deleted. Nothing below this
> line reflects current status; read it as history only.
>
> - **yellow_pad batch arrived and transcribed/checked.** The transcription
>   effort (`~/Desktop/image_to_transcribe/`, outside this repo — see the
>   2026-08-25 block below for the workflow) now has all three paper-type
>   folders 1:1 image-to-`.txt` matched: `bond/` 22/22, `greenbook/` 145/145,
>   `yellow_pad/` 22/22. Of the 22 yellow_pad `.txt` files, 22 were checked
>   directly against their images; 4 had badly garbled OCR-artifact-style text
>   (e.g. `indude<stdioh>`, `printt`, `∠`, `roturn false`) and were rewritten
>   to match the image, preserving each student's actual bugs (e.g. a missing
>   `&` in a `scanf` call, a trailing comma in an array initializer) per
>   `ai-photo-reads-are-not-label-evidence` / `ocr-cleanup-scope`. One file
>   (`submission_1787810220391.txt`, an `is_prime` program) looked garbled
>   because it cuts off mid-ternary, but the physical page itself is
>   cropped/torn at that exact point — left unchanged, since the cutoff is
>   accurate, not an AI error. This pass is still Claude-vs-photo checking
>   only, not physical-paper verification — see next bullet.
> - **Teammate physical-paper verification now underway.** A standalone
>   instructions doc, `image_to_transcribe/VERIFICATION_INSTRUCTIONS.md`, was
>   written for the teammate who holds the actual physical papers: per-file
>   procedure (get the paper, read the `.txt` line by line against it, edit
>   mismatches in place, preserve student bugs, skip cleanly-crossed-out
>   attempts, flag heavily-corrected pages with a `LOW CONFIDENCE` comment),
>   plus explicit "don't"s (don't touch `labels.csv` yet, don't worry about
>   retake-matching). Planned reconciliation step once he reports a folder
>   done: diff his edited `.txt` files against Claude's pre-verification
>   versions (kept as a snapshot before his pass) to catch cases where either
>   side's read was wrong, resolving disagreements against the physical page
>   — see `dual-verification-then-diff` project memory. Only reconciled files
>   are eligible to feed the eventual `labels.csv` rebuild. Not started yet;
>   waiting on the teammate's first completed folder.
> - **`labels.csv` rebuild still not started** — explicitly deferred until
>   every image across all three folders has been through both the
>   Claude-vs-photo check above and the teammate's physical-paper pass, at
>   which point it's a wholesale rebuild from verified `.txt` files (old rows
>   removed, fresh rows written in), not a retake-pairing merge.
> - No pipeline/preprocessing code changed this block — same holding pattern
>   as the 2026-08-25 block below (data volume/verification is the active
>   work, not engineering).
>
> ---
>
> ## 🔵 STATUS 2026-08-25 (superseded by the 2026-08-28 block above)
>
> - **`dataset_review/` fully reviewed.** Human review of all 148 raw images
>   is done: `usable/` 137, `usable_if_cropped/` 3,
>   `deferred_needs_line_exclusion/` 7, `not_usable/` 1 (3 duplicates dropped,
>   retained as `dropped` in the verdict table for audit). Decisions are in
>   `ocr_feature/dataset_review/VERDICTS.md`; categorization rules and the
>   `usable/`-first sequencing decision are in `docs/CLAUDE.md` (moved from
>   the project root into `docs/` — gitignored like the rest of this folder,
>   so it's no longer accidentally trackable; note this may affect any tooling
>   that auto-loads a root-level `CLAUDE.md`).
> - **Real transcription work started** on new capture batches (bond +
>   greenbook so far; yellow_pad arrived and was transcribed as of the
>   2026-08-28 block above) — separate from the `dataset_review/usable/`
>   137-page backlog referenced
>   above, not a replacement for it. Workflow: images live in paper-type
>   folders, each paired with a same-basename `.txt` in a sibling `*_txt/`
>   folder; Claude proposes a transcription read from the image, the human
>   corrects it against the physical paper (per
>   `ai-photo-reads-are-not-label-evidence` — an AI photo read is never
>   ground truth on its own). These `.txt` files still need a merge step into
>   `labels.csv` before `build_recognition_dataset.py` can use them; not yet
>   built as of this block.
> - **`compare_config.py` added** (`ocr_feature/compare_config.py`) — a dev
>   tool that runs one image through grayscale+denoise (shipped default) and
>   adaptive binarization side by side, printing both OCR outputs/confidences
>   (and CER, given a matching `.txt`). `--show` opens both preprocessed
>   images as VS Code tabs. Built to give a live, reproducible demo of the
>   binarization-vs-grayscale finding for the thesis defense, not for routine
>   pipeline use. See `ocr/DEFENSE_PREP.md` §14 for the full writeup this
>   supports (six binarization-rescue attempts, all failed, plus the deskew/
>   shadow-removal/bleed-through investigation) and `ocr/CODEBASE_GUIDE.md`'s
>   file-purpose table for how it differs from `try_config.py`.
> - **Dead-code audit (2026-08-25): clean.** Ran `vulture` across all 27
>   project `.py` files at every confidence level; the only 3 hits were
>   FastAPI route handlers in `main.py` (false positives — invoked via HTTP
>   routing, not direct calls). The `threshold=True` binarization path in
>   `core/preprocess.py` was specifically confirmed live (via
>   `compare_config.py`), not dead.
> - **Web frontend work now documented properly.** New
>   `web/WEB_CODEBASE_GUIDE.md` — file-by-file walkthrough (matching this
>   doc's sibling `ocr/CODEBASE_GUIDE.md` style) of Nombrado's frontend work:
>   the `code-editor.ts` component in full, and the OCR-extraction/
>   save-safety/feedback logic in `submissions-list.ts` and
>   `services/supabase.ts`. `web/VERIFICATION_UI.md`'s stale "NOT YET
>   COMMITTED" note on the Format button was also corrected (it landed as
>   `9c719f3`, 2026-08-11) — see the scope note at the top of this file.
> - **Test-set isolation bug found and fixed (2026-08-25) —
>   `build_recognition_dataset.py`.** `_load_rows()` was pooling
>   `samples/labels.csv` (the held-out set `evaluate_cer.py` measures the
>   `0.149` baseline against) together with `datasets/verified/labels.csv`
>   into the same train/val split — meaning most of `samples/` was eligible
>   to end up in `train.txt`, contradicting `FINE_TUNING_READINESS.md`'s own
>   stated design and, if a real fine-tune had run first, would have
>   invalidated any "after" CER measured against `samples/`. Fixed: the
>   builder now reads only `datasets/verified/labels.csv`; `samples/` can
>   never contribute a crop. Caught and fixed while both label sources'
>   image folders are still empty (mid-retake) — no real training run was
>   ever exposed to this. Full writeup: `ocr/FINE_TUNING_READINESS.md` §5
>   item 2a. This is the one exception to "no production code changed" below
>   — it's dataset-tooling correctness, not a pipeline/preprocessing change.
> - **No pipeline/preprocessing code changed this block** (see the
>   test-set-isolation fix just above for the one dataset-tooling exception).
>   Everything else is tooling, documentation, and dataset-prep workflow —
>   the project is deliberately holding on further pipeline changes until
>   the transcription pass produces enough real labeled volume to fine-tune
>   against (per the 2026-08-06 block below: preprocessing is exhausted,
>   dataset size is the actual blocker).
>
> ---
>
> ## 🔵 STATUS 2026-08-10 (superseded by the 2026-08-25 block above)
>
> - **WER + token-level recognition accuracy added — matches thesis objective
>   7** ("CER, WER, and token-level recognition accuracy"). `evaluate_cer.py`
>   now prints a second table alongside the existing CER one:
>   - **WER** — word error rate over `str.split()` tokens. Lower is better.
>     First measured (14 samples): overall **raw 0.699 / clean 0.656**.
>   - **Token-level recognition accuracy** — `1 - (edit distance over
>     C-lexical tokens / reference token count)`. HIGHER is better; a
>     lightweight C lexer (`tokenize_c` in `evaluation.py`) makes operator
>     spacing (`x=5` vs `x = 5`) never count as an error. First measured:
>     overall **raw 0.715 / clean 0.729**.
>   - **CER unaffected**: `clean_ws 0.149` baseline unchanged — purely
>     additive. WER reads much higher than CER by design (one misread
>     character fails a whole word for WER, ~1/9 of it for CER on a 9-char
>     word) — not a regression, the metrics measure different granularities.
>   - Implementation: `evaluation.py` (`wer`, `tokenize_c`, `token_accuracy`,
>     `evaluate_word_token_pair`), reported as a separate table since WER/
>     token-accuracy and CER have opposite "good direction." 10 new tests;
>     **suite now 78/78** (was 68/68). Full numbers: `ocr/EVALUATION.md` top
>     banner.
>   - **Committed** `c941644` (2026-08-12), "Add WER and token-level
>     recognition accuracy metrics."
>
> ---
>
> ## 🔵 STATUS 2026-08-09 (superseded by the 2026-08-10 block above)
>
> - **Line-merge fix COMMITTED AND PUSHED** — `afd2ef2` on `ocr_feature`
>   (`2feb357..afd2ef2`). Contains: the horizontal-overlap grouping veto,
>   `core/debug_artifact.py` (the debug I/O split), `evaluators/
>   build_recognition_dataset.py` (new), and a `warmup()`/whitespace tidy in
>   `main.py`. This is the code described in the 2026-08-08 block below — that
>   work is no longer "uncommitted, awaiting review," it has landed.
> - **Post-commit code review (high effort, 2026-08-09) found 5 issues, all
>   resolved same day** — full detail in the review's findings, summarized:
>   1. *(fixed)* Crop filenames were inconsistent between the two label
>      sources — `samples/`-derived crops embedded the source extension
>      mid-name (`<name>.jpeg_line3.jpg`); now both sources produce clean
>      extension-less names, via `Path(filename).stem`.
>   2. *(fixed)* Added `test_identical_x_boxes_within_tolerance_do_not_merge`
>      — an earlier test was narrowed to unit-test `_expected_line_y` alone
>      when the overlap veto made its old full-pipeline assertion stale; this
>      restores end-to-end coverage that same-x stacked boxes stay separated
>      through `_group_detection_records`, not just the math helper.
>   3. *(fixed)* Extracted `line_member_bounds()` in `ocr_pipeline.py` — a
>      shared union-bounding-box helper now used by both
>      `_group_structured_lines` and `build_recognition_dataset.py`, so the
>      live pipeline and the offline crop tool can't compute a line's box
>      differently.
>   4. *(fixed)* `build_recognition_dataset.py`'s `main()` now clears
>      `datasets/recognition/` before writing, so a rerun can't leave stale
>      crops from a page whose line count changed after a retake — no more
>      needing to remember `rm -rf` first.
>   5. *(deliberately NOT coded — documented as a measured watch-item)* The
>      overlap veto divides by the *narrower* box, so in principle a very
>      short trailing fragment (a brace, a semicolon) could be pushed over the
>      30% cutoff by a small overlap. **Measured against the full cohort
>      before touching anything:** this does not occur on current data (the
>      only short fragments are a correctly-split misread brace at 86.7% and
>      a correctly-merged stray mark at 0%). Coding an unmeasured fix here
>      would risk regressing the validated brace splits, so it was left alone
>      with an explicit revisit trigger. Full writeup + the trigger condition:
>      `ocr/LINE_MERGE_INVESTIGATION.md`'s "Known limitation" section.
> - **Test count: 68/68** (was 67/67 after the original fix; +1 from finding
>   #2's restored coverage). All 7 files still pass standalone.
> - **Regenerated `datasets/recognition/` to verify the fixes**: same 126
>   train / 14 val (140 total), same 7/21 skip list — confirms the naming and
>   dedup fixes are behavior-preserving, not just theoretically correct.
> - **Still NOT committed, by choice:** the comment-only changes (evaluator
>   run-command docstrings, the `preprocess.py` grayscale-vs-binarization
>   rationale rewrite). No code behavior in either — held back deliberately
>   since they're "just comments," not because anything is wrong with them.
> - **Colab fine-tuning dry run — see [`## Colab fine-tuning dry run —
>   step-by-step`](#colab-fine-tuning-dry-run--step-by-step) below** for the
>   concrete procedure (data upload, PaddleX/PaddleOCR install, config,
>   training, and the honest caveat that this is a pipeline proof at current
>   volume, not a production swap-in).
> - **Immediate next steps, in order:**
>   1. Decide whether to commit the deferred comment-only changes now or keep
>      holding them — no code risk either way.
>   2. Begin the C-formatter / judge0 work — unblocked now that the grouping
>      fix (correct per-line structure) is committed and pushed.
>   3. Send the shadow-detection writeup to Nikko (`ocr/QUALITY_GATE_REVIEW.md`,
>      with the "read-only reference, don't copy verbatim" caveat).
>   4. Retake all 14 sample images — every one currently has shadows or dim,
>      uneven lighting.
>   5. Re-verify retakes against physical paper, update `samples/labels.csv` if
>      text changed, then `rm -rf datasets/recognition/` and rerun
>      `build_recognition_dataset.py` (now auto-clears anyway, but the source
>      images must be replaced first). 7 of 21 pages are currently skipped —
>      expect some to recover with cleaner captures.
>   6. Re-measure phantom detections on the clean images (gated — see
>      `ocr/PHANTOM_DETECTION_INVESTIGATION.md`); decide if the height filter
>      is still needed.
>   7. Keep collecting papers (more writers, decent/readable handwriting,
>      raw pad coverage) toward the 200–500 line minimum-viable tier — 140
>      crops exist now, still dry-run tier.
>   8. Once volume is usable: run the Colab dry run below for real, past just
>      a pipeline-mechanics proof.
>
> ---
>
> ## 🔵 STATUS 2026-08-08 (superseded by the 2026-08-09 block above)
>
> - **Code-quality pass (2026-08-07), behavior-preserving.** A dedup / dead-code
>   / measured-comments sweep over `ocr_feature`. **CER baseline UNCHANGED**
>   (`clean_ws 0.149` over 14 gate-framed samples) — this pass changed structure,
>   not accuracy. Tests were 64/64 after that pass; the current total is
>   **67/67** after the measured line-grouping fix below.
>   - **Deduplication:** the shared C string/char-literal regex moved to
>     `core/c_literals.py` (`C_LITERAL`); the shared "coerce to a finite float or
>     None" guard moved to `core/numeric.py` (`finite_float`). Both are imported
>     by `c_code_cleanup.py` and `c_code_suggestions.py` / `ocr_pipeline.py`
>     instead of being re-declared. `export_dataset.py` now imports `normalize_ws`
>     from `evaluation.py` instead of a second copy.
>   - **Cleanup vs suggestions split by certainty (no overlap):**
>     `c_code_suggestions.py` no longer re-proposes the keyword/header fixes that
>     `c_code_cleanup.py` already auto-applies (removed `_TOKEN_FIXES`,
>     `_WORD_TOKEN`, `_INCLUDE_CANDIDATE`, `_HEADER_FIXES`); it now flags only
>     function-call misspellings, which genuinely need human approval.
>   - **Dead code removed:** `_group_into_reading_order` (no production caller;
>     `_group_structured_lines` is the live path). Its unit tests were repointed
>     to the shared `_group_detection_records`, keeping identical coverage.
>   - **Comments now measured, not speculative:** the `adaptive_denoise`/2.2
>     trigger and `REC_SCORE_FLOOR` were re-verified against v6 on the gate-framed
>     set (trigger is inert on gate input; floor sits in the 0.291→0.334
>     junk/real gap). Comments rewritten to state the measured result. See
>     `ocr/EVALUATION.md`, `ocr/QUALITY_GATE_REVIEW.md`.
>   - **Test isolation fixed:** every `tests/test_*.py` now documents its
>     standalone run command (`.venv/bin/python -m tests.test_<name>`), and
>     `test_ocr_pipeline.py` now stubs `core.numeric` so it runs in isolation
>     (previously it only passed as part of the full suite — an ordering fluke).
> - **Preprocessing settled + mechanism corrected (2026-08-07).** Re-ran the
>   grayscale/binarization and color/grayscale A/Bs same-cohort on the current 14
>   black-pen samples: grayscale `0.149` vs binarized `0.201` (+0.052 worse);
>   4-way — grayscale+denoise `0.149` > color no-denoise `0.153` > grayscale
>   no-denoise `0.169` > color+colored-denoise `0.194`. The old "PaddleOCR is
>   trained on grayscale" rationale was **retired** — unverifiable against the
>   PP-OCRv6 paper (3-channel `3×48×W` input) and a maintainer says RGB is
>   preferred. Corrected mechanism: grayscale wins by unlocking an effective
>   single-channel denoiser, not by matching training. Defense line is now "we
>   measured it." Docs updated: `EVALUATION.md` top banner, `preprocess.py`
>   comment, `CODEBASE_GUIDE.md`, `binarization-off-by-default` memory.
> - **Recognition-crop dataset builder added (2026-08-07), `evaluators/
>   build_recognition_dataset.py`.** Converts whole-page labels into
>   PaddleX-format per-line crops (`datasets/recognition/images/` +
>   `train.txt`/`val.txt`) — the conversion step FINE_TUNING_READINESS.md
>   previously listed as unwritten. Skips any page where OCR's detected line
>   count doesn't match ground truth, rather than guessing alignment. Current
>   post-grouping run: **126 train / 14 val crops (140 total)**, 7/21 pages
>   skipped on mismatch (4/14 sample pages, 3/7 verified pages).
>   This remains dry-run tier (200–500 lines is minimum viable), so a Colab
>   fine-tune is a pipeline proof, not a production PP-OCRv6_medium swap-in.
>   The builder originally required adding `x_max` per detection to
>   `_group_detection_records` for crop-box unions; that was behavior-preserving.
> - **Debug I/O split out of the pipeline (2026-08-08), behavior-preserving.**
>   `_jsonable` and `_write_debug_artifact` moved from `core/ocr_pipeline.py`
>   into a new **`core/debug_artifact.py`** (the writer is now module-public
>   `write_debug_artifact`). Reason: `ocr_pipeline.py` should hold recognition
>   logic only — debug JSON dumping is developer-facing I/O, the same
>   separation `preprocess.py` already has. Note this is a *cohesion* split,
>   not deduplication like `c_literals.py`/`numeric.py` were — the helpers had
>   a single caller. **Verified unchanged:** `clean_ws 0.149` (bond 0.133 /
>   greenbook 0.159 / yellow_pad 0.171), 64/64 tests, all 7 test files still
>   pass standalone, artifacts still written to `outputs/debug/`. The test stub
>   in `test_ocr_pipeline.py` was updated in the SAME change (it now loads the
>   real `core.debug_artifact` alongside `core.numeric` via a shared
>   `load_real()` helper) — skipping that would have re-introduced the
>   isolation bug fixed on 2026-08-07.
> - **Line-merge grouping fix DONE locally (2026-08-08) — since COMMITTED as
>   `afd2ef2` and pushed 2026-08-09; see the current block above.**
>   `_group_detection_records` keeps the existing vertical/trend gate, then
>   vetoes candidates whose x-range overlaps any actual line member by more than
>   30% of the narrower width. The proposed 50% cutoff was rejected because a
>   confirmed `writer1_menu_dowhile_bond` merge is only 37.3%; measured retained
>   same-row fragments peaked at 7.9%. Per-member intervals avoid order-dependent
>   false splits across empty gaps in a multi-fragment line.
>   `build_recognition_dataset.py`: skips **8/21→7/21** overall and
>   **5/14→4/14** on samples; crops **113/13→126/14** train/val
>   (**126→140 total**). Recovered `nombrado_s01_total_loop_gate` and
>   `writer1_menu_dowhile_bond`. The documented
>   `submission_1785907170842` merge is also corrected; it is newly skipped
>   only because that exposes a pre-existing spurious bottom-page `0` detection,
>   not an over-split. All 7 test modules pass standalone; full suite **67/67**.
>   CER was not used as the signal because `normalize_ws` collapses newlines.
>   Full evidence: `ocr/LINE_MERGE_INVESTIGATION.md` and `ocr/EVALUATION.md`.
> - **Phantom detections — documented 2026-08-08, gated on clean images.**
>   The detector sometimes invents a line where there's no writing (the phantom
>   `0` on `submission_1785907170842`, a 9px box on a shadowed region — exposed
>   once the merge fix above stopped a canceling error from hiding it). Measured:
>   confidence can't catch it (0.713, above the 0.3 floor), but box height
>   separates it cleanly (0.13× median vs 0.59× smallest real, across all 277
>   detections). Candidate fix = height-outlier filter, but deliberately NOT
>   built: root cause is lighting, so the first test is whether clean captures
>   from the quality gate make it disappear on their own. Re-measure on clean
>   images before deciding a code filter is needed. Writeup:
>   `ocr/PHANTOM_DETECTION_INVESTIGATION.md`.
> - **~~⚠️ NOT YET COMMITTED~~ — committed 2026-08-09 as `afd2ef2`; only the
>   comment-only evaluator/preprocess changes remain uncommitted, by choice.
>   See the current block above.**
> - **Immediate next steps, in order (superseded by the list in the current
>   block's context — kept here for history):**
>   1. ~~Owner reviews~~ — done; landed as `afd2ef2`.
>   2. Only after the grouping fix lands, begin the C-formatter / judge0 work,
>      which depends on correct per-line text structure.
>   3. Send the shadow-detection writeup to Nikko (`ocr/QUALITY_GATE_REVIEW.md`,
>      with the "read-only reference, don't copy verbatim" caveat).
>   4. Retake all 14 sample images — every one currently has shadows or dim,
>      uneven lighting.
>   5. Re-verify retakes against physical paper, update `samples/labels.csv` if
>      text changed, rebuild `datasets/recognition/`, and rerun the builder.
>      Seven of 21 pages remain skipped (4/14 sample, 3/7 verified).
>   6. Keep collecting papers (more writers, raw pad coverage) toward the
>      200–500 line minimum-viable fine-tuning volume; see the 2026-08-06 block
>      below for the original targets.
>   7. Once volume is usable: Colab dry-run training as a pipeline proof, not a
>      baseline replacement.
>
> ---
>
> ## 🔵 STATUS 2026-08-06 (superseded by the 2026-08-08 block above)
>
> - **Binarization off by default (2026-08-06, measured).** `PreprocessConfig.
>   threshold` flipped `True → False` — PaddleOCR now receives the denoised
>   grayscale image, not a hard-binarized one. Full-cohort A/B: overall clean_ws
>   `0.166 → 0.149`, bond and greenbook subgroups both improved, 9/13 pages
>   better; pad slightly worse at n=2 (noise-level, revisit with more pad data).
>   `REC_SCORE_FLOOR` re-verified safe under grayscale. This `0.149` figure was
>   itself superseded later the same day — see the deciding experiment below.
>   Threshold code kept behind `threshold=True`. Full numbers:
>   `ocr/EVALUATION.md` top banner.
> - **THE DECIDING EXPERIMENT RAN (2026-08-06).** 7 of the raw `nombrado_*`
>   pages were retaken through Nikko's gate (camera-scan) and compared
>   page-for-page against their raw originals — same writer, same handwriting,
>   only the scanner's crop/de-warp+JPEG differing. Result: **paper-type
>   dependent, not a wash** — gate is worse on every bond page (+0.015 avg),
>   better on 2/3 greenbook pages (−0.012 avg). Raw versions replaced with
>   gate versions in `samples/` (ground truth unchanged); `samples/` is now
>   **100% gate-framed** — no more raw/production inconsistency. Full table:
>   `ocr/EVALUATION.md` top banner.
> - **Current official baseline: `clean_ws 0.149`** over 14 gate-framed samples
>   (bond 0.133 / greenbook 0.159 / yellow_pad 0.171). (The interim `0.151`/12
>   figure predated the two `writer1` pages; adding them settled it at 0.149.)
> - **Quality gate shipped raw-upload** (Nikko, branch tip `d57a1bc`, verified
>   directly): raw-only upload, `SCANNER_MODE_BASE`, `processDocument` removed,
>   Enhance filter removed. Gate now does ONLY geometric de-warp + JPEG — zero
>   photometric processing. DB images are raw, just *framed*. The old
>   "illumination normalization" concerns in `QUALITY_GATE_REVIEW.md` §5–§7 are
>   resolved/obsolete (see that file's top banner).
> - **Ruled-line removal REMOVED 2026-08-06.** Built two removers + a denoise-
>   threshold variant, measured all three against the gate-framed samples, none
>   was a net win (width alone can't separate printed rules from handwriting).
>   Code deleted; finding preserved in `ocr/EVALUATION.md` + git. 65/65 tests pass.
> - **Immediate next task:** the raw-vs-gate experiment is DONE (see above).
>   Next up: process the next batch of papers from a new writer (already in
>   progress), plus more raw pad coverage. Device for Nikko's thresholds:
>   M2101K6G / Android 13. Keep collecting ruled-paper + more writers toward
>   fine-tuning.
> - **Data-collection rule:** `samples/` = test (verify via chat → physical
>   paper → paste back, NEVER the app's "Save Verified Text" button, which routes
>   to training via `export_dataset.py`). `datasets/verified/` = train. No image
>   in both.
>
> ---
>
> **OCR STATUS (2026-08-03) — supersedes the 2026-08-02 retraction.** The 13
> labels under `ocr_feature/samples/` were physically verified and are literal
> (the earlier "not literal / s04–s07" claim was an AI photo-read error, since
> withdrawn). They are now valid for accuracy and model-ranking claims. Models
> swapped to **`PP-OCRv6_medium`** (v6 beat v5 `0.181` on the original 13-page
> cohort at `0.148`). **Baseline update 2026-08-04:** those 5 `nikko` close-ups
> were deleted (non-representative), so the baseline then became
> **`clean_ws 0.190`** over 8 full-page `nombrado` captures — itself superseded
> 2026-08-06 by `0.149` under the grayscale default (see status block above) — (bond 0.165 / greenbook
> 0.231) — a cohort change, not a regression (see `ocr/EVALUATION.md`). Consensus
> tested, rejected, and code removed 2026-08-04. Run
> evaluators as modules: `python -m evaluators.evaluate_cer`. Still do not tune
> against these already-viewed 13 pages — use a fresh cohort.
> See [`ocr/RAW_OCR_CONSENSUS_HANDOFF.md`](ocr/RAW_OCR_CONSENSUS_HANDOFF.md).
> The evaluators enforce this fail-closed before OCR models load: every
> `labels.csv` row must have `literal_verified=true` and nonblank
> `literal_verified_by` and `literal_verified_at`.

## Where things stand right now

The OCR extraction pipeline (`ocr_feature/`) is functionally complete for
the milestone: capture → extract → keyword cleanup → reading-order
correction → confidence filtering → editable code widget for teacher
verification. See [`ocr/PIPELINE.md`](ocr/PIPELINE.md) for exactly how and
why each part works the way it does.

**What's NOT done, and can't be yet:** model fine-tuning. The recognition
model is the off-the-shelf `PP-OCRv6_medium_rec` (swapped from
`en_PP-OCRv5_mobile_rec` on 2026-08-03; `clean_ws 0.181 → 0.148` on the
verified cohort — see `ocr/PIPELINE.md`). That was a model *selection*, not
fine-tuning — every improvement so far is choosing/configuring off-the-shelf
models, not training one. Character-level misreads persist and are dominated by
structural C punctuation: braces are near 0% recall (`}` at ~0%, `{` ~35%),
semicolons often read as commas. These are a recognition-model limitation that
only fine-tuning fixes — see [`ocr/LIMITATIONS.md`](ocr/LIMITATIONS.md) for the
full breakdown of what's fixable by engineering vs. what needs fine-tuning.

## The actual blocker: dataset size

> **Superseded in part — see the 2026-08-06 status block at top.** The "zero
> validated pages" framing below is stale: `samples/labels.csv` now has verified
> pages with full literal provenance (the original 8 nombrado + 5 gate-framed).
> The core point still holds: the *volume* is nowhere near fine-tuning scale.

Fine-tuning cannot start yet. Current labeled dataset (2026-08-02):
**13 samples** in `ocr_feature/samples/` + `labels.csv` — 2 writers, bond
+ greenbook paper. The earlier claim that every label was individually
verified against the physical page is retracted: the cohort requires complete
literal human revalidation and currently contributes **zero validated
accuracy-reference pages**. There is also 1 potentially usable Supabase pair
(`d8cb2ec1`), but it needs the same explicit provenance check before training
or evaluation; see below for why the other 6 exported pairs don't count.

| Tier | Lines needed | Status |
|---|---|---|
| Dry run / pipeline test | 5–20 | ⚠️ 13 images exist; labels need literal revalidation |
| Minimum viable attempt | 200–500 | ❌ not there |
| Reasonable first real attempt | 1,000–2,000 | ❌ far off |

This is not a gap in the engineering work — it's a data-collection
bottleneck. See [`ocr/EVALUATION.md`](ocr/EVALUATION.md) for exactly how to
add samples and why writer diversity matters more than raw volume.

**The dataset also collects itself, with a caveat learned the hard
way.** `ocr_feature/evaluators/export_dataset.py` pulls every teacher-verified
submission from Supabase into `datasets/verified/`. **But `status='verified'`
does not currently guarantee a human actually corrected the text** — of 7
exported pairs, only 1 (`d8cb2ec1`) is a genuine correction; 4 are the
OCR's own output saved unedited, and 1 has a label describing a different
program than its image entirely. This was discovered by treating those
labels as ground truth and getting a measurement retraction as a result
(full story: `ocr/CAPTURE_GATE_FINDINGS_3_CORRECTION.md` §8). **An export
guard that requires an explicit human-review signal, not just the
`verified` status, is still an open task** — see the cleanup section below.

**Paper types matter as much as writer count.** The university uses exactly
three: bond (short/long), greenbook, yellow pad. The historical claim that
greenbook scored ~2.3× worse than bond, and that `adaptive_denoise` partially
closed that gap, is a canonical-reference diagnostic—not validated accuracy or
a defensible paper-type ranking. Paper diversity is still a sound collection
requirement, but its effect must be remeasured only after literal labels exist.
Yellow pad is not yet represented in any collected data.

**If you're picking this up to help collect data:** the fastest way is
dictating a fixed list of C snippets to multiple different people to
copy-write by hand (not asking them to write arbitrary code) — you already
know the intended prompt in advance, but the prompt is **not** ground truth:
writers can make mistakes or substitutions. A second human must still inspect
each physical page and transcribe exactly what was written, including errors,
with provenance. This prevents labels from being derived from OCR output while
remaining character-faithful. Prioritize many writers across all three paper
types over many snippets from one person on one paper type.

## Colab fine-tuning dry run

Moved to its own doc so it's a standalone, followable reference:
[`ocr/COLAB_FINE_TUNING_GUIDE.md`](ocr/COLAB_FINE_TUNING_GUIDE.md). Summary:
14-step procedure (build crop dataset locally → zip → upload to Colab →
install the pinned `paddleocr==3.7.0` + PaddleX's PaddleOCR training plugin →
train → export → swap the checkpoint into `ocr_pipeline.py` → re-measure).
At current volume (140 crops) this is a **pipeline-mechanics proof only**,
not a real fine-tuning attempt — see that doc's caveat before running it.

## Known bugs — all fixed

The two code-review findings are fixed and committed (line-merge:
`b72f427`; save-status race: `263b6d7`). Full history in
[`PENDING_FIXES.md`](PENDING_FIXES.md).

A third, worse bug was found and fixed on 2026-07-29 while building the
dataset export: **verification save was overwriting `extracted_text`**
with the teacher's edits, so every verified submission measured a false
0.0 CER — the record of what the OCR actually output was being destroyed.
Fixed in `bf0c331` (on `ocr_feature`): teacher edits now go only to
`verified_text`; `extracted_text` keeps the OCR's own output. The 7
submissions verified before the fix have corrupted `extracted_text`
(unrecoverable). Their image + `verified_text` pairs are only training-data
candidates; none is valid until the text receives literal review and the
required verifier/date provenance.

## Historical experiments (accuracy rankings retracted; do not rerun this cohort)

- Preprocessing (grayscale/denoise/threshold) — A/B tested multiple times,
  with historical canonical-reference diagnostics favoring the current
  config. That is not a validated accuracy ranking. **Note:** an earlier
  ablation claiming this was also validated against "7 real teacher-verified
  captures" at 0.153 CER was retracted — those labels were mostly the OCR's
  own output, not independent ground truth. The dev-sample result and the
  broader lesson that preprocessing can behave differently across capture
  conditions remains a hypothesis to retest with valid literal ground truth;
  no accuracy ranking from the current labels stands. See `ocr/EVALUATION.md`.
- Detection model: `PP-OCRv6_medium_det` (as of 2026-08-03). A verified-label
  sweep confirmed the heavier `PP-OCRv5_server_det` is *worse* at ~9x runtime, so
  detection stays lightweight; detection is not the bottleneck. Supersedes the
  earlier `PP-OCRv5_mobile_det` default and the retracted mobile-vs-server
  accuracy claim.
- Recognition model: `PP-OCRv6_medium_rec` (as of 2026-08-03), selected on the
  13 verified labels (`clean_ws 0.181 → 0.148`). The earlier `en_PP-OCRv5_mobile_rec`
  was pinned to avoid multilingual CJK misreads; on verified labels that CJK cost
  measured ~0.0001 CER, far below the 0.033 gain, so v6 was adopted and a
  non-ASCII filter was deliberately not added (self-announcing errors are safer
  than silent deletions in grading). `PP-OCRv5_server_rec` was confirmed worse
  (0.279, heavy CJK). See `ocr/PIPELINE.md`.
- Reading-order + line-merging, confidence-based phantom filtering — both
  remain implemented; their accuracy effect is not validated by this cohort.
- **2026-08-02: two adaptive preprocessing features, both on by default.**
  `threshold_block_scale` sizes the threshold block to each page's measured
  handwriting size (historical diagnostic 0.223 → 0.198).
  `adaptive_denoise` classifies each page's paper texture and raises
  denoise strength only on textured paper like greenbook (historical
  diagnostic 0.198 → 0.181 overall, greenbook 0.354 → 0.282). These figures
  are not OCR accuracy and do not validate either feature's ranking. The old
  ablation also included several
  things whose canonical-reference diagnostics did not improve (ruled-line
  removal, CLAHE, Sauvola, higher-resolution recognition). Do not treat that
  as a valid ranking or rerun them on this cohort; retest only under a future
  provenance-backed protocol.
- Cross-platform `requirements.txt` + a real PaddlePaddle version bug fixed
  and verified against the actual upstream GitHub issue. See
  [`ocr/TROUBLESHOOTING.md`](ocr/TROUBLESHOOTING.md).

## Remaining optional improvements (lower priority, do after data collection is underway)

- **Guarded function-call OCR suggestions** — the combined OCR-review
  highlighter is implemented. The next scoped improvement is the evaluated,
  non-mutating unique one-edit matcher documented in
  `ocr/OCR_REVIEW_SUGGESTION_AB.md`. Keep its ambiguity/declaration guards and
  rerun the held-out evaluation after implementation.
- **Detection parameter tuning** (e.g. `text_det_unclip_ratio`) — minor,
  untested, lowest priority of everything on this list.

## Open coordination item (not OCR, but affects OCR results)

**2026-08-25 — proposed skew/angle rejection check, unresolved.** JC raised
adding a skew/angle check to the quality gate: reject a photo outright if
the paper is tilted at a significant angle, before it reaches OCR, so OCR
never has to compensate for geometry. Agreed in principle this belongs at
the gate (validation/geometry only, consistent with
`quality-gate-should-not-binarize`) and is orthogonal to the grayscale-vs-
binarization work (pixel-intensity axis vs. geometry axis — fixing one
doesn't substitute for the other). **Unresolved technical question, not yet
answered:** does the scanner's existing `warpPerspective` crop already
correct in-plane rotation (a page photographed straight-on but sitting
crooked) as a side effect of its corner-quad warp, or does it only fix
trapezoidal perspective distortion and leave rotation intact? Those are two
different corrections — perspective-safe doesn't imply rotation-safe. Not
verified against the actual scanner code (not in this repo, couldn't be
checked from the OCR side). **Next step:** confirm with JC/whoever owns the
scanner code before building a possibly-redundant Hough-line-based rotation
check; if rotation does survive the crop, a reject-only (not correcting)
Hough-line check on the gate is the agreed-on direction.

The mobile app's capture-quality gate has a `feature/slant-detection` branch
(teammate's work) not yet merged to `develop`. Its blur threshold was
calibrated against real OCR confidence data earlier this session (~1300,
reviewed independently by both component owners). That refers only to the
blur-threshold review, not independent transcription or OCR-accuracy
validation. Worth checking whether it's merged and whether the threshold held
up; any claimed effect on OCR accuracy needs valid literal references.

**Update 2026-07-29 — gate findings from real-capture analysis** (12
uploaded images run through the pipeline, gate code reviewed). **Note:**
the "0.095 vs 0.153" comparison originally in this bullet was retracted —
0.153 came from the same tainted `verified_text` labels described above.
The confidence-based observations below don't depend on that number and
still stand (they're about detection confidence, not CER against a
label):

- Same page captured 3× (`5424c20b`/`7b2f4eac`/`efcff566`) produced three
  different misreads of the same word (`zer0`/`2e00`/`2er0`) — capture
  conditions alone change errors.
- **Gap: nothing in the gate (merged or WIP) checks framing/page
  boundaries.** A sharp, well-lit, straight capture (`7b2f4eac`) contained
  a confident phantom line (`return o`) from outside the answer area —
  passes every existing check, can't be confidence-filtered (scored high).
  Fix belongs capture-side: framing guide / page-boundary detection.
- Calibration data for gate thresholds now exists: bad captures measured
  0.77–0.80 average OCR confidence, clean ones 0.87–0.93 → "flag below
  ~0.85" is evidence-backed. The gate's current numbers (blur 1300,
  lighting spread 50, slant cv 1.0) can be validated against the 12 real
  uploads + their `outputs/debug/` JSONs.
- WIP slant detection caveats: possible false positive on sparsely
  written pages (flat projection ≠ slanted); leftover debug `print`.

## Handing over the capture-gate findings (private note)

**Current version:**
[`ocr/CAPTURE_GATE_FINDINGS_3_CORRECTION.md`](ocr/CAPTURE_GATE_FINDINGS_3_CORRECTION.md)
— this is what was actually sent to the teammate. Rounds 1
([`CAPTURE_GATE_FINDINGS.md`](ocr/CAPTURE_GATE_FINDINGS.md)) and 2
(`_2.md`) are retracted; kept only for the record, with banners at the
top of each. The old delivery guidance is superseded wherever it treated CER
against the withdrawn labels as evidence. Keep the component-level language
and caveats, but attach the retraction explicitly:

1. Lead with §3 (what works) — the document scanner solves the framing
   phantom, which is the hardest problem on the capture side.
2. Present §5 only as a retracted canonical-reference diagnostic. Do not call
   the set verified and do not claim it measured OCR accuracy.
3. Explain that confidence and visual inspection cannot substitute for literal
   ground truth; no regression or improvement claim survives from this set.
4. Offer §10 as a joint session rather than a request for rework, and
   note that §8 item 1 is a question, not an accusation — local testing
   via `/api/ocr/extract-upload` would leave no trace visible from the
   OCR side.
5. State the §1 caveats before he does: the numbers come from his
   enhancement applied to old raw captures, not from his real pipeline.

Framing for the milestone writeup, which is defensible and person-neutral:
*"The prior capture-enhancement accuracy comparison was retracted because its
references were not proven literal ground truth. A joint calibration and
human-transcription protocol was defined; no accuracy ranking should be made
until new valid evidence exists."*

## Quick reference: how to check anything yourself

```bash
cd ocr_feature
source .venv/bin/activate
# Do not run either OCR evaluator on the current 13 labels.
# First obtain literal human revalidation and define a fresh protocol.
# Every labels.csv row must then have literal_verified=true plus nonblank
# literal_verified_by and literal_verified_at before models will load.
```

Full setup instructions: [`ocr/README.md`](ocr/README.md).

This file is the single current-state narrative — updated in place as things
change, organized by topic, with the valid/retracted split called out inline.
