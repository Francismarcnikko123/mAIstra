# Pre-extraction on submission — design

> **Implementation status, 2026-09-24:** The optional worker and Option A
> **Extracting…** badge are implemented and pushed on `feature/pre-extraction`
> (including the `feature/program-tabs` merge). Live phone-photo, server-off
> and restart catch-up checks passed. The design discussion below remains
> the historical proposal; use the
> [implementation plan](../plans/2026-09-24-pre-extraction-on-arrival.md)
> and [running guide](../../setup/RUNNING_LOCALLY.md) for current behavior.

> **Implementation plan:** `docs/superpowers/plans/2026-09-24-pre-extraction-on-arrival.md`.
>
> **Addendum 2026-09-24 (still not implemented).** Re-discussed with the user; the design stands. Updates:
> - **Leaning answers:**
>   - Q1: standalone, started with the OCR server (`ocr_feature/main.py` lifespan) so the model loads once.
>   - Q2: poll (~10 s, small batches, oldest first).
>   - Q3: the worker writes.
> - **Minimal v1 without a migration:**
>   - Skip the provenance / `extraction_status` columns at first.
>   - The web already derives "extracted" from `extracted_text` (`getSubmissionStatus`), so no `status` write is needed.
>   - Failures log and leave the paper "new".
>   - Add the columns later, as a request to Jayrald, who now owns the Supabase schema (`docs/TEAM_SYNC.md`).
> - **Write guard:** a conditional update that goes through only if `extracted_text` and `verified_text` are still empty at write time. Checking before the OCR call isn't enough.
> - **Review-screen changes (Nombrado's area):**
>   - The button reads **Extract now** with no text and **Re-extract** once there is text.
>   - Seed `extractedText[id]` from the saved `extracted_text`, so the re-extract dialog doesn't treat pre-extracted text as teacher edits.
>   - Re-fetch the row when the review opens.
> - **Program tabs:** the worker only fills Program 1's baseline (`extracted_text`). It never touches `answers`.
> - **Server key:** a server-side Supabase key goes in a local `.env` only, never in browser or mobile code. Tell Jayrald and get his OK.
> - **For the thesis:** log upload→extracted delay per paper.
> - **Branch:** its own, `feature/pre-extraction`, off `feature/program-tabs`. Updated later on 2026-09-24: it builds on that branch's OCR text panel; see the plan.

**Date:** 2026-09-11
**Branch:** `feature/reading-order-reassembly` (web + a small worker)
**Status:** design, not yet implemented

## Problem

Today OCR runs **on demand**: the teacher opens a submission, clicks
"Extract code", waits for the OCR backend, then edits/verifies. Extraction is
coupled to the teacher's review session, so every submission starts with a wait.

Better: run OCR **the moment a submission lands**, store the result in
`extracted_text`, so when the teacher opens the submission the raw text is
already there and their only job is to **edit/verify** it — the human-in-the-loop
role, unchanged.

This is a UX / architecture change, not a correctness change: **same OCR, same
text, computed earlier and stored**. It does not touch recognition quality.

## Goals

- When a new submission is created, automatically produce its OCR text and
  persist it to `extracted_text` before the teacher opens it.
- Keep the teacher as the required human-in-the-loop verifier — pre-extraction
  fills only the *raw baseline*, never a verified answer.
- Fit the current local-service architecture without requiring the OCR backend
  to be publicly hosted.
- Record provenance (model version + timestamp) so stale extractions are
  identifiable after a future fine-tune.
- Degrade gracefully: if OCR is unavailable at ingest, the submission is fine and
  the teacher can still extract manually.

## Non-goals

- Not removing human verification. The teacher still confirms every submission;
  `verified_text` still comes only from the teacher.
- Not hosting/deploying the OCR model as a public service (that is the eventual
  "production" shape, called out below but out of scope for v1).
- Not changing the OCR pipeline or its output.
- Not auto-grading or auto-verifying.

## Design

### Two possible trigger models

1. **Teacher-side background worker (v1 — fits current setup).** A small process
   on the machine that runs the OCR backend subscribes to new submissions,
   pre-extracts each via the existing endpoint, and writes `extracted_text` back.
   No hosting change; uses the local backend already in use.
2. **Server-hosted OCR + DB webhook (future).** Deploy the FastAPI + models
   somewhere reachable; a Supabase Edge Function calls it on insert. Fully
   automatic and machine-independent, but requires hosting the model weights and
   ~9s/page CPU capacity. Explicitly deferred.

**v1 = model 1.**

### Components (v1)

- **Subscription:** reuse the existing realtime channel. `SupabaseService`
  already exposes `subscribeToSubmissions(callback)`; the worker uses the same
  Supabase client/table to receive INSERTs (or polls for submissions whose
  `status` is new and `extracted_text` is empty, if a standalone worker is
  simpler than embedding in the web app).
- **OCR call:** the existing `POST /api/ocr/extract-from-url` endpoint already
  takes `{ submission_id, image_url }` and returns `raw_text`, `cleaned_text`,
  `line_details`, `review_suggestions`, `review_diagnostics`, and a
  `saved_to_db: false` flag. The worker calls it per new submission.
- **Persistence:** the worker writes `extracted_text = cleaned_text` (matching
  the existing meaning of that column — "the OCR's own output, the baseline the
  teacher edits") plus provenance fields (below). It writes **only**
  `extracted_text` (and provenance/status), never `verified_text`.
  - Alternative: add an opt-in mode to the endpoint that persists server-side
    (the `saved_to_db` flag suggests this was anticipated). Decide in Open
    questions; v1 default keeps the OCR backend write-free and lets the worker
    own the DB write, so the backend stays a pure function.

### Provenance (new columns / fields on `submissions`)

- `extracted_model_version` — the recognizer/model identifier live at extraction.
- `extracted_at` — timestamp.
- (Optional) `extraction_status` — `pending | done | failed`, to drive UI and
  retries.

### Data flow

Submission INSERT (image_url) → worker sees it → `extract-from-url` →
worker writes `extracted_text` + provenance + `extraction_status = done`.
Teacher opens submission → text already present → edits → saves `verified_text`
(unchanged existing flow, including the Re-extract guard).

### Interaction with existing behavior

- **Re-extract guard is unchanged and complementary.** Pre-extraction fills the
  raw baseline; the existing "Re-extract and discard edits?" dialog still
  protects any teacher edits if they later re-run OCR.
- **Manual Extract stays as a fallback** for submissions the worker hasn't
  processed yet or where OCR failed.

## Error handling / safety

- **OCR down / call fails at ingest:** leave `extracted_text` empty, set
  `extraction_status = failed` (or leave pending), never block or drop the
  submission. Teacher can trigger manual extract. Optional bounded retry.
- **Idempotency:** the worker only pre-extracts a submission whose
  `extracted_text` is empty (and `verified_text` is empty) — it must never
  overwrite existing extracted text or any teacher edit.
- **Async / non-blocking:** pre-extraction runs off the submission's critical
  path; a slow OCR call never slows submission creation.
- **Cost:** OCR runs per submission (~9s/page CPU). Acceptable when most
  submissions are reviewed; a simple queue (one at a time) prevents overload. If
  unreviewed volume becomes large, revisit.
- **Grading integrity:** only `extracted_text` (raw) is written automatically;
  `verified_text` remains teacher-only; provenance records which model produced
  the text so it is never mistaken for verified ground truth.

## Testing / validation

- **Worker unit/integration:** given a fake new-submission event, asserts it
  calls `extract-from-url` once, writes `extracted_text` + provenance, and does
  **not** touch `verified_text`; on OCR failure sets failed/pending and writes no
  text; is idempotent (skips a submission that already has `extracted_text`).
- **End-to-end (local):** create a submission → confirm `extracted_text`
  populated before opening the review UI → open it → text is pre-filled → edit →
  save `verified_text` works exactly as before.
- **Regression:** the on-demand manual Extract path and the Re-extract guard
  still work unchanged (existing web tests stay green).

## Open questions (resolve before/with implementation)

1. **Worker location:** standalone script (Python, next to the OCR backend) vs.
   embedded in a running web/service process. Leaning standalone Python so it
   lives with the backend and needs no browser session open.
2. **Push vs. poll:** Supabase realtime INSERT subscription vs. a periodic poll
   for `extracted_text IS NULL`. Poll is simpler and self-healing after
   downtime; realtime is lower-latency. Possibly poll for v1.
3. **Who writes the DB row:** worker writes it (backend stays a pure function) vs.
   an opt-in `save_to_db` mode on `extract-from-url` (the `saved_to_db` flag
   hints at this). Leaning worker-writes for v1.
4. **Schema migration:** adding `extracted_model_version` / `extracted_at` /
   `extraction_status` to `submissions` — confirm with whoever owns the Supabase
   schema (coordinate, since the schema is shared).
