# Dataset photo review — verdicts (2026-08-17 batch, all greenbook, already-graded papers)

Source: `untitled folder` on Desktop (160 unique photos after excluding Live Photo
`.MOV`/`.AAE` sidecars and Photos-app-edited `" 1.HEIC"` duplicates). Reviewed from
downsized 1200px JPEGs, not full-resolution HEIC — spot-check full-res before final use,
especially the flagged small-mark cases below.

**Independent visual re-audit (2026-08-17):** classifications below were re-derived from
the actual JPEG pixels, without using the previous verdict labels as evidence. The prior
categories were treated only as folders to inspect; they were rewritten after the image
review.

Folders: `usable/`, `usable_if_cropped/`, `not_usable/`, and
`deferred_needs_line_exclusion/` (potentially usable once per-line exclusion is supported).

**Important crop distinction:** the recognition builder later creates one crop per
detected handwritten line, but that is not the same as cleaning a source page. It does
not automatically remove page edges, rotate a page, or discard a line containing an
unrecoverable scribble. Therefore `usable_if_cropped` means the source page needs a
simple page-level trim or orientation fix before line extraction; it does not mean that
every page that will produce line crops belongs there. Pages whose code is already
legible remain `usable`.

## Consistent categorization rule

- **usable** — the target C code is legible. Non-obscuring ticks, circles, erasures,
  scratch work, readable strike-throughs, and additional legible handwriting do not
  disqualify a page. This includes `IMG_0259`: the lower calculation is legible and
  does not hide the code above it.
- **usable_if_cropped** — the target code is legible, but unrelated edge content or
  a small non-code area must be removed with a simple crop. A blank facing page alone
  does not require cropping.
- **deferred_needs_line_exclusion** — most code is useful, but one or more mid-page
  lines contain genuinely unrecoverable content. These are not ready for the current
  whole-page dataset builder, which has no per-line exclusion support. The readable
  lines should be retained; only the obscured lines should be excluded once that
  per-line workflow is available.
- **not_usable** — relevant C/algorithm content is materially unreadable, or the
  page contains no useful C-related content. A legible worksheet, trace, fragment,
  or partial answer is still `usable` even when it is not a complete program.

## Implementation handoff

These folders are the human-reviewed source-page staging set. The recognition builder
should apply the same workflow to every accepted page:

1. `usable`: run normal line detection and line cropping.
2. `usable_if_cropped`: apply the required page-level trim or rotation, then run line
   detection and line cropping.
3. `deferred_needs_line_exclusion`: retain readable detected lines and exclude only
   the explicitly obscured lines; do not discard the entire page. This requires a
   per-page exclusion manifest or equivalent line-selection support.
4. `not_usable`: exclude from dataset generation.

The current builder reads `samples/` and `datasets/verified/`, not these review folders,
and skips a whole page when detected and labeled line counts differ. Future changes
must preserve label alignment when adding per-line exclusions.

## Known duplicate/burst shots — don't double-count as separate pages

- `IMG_0250` / `IMG_0256` / `IMG_E0250` — same page; keep `IMG_0250` as the
  canonical copy and drop `IMG_0256`/`IMG_E0250`; the page remains deferred pending
  line exclusion
- `IMG_0350` / `IMG_0351` — duplicate page; keep usable `IMG_0350`, drop `IMG_0351`
- `IMG_0390` + `E0390`, `IMG_0428`–`IMG_0432` + their `E`-twins — same pages shot twice;
  the `E` version is upright, the plain-numbered one is sideways — **RESOLVED 2026-08-17:
  plain-numbered sideways copies dropped from `usable_if_cropped/`, only `E`-versions kept**
- **RESOLVED 2026-08-17** — `0358`/`E0358` and `0374`/`E0374` are pixel-identical;
  `0367`/`E0367` is the same page, `0367` sideways. Kept `E0358`, `E0367`, `E0374`;
  dropped `0358`, `0367`, `0374`.

## Re-audit (2026-08-17)

Corrected an inconsistency: many entries here were marks/self-corrections identical in kind
to hundreds already accepted as `usable` elsewhere (non-overlapping ticks/circles, or strikes
still legible underneath). Those 7 were moved to `usable` with no editing needed:
`IMG_0248`, `IMG_0296`, `IMG_0299`, `IMG_0316`, `IMG_0324`, `IMG_0362`, `IMG_E0390`.

A second legibility pass found additional pages that were too strictly rejected. These
were moved to `usable` because their C code remains readable despite abandoned attempts,
grading marks, annotations, or scratch work: `IMG_0255`, `IMG_0260`, `IMG_0263`,
`IMG_0301`, `IMG_0327`, `IMG_0355`.

Pages with readable code but genuinely obscured mid-page lines were moved to
`deferred_needs_line_exclusion`: `IMG_0279`, `IMG_0290`, `IMG_0338`, `IMG_0343`,
`IMG_0384`.

`IMG_0311` was reviewed again and promoted to `usable`: the apparent whiteout/strike
does not prevent reading the code, so it does not require line exclusion.

The same rule was applied to seven deferred pages whose marks affect only small areas
and do not prevent reading the page: `IMG_0320`, `IMG_0357`, `IMG_0359`, `IMG_0369`,
`IMG_0381`, `IMG_0384`, and `IMG_0385`. These were promoted to `usable`.

`IMG_0380` was also promoted to `usable`: its array/function notes are legible, and
the blank lower area and surrounding scratch work do not require cropping.

The remaining genuinely obscure otherwise-unrecoverable content (dense scribble/whiteout
you can't read through) or mix code with non-code content is not fixable by a paint-over mask.
Two real subtypes remain:
- **Edge trim** — `IMG_0278`, `IMG_0281`, `IMG_0302`
- **Needs per-line exclusion** — `IMG_0250`, `IMG_0279`, `IMG_0290`, `IMG_0308`,
  `IMG_0338`, `IMG_0343`, `IMG_0392`. **Note:**
  `build_recognition_dataset.py` currently has no per-line exclusion — it is whole-page only
  (line-count mismatch skips the entire page). These need either that capability built, or
  manual exclusion of just those pages when building the training set.

## Needs a full-resolution spot-check (small/thin marks, verdict may change)

`IMG_0308`, `IMG_0316`, `IMG_0357`

## Full per-file table

| File | Verdict | Note |
|---|---|---|
| IMG_0245 | usable | clean, no marks/erasures |
| IMG_0246 | usable | crossed-out lines, still fully legible (printf/scanf/if visible), confirmed by user |
| IMG_0247 | usable | red squiggle near `if` line, graded-paper mark; code remains legible |
| IMG_0248 | usable | red squiggle in blank space + a fully-scratched abandoned line (natural to skip in transcription), rest fully legible — reclassified 2026-08-17 |
| IMG_0250 | deferred_needs_line_exclusion | heavy mid-page scribble block; surrounding C code remains readable; duplicate of 0256/E0250 |
| IMG_0253 | usable | minor self-correction strikethrough |
| IMG_0254 | usable | red tick margin, not overlapping |
| IMG_0255 | usable | abandoned first attempt and scratch work, but the lower C solution remains legible — reclassified 2026-08-17 |
| IMG_0256 | dropped | duplicate of canonical `IMG_0250`; removed from the review folders — reclassified 2026-08-17 |
| IMG_0257 | usable | clean |
| IMG_0258 | usable | clean, sparse |
| IMG_0259 | usable | clean, legible code; lower calculation is separate and does not obscure it — reclassified 2026-08-17 |
| IMG_0260 | usable | annotations and output diagrams are present, but the C code remains legible — reclassified 2026-08-17 |
| IMG_0261 | usable | self-correction strike + margin marks |
| IMG_0262 | usable | clean |
| IMG_0263 | usable | first attempt is crossed out, but the second C solution remains legible — reclassified 2026-08-17 |
| IMG_0264 | usable | rotated by user 2026-08-17, now upright and legible |
| IMG_0265 | usable | clean fragment |
| IMG_0266 | usable | white correction-tape patches present, text unaffected |
| IMG_0267 | usable | clean |
| IMG_0268 | usable | sparse fragment, legible |
| IMG_0269 | usable | small red circle, non-overlapping |
| IMG_0270 | usable | red circle/strike thin, legible underneath |
| IMG_0271 | usable | red circles encircle text, don't obscure |
| IMG_0272 | usable | sparse, legible |
| IMG_0273 | usable | minor self-correction |
| IMG_0274 | usable | minor self-correction, red arrows margin |
| IMG_0275 | usable | thin red circle, non-obscuring |
| IMG_0276 | usable | red circle encircles block |
| IMG_0277 | usable | sparse scratch fragments, legible |
| IMG_0278 | usable_if_cropped | dense illegible scribble at top (genuinely unreadable, not a legible-through strike) — needs top-edge trim, clean switch-case below |
| IMG_0279 | deferred_needs_line_exclusion | red X and black scribbles obscure several mid-page lines, but the remaining C code is readable |
| IMG_0280 | usable | clean |
| IMG_0281 | usable_if_cropped | illegible black blob at very top only — needs top-edge trim, rest clean |
| IMG_0282 | usable | clean |
| IMG_0283 | usable | minor self-correction |
| IMG_0284 | usable | math scratch in margin, doesn't overlap |
| IMG_0285 | usable | minor self-corrections |
| IMG_0286 | usable | clean |
| IMG_0287 | usable | sparse, clean |
| IMG_0288 | usable | small red dots, non-overlapping |
| IMG_0289 | usable | legible C-related worksheet with `scanf`, arrays, indexing, and output traces — reclassified 2026-08-17 |
| IMG_0290 | deferred_needs_line_exclusion | whiteout covers several lines, but the remaining C code is readable; exclude the obscured lines |
| IMG_0291 | usable | small localized corrections |
| IMG_0292 | usable | minor red tick |
| IMG_0293 | usable | red arrows in margin |
| IMG_0294 | usable | short self-correction scribble |
| IMG_0295 | usable | thin red marks, legible |
| IMG_0296 | usable | not actually a two-page spread (mislabel corrected); small scribbled fragment at top of one "case," other 3 cases fully clean — reclassified 2026-08-17 |
| IMG_0297 | usable | sparse scratch fragment |
| IMG_0298 | usable | tiny red tick |
| IMG_0299 | usable | not actually a two-page spread (mislabel corrected); red circles don't obscure text — reclassified 2026-08-17 |
| IMG_0300 | usable | thin red margin marks |
| IMG_0301 | usable | low contrast and grading marks are present, but the C code remains readable — reclassified 2026-08-17 |
| IMG_0302 | usable_if_cropped | only top ~4 lines legible, rest is severe bleed-through ghosting — needs bottom-edge trim |
| IMG_0303 | usable | small red circle |
| IMG_0304 | usable | sparse, legible |
| IMG_0305 | usable | tiny non-obscuring white patches |
| IMG_0306 | usable | tiny non-obscuring white patches |
| IMG_0307 | usable | red margin comment, non-overlapping |
| IMG_0308 | deferred_needs_line_exclusion | whiteout genuinely covers several words (not a legible-through strike) — needs those specific lines excluded, verify at full res |
| IMG_0309 | usable | small red margin marks |
| IMG_0310 | usable | small red tick + margin patches |
| IMG_0311 | usable | X-strike and grading marks are present, but the code remains readable — reclassified 2026-08-17 |
| IMG_0312 | usable | faint bleed-through, doesn't obscure |
| IMG_0313 | usable | red circle/check margin |
| IMG_0314 | usable | clean |
| IMG_0315 | usable | self-correction + red ticks |
| IMG_0316 | usable | red mark in blank space, self-correction legible through strike, trailing illegible bit is a natural stopping point (like IMG_0246) — reclassified 2026-08-17 |
| IMG_0317 | usable | decorative doodle in margin only |
| IMG_0318 | usable | self-corrections + margin ticks |
| IMG_0319 | usable | red margin comment |
| IMG_0320 | usable | one marked `if` line is still readable in context; the page remains usable — reclassified 2026-08-17 |
| IMG_0321 | usable | red circle/arrow margin |
| IMG_0322 | usable | red check margin |
| IMG_0323 | usable | small red margin mark |
| IMG_0324 | usable | fully legible through the diagonal strike (like IMG_0246/IMG_0344) — reclassified 2026-08-17 |
| IMG_0325 | usable | thin orange circle |
| IMG_0326 | usable | one self-correction strike, rest clean |
| IMG_0327 | usable | marked earlier fragment and scratch work, but the C code remains readable — reclassified 2026-08-17 |
| IMG_0328 | usable | small orange margin mark |
| IMG_0329 | usable | orange margin marks + minor self-correction |
| IMG_0330 | usable | minor self-corrections |
| IMG_0331 | usable | orange margin arrows |
| IMG_0332 | usable | orange tick margin |
| IMG_0333 | usable | orange circle, non-obscuring |
| IMG_0334 | usable | minor self-correction scribble |
| IMG_0335 | usable | self-correction strike, legible |
| IMG_0336 | usable | orange margin marks |
| IMG_0337 | usable | orange marks in margin |
| IMG_0338 | deferred_needs_line_exclusion | scribbles obscure several mid-page lines, while the remaining C code is readable |
| IMG_0339 | usable | orange margin marks |
| IMG_0340 | usable | minor orange arrow |
| IMG_0341 | usable | orange marks + minor inline self-correction |
| IMG_0342 | usable | minor orange margin marks |
| IMG_0343 | deferred_needs_line_exclusion | dense scribble blocks obscure several lines; the remaining C code is readable |
| IMG_0344 | usable | diagonal strike not bold, confirmed legible underneath by user |
| IMG_0345 | usable | tiny red squiggle |
| IMG_0346 | usable | minor self-correction scribble |
| IMG_0347 | usable | moderate short self-corrections, legible |
| IMG_0348 | usable | one small self-correction |
| IMG_0349 | usable | one small self-correction |
| IMG_0350 | usable | sparse, one word struck |
| IMG_0351 | dropped | duplicate of usable `IMG_0350`; removed from the review folders — reclassified 2026-08-17 |
| IMG_0352 | usable | clean |
| IMG_0353 | usable | self-correction strikes, legible |
| IMG_0354 | usable | minor self-correction |
| IMG_0355 | usable | abandoned restart and scratch marks are present, but the remaining C code is legible — reclassified 2026-08-17 |
| IMG_0356 | usable | sparse fragment, minor single-word scribble |
| IMG_0357 | usable | marked characters are localized and the surrounding C solution remains readable — reclassified 2026-08-17 |
| IMG_0358 | dropped | pixel-identical duplicate of IMG_E0358, kept E-version instead |
| IMG_0359 | usable | localized scribble does not prevent reading the remaining C answer — reclassified 2026-08-17 |
| IMG_0360 | usable | minor self-correction |
| IMG_0361 | usable | single thin self-correction strike |
| IMG_0362 | usable | hatched block is a fully abandoned/replaced attempt (skip in transcription), content before and after is legible — reclassified 2026-08-17 |
| IMG_0363 | usable | sparse, faint bleed-through doesn't obscure |
| IMG_0364 | usable | tiny red margin mark |
| IMG_0365 | usable | thin red marks, legible |
| IMG_0367 | dropped | sideways duplicate of IMG_E0367, kept upright E-version instead |
| IMG_0368 | usable | red margin comment + thin marks |
| IMG_0369 | usable | localized mark affects one expression, while the rest of the C content remains readable — reclassified 2026-08-17 |
| IMG_0370 | usable | minor self-corrections |
| IMG_0371 | usable | minor self-corrections + red margin marks |
| IMG_0374 | dropped | pixel-identical duplicate of IMG_E0374, kept E-version instead |
| IMG_0375 | usable | thin red margin marks |
| IMG_0376 | usable | tiny red squiggle |
| IMG_0378 | usable | minor self-correction + small red mark |
| IMG_0379 | usable | clean, normal code comments only |
| IMG_0380 | usable | legible array/function notes; blank lower area and scratch work do not require cropping — reclassified 2026-08-17 |
| IMG_0381 | usable | localized whiteout/marks do not prevent reading the page — reclassified 2026-08-17 |
| IMG_0382 | usable | one thin self-correction |
| IMG_0383 | usable | small red ticks |
| IMG_0384 | usable | strike-throughs and scribbles are present, but the C content remains readable — reclassified 2026-08-17 |
| IMG_0385 | usable | small marked token does not prevent reading the C content — reclassified 2026-08-17 |
| IMG_0386 | usable | clean |
| IMG_0388 | usable | minor self-correction + small red mark |
| IMG_0389 | usable | minor crossed-out short segment |
| IMG_0390 | usable_if_cropped | rotated; dup of IMG_E0390, prefer E-version |
| IMG_0391 | usable | minor red mark + small crossed word |
| IMG_0392 | deferred_needs_line_exclusion | dense black scribble genuinely covers ~2 lines mid-page, unrecoverable — needs those lines excluded, clean before/after |
| IMG_0393 | not_usable | very heavy scribble/scratch-out covering ~half the page |
| IMG_0394 | usable | clean |
| IMG_0395 | usable | clean |
| IMG_0396 | usable | clean |
| IMG_0428 | usable_if_cropped | rotated; dup of IMG_E0428, prefer E-version |
| IMG_0429 | usable_if_cropped | rotated; dup of IMG_E0429, prefer E-version |
| IMG_0430 | usable_if_cropped | rotated; dup of IMG_E0430, prefer E-version |
| IMG_0431 | usable_if_cropped | rotated; dup of IMG_E0431, prefer E-version |
| IMG_0432 | usable_if_cropped | rotated; dup of IMG_E0432, prefer E-version |
| IMG_E0250 | dropped | duplicate of canonical `IMG_0250`; removed from the review folders — reclassified 2026-08-17 |
| IMG_E0264 | usable | moderately messy but legible; distinct content from IMG_0264 |
| IMG_E0358 | usable | orange marks non-overlapping; possible dup/retake of IMG_0358 |
| IMG_E0367 | usable | orange marks non-overlapping; possible dup/retake of IMG_0367 |
| IMG_E0374 | usable | left answer page is fully legible; blank facing page does not interfere — reclassified 2026-08-17 |
| IMG_E0390 | usable | upright (preferred over IMG_0390), self-correction legible through strike, red circles don't obscure — reclassified 2026-08-17 |
| IMG_E0428 | usable | upright, clean; preferred over IMG_0428 |
| IMG_E0429 | usable | upright, clean; preferred over IMG_0429 |
| IMG_E0430 | usable | upright, clean; preferred over IMG_0430 |
| IMG_E0431 | usable | upright, clean; preferred over IMG_0431 |
| IMG_E0432 | usable | upright, clean; preferred over IMG_0432 |
