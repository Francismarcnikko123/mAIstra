# Command Reference — one line each

## Auto-extraction check — 2026-09-24

From `ocr_feature/`, start `.venv/bin/uvicorn main:app --reload --port 8000`
with `AUTO_EXTRACT=true` in `.env` when you intend to test new-paper
pre-extraction. `curl http://localhost:8000/` reports `status` and
`auto_extract` (`enabled`, `since`, `failed`). The worker is off by default;
its start-date limit protects old papers. For a controlled restart catch-up
test, set `AUTO_EXTRACT_SINCE` just before the test photo. See
[RUNNING_LOCALLY.md](setup/RUNNING_LOCALLY.md) for the exact behavior and
shared-cloud caution.

## Offline continuation experiment — 2026-09-14

From `ocr_feature` with its existing virtual environment:

| Command | Purpose |
| --- | --- |
| `PYTHONPATH=. .venv/bin/python -m tests.manual_continuation --help` | Read the tester's usage docstring without loading OCR. |
| `PYTHONPATH=. .venv/bin/python -m tests.manual_continuation "/path/to/photo.jpg"` | Fresh OCR + prototype comparison; unique output directory per run. |
| `PYTHONPATH=. .venv/bin/python -m tests.manual_continuation outputs/continuation_association_intake/development/writerX_page05.jpg` | Try the existing two-question development paper. |
| `PYTHONPATH=. .venv/bin/python -m unittest tests.test_manual_continuation -v` | Run model-free checks for the manual runner. |
| `PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_development --prototype` | Replay frozen development OCR; score association separately from order. |
| `PYTHONPATH=. .venv/bin/python -m evaluators.evaluate_continuation_reserved` | Replay the recorded reserved experiment; reject changed rules/fixtures. |

The manual command accepts `--output-dir outputs/my_checks` and does not enable
anything in the web app. See [session handoff](../ocr_feature/reports/2026-09-14-continuation-session-handoff.md) for the current scope and result interpretation.

Every command used across the OCR docs (`DEFENSE_PREP.md`, `CODEBASE_GUIDE.md`,
`RUNNING_LOCALLY.md`, `NEXT_STEPS.md`), collected in one place so you don't
have to hunt through multiple files during live prep. Grouped by what you're
trying to do, not by which file it came from. All `ocr_feature/` commands
assume you've already `cd ocr_feature && source .venv/bin/activate` (or
prefix with `.venv/bin/python` instead of activating — both forms appear in
the other docs and are equivalent).

## Start the three local services

| Command | Directory | One-line explanation |
|---|---|---|
| `uvicorn main:app --host 0.0.0.0 --port 8000` | `ocr_feature/` | Starts the OCR backend (PaddleOCR pipeline). |
| `uvicorn main:app --host 0.0.0.0 --port 8001` | `judge0_api/` | Starts the Judge0 wrapper API that talks to the remote Judge0 VM. |
| `npm start` | `maistra_web/` | Starts the Angular dev server on `http://localhost:4200`. |
| `curl http://localhost:8001/` | anywhere | Health-checks the Judge0 wrapper; expect `{"status":"ok"}`. |
| `curl -H "X-Auth-Token: <TOKEN>" http://<VM_IP>:2358/about` | anywhere | Confirms the remote Judge0 VM itself is reachable and returns its version. |

## OCR backend — tests

| Command | One-line explanation |
|---|---|
| `.venv/bin/python run_tests.py` | Runs the whole OCR unit-test suite (fast, no models loaded). |
| `.venv/bin/python run_tests.py -v` | Same, verbose — prints every individual test name/result. |
| `.venv/bin/python -m unittest discover -s tests -p "test_*.py"` | Alternate way to run the full suite via stdlib `unittest` directly. |
| `.venv/bin/python -m unittest test_c_code_cleanup.py -v` | Runs just the cleanup-module tests (verbose). |
| `.venv/bin/python -m unittest test_evaluation.py -v` | Runs the evaluation-module tests. |
| `.venv/bin/python -m unittest test_ocr_pipeline.py` | Runs just the grouping/geometry pipeline tests. |
| `.venv/bin/python -m unittest test_robustness.py -v` | Runs just the robustness-diagnostic tests. |
| `.venv/bin/python -m unittest test_export_dataset.py -v` | Runs just the dataset-export tests (contamination guard, skip logic). |

## OCR backend — try a change on one image

| Command | One-line explanation |
|---|---|
| `.venv/bin/python try_config.py` | Runs the default sample image through the default preprocessing config and prints `cleaned_text` + confidence — the fastest way to eyeball one change. |
| `.venv/bin/python try_config.py path/to/photo.jpg` | Same, on a specific image. |
| `.venv/bin/python try_config.py path/to/photo.jpg --adaptive-denoise` | Same, forcing the adaptive-denoise branch on regardless of measured noise. |
| `.venv/bin/python compare_config.py path/to/image.jpg` | Runs one image through production preprocessing *and* adaptive binarization side by side, printing both outputs (and CER, resolved from `labels.csv` by image name) — built to demonstrate why `threshold=False` ships by default. |
| `.venv/bin/python compare_config.py path/to/image.jpg --show` | Same, and also opens both processed images for a visual look. |

## OCR backend — full metrics (the real accuracy check)

| Command | One-line explanation |
|---|---|
| `.venv/bin/python -m evaluators.evaluate_cer` | Runs CER/WER/token-accuracy on the held-out `samples/` set, broken down by paper type and writer — the authoritative accuracy check after any change. |
| `.venv/bin/python -m evaluators.evaluate_robustness` | Measures OCR sensitivity to synthetic stressors (blur, rotation, noise) — diagnostics, not a real-paper accuracy claim. |
| `.venv/bin/python -m evaluators.crosswriter_eval` | Runs the currently-configured recognizer on writers fully excluded from a cross-writer retrain, to measure generalization to unseen handwriting. |

## OCR backend — dataset pipeline

| Command | One-line explanation |
|---|---|
| `.venv/bin/python -m evaluators.export_dataset` | Pulls every `verified` or `graded` page from Supabase into `datasets/verified/` (images + `labels.csv`) for fine-tuning, reading each page's programs from `submission_programs` (split pages keep one block per program in `program_blocks`). Needs `SUPABASE_URL` and `SUPABASE_KEY` in `ocr_feature/.env`. Merges into existing writer-batch rows rather than overwriting them, and prints a provenance/correction-distance summary. **Writes to the training data; check the summary before retraining.** |
| `.venv/bin/python -m evaluators.build_recognition_dataset` | Crops per-line training images from `datasets/verified/` pages, pairing each crop with its ground-truth text. A split page's programs are each matched to the page's lines on their own. |
| `.venv/bin/python -m evaluators.build_crosswriter_dataset` | Builds the writer-disjoint measurement dataset (holds out specific greenbook writers entirely) for the cross-writer generalization experiment. |
| `.venv/bin/python select_holdout.py` | Picks a stratified test-set holdout from `datasets/verified/labels.csv`, moves those images to `samples/`, and removes them from the training set. |
| `.venv/bin/python import_verified_batch.py --verified-by "Name of verifier"` | One-off import of a teammate's physically-verified, writer-named photo batch into `datasets/verified/`; records `literal_verified`/`_by`/`_at` provenance and merges into existing Supabase-sourced rows rather than overwriting them. |

## OCR backend — reading a debug artifact

| Command | One-line explanation |
|---|---|
| `cat outputs/debug/<stem>_preprocessed.json \| python3 -m json.tool` | Pretty-prints one extraction's full debug artifact (raw/cleaned text, every detection score, dropped fragments, grouped lines). |
| `python3 -c "import json,sys; d=json.load(sys.stdin); [print(x['score'], repr(x['text'])) for x in d['dropped_low_confidence']]" < outputs/debug/<stem>_preprocessed.json` | Prints just the fragments the confidence filter dropped, with their scores — the fastest way to see what `REC_SCORE_FLOOR` actually removed. |

## Web app (`maistra_web/`)

| Command | One-line explanation |
|---|---|
| `npm ci` | Clean-installs dependencies exactly as locked (use this, not `npm install`, when switching machines/OS). |
| `npm start` | Starts the dev server (alias for `ng serve --configuration development`). |
| `ng serve --configuration production` | Starts the dev server built against the production environment config. |
| `npx ng test --watch=false` | Runs the unit tests once (Vitest via `@angular/build:unit-test`, not Karma). 309 tests on `judge0-integration` as of 2026-09-27. |
| `npm run e2e` | Runs the Playwright end-to-end tests (fake backend, no cloud writes; own dev server on port 4300). 9 tests as of 2026-09-27. |
| `npx playwright install chromium` | One-time download of Playwright's test browser (after `npm ci`). |
| `npx ng test --watch=false --include=src/app/components/submissions-list/extra-answers.spec.ts` | Runs only the named spec file(s). |
| `npx tsc -p tsconfig.app.json --noEmit` | Type-checks the app without building (`tsconfig.spec.json` for the tests). |
| `ng build` | Builds the app (development config by default). |
| `ng build --configuration production` | Production build. |

## Git — branch/doc discipline for this repo

| Command | One-line explanation |
|---|---|
| `git status --short` | Quick view of what's modified/staged/untracked before doing anything destructive. |
| `git ls-files docs/` | Shows exactly which docs are git-tracked (should only be `PROJECT_OVERVIEW_AND_CHANGES.md` + `docs/setup/*.md`) — check this before ever staging anything under `docs/`. |
| `git stash push -m "<message>" -- <files>` | Shelves specific modified tracked files (not everything) so a branch switch isn't blocked, without losing the changes. |
| `git stash pop` | Restores the most recently stashed changes onto the current branch. |
| `git stash list` | Shows what's currently stashed. |
| `git checkout <branch>` | Switches branches (fails if it would overwrite uncommitted tracked-file changes — stash first). |
| `git log --oneline -- <path>` | Shows the commit history for one specific file, on the current branch. |
| `git branch -r --contains <commit>` | Shows which remote branches already contain a given commit — useful for checking whether something's actually been pushed. |

## Judge0 VM networking (only if the wrapper can't reach it)

| Command | One-line explanation |
|---|---|
| `ifconfig \| grep "inet " \| grep -v 127.0.0.1` | Shows your own machine's LAN IP (macOS/Linux) — used to confirm both machines share a subnet. |
| `ssh <user>@<host_ip> -p <forwarded_ssh_port>` | SSHes into the teammate's Judge0 VM through the VirtualBox port-forward. |
| `sudo docker compose ps` (inside the VM) | Lists the four Judge0 containers (`db`, `redis`, `server`, `workers`) and whether they're `Up`. |
| `grep AUTHN_TOKEN judge0.conf` (inside the VM) | Reads the Judge0 API token needed for `judge0_api/.env`. |
| `lsof -nP -i :<PORT>` (macOS) | Confirms a port-forward is actually listening on all interfaces (`*.PORT`), not just localhost. |

---

**Full detail behind any of these:** `docs/setup/RUNNING_LOCALLY.md` (service
startup + VM networking troubleshooting), `docs/ocr/DEFENSE_PREP.md` §12
(before/after code + verify steps for a specific change), `docs/ocr/CODEBASE_GUIDE.md`
§10 (the same, organized by file/constant).
