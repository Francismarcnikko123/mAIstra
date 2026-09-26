# Pre-extraction on arrival: implementation plan

> Design: `docs/superpowers/specs/2026-09-11-pre-extraction-on-submission-design.md` (and its 2026-09-24 addendum). Speed context: `docs/ocr/EVALUATION.md`, "Speed experiment — 2026-09-24" (about 7 s per page on CPU; the fix is to hide the wait, not to change the model).
> **Status (2026-09-24):** Tasks 1–5 and 8 are committed on `feature/pre-extraction` (`6d02e52`, `eba1a37`, `632bf30`). Task 6 Option A is implemented and live-checked with the user.
> - After Option A: OCR 231/231 tests, web 114/114 tests; both TypeScript checks and Angular build pass (the known CSS budget warning remains). The 20-sample evaluator is unchanged: clean_ws CER 0.099, clean WER 0.328, clean token accuracy 0.716.
> - A read-only check against the cloud confirmed the worker's query. It also found **204 of 209 papers unread** (old test data), so a start-date limit was added (`AUTO_EXTRACT_SINCE`, default = server start). With the default, 0 papers would be read.
> - Option A adds the OCR health state, the web badge, and a realtime UPDATE listener while preserving existing callers and teacher edits.
> - Live check: a new phone paper showed **Extracting… → Needs review** without a reload. With the OCR server stopped, a second paper showed **Needs OCR**. Restarting with `AUTO_EXTRACT_SINCE` set just before the test photos caught it up, and the same open page changed to **Needs review**. No direct database write was made by the test.

**Goal:** when a paper arrives from the phone, the OCR server reads it in the background and saves `extracted_text`. When the teacher opens it, the code is already there. Same pipeline and settings, so accuracy is unchanged (clean_ws CER 0.099 / WER 0.328 / token accuracy 0.716).

**Rules this keeps:**
- **Never overwrite work.** The worker only writes to a paper whose `extracted_text` and `verified_text` are both still empty at write time. The check is a conditional update, not just a read beforehand.
- **Same pipeline.** The worker calls the same extraction function as the button, under the same `_ocr_lock`.
- **OCR output stays separate from teacher edits.** It writes `extracted_text` only, never `verified_text`, `answers` or `status`. The web already shows "Extracted" when `extracted_text` is set.
- **No keys in browser or mobile code.** The key lives only in `ocr_feature/.env`, which is gitignored.
- **The teacher stays in control.** Extract now and Re-extract remain the manual fallback.

**Branch:** `feature/pre-extraction`, branched from `feature/program-tabs` after the review aids are committed. The web part builds on that branch's OCR text panel and review changes, and both branches are Nombrado's. Merge order: program tabs first, then pre-extraction.

---

## Task 0: Gate (no code)

- [ ] Commit and push the finished review aids on `feature/program-tabs`.
- [ ] Tell Jayrald in `TEAM_SYNC.md` (Nombrado → Changed; and a request line in his To do):
  - The OCR server will write `extracted_text` to cloud papers by itself when `AUTO_EXTRACT=true`.
  - For now it uses the publishable key. That works only while `submissions` has no RLS. When he enables RLS, he needs to give Nombrado a secret key (`sb_secret_…`), which goes into `ocr_feature/.env` only.
  - `supabase.ts` gets one small additive read method, and the realtime subscription also listens for UPDATEs (Task 6). Both are in his file, so ask first.
- [ ] Decide where to test end to end:
  - **Local Supabase (preferred):** Docker + `supabase start`, per `docs/setup/SUPABASE_CLOUD_LOCAL_SWITCHING.md`.
  - **Or the cloud,** with Jayrald's OK.

## Task 1: One extraction function for the endpoint and the worker

**File:** `ocr_feature/main.py`

- Move the body of `extract_from_url` into `extract_image_url(image_url: str) -> dict`:
  - it creates a temporary folder
  - calls `download_image`
  - calls `extract_text_from_image`
  - returns `{raw_text, cleaned_text, average_confidence}`
- The endpoint calls it; its behavior is unchanged.
- **Test:** the existing suite passes. Add a unit test with `download_image` and `extract_text_from_image` stubbed: the function returns the cleaned text, and the temporary folder is removed afterwards.

## Task 2: The worker (pure logic, testable without network)

**New file:** `ocr_feature/core/auto_extract.py`. Only stdlib at import time, like `debug_artifact.py`.

```python
@dataclass
class AutoExtractConfig:
    enabled: bool
    interval_seconds: float = 10
    batch_size: int = 5
    max_failures: int = 3

def config_from_env(env) -> AutoExtractConfig
    # AUTO_EXTRACT, AUTO_EXTRACT_INTERVAL_SECONDS

def run_once(store, extract, failures, now, log) -> int:
    """One polling pass. Returns how many papers were saved."""
```

- **`store`** is a small interface (see Task 3):
  - `pending(limit)` returns `[{id, image_url, captured_at}]`: papers where `extracted_text` and `verified_text` are empty and `image_url` is set, oldest first.
  - `save_extracted_text(id, text)` returns `True` only if the conditional update changed a row.
- **`extract(image_url)`** is `extract_image_url` from Task 1.
- **`failures`** is `dict[id, int]`. A paper that failed `max_failures` times is skipped until the server restarts. It stays "New" for the teacher's Extract now.
- **Logging**, one line per paper: id, result (`saved` / `skipped: teacher got there first` / `failed: <reason>`), extraction seconds, and **arrival→saved delay** (`now - captured_at`, the thesis number).
  - No code text or image contents in the log.
  - Timings are also appended to `outputs/auto_extract_timings.csv`, which is gitignored and holds only ids and seconds.

**Tests** (`ocr_feature/tests/test_auto_extract.py`, fake store and fake extract):
1. Saves each pending paper once with the cleaned text.
2. A paper the teacher filled in meanwhile (`save_extracted_text` returns False) is logged as skipped, and it's not an error.
3. An extraction error counts a failure; after `max_failures` the paper isn't retried.
4. Empty `pending` does nothing.
5. `config_from_env`: off by default, on with `AUTO_EXTRACT=true`, interval parsed, bad values fall back to defaults.
6. Nothing in `run_once` touches `verified_text`, `answers` or `status`. The fake store records every call.

## Task 3: The Supabase store

**Same file, a class using `supabase` 2.31 (already in `requirements.txt`).**

- `SupabaseStore(url, key)`:
  - `pending(limit)` runs `select id, image_url, captured_at` with `extracted_text is null` (also treat `''` as empty via `or`), `verified_text is null`, and `image_url not null`, ordered by `captured_at` ascending, limited to `limit`.
  - `save_extracted_text(id, text)` runs `update({extracted_text: text}).eq('id', id)` plus the same empty-filters, and returns whether a row came back.
- **Env:** `SUPABASE_URL`, `SUPABASE_KEY`.
  - The old unused `SUPABASE_ANON_KEY` (a dead legacy key) is removed from the local `.env`.
  - `ocr_feature/.env.example` documents the variables, with no values.
- **Test:** with a mocked client, check the filters and the update payload. Only `extracted_text` is written.

## Task 4: Start and stop with the server

**File:** `ocr_feature/main.py` (the `lifespan` hook)

- After `warmup()`: if `config_from_env(os.environ).enabled`, and `SUPABASE_URL` / `SUPABASE_KEY` are set, start a daemon thread that loops `run_once` then waits `interval_seconds` on a `threading.Event`.
- On shutdown, set the event and join briefly.
- If it's enabled but the URL or key is missing, log one clear warning and don't start. The API still works.
- It uses the existing `_ocr_lock` through `extract_text_from_image`, so manual extractions and the worker queue behind each other.
- **Test:** `lifespan` with `AUTO_EXTRACT` unset starts no thread. With it set and a fake store, it starts and stops cleanly.

## Task 5: Web review uses the pre-extracted text correctly

**File:** `submissions-list.ts` / `.html` (Nombrado's OCR-extraction parts)

1. **Re-extract guard baseline.** Today `extractText()` compares the editor with `extractedText[id]`, which is empty for a pre-extracted paper, so an untouched paper would ask "discard edits?". Compare with `extractedText[id] ?? submission.extracted_text` instead.
2. **Wording:**
   - Empty placeholder: "Not extracted yet. Papers are read automatically while the OCR server runs, or choose Extract now."
   - Button: **Extract now** when there's no text, **Re-extract code** when there is.
3. **Fresh row on open.** `openModal()` re-reads that one submission (`extracted_text`, `verified_text`, `answers`), using a new additive `getSubmission(id)` in `supabase.ts` (Jayrald's file; ask in Task 0). If `extracted_text` arrived since the list loaded and the editor is empty, fill it. Never replace existing editor text.
- **Tests:**
  - Re-extract on an untouched pre-extracted paper runs without the confirmation.
  - Opening a paper picks up `extracted_text` that arrived later.
  - It never overwrites editor text the teacher already has.

## Task 6 (replaced 2026-09-24): Option A — the list shows "Extracting…" and updates itself

**Why:** the user wants papers to be effectively "already extracted" by the time a teacher looks. The worker saves text ~26 s after capture, but the list showed **Needs OCR** until a reload.

**Live test on 2026-09-24:** one real phone photo; read-only listener; no writes by the test.
- The worker saved paper `60c59144` 26 s after capture; the OCR took 22 s.
- Realtime delivered the INSERT **and** the worker's UPDATE (`has_extracted_text=True`) at the moment of saving. (An earlier "missing" reading was the test's own output buffering, not Supabase.)
- The browser at `localhost:4200` can reach the OCR server's health check (`GET http://localhost:8000/` → 200).

**Rule:** "Extracting…" only shows when extraction is really happening. The web app asks the OCR server; it never guesses from time.

### A1. OCR server reports what it's doing
**File:** `ocr_feature/main.py`

- `lifespan` keeps the worker on `app.state.auto_extract`.
- `GET /` adds, without changing the existing field:

  ```json
  {"status": "MaestrAI OCR Backend is running",
   "auto_extract": {"enabled": true, "since": "2026-09-24T10:09:00+00:00", "failed": ["<ids given up>"]}}
  ```

  With the worker off: `"auto_extract": {"enabled": false}`.
- **Tests** (`tests/test_main.py`): the health output with the worker on and off; `failed` lists only papers at `max_failures`.

### A2. Web knows whether auto-extract is running
**File:** `submissions-list.ts` (Nombrado's OCR-extraction parts)

- New state `autoExtract: { enabled: boolean; since: string | null; failed: Set<string> }`, starting as off.
- `checkOcrServer()`:
  - GETs `http://localhost:8000/` with a short timeout.
  - Any error means off, so it never breaks the page.
  - Runs in `ngOnInit`, then every 30 s, and after each list reload.
- The interval is cleared in `ngOnDestroy`, with the existing timer and destroy protections.
- **Tests:** on, off, unreachable, and the timer cleared on destroy.

### A3. Badge: "Extracting…" vs "Needs OCR"
**Files:** `submissions-list.ts` / `.html`, plus a small style in `program-tabs.css`

- `isBeingExtracted(submission)` is true only if **all** of these hold:
  - the paper would be **Needs OCR** (no `extracted_text`, no `verified_text`)
  - `autoExtract.enabled`
  - `captured_at >= autoExtract.since`
  - its id isn't in `autoExtract.failed`
- The card badge shows **Extracting…** in that case; otherwise the label is unchanged.
- The status filter is unchanged: extracting papers still count under "Needs OCR", so no filter logic changes.
- **Tests:**
  - A new paper with the server on shows Extracting…
  - With the server off, or for an old paper, or one it gave up on, it shows Needs OCR.
  - Once `extracted_text` arrives, it shows Needs review.

### A4. List updates itself when the worker saves
**Files:** `supabase.ts` (Jayrald's file: one additive listener, announce in `TEAM_SYNC.md`), `submissions-list.ts`

- `subscribeToSubmissions(onInsert, onUpdate?)` adds an `UPDATE` listener on the same channel. Existing callers are unchanged.
- The component's `onUpdate(row)` calls a shared `applyFreshSubmission(row)`, the same helper that "re-read on open" (Task 5.3) now uses:
  - fill `extracted_text` on the list row and the open paper **only if empty**
  - update `status`
  - fill the editor and its saved snapshot only if the editor is empty
  - regroup and refresh
- It never replaces editor text, `verified_text` or tabs the teacher has on screen.
- **Tests:**
  - An update fills an empty paper and flips its badge.
  - An update never overwrites a teacher's text.
  - The subscription registers both INSERT and UPDATE.

### A5. Verify
- Both test suites, the type checks and `ng build`.
- **Live:**
  1. OCR server on: take a photo. The card shows **Extracting…**, then **Needs review** by itself, with no reload.
  2. Stop the server: a new photo shows **Needs OCR**.
  3. Start the server again: it catches up and the badge flips by itself.
- Old papers keep showing **Needs OCR**, as intended; only papers after the start date are extracted.

### A6. Docs
- `TEAM_SYNC.md`:
  - `supabase.ts` gained an UPDATE listener
  - the status badge can show "Extracting…"
  - the health check has an `auto_extract` field
- The overview's pre-extraction section, `RUNNING_LOCALLY.md` (what the badge means), and this plan's status.

**Not in option A:**
- polling the database for papers still extracting (realtime was proven, and re-read on open stays as the safety net)
- any phone change
- backfilling old papers

## Task 6 (original, superseded by option A above): List updates without reloading (needs Jayrald's OK)

**File:** `supabase.ts` `subscribeToSubmissions()`

- Also listen for `UPDATE` on `submissions`. For an update, patch only that row's `extracted_text` / `status` in the list (and fill `editableText` if it's empty), instead of re-fetching everything.
- The status badge changes from **Needs OCR** to **Needs review** by itself when the worker finishes.
- **Test:** an UPDATE payload patches one row and never replaces existing editor text.
- *If Jayrald prefers not to,* skip this task. Task 5.3 already gives the teacher fresh text on open; only the badge waits for the next reload.

## Task 7: Verify

- [ ] OCR suite (`python run_tests.py`) and web suite (`npx ng test --watch=false`), type checks, `ng build`.
- [ ] `evaluate_cer` still 0.099 / 0.328 / 0.716 (the pipeline is untouched; this confirms it).
- [ ] End to end on the environment chosen in Task 0:
  1. Start the server with `AUTO_EXTRACT=true`.
  2. Insert or upload a paper.
  3. It's saved within about 10 s plus about 7 s per page.
  4. Open it: the code and OCR text panel are there, with no Extract click.
  5. The badge changes by itself (if Task 6 is done).
- [ ] Race check: open a paper, type in Program 1 and save before the worker reaches it. The worker logs "skipped" and doesn't overwrite.
- [ ] Server off: papers stay "Needs OCR" and Extract now works. Server back on: it catches up.

## Task 8: Docs

- `docs/setup/RUNNING_LOCALLY.md`: `.env` variables, the on/off switch, what the log lines mean.
- `docs/ocr/README.md` and `ocr/CODEBASE_GUIDE.md`: `core/auto_extract.py`.
- `docs/PROJECT_OVERVIEW_AND_CHANGES.md`: a short "Pre-extraction on arrival" section.
- `docs/TEAM_SYNC.md`: Changed (the worker writes `extracted_text`; Task 5/6 changes to shared files).
- The spec: mark implemented, with commits.
- `docs/ocr/EVALUATION.md`: arrival→saved delay numbers from the end-to-end run, for the thesis.

---

## Not in this version

- Provenance columns (`extracted_model_version`, `extracted_at`, `extraction_status`). They're a schema request to Jayrald later; the log covers it for now.
- Hosting the OCR server. It runs only while the OCR machine is on.
- Signed URLs for a private storage bucket. That's needed only if Jayrald makes the bucket private.
- Any speed change to the model. Batch 1 was measured and declined; see `EVALUATION.md`.
