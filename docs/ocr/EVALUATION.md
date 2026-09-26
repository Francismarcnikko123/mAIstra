# OCR Evaluation — CER Methodology

## Speed experiment: CPU threads and recognition batch size — 2026-09-24

**Question:** can extraction be made faster without changing the model or the image?

**Where the time goes** (Apple M3, 8 cores, CPU only; greenbook page, 47 lines):
- preprocessing: 0.1 s
- detection: about 1.5 s
- recognition: most of the rest
- a full page: about 7.4 s
- model load at server start: 4.3 s, once

**Test:** 4 pages (2 greenbook, 1 bond, 1 yellow pad), timed within one run. Absolute times drift between runs, so only compare rows within the same run.

| Setting | s/page | Output vs current |
|---|---|---|
| threads 10 (default), batch 6 (default) | 10.8 / 11.5 | — |
| threads 8 or 4, batch 6 | 10.7–10.9 | identical |
| batch 12 / 24 / 3 | 11.7–13.1 | different |
| **batch 1** | **6.4** | **different** |

**Full evaluation of batch 1** (`evaluate_cer`, 20 pages), against the shipped batch 6:
- clean_ws CER 0.099 → **0.100**
- clean WER 0.328 → **0.331**
- clean token accuracy 0.716 → **0.714**
- 9 pages got worse and 3 better, by 0.004–0.011 CER each

**Decision: keep batch 6 (not changed).**
- Thread count has no effect.
- Batch 1 is about 45% faster but slightly less accurate. Switching would also mean re-recording every cited number, and the thesis rule is that the measured configuration is the one that runs.
- The waiting problem is addressed by the optional pre-extraction worker on `feature/pre-extraction` ([implementation plan](../superpowers/plans/2026-09-24-pre-extraction-on-arrival.md)); it hides the wait without changing the model or measured results.
- Revisit batch 1 only with a deliberate re-baseline, e.g. after the next fine-tune, when all numbers are re-measured anyway.

## Continuation experiment — 2026-09-14

Current production regression is clean_ws CER 0.099, clean WER 0.328, clean token
accuracy 0.716 and green_writer10 clean_ws CER 0.061. These CER results run the
production pipeline, not the offline prototype. In the separate same-writer
association pilot, exact retained-record order is 8/8 development and 3/3 reserved;
strict continuation-edge recall is 6/8 and 1/2 respectively. Correct order is not
membership accuracy. Manual photo testing reports proposals, not accuracy scores.

Reserved results are now known; use a fresh holdout if they inform v2 rules. All
11 supplied photos were included; the skipped Example 7 ID is an unresolved mapping,
not evidence of missing input. The historical frozen manifests remain unchanged.
Full metrics, protocol and commands: [session handoff](../../ocr_feature/reports/2026-09-14-continuation-session-handoff.md).

> ## ⚠️ Confidence-flag precision measured — 2026-09-04 (the flag is high-precision, LOW-recall)
>
> Before shipping the web confidence-highlighting feature, measured whether a
> low per-line confidence actually predicts a wrong line. On `samples/` (361
> OCR lines, 105 = 29% actually wrong vs. their best-match verified line):
>
> | threshold | lines flagged | precision | recall | errors MISSED (confident misreads) |
> |---|---|---|---|---|
> | < 0.70 | 6 | 0.67 | 0.04 | 101 (96%) |
> | < 0.75 | 9 | 0.78 | 0.07 | 98 (93%) |
> | < 0.85 | 24 | 0.71 | 0.16 | 88 (84%) |
> | < 0.90 | 59 | 0.66 | 0.37 | 66 (63%) |
>
> - **Precision is decent (~0.7–0.8):** when a line IS flagged, it's usually a
>   real error — so the flag is trustworthy as a *positive* signal.
> - **Recall is very low:** at a usable threshold the flag catches <16% of
>   errors. **The model is often confidently wrong** — ~84–93% of errors are
>   "confident misreads" that carry no low-confidence flag.
> - **Design consequence (this is the important part):** confidence coloring is
>   a HIGH-precision, LOW-recall *hint* ("look here first"), NOT an error
>   detector. So the shipped feature does NOT rely on it — the real coverage
>   comes from (a) deterministic structural checks (brace/paren/bracket balance
>   → catches missing content regardless of confidence), (b) the backend's
>   dictionary-based misspelling suggestions (`sizcof`→`sizeof` → catches
>   confident misreads the color misses), and (c) a standing "verify the whole
>   page" reminder. Thresholds set to 0.70 (red) / 0.85 (amber) — the best
>   precision/recall trade on this data.
> - **Defense answer** to "does your confidence flag catch errors?": *"We
>   measured it — precision ~0.75, recall ~0.16. Confidence is a weak error
>   detector because the model is often confidently wrong, so we don't rely on
>   it: the structural and misspelling checks (which don't use confidence) and a
>   verify-everything reminder carry the load; the colors are a high-precision
>   hint on top."* Full study: `evaluators` scratch / this banner.

> ## ✅ Detection threshold lowered to recover braces — 2026-09-04 (SHIPPED change)
>
> **Change:** `core/ocr_pipeline.py` now passes `text_det_box_thresh=0.30`
> (PaddleOCR default is 0.60). This is a real pipeline change, decided by
> measurement.
>
> **Why:** debug-artifact analysis showed the fine-tuned recognizer reads braces
> *well* (0.9–1.0 confidence; the old "~0% brace recall" was the STOCK model and
> is now stale — see LIMITATIONS.md). The residual brace losses were
> **detection-stage**: standalone braces (and some faint whole code lines) had
> box scores below the 0.60 cutoff, so the recognizer never saw them. `dropped_
> low_confidence` was empty — the confidence floor was *not* the cause.
>
> **Re-measured 2026-09-22** (fine-tuned model, 20-image held-out set,
> count-based proxy): aggregate brace recall ≈96% (open 86/90, close 87/89),
> confirming braces are largely recovered. But per-page **exact** brace counts
> matched on only 8/20 pages (~40%), and net brace-balance matched on 11/20
> (~55%) — small per-page discrepancies (±1–2 braces, occasional stray or
> missed) persist. This is the residual that limits brace-dependent reading-order
> reassembly even on clean-gutter pages. Count-based; positional recall would be
> slightly lower. Consistent with the "~1 brace/page residual" finding above.
>
> **A/B (20-image gate set, sweeping box_thresh):**
>
> | box_thresh | overall CER | `}` recovered |
> |---|---|---|
> | 0.60 (old default) | 0.126 | 82/89 |
> | 0.40 | 0.126 | 86/89 |
> | **0.30 (shipped)** | **0.126** | **87/89** |
>
> - **Overall CER unchanged (0.126) at every value** — no phantom-detection
>   regression. Brace recovery rises to 87/89.
> - **Sharper 0.40-vs-0.30 diff:** every extra detection at 0.30 was REAL content
>   (1 brace + 4 whole code lines that had been missing entirely — `scanf(...)`,
>   a `for` loop, two `printf`s), **zero junk**. So 0.30 recovers strictly more
>   real content than 0.40 with no phantom text.
> - **Why CER stays flat despite recovering 4 lines:** the recovered lines carry
>   their own recognition errors, so a missing line (deletion) becomes a
>   present-but-imperfect line (substitutions) — ~net-neutral on CER. But for a
>   grading app this is a real win by "misread beats missing": a recovered line
>   is visible and teacher-fixable in the widget; a dropped line may never be
>   noticed. `REC_SCORE_FLOOR=0.3` still guards recognition against genuine junk.
> - **Honest caveat:** a 20-image set can't fully rule out phantoms on *unseen*
>   images; the mitigation is that every marginal detection here was coherent
>   code, not noise — strong evidence 0.30 operates on real faint content.
> - **Detector fine-tuning** was considered and is NOT done: it needs bounding-
>   box annotations (a different, heavier label format than the recognition line-
>   crops), and detection was previously found "not the bottleneck." The
>   threshold change captures the brace-recovery win at near-zero cost; detector
>   fine-tuning stays future work.

> ## ✅ Binarization re-measured on the FINE-TUNED model — 2026-09-04 (stronger no-go)
>
> The "binarization is worse" evidence was previously only the **stock** model
> (grayscale 0.149 vs binarized 0.201, +0.052). Re-ran it on the **shipped
> fine-tuned recognizer** + current 20-image test set (`threshold=False` shipped
> vs `threshold=True`, via `dataclasses.replace`). `clean_ws` CER:
>
> | group | grayscale (shipped) | binarized | Δ |
> |---|---|---|---|
> | **overall** | **0.126** | **0.218** | **+0.092 worse** |
> | bond | 0.005 | 0.028 | +0.023 |
> | yellow_pad | 0.071 | 0.085 | +0.014 |
> | greenbook | 0.159 | 0.283 | +0.124 |
>
> - **Binarization hurts 19 of 20 files** (only one yellow page improved, by
>   0.009). Greenbook is worst-hit — individual files jump +0.20 to +0.41.
> - **The penalty is LARGER on the fine-tuned model than the stock one** (+0.092
>   vs the old +0.052, ~1.75×). Mechanism: the fine-tuned recognizer was **trained
>   on grayscale crops** (dataset built with `threshold=False`), so binarized
>   input is now out-of-distribution *on top of* the original edge-hardening /
>   ruled-line-solidifying problem. Binarization is a stronger no-go than ever.
> - **Defense answer** to "why not binarize / scan-to-black-and-white?": *"We
>   measured it on the deployed model — binarization raises CER from 0.126 to
>   0.218 (+73% relative), hurting every paper type, worst on greenbook. It
>   hardens anti-aliased pen strokes and solidifies printed ruled lines the
>   detector then skips, and our model was trained on grayscale so binary input
>   is out-of-distribution. Grayscale + adaptive denoise is the measured winner."*

> ## ✅ adaptive_denoise ON-vs-OFF re-measured — 2026-09-04 (fine-tuned model)
>
> The previous "byte-identical, 0.149 either way" A/B for `adaptive_denoise`
> was the **stock** model on an older, smoother cohort. Re-ran it on the
> **shipped fine-tuned recognizer** + the current 20-image gate test set
> (each sample through `extract_text_from_image` twice, configs differing only
> in `adaptive_denoise` via `dataclasses.replace`). Result (`clean_ws` CER):
>
> | group | ON (shipped) | OFF | Δ (ON−OFF) |
> |---|---|---|---|
> | **overall** | **0.126** | 0.123 | +0.003 |
> | bond | 0.005 | 0.005 | +0.000 (branch never fires, noise ~0.46) |
> | yellow_pad | 0.071 | 0.077 | **−0.006 (ON helps)** |
> | greenbook | 0.159 | 0.153 | +0.006 (ON slightly worse) |
>
> - **The ON column = 0.126 exactly**, reproducing the released headline number
>   — confirms nothing in the pipeline drifted, and that 0.126 was always
>   measured *with* adaptive_denoise on (it's the shipped default; "turning it
>   on" is not a change).
> - **Branch fires on 15/20 samples** (background noise ≥ 2.2) — confirms it's
>   genuinely active on gate-framed input, not inert. The gate crops/de-warps
>   geometry but does NOT smooth paper texture, so greenbook speckle and
>   yellow-pad grain survive and trigger the stronger denoise.
> - **Net effect is ~neutral (+0.003 = within noise at n=20).** It is NOT
>   degrading accuracy: helps yellow pad, no effect on bond, marginally hurts
>   greenbook (driven mostly by a single file swinging). Kept ON — it's
>   neutral-to-helpful, 0.126 is the validated/released number, and the
>   fine-tuned model was trained through this same config.
> - **Defense-ready answer** to "did you verify this preprocessing step helps?":
>   *"We A/B'd it on the deployed model + current test set — neutral on gate
>   input (0.126 vs 0.123, within noise), helps yellow pad, kept on because it
>   doesn't hurt and it's the configuration that produced our released result."*
> - Note on input paths: the mobile app is camera→gate only (no gallery upload
>   in the current UI); the backend `extract-upload` endpoint accepts raw files
>   directly but isn't wired to a production UI. So in practice today everything
>   is gate-processed — the "calibrated for raw uploads" rationale is real
>   (the endpoint exists) but mostly latent; the honest primary justification is
>   "measured neutral, not harmful."

> ## ✅ First real fine-tune measured — 2026-08-30 (the payoff)
>
> Fine-tuned `PP-OCRv6_medium_rec` on **2,491 train / 278 val** handwritten
> line crops (`datasets/recognition/`), 40 epochs, best checkpoint at epoch 39.
> This training data comes from the physically-verified writer-pseudonym batch
> — source folder `~/Downloads/image_to_transcribe_verified/`
> (`bond_writer1_2`, `green_writer10_B2_1`, etc. — see `NEXT_STEPS.md`'s
> "dataset batches" bullet, which also documents a same-day correction: a
> `submission_*`-named folder was briefly and incorrectly assumed to be a
> separate unverified batch, until md5 comparison proved it was the same
> verified content under its pre-rename name; it's since been deleted).
> Colab val metrics at best: exact-line acc **0.543**, norm_edit_dis **0.888**
> — but that is the *validation* split, not a held-out test, so it is **not**
> the headline number. Reproduce the training via
> `docs/ocr/COLAB_SETUP_WORKING.md`.
>
> **Held-out test result — same 20 images, stock vs fine-tuned, same pipeline.**
> The test set is the current `samples/` (the 20 pages `select_holdout.py`
> moved out of training this session; never seen in training). Both models run
> through the identical `ocr_pipeline.py` + `evaluate_cer`. Recognition-error
> CER (`clean_ws`, lower better):
>
> | group | stock PP-OCRv6 | fine-tuned | change |
> |---|---|---|---|
> | **overall** | **0.274** | **0.126** | **−54%** |
> | bond | 0.089 | 0.005 | −94% |
> | yellow_pad | 0.175 | 0.071 | −59% |
> | greenbook | 0.328 | 0.159 | −52% |
>
> (Overall across all four CER columns — stock raw/clean/raw_ws/clean_ws
> `0.399/0.398/0.276/0.274`; fine-tuned `0.274/0.273/0.127/0.126`.)
> **Every one of the 20 files improved; zero regressions.** A 54% reduction
> consistent across all paper types (bond, yellow_pad, greenbook) and across
> the 15 test writers is a robust effect, not small-sample noise.
>
> **Writer-disjointness — greenbook IS writer-disjoint; bond/yellow are not.**
> (Corrected 2026-09-01 after an earlier miscount that ignored the batch in
> the filename.) Writer identity = paper type + writer number + **batch**:
> numbering resets per batch, so `green_writer19_B1` and `green_writer19_B2`
> are *different* students; no-batch files (the first dataset) are identified
> by number within their paper type. Under this correct identity:
>
> | paper type | writer-disjoint test writers | note |
> |---|---|---|
> | **greenbook** | **8 of 9** (13 of 14 test images) | only `green_writer1` (no-batch, first dataset) also appears in training |
> | bond | 0 of 2 | no batch, only ~4 writers — holding one out is too costly |
> | yellow_pad | 0 of 4 | same as bond |
>
> So **13 of the 20 test images are from writers never seen in training** —
> the greenbook result (**CER 0.159**, the bulk of the test set) is
> effectively a **new-writer** number already, not same-writer. Only the 6
> bond/yellow images plus the one legacy `green_writer1` page are same-writer.
> A defensible framing: *"greenbook — our largest and hardest paper type — is
> writer-disjoint, so 0.126 is largely a genuine unseen-writer result; bond
> and yellow remain same-writer only because those types have too few writers
> to hold one out without gutting training, and more writers there is planned."*
>
> **Cross-writer experiment (2026-09-01) — independent new-writer confirmation.**
> Separate MEASUREMENT model (not the shipped one): 4 greenbook writers
> (7/8/20/27) were excluded *entirely* from training, the model retrained on
> the rest (2292/231 crops vs the full 2491/278), then evaluated on those 4
> writers' 15 pages — handwriting never seen in any form. Reproducible via
> `evaluators/build_crosswriter_dataset.py` + `evaluators/crosswriter_eval.py`
> (model selected by the `MAISTRA_REC_MODEL_DIR` env var; the 76MB measurement
> model lives in `models/fine_tuned_rec_crosswriter/`, gitignored).
>
> | on the 15 never-seen-writer pages | stock | cross-writer fine-tuned | change |
> |---|---|---|---|
> | **CER (clean_ws)** | 0.296 | **0.123** | **−58%** |
> | **WER (clean)** | 0.792 | **0.397** | **−50%** |
> | token accuracy | 0.394 | 0.657 | +26.3 pts |
>
> Two things this proves: (1) the fine-tuned model **generalizes** — 0.123 on
> never-seen writers ≈ the 0.126 headline, no degradation; (2) the improvement
> **is not memorization of known writers** — fine-tuning cut CER 58% on writers
> it had zero exposure to. Per-writer CER 0.073–0.158 (consistent, no
> catastrophic failure). Caveats: small (15 pages / 4 writers), greenbook-only,
> and the measurement model trained on *less* data than the shipped one — so
> 0.123 is if anything a **conservative** estimate of the shipped model's
> new-writer performance. **This is a measurement experiment; the shipped model
> (`models/fine_tuned_rec/`) trains on ALL writers.**
>
> **WER + token-accuracy on THIS 20-image set (measured 2026-09-01, objective 7).**
> Same stock-vs-fine-tuned comparison, same test set, via `evaluate_cer`
> (stock run used a temporary recognizer swap in `ocr_pipeline.py`, reverted
> after):
>
> | metric (clean) | stock | fine-tuned | change |
> |---|---|---|---|
> | **CER** (lower better) | 0.274 | 0.126 | −54% |
> | **WER** (lower better) | 0.726 | 0.359 | −51% |
> | **C-token accuracy** (higher better) | 0.487 | 0.701 | +21.4 pts |
>
> By-type clean WER: bond `0.547 → 0.050`, yellow_pad `0.641 → 0.215`,
> greenbook `0.776 → 0.444` — improved on every paper type. WER reads higher
> than CER by design (one wrong char fails the whole word); the point is the
> *relative* drop, which tracks CER. (Raw variants: WER `0.743 → 0.363`,
> token-acc `0.483 → 0.699`.) These supersede the earlier 14-sample WER
> (`raw 0.699 / clean 0.656`) quoted later in this doc, which was a different,
> easier set.
>
> **CRITICAL methodology note — do not reuse the old `0.149` baseline.** The
> `clean_ws 0.149` figure throughout the rest of this doc was measured on a
> *different, easier* 14-sample set that predates this session. This session's
> held-out set is harder (heavy greenbook, messier writers), so the **stock
> model scores 0.274 on it**. The only valid comparison is stock-vs-fine-tuned
> on the *same* set: **0.274 → 0.126**. Never write "0.149 → 0.126" — that
> mixes two different test sets and is not defensible.
>
> **Defensible thesis sentence:** *"On a 20-image held-out test set, fine-tuning
> PP-OCRv6 on 2,491 handwritten C-code line crops reduced recognition CER from
> 0.274 to 0.126 (−54%), improving every sample with no regressions."*
>
> **Still improving at epoch 39** (val acc 0.51→0.54 over the last epochs, no
> overfitting seen) → a longer run (60–80 epochs) is a natural future-work
> lever. The swap-in lives in `core/ocr_pipeline.py` as
> `text_recognition_model_dir="models/fine_tuned_rec/inference"` (local
> experiment; the 76 MB model file's versioning is still undecided — not
> committed as the default yet).

> ## ✅ WER + token-level accuracy added — 2026-08-10 (thesis objective 7)
>
> `evaluate_cer.py` now reports three metric families, matching the paper's
> objective 7 ("Character Error Rate (CER), Word Error Rate (WER), and
> token-level recognition accuracy"):
>
> - **CER** — unchanged; character edit distance / reference length. Lower
>   better. The `clean_ws 0.149` baseline is unaffected (verified: the CER
>   table prints identical numbers after this change — the additions are
>   purely additive).
> - **WER** — word error rate over `str.split()` tokens (edit distance /
>   reference word count). Lower better. No `_ws` variant: `split()` already
>   collapses whitespace runs, so a raw and normalized split give identical
>   tokens. First measured values (14 samples): overall **raw 0.699 / clean
>   0.656**.
> - **Token-level recognition accuracy** — `1 - (edit distance over C-lexical
>   tokens / reference token count)`, floored at 0. HIGHER better. Tokens come
>   from a lightweight C lexer (`tokenize_c` in `evaluation.py`), so operator
>   spacing (`x=5` vs `x = 5`) never counts as an error, and string/char
>   literals stay atomic (reuses the `C_LITERAL` pattern). First measured
>   values: overall **raw 0.715 / clean 0.729**.
>
> **Why WER reads much higher than CER (expected, worth stating at defense):**
> WER is whole-word — a single misread character makes the entire word wrong
> (`factonial` vs `factorial` = one full WER error but ~1/9 CER). So WER
> inflating relative to CER on handwriting is normal, not a regression; the
> three metrics measure different granularities on purpose. Cleaned beats raw
> on all three, a good consistency signal. Implementation: `evaluation.py`
> (`wer`, `tokenize_c`, `token_accuracy`, `evaluate_word_token_pair`), printed
> as a second table in `evaluate_cer.py` (kept separate from CER because their
> good-direction differs). 10 unit tests in `tests/test_evaluation.py`; suite
> now 78/78.
>
> ## ✅ Line grouping overlap guard — completed 2026-08-08
>
> `_group_detection_records` now keeps the existing vertical/trend tolerance as
> its first gate, then vetoes a merge when the candidate overlaps any actual
> current-line member by more than 30% of the narrower width. Member intervals
> are checked individually so an empty gap inside a multi-fragment line's
> bounding span cannot cause an order-dependent false split.
>
> The originally proposed ~50% cutoff failed the full case set: one confirmed
> `writer1_menu_dowhile_bond` merge overlaps by only 37.3%. Across the available
> cohort debug artifacts, retained same-row fragments reached at most 7.9%
> overlap while confirmed stacked rows started at 37.3%, so 30% preserves the
> measured gap. The final live 21-page builder run covered the remaining source
> with no stored artifact.
>
> **Structural A/B:** `build_recognition_dataset.py` skips **8/21 → 7/21**;
> within the 14-sample test cohort, **5/14 → 4/14**. Train/val crops rose from
> **113/13 (126 total) → 126/14 (140 total)**. Recovered pages:
> `nombrado_s01_total_loop_gate` and `writer1_menu_dowhile_bond`.
>
> `submission_1785907170842` is newly skipped at 10 OCR vs 9 ground-truth
> lines, but not because of an over-split: the guard corrects its documented
> 69% row merge and exposes a pre-existing spurious bottom-page `0` detection
> that had previously canceled the count error. This demonstrates why the full
> skip-list diff and debug geometry matter in addition to the aggregate rate.
>
> **CER is not the acceptance signal for this change.** `normalize_ws`
> collapses newlines, so `clean_ws` is structurally blind to line merges. No
> CER rerun was used to justify the guard; the current official baseline remains
> the 14-sample `clean_ws 0.149` documented below.

> ## ✅ Preprocessing settled — updated 2026-08-07: same-cohort A/B on the current 14 samples
>
> Re-ran the grayscale-vs-binarization and color-vs-grayscale questions on the
> **current 14-sample cohort** (all gate-framed, black ballpoint pen only), so
> the numbers are same-cohort and directly comparable — not the earlier
> cross-cohort `0.166` figure. Both settle the same way:
>
> **Grayscale vs binarization (denoise on, current default vs `threshold=True`):**
> overall grayscale `0.149` vs binarized `0.201` (**+0.052 worse**). Per-subgroup
> delta (binarized − grayscale): bond **+0.026**, greenbook **+0.098**,
> yellow_pad **−0.010** (n=2). Binarization is decisively worse for black pen;
> grayscale wins on bond and greenbook, and yellow_pad is noise-level at n=2.
>
> **4-way, color/grayscale × denoise on/off (clean isolation):**
>
> | variant | clean_ws |
> |---|---|
> | grayscale + denoise (current default) | **0.149** |
> | color, no denoise | 0.153 |
> | grayscale, no denoise | 0.169 |
> | color + colored-denoise | 0.194 |
>
> **Measured mechanism (replaces the earlier "trained on grayscale" claim).**
> The old rationale — "PaddleOCR is trained on natural grayscale, binarization
> destroys anti-aliased stroke gradients" — was **not verifiable** against
> primary sources: the PP-OCRv6 arXiv paper only documents a 3-channel
> `3×48×W` recognition input, and a PaddleOCR maintainer states RGB is
> *preferred* over grayscale. So we don't claim the model prefers grayscale.
> What the numbers actually show: grayscale's edge comes from **unlocking an
> effective single-channel denoiser** (`cv2.fastNlMeansDenoising`). Compare
> like-for-like: with denoise off, color (0.153) slightly beats grayscale
> (0.169); grayscale only pulls ahead once denoising is applied (0.169 → 0.149),
> and the colored denoiser on the color path is weaker (color 0.153 → 0.194).
> Binarization is worse for a separate reason — it hardens anti-aliased stroke
> edges and turns greenbook ruled lines into solid black runs (see the dropped
> `printf` recovery below). Bottom line: **grayscale + denoise, binarization
> off** is the measured best config for our black-pen data, and the honest
> defense line is "we measured it," not "the model was trained that way."
>
> **RETRACTION WITHDRAWN (2026-08-03):** The 2026-08-02 retraction below is
> withdrawn. It asserted that direct paper inspection had found non-literal
> labels for at least s04–s07. On 2026-08-03 all 13 source pages were inspected
> physically by John Cale Nombrado; **every label was literal as written and no
> row required correction.** The suspected discrepancies (`70` vs `10` on
> s04/s06/s07, `Int`/`Sum` capitalization on nikko_001/nikko_003, loop bounds on
> s08) did not exist on the pages.
>
> Root cause: the flagged discrepancies originated from an **AI reading the
> sample photographs**, not from a physical page check. That method fails through
> the same glyph confusions as the OCR under test (`1`/`7`, ambiguous capitals),
> so it produced errors correlated with the pipeline's own. A later AI pass
> reproduced the identical misreads and this was mistaken for corroboration.
>
> The v5 `.181 clean_ws` was re-derived against the then-verified labels
> (2026-08-03), and the models were then swapped to **`PP-OCRv6_medium`**, scoring
> **`clean_ws 0.148`** on that 13-page cohort — v6 clearly beat v5. The separate
> Supabase `0.153` retraction is unaffected and remains in force.
>
> ## ⚠️ Baseline status — updated 2026-08-04
>
> The 5 `nikko` close-up images were **deleted 2026-08-04** (they were tight crops
> that don't match the quality-gated capture flow — non-representative of real
> production captures). Their `labels.csv` rows remain as text records but are
> now dead pointers, skipped at run time. Consequences:
>
> - **The `0.148` figure is no longer reproducible** — it was averaged over a
>   13-page cohort that no longer exists on disk. It stays valid as a *historical*
>   v6-vs-v5 result, but it can't be re-run.
> - **Baseline as of 2026-08-04 (superseded 2026-08-06 → `0.149`, grayscale default — see banner above): `clean_ws 0.190`** over the 8 remaining
>   full-page `nombrado` captures — **bond `0.165`, greenbook `0.231`**.
> - **This is NOT a regression.** Every page's CER is unchanged; the average rose
>   only because the easy close-ups (which scored ~0.095 and were unrepresentative)
>   left the set. `0.148 → 0.190` is a cohort-composition change, not a quality
>   change — never cite it as "the OCR got worse."
> - **The stable, citable metric is per-paper-type** (`bond 0.165` / `greenbook
>   0.231`), which doesn't move when pages are added or removed. Prefer these over
>   any single aggregate.
> - The single-writer caveat still applies: this is `nombrado` only until the
>   multi-writer collection lands.
>
> The historical tables below that show `0.148` describe the original 13-page
> cohort as measured at the time; read them as history, not current reproducible
> state.
>
> **Rule, now binding:** an AI reading of a sample image may not establish,
> refute, or retract a label. Label-validity claims require a named human and the
> physical page. Never silently edit labels by AI or tune to a viewed set.
>
> ## 🎯 THE DECIDING EXPERIMENT (2026-08-06) — does Nikko's gate help or hurt, deconfounded
>
> **This is the measurement the project has been trying to get since the first
> branch review.** Same physical pages (`nombrado_s01/s02b/s04/s05/s06/s07/s08`),
> same writer, same handwriting — retaken through Nikko's actual quality gate
> (camera-scan, `SCANNER_MODE_BASE`: edge-detect + perspective de-warp + JPEG,
> confirmed live per his answers below). Only the scanner's crop/de-warp+JPEG
> differs. Both sides measured under the current grayscale default.
>
> | pair | paper | raw | gate | delta |
> |---|---|---:|---:|---:|
> | s01_total_loop | bond | 0.157 | 0.170 | +0.013 worse |
> | s02b_two_numbers | bond | 0.145 | 0.151 | +0.005 worse |
> | s04_sumarray | bond | 0.116 | 0.134 | +0.017 worse |
> | s05_factorial | bond | 0.128 | 0.151 | +0.023 worse |
> | s06_struct_green | greenbook | 0.229 | 0.209 | **−0.020 better** |
> | s07_swap_green | greenbook | 0.234 | 0.211 | **−0.023 better** |
> | s08_nested_green | greenbook | 0.166 | 0.172 | +0.007 worse |
> | **overall (7)** | | **0.168** | **0.171** | **+0.003 (~noise)** |
>
> **By paper type — a real, paper-type-dependent split, not a wash:**
> **bond: gate is worse on every page** (delta +0.015 avg) — the scanner's
> crop/de-warp measurably degrades already-clean bond captures. **greenbook:
> gate is better on 2 of 3** (delta −0.012 avg) — plausible the de-warp/
> straightening genuinely helps a harder capture surface. Small n (4 bond, 3
> greenbook) — real signal, not a universal law, but this is the first
> genuinely deconfounded measurement of the gate's effect the project has had.
> No further "is it the gate or the paper" ambiguity for these 7 pages — the
> writer, paper, and content are held constant; only the gate differs.
>
> **Resolution:** raw versions of these 7 pages were replaced with the
> gate-framed versions in `samples/labels.csv` (ground truth unchanged, same
> physical pages; `capture_condition` updated to `gate_raw`; old raw files
> deleted). New official baseline below.
>
> ## ✅ Baseline status — updated 2026-08-06: binarization off by default, new baseline `0.149`
>
> **Default change (2026-08-06): `PreprocessConfig.threshold` flipped `True → False`**
> — the pipeline now feeds PaddleOCR the denoised **grayscale** image instead of a
> hard-binarized one. Rationale (see the 2026-08-07 same-cohort banner at the very
> top for the corrected mechanism — grayscale + denoise beats binarization by
> measurement, not because the model was "trained on grayscale"). Measured on
> the full 13-sample cohort (bond + greenbook + yellow_pad, raw + gate-framed,
> 3 writers): overall clean_ws `0.166 → 0.149`; bond `0.142 → 0.125`; greenbook
> `0.196 → 0.168`; yellow_pad `0.161 → 0.171` (+0.010, n=2 — noise-level, revisit
> as pad coverage grows). 9 of 13 pages improved. This is NOT a rerun of the
> misleading 2026-07-30 "grayscale-only" result (5 clean bond pages, which
> inverted when greenbook arrived) — this cohort spans every paper type and both
> capture paths, and the win holds on 2 of 3 subgroups. `REC_SCORE_FLOOR` (0.3)
> was re-verified under grayscale input the same day: clean gap (dropped junk
> ≤0.25 — mostly empty detections on pad ruling remnants — real text ≥0.36, p5
> 0.82); floor behavior unchanged. The threshold code remains fully functional
> behind `threshold=True` for evaluators and any future conditional use.
>
> **Bonus: grayscale recovers the dropped `printf` line** (page `826cc0e5`, the
> gate-framed greenbook detection miss that drove the entire line-removal
> investigation). Verified directly 2026-08-06: under binary the ruling line
> hardened into a solid black run, crowded the row, and the detector skipped the
> whole line; under grayscale the ruling stays faint gray and the detector boxes
> the row normally. **The detection miss was largely a binarization artifact** —
> no line-removal surgery needed. The recovered line still carries recognition
> errors (`%d>n`, `return o`) — fine-tuning targets — but a misread line the
> teacher can fix beats a missing line in a grading app. This also explains why
> greenbook was the largest subgroup winner in the A/B above.
>
> **Superseded again — see the deciding-experiment banner above.**
> The `0.149`/13-sample figures below were measured before the raw-vs-gate
> swap. **Current baseline (official `evaluate_cer` re-run, 14 samples, ALL
> gate-framed): `clean_ws 0.149`** — bond `0.133` · greenbook `0.159` ·
> yellow_pad `0.171`. (The interim `0.151`/12-sample figure was measured after
> the raw-vs-gate swap but before the two `writer1` pages were added; adding
> them grew the set to 14 and settled the average at `0.149`.) The `nombrado_*`
> raw pages no longer exist in `samples/`; every sample is now gate-framed,
> closing the raw/gate inconsistency that made earlier baselines
> non-representative of production.
>
> ## ⚠️ Baseline status — updated 2026-08-05: first gate-processed + first pad numbers
>
> 5 new samples added to `samples/labels.csv`, sourced from real DB submissions
> confirmed to have gone through Nikko's actual quality gate (`capture_condition
> =gate_raw` — geometric de-warp + illumination normalization applied, not raw
> camera output). This is the **first-ever measurement on gate-processed images
> and the first-ever pad coverage** in this project.
>
> | sample | program | paper | writer | clean_ws |
> |---|---|---|---|---:|
> | `submission_1785902823075.jpg` | pointer | bond | writer1 | 0.029 |
> | `submission_1785907663332.jpg` | sum | greenbook | nikko | 0.123 |
> | `submission_1785907170842.jpg` | add-function | greenbook | nikko | 0.167 |
> | `submission_1785907816105.jpg` | pointer | yellow_pad | writer1 | 0.107 |
> | `submission_1785907946017.jpg` | array | yellow_pad | writer1 | 0.216 |
>
> Average of these 5: **`clean_ws 0.128`** — better than the `0.190` nombrado-only
> baseline, though not directly comparable (different writers/content/paper mix).
> By paper type across the full 18-row cohort (dead `nikko_*` pointers skipped):
> bond `0.181`, greenbook `0.240`, yellow_pad `0.203`.
>
> **What this measures, and what it doesn't yet:** these numbers show
> gate-processed greenbook/pad performing in a reasonable range, not obviously
> worse than untouched raw bond/greenbook. But it is **confounded** — different
> writer, different (shorter) code than the nombrado baseline — so it is evidence
> the gate isn't degrading things, not proof it helps. The clean, deconfounded
> comparison (same physical page, same writer, raw vs. gate) is in progress: the
> existing `nombrado_*` raw pages (s01–s08) are being retaken through Nikko's
> gate for exactly this pairing — see `QUALITY_GATE_REVIEW.md` §7. Do not delete
> the current raw `nombrado_*` files until that paired measurement runs.
>
> **Line-detection finding (2026-08-05):** diagnosed a dropped line on a
> gate-processed greenbook page (`printf(...)` never appeared in output). Root
> cause was NOT the confidence filter (`dropped_low_confidence` was empty on both
> test images) — it was a detection-stage miss. The greenbook's ruling lines
> *survived* Nikko's gate + our denoise (unlike untouched raw greenbook, where
> they get smeared away — see `quality-gate-should-not-binarize` memory) and
> crowded out that row. A/B with a horizontal-line remover recovered the
> missing line (mechanism validated) but regressed average clean_ws across the 5
> new samples `0.128 → 0.144` (clips glyphs on pages that didn't need it).
>
> **Resolution (2026-08-06) — line-removal removed from the pipeline entirely.**
> Two removers were built and measured: a blunt "erase any long horizontal run"
> (`0.128 → 0.144`) and a sharper "near-full-width runs only" (`0.128 → 0.135`,
> and it stopped damaging the pad pages). A width-fraction sweep
> (0.5/0.65/0.8/0.9) then found **no value that is a clean win**: 0.5 recovers a
> dropped line but costs +0.007; 0.65–0.9 cost less (+0.003) but stop recovering
> it (a crowded row's rule is only ~50–65% visible width — the writing occludes
> its middle — so the pages that most need removal are where the width test is
> weakest), and one greenbook page regresses at *every* fraction including 0.9
> (it has a genuinely full-width handwriting element width-filtering can't
> protect). Conclusion: **width alone cannot separate printed rules from
> handwriting, and preprocessing line-removal is the wrong tool.** The code
> (`remove_horizontal_lines` flag, `_remove_horizontal_lines` function, config
> fields) was removed 2026-08-06 rather than kept as dead, off-by-default code —
> the finding is preserved here and in git history. The robust fix for lined
> paper is **fine-tuning on real ruled-paper samples**, not editing pixels
> before OCR. If ever revisited, a straightness/periodic-spacing detector
> (Hough-based), not morphological width, is the direction.
>
> **Follow-up (2026-08-06) — the texture-based paper-type proxy itself is
> broken under gate processing, and a second candidate fix also failed.**
> Measured `_background_noise` texture scores across the current cohort:
> raw bond 0.49–0.94, gate bond 1.50, **gate greenbook 1.75–2.00**, gate
> yellow_pad 1.94–1.97, raw greenbook 2.53–2.62. The `textured_paper_threshold
> =2.2` split (calibrated only on raw captures) puts gate-framed greenbook
> on the *wrong side* — it reads as smooth paper and gets weak denoise, letting
> its ruling lines survive.
>
> **Correction on mechanism (2026-08-06, verified against branch tip `d57a1bc`):**
> earlier notes attributed the lowered gate-greenbook texture score to Nikko's
> "illumination normalization." **That code no longer exists** — Nikko shipped
> raw-only upload (`processDocument` removed) and removed the Enhance filter
> (scanner forked to `SCANNER_MODE_BASE`). The gate is now read-only measurement;
> the ONLY pixel operations applied to a DB image are the scanner's edge-detect +
> **perspective de-warp** and JPEG encode. So if the gate is responsible for the
> lower texture score at all, the only possible mechanism left is the **de-warp
> resampling smoothing the paper speckle** that `_background_noise` keys on — not
> any photometric processing. This remains one candidate among several (his
> paper/pen/lighting simply differing from the raw cohort's is equally live); the
> same-page s06/s07/s08 retake isolates de-warp+JPEG as the single variable. Lowering the threshold to 1.7 to fix this was
> tested and **also failed**: it recovered the dropped line on 1 of 2
> gate-greenbook samples (`0.167→0.145`) but regressed the other
> (`0.123→0.172`) and badly regressed both yellow_pad samples
> (`0.107→0.165`, `0.216→0.320`), since gate-greenbook and yellow_pad now
> occupy the same texture band — no single threshold can move one without
> sweeping in the other.
>
> **Important — do not cite "the gate causes this" as established.** Every
> comparison available conflates gate-vs-raw with writer, physical paper, and
> capture conditions all at once (raw greenbook = nombrado's paper/writing/
> lighting; gate greenbook = Nikko's). One gate-greenbook page scored well
> (0.123) at the *default* threshold while the other did not (0.167) — a
> difference *within* the same gate + same paper type + same writer, which
> argues for **per-page capture condition** (line darkness, row spacing,
> shadow) as the operative variable at least as much as gate-vs-raw. The only
> experiment that can actually isolate the gate's effect is a same-physical-
> page raw-vs-gate pair — planned via retaking `nombrado_s06/s07/s08` through
> the gate (see `QUALITY_GATE_REVIEW.md` §7). Until that runs, treat the
> gate-causation story as a hypothesis under test, not a finding.

> **CAPTURE-MODE DEFECT (2026-08-03):** Separately from label literalness, all 5
> `nikko_*` samples are disqualified as evaluation data. They are labeled
> correctly but were captured as tight close-up crops of the answer, before the
> mobile capture quality gate existed — not full-page-framed like nombrado's
> samples. Once the quality gate ships it will only permit full-frame captures,
> so these 5 images test a capture mode production will never produce.
> **Verdict: recapture, not relabel.** Until nikko has replacement samples
> captured under the gated framing protocol, do not cite any writer-subgroup
> comparison from this cohort as representative — the nikko/nombrado gap
> reflects capture mode as well as handwriting and paper type.
> `evaluate_cer.py` fails closed on any row lacking literal provenance before it
> loads the OCR model. (Historical note: the `nikko_*` sample images were later
> deleted — see the `nikko-samples-need-recapture` project memory — so those
> `labels.csv` rows are now dead pointers skipped at run time.)

## What CER is

Character Error Rate: the standard OCR accuracy metric. Levenshtein edit
distance between OCR output and the correct (ground truth) text, divided by
the length of the ground truth. Lower is better — 0.0 = perfect, 1.0 = as
many errors as characters.

## The tool

`ocr_feature/evaluators/evaluate_cer.py` — a standalone dev/research script,
not part of the live backend. It refuses to score any cohort whose rows lack
literal human provenance (`literal_verified`, `literal_verified_by`,
`literal_verified_at`); see `literal_provenance_issues()` in `evaluation.py`
(the shared metrics library, at the package root). The current 13-label cohort
passes that gate as of 2026-08-03. Run it as a module from `ocr_feature/`
(running by file path breaks its imports):

```bash
.venv/bin/python -m evaluators.evaluate_cer
```

It reads every `(filename, ground_truth_text)` pair from
`samples/labels.csv`, runs each image through the real pipeline, and reports
per-image and average CER across four variants:
- `raw` — raw OCR output vs ground truth (strict)
- `clean` — after the keyword cleanup layer (strict)
- `raw_ws` / `clean_ws` — same, but whitespace-normalized (measures
  recognition accuracy only, since layout/formatting differences aren't
  character-recognition errors and the teacher reformats anyway)

## Verified 13-label baseline (2026-08-03)

Measured on all 13 physically verified labels. 2 writers, bond + greenbook, 13
pages. **Current models: `PP-OCRv6_medium_det` + `PP-OCRv6_medium_rec`** (see
`PIPELINE.md` for the selection sweep). This is the current citable baseline.

| Metric | v6 (current) | v5 mobile (previous) |
|---|---|---|
| raw (strict) | 0.194 | 0.227 |
| clean (strict) | 0.190 | 0.223 |
| raw_ws | 0.153 | 0.186 |
| **clean_ws** | **0.148** | **0.181** |

The v5 `0.181` reproduced the previously retracted figure exactly — expected,
and itself a check: the labels were confirmed rather than edited, the pipeline is
deterministic, so the arithmetic was always right; the old retraction concerned
label provenance, not computation. The v6 swap on 2026-08-03 then improved every
metric by ~0.033 (18% relative on `clean_ws`), better on 11/13 pages.

### Subgroup results, and the confound that matters

Full-cohort subgroup means, v6 (current) run:

| group | raw | clean | raw_ws | clean_ws |
|---|---|---|---|---|
| bond | 0.167 | 0.163 | 0.128 | 0.124 |
| greenbook | 0.283 | 0.279 | 0.235 | 0.231 |
| writer nikko | 0.131 | 0.123 | 0.091 | 0.082 |
| writer nombrado | 0.233 | 0.231 | 0.191 | 0.190 |

**Do not cite the bond-vs-greenbook row as the paper-type effect.** Writer and
paper type are fully confounded in this cohort: nikko wrote only bond pages, and
every greenbook page is nombrado's. The writer effect (0.082 vs 0.190, ~2.3×) is
larger than the apparent paper effect, so the headline greenbook gap is partly
just handwriting difficulty. (The nikko rows are also captured pre-quality-gate
and are flagged for recapture — see the capture-mode notice at the top; treat the
writer subgroup as doubly caveated.)

Holding writer constant, within nombrado's pages only (v6):

| nombrado pages | clean_ws |
|---|---|
| bond (s01, s02, s02b, s04, s05) | 0.165 |
| greenbook (s06, s07, s08) | 0.231 |

**+0.066 clean_ws for greenbook vs bond, writer held constant** — essentially
unchanged from v5's +0.067. This gap is real in the data but **unexplained**, and
should NOT be presented as a paper-texture / preprocessing problem. A 2026-08-03
diagnostic pass tested and refuted every mechanistic cause:

| hypothesis | test | result |
|---|---|---|
| texture leaks in as phantom ink | error-op mix | refuted — greenbook is 56% substitutions like bond, insertions not elevated |
| downscaling loses detail | `max_side` 1600→3200 | refuted — higher res neutral then catastrophic |
| small handwriting | glyph height post-denoise | refuted — greenbook 14–16px, *larger* than bond's 10px |
| wrong threshold block | fixed blocks 31/41/51 | refuted — current scaled block already near-optimal |
| symbol-heavy content | hard-symbol density vs CER | refuted — the most symbol-dense page is bond `s04`, and it has the *lowest* CER |

So the greenbook penalty is **not preprocessing-addressable** (four preprocessing
levers ruled out) and **not content** (symbol density anti-correlates). With n=3
greenbook pages from one writer, it also cannot be confirmed as a genuine *paper*
effect versus three idiosyncratically-harder pages — a +0.066 gap on 3 pages is
one or two pages from vanishing. Do not tune anything to it. Resolving it requires
more greenbook samples across multiple writers (to establish whether the effect is
real) and, for the accuracy itself, fine-tuning. Yellow pad remains unrepresented.
The pipeline itself is not implicated — glyph measurement, block sizing, and
adaptive denoise all behave correctly on greenbook.

### Symbol-level error profile — the fine-tuning target

Per-character analysis on the verified cohort (both models) shows the dominant
residual error is structural C punctuation, not letters:

| char | in truth | v5 mobile produces | v6 medium produces |
|---|---:|---:|---:|
| `}` | 31 | 2 (6%) | 0 (0%) |
| `{` | 31 | 8 (26%) | 11 (35%) |
| `;` | 78 | 46 (59%) | 55 (71%) |
| `,` | 46 | 58 (126%) | 58 (126%) |

Roughly 52 of the 148 deletions are missing braces; `}` is misread as `3`/`2`,
`;` as `,`. The regions are detected but mis-recognized, which is why a bigger
detector did not help. This is the specific, defensible fine-tuning target:
handwritten C punctuation, braces first. **Do not reconstruct braces from
indentation** — a missing brace may be the student's actual mistake, and
synthesizing it would inflate the grade (violates the closed-vocabulary rule).

### Recognition consensus — evaluated, rejected, code removed

A raw-OCR "consensus" experiment (running the recognition model over ±0.5°
rotations of the same image and voting per line) was evaluated, **rejected**, and
its code **removed 2026-08-04** — the pipeline is baseline-only. The net CER
change was noise, it cost ~165% runtime, and the per-decision audit showed it
corrupting correct C keywords. Full numbers and the structural root-cause
analysis are retained in
[`RAW_OCR_CONSENSUS_HANDOFF.md`](RAW_OCR_CONSENSUS_HANDOFF.md).

The one lesson worth keeping here: the aggregate CER alone read as harmlessly
neutral — it was the mandatory per-decision audit that exposed the keyword
corruption. When evaluating any future candidate, keep that per-decision review
step non-optional.

### How the baseline moved through this project

| stage | clean_ws CER | what changed |
|---|---|---|
| original (1 writer, clean bond samples only) | 0.095 | — |
| + 1 more writer, harder captures | 0.125 | cohort got harder |
| + greenbook paper introduced | 0.223 | cohort got harder; not a regression |
| + adaptive threshold block | 0.198 | preprocessing change |
| + adaptive denoise by paper type | 0.181 | v5 mobile models; matches 2026-08-03 verified re-run |
| + swap to v6_medium models | **0.148** | model selection on the original 13-page cohort (superseded — see baseline status at top) |
| − 5 nikko close-ups deleted (2026-08-04) | **0.190** | 8 full-page nombrado pages (bond 0.165 / greenbook 0.231) — cohort change, not a regression |
| + 5 gate-processed samples added (2026-08-05) | **0.128** (new samples only) | first gate-processed + first pad measurement; confounded by writer/content, see baseline status at top |
| + binarization off by default (2026-08-06) | **0.149** (full 13) | `threshold=False`: feed PaddleOCR denoised grayscale, not binary — improved 9/13 pages, bond and greenbook subgroups both better; see 2026-08-06 banner at top |
| + raw nombrado pages replaced with gate-framed retakes (2026-08-06) | **0.151** (12, all gate-framed) | deconfounded raw-vs-gate experiment run first (see top banner): bond worse under gate (+0.015), greenbook better (−0.012); test set now 100% gate-framed, closing the raw/production inconsistency |
| + 2 `writer1` gate pages added (2026-08-06) | **0.149** (14, all gate-framed) | test set grew to 14; **current reproducible baseline** — bond 0.133 / greenbook 0.159 / yellow_pad 0.171 |

Read this table as experiment order, not as a controlled ablation. The rises
come from adding harder pages to the cohort, not from the pipeline getting
worse. Only the final two rows have been re-derived against verified labels; the
intermediate rows have not been re-run since verification and should not be
quoted individually as validated measurements.

### Original single-writer diagnostic, for reference

5 labeled samples, one writer, clean bond paper, as of the reading-order +
line-merge + confidence-filter changes:

| Metric | Value |
|---|---|
| raw (strict) | 0.148 |
| clean (strict) | 0.137 |
| raw_ws | 0.107 |
| **clean_ws** | **0.095** |

These 5 pages belong to the now-verified cohort, so the label-provenance
objection no longer applies to them. The figures have not been re-derived since
verification, however, and a 5-page single-writer subset cannot serve as a
control for the full cohort. Treat as historical context; re-run before citing.

## ⚠ Supabase-derived "real-capture baseline" — RETRACTED 2026-07-30

**A figure of 0.153, once reported here as a real-capture baseline, is
invalid and must not be cited.** It scored against `verified_text` from
`datasets/verified/`, but 4 of those 7 exported pairs contain the OCR's
own unedited output (saved without correction during app testing) and 1
contains a label for a different program entirely. All seven pairs are
quarantined, including `d8cb2ec1`, because the old save path overwrote its
original `extracted_text`. The 0.153 average was an artifact of four
self-comparisons plus one mismatched label at CER 0.935.

**This retraction stands and is unaffected by the 2026-08-03 label
verification.** Its defect is self-comparison in the Supabase export, which is a
different and still-real problem; nothing about the `samples/` cohort changes it.
The claim once made here — that `.181` failed to resolve this because s04–s07
were nonliteral — is itself withdrawn (those labels were literal), but the
Supabase figure remains invalid on its own grounds. Full failure analysis and the
ground-truth validation protocol that now applies to all measurements:
`CAPTURE_GATE_FINDINGS_3_CORRECTION.md` §8 and
`RAW_OCR_CONSENSUS_HANDOFF.md`.

Any historical figure computed on the "real (7)" `datasets/verified/`
column elsewhere in this file inherits the same defect. The `samples/` columns
had a separate literal-provenance gap, which was closed on 2026-08-03.

### Pipeline-engineering contribution (2026-07-30, dev samples)

Stages were toggled cumulatively with the OCR models held constant. This
five-page diagnostic did not use the contaminated Supabase export, and its pages
belong to the cohort verified on 2026-08-03, so the label objection no longer
applies. It has not been re-run since verification, and five single-writer bond
pages cannot support a general claim about pipeline contribution:

| Stage | CER |
|---|---|
| 1. bare — PaddleOCR's own order, no filter, no cleanup | 0.113 |
| 2. + confidence filter | 0.113 |
| 3. + reading-order grouping | 0.107 |
| 4. + keyword cleanup (production) | **0.095** |

The old “pipeline engineering reduced CER by 15%” conclusion stays retracted —
not for label reasons now, but because a 5-page single-writer cohort cannot
support it and the stages were never re-run on the full verified 13. Re-run
cumulatively on the verified cohort before making any contribution claim.

The confidence filter's `~0–1%` contribution claim likewise stays withdrawn. Its
rationale is grade integrity as a fail-safe, not a claimed accuracy percentage.

### Preprocessing ablation (2026-07-30, dev samples)

| Config | CER |
|---|---|
| denoise + threshold (pre-adaptive default) | 0.095 |
| no denoise | 0.087 |
| no threshold | 0.094 |
| grayscale only | **0.085** |

Measured on 5 single-writer bond pages only — all clean paper. The ranking here
(grayscale-only best) is the reason the "never tune against clean samples alone"
rule exists: it inverted once textured paper entered the cohort. Labels are no
longer the objection, but this ablation has not been re-run on the verified 13
and must not be used to rank preprocessing configs.

### Why "never tune against clean samples alone" — the paper-type finding

The clean-bond ablation above favored minimal preprocessing; adding greenbook
reversed that for textured paper, which is what motivated the paper-adaptive
mechanism (measure background texture, then choose treatment). That mechanism is
implemented and on by default.

The specific `0.354 → 0.282` figure stays withdrawn — it was never re-derived,
and the current run's greenbook `clean_ws` is `0.282` on a cohort with different
composition, so quoting the pair as a before/after would be misleading.

Practical rule going forward, reinforced by the 2026-08-03 results: any
preprocessing change must report subgroup CER across every target paper type,
never just a mean — **and must de-confound writer from paper type**. In this
cohort the writer effect (~2.8×) exceeds the paper effect, and the naive
bond-vs-greenbook gap overstates the paper penalty by roughly 2×. Compare within
a writer, or collect a cohort where each writer covers each paper type.

## Second data source: submissions tagged `verified`

`python -m evaluators.export_dataset` pulls `status='verified'` submissions from Supabase
into `datasets/verified/`. The implemented exact-match guard quarantines
suspected contamination. Exported `verified_text` is a candidate label, not
ground truth without source-based human review and provenance.

Caveats:
- The 7 legacy pairs have `extracted_text` equal to
  `verified_text` (a save-path bug overwrote the OCR output — fixed in
  `bf0c331`). All seven remain quarantined, including `d8cb2ec1`; rerunning OCR
  cannot by itself establish that their labels are literal.
- The export warns when identical verified text appears on multiple
  submissions (re-captures of one page) — keep such groups on the same
  side of any train/test split.

## Dataset: `samples/` + `labels.csv`

13 image/label pairs, 2 writers, bond + greenbook paper. All 13 were physically
verified against their source pages by John Cale Nombrado on 2026-08-03 and
carry literal provenance. Subgroup analysis is permitted, with the writer/paper
confound above accounted for.

- `samples/` images — real handwritten C photos, **tracked in git** as of
  2026-08-30 (the held-out CER test set; committed `dfc00fc` so the exact
  20-image set behind the 0.274→0.126 result is reproducible). Note the
  current set is `.jpg` writer-pseudonym files (`bond_writer1_1.jpg`, etc.);
  the old `.jpeg` `nombrado_*`/`submission_*` names this line used to
  reference were retired this session.
- `samples/labels.csv` — `filename,ground_truth_text` plus metadata and the
  three provenance columns `literal_verified`, `literal_verified_by`,
  `literal_verified_at`. Every row is a human transcription confirmed against
  the physical page, character-for-character, including student mistakes. Never
  copy OCR or a prepared prompt as ground truth.

### Adding a new sample
1. Drop the image in `samples/`
2. Have a human view the captured physical/source page and transcribe exactly
   what was written, preserving deviations from any prepared prompt. Add that
   literal text to `labels.csv` (wrap it in `"..."`, doubling literal `"`).
3. **Confirm ambiguous glyphs with the writer, don't guess from the
   image.** Example encountered: one writer's lowercase `f` looks capital;
   confirming directly avoided mislabeling every `for` as `For` (which
   would also break compilation downstream, since `For` isn't a C keyword).
4. **Never use an AI reading of the photograph to establish, confirm, or dispute
   a label.** An AI misreads handwriting through the same failure modes as the
   OCR being evaluated — `1`/`7`, ambiguous capitals — so its errors correlate
   with the pipeline's rather than being independent of them. On 2026-08-02 an AI
   photo read produced seven false discrepancies that triggered a retraction of
   valid results; a second AI pass reproduced the identical misreads, which was
   briefly mistaken for confirmation. Two correlated reads are not corroboration.
   Only a named human with the physical page can settle a label.
5. Fill `literal_verified` / `literal_verified_by` / `literal_verified_at`.
   `evaluate_cer.py` refuses to score a cohort with any row missing these.

### Naming convention
`<writer>_s<snippet>_<desc>_<condition>.jpeg` — `_raw` for a plain camera
capture, `_scan` reserved for the same sheet re-photographed through the
mobile app once its capture flow is frozen. Keeping the condition in the
filename means the two can never get silently averaged together.

### Efficiency tip
Prepared snippets can standardize coverage, but they are prompts only. A writer
may deviate or make mistakes, so every captured page still requires human,
character-faithful transcription from the physical source. Prioritize writer
diversity and symbols such as `{ } < > & * #`.

### Paper types
The target population is a **closed set of three**: bond (short/long),
greenbook, yellow pad — not open-ended paper diversity. Collect enough of
each to calibrate `preprocess.py`'s paper-type classifier
(`_background_noise`, currently thresholded at 2.2) with literal labels and
more than a handful of samples per class. Greenbook now has 5 pages across 2
writers (3 raw nombrado, 2 gate-processed nikko); yellow pad has 2 pages
(gate-processed, writer1) as of 2026-08-05 — still thin for calibration, but no
longer zero. The highest-value collection target remains **more writers per
paper type** and **raw pad coverage** (currently zero raw pad samples exist,
only gate-processed), to break remaining confounds — and, since preprocessing
line-removal was tried and removed (it can't cleanly separate rules from
handwriting), to build the **fine-tuning** set that is the actual fix for lined
paper.

## Re-testing after fine-tuning

The pre-fine-tuning baseline is the **current reproducible** figure, not any
superseded number (`0.148`, `0.190`, `0.128`, `0.151` — see the baseline-status
banners at the top): **`clean_ws 0.149`** over 14 samples, all gate-framed
(bond `0.133` / greenbook `0.159` / yellow_pad `0.171`). Each item must be
re-measured after a fine-tuned model exists, and compared against this:

| Item | Why it needs re-checking |
|---|---|
| CER baseline | The whole point — proves fine-tuning helped, with a number. Compare against the current reproducible baseline (`0.149` overall, 14 gate-framed samples, 2026-08-06), NOT the superseded `0.148`/`0.190`/`0.128`/`0.151`. Report per paper type and per writer, not just overall, and de-confound the two |
| `REC_SCORE_FLOOR` (0.3) | Re-verified against v6 on the gate-framed test set (2026-08-06): dropped items are empty-text phantoms (0.0) or junk (highest 0.291), lowest real kept detection 0.334 — floor sits in the 0.291→0.334 gap. A fine-tuned model shifts the distribution again, so recheck the same way after fine-tuning |
| Keyword cleanup dictionary | Check which rules still fire — some may go dormant if the model learns those keywords natively (keep them anyway, they're free). Note the cleanup layer's current effect is small: `raw_ws 0.156` → `clean_ws 0.149` (2026-08-06 run) |
| `threshold_block_scale` (1.5) and `textured_paper_threshold` (2.2) | Calibrated on 3 greenbook pages from one writer — too thin to trust. Recalibrate on a de-confounded cohort before and after model change |

Reading-order/line-merging is geometry-based and model-independent — no
re-testing needed there.
