# OCR Backend — Overview

## Auto-extraction update — 2026-09-24

Pushed `feature/pre-extraction` adds an optional worker, off by default, that
uses the same OCR pipeline to fill `extracted_text` for eligible new papers.
`GET /` reports `auto_extract.enabled`, `since` and `failed` so the web can
show an accurate **Extracting…** badge. The worker leaves teacher edits and
old papers alone. OCR tests passed 231/231 and the 20-page evaluator remained
at clean_ws CER 0.099 / WER 0.328 / token accuracy 0.716 at that checkpoint.
See [RUNNING_LOCALLY.md](../setup/RUNNING_LOCALLY.md) for its switch and start-date limit.

## Current status — 2026-09-23

Code-complete for now; waiting for the new bond paper and yellow pad datasets
(new-writer accuracy on those paper types is unmeasured, see
[`LIMITATIONS.md`](LIMITATIONS.md)). Import checklist: `../NEXT_STEPS.md`,
2026-09-23 block.

## Continuation association status — 2026-09-17

The conservative continuation-association rules are now part of the production
layout path through `core/continuation.py` and `core/layout/__init__.py`.
Consequently, both FastAPI endpoints and the web app use them automatically.
The frozen prototype remains an offline research artifact, and
`tests/manual_continuation.py` still compares a real photo with that historical
prototype; its docstring explains the CLI and saved comparison. From `ocr_feature`:

```sh
PYTHONPATH=. .venv/bin/python -m tests.manual_continuation "/path/to/photo.jpg"
```

Frozen fixture replay uses `evaluators.evaluate_continuation_development --prototype`
or `evaluators.evaluate_continuation_reserved`. Production replay is the default
development evaluator mode. See [session handoff](../../ocr_feature/reports/2026-09-14-continuation-session-handoff.md) for scope and results.

FastAPI backend that extracts handwritten C code from photos using
PaddleOCR, cleans up known keyword misreads, and returns it for teacher
verification in the web app.

## Files (`ocr_feature/`)

| File | Role |
|---|---|
| `main.py` | FastAPI app (entrypoint at root): `/api/ocr/extract-upload`, `/api/ocr/extract-from-url` — run with `uvicorn main:app` |
| `core/` | The OCR domain logic: `ocr_pipeline.py` (recognition + orchestration — PaddleOCR config, confidence filtering, entry point), `layout/` (reading-order / indentation geometry package: `columns.py` detects full/banded columns, `displacement.py` provides trace/brace-reassembly primitives, `braces.py` handles literal-safe brace depth, `format.py` reconstructs indentation/blank lines, and `__init__.py` coordinates grouping; split out of `ocr_pipeline.py` on 2026-09-13 and organized into modules on 2026-09-17), `preprocess.py` (downscale, denoise, threshold), `c_code_cleanup.py` (closed-vocabulary keyword fixes — see PIPELINE.md) |
| `try_config.py` | Dev tool, not part of the app: run one real image through OCR with a given `PreprocessConfig`, print the text. No server, no ground truth needed |
| `compare_config.py` | Dev tool: run one image through grayscale+denoise *and* adaptive binarization side by side, print both texts/confidences (and CER, resolved from the project's `labels.csv` by image name — built from the verified `.txt` transcriptions; a loose `.txt` beside the image is intentionally ignored, since it is redundant with `labels.csv` and lives outside the project root). `--show` opens both preprocessed images as VS Code tabs. Built to demonstrate the binarization-vs-grayscale finding live — see `DEFENSE_PREP.md` §14 |
| `evaluators/` | Standalone dev/research tools, not part of the live app: `evaluate_cer.py`, `evaluate_robustness.py`, `robustness.py`, `evaluation.py` (shared metric helpers — CER, edit distance, provenance gate), `export_dataset.py` (Supabase → training-pair export), `build_recognition_dataset.py` (whole-page labels → per-line crops for fine-tuning) |
| `import_verified_batch.py` | Dev tool: imports a physically-verified writer-pseudonym batch (source: `~/Downloads/image_to_transcribe_verified/`) into `datasets/verified/`. Guards against copying anything already held out in `samples/` (see `NEXT_STEPS.md`'s "dataset batches" bullet for a caught-and-fixed contamination bug in this guard's history) |
| `select_holdout.py` | Dev tool: moves a subset of verified images out of `datasets/verified/` (train) into `samples/` (test) — this is how the current 20-image held-out test set was chosen |
| `tests/` | Unit tests (`test_*.py`); run via `run_tests.py` |
| `run_tests.py` | Test runner — discovers and runs everything in `tests/` |
| `requirements.txt` | Direct dependencies, cross-platform (see TROUBLESHOOTING.md) |
| `samples/` | **Tracked in git** — labeled images + `labels.csv`, the held-out CER test set (never used in training) |
| `datasets/verified/` | **Tracked in git** — the train set: physically-verified images + `labels.csv`, feeds `build_recognition_dataset.py` |
| `datasets/recognition/` | Local, gitignored — per-line crops derived from `datasets/verified/`, fully regenerable via `build_recognition_dataset.py` |
| `models/` | Fine-tuned recognizer weights (not committed — GitHub Release, see `models/README.md`) required by `core/ocr_pipeline.py`; no stock-model fallback |
| `notebooks/` | `finetune_ppocrv6_rec_colab.ipynb` — the Colab notebook that produced `models/fine_tuned_rec/`; see `COLAB_SETUP_WORKING.md` for the working procedure it's based on |
| `core/auto_extract.py` | Pre-extraction on arrival (2026-09-24): background worker started by `main.py` when `AUTO_EXTRACT=true`; reads new papers and saves `extracted_text` with a conditional update. See `docs/setup/RUNNING_LOCALLY.md`. |
| `.env.example` | The OCR server's settings (Supabase URL/key, auto-extract switch) with no values. Copy to `.env`. |
| `uploads/` | Local, gitignored. No longer written by the API (2026-09-24): each request uses a temporary folder deleted afterwards. Old files here can be deleted. |
| `outputs/` | Local, gitignored — preprocessed image cache |

The OCR-review *suggestions* backend (per-line review evidence + word-misread
hints) was **removed 2026-09-12** (commit `43addce`) as unused on
`feature/reading-order-reassembly` — its flagging UI lives only on the unmerged
experiment branch. The earlier experiment is kept for history in
[`OCR_REVIEW_SUGGESTION_AB.md`](OCR_REVIEW_SUGGESTION_AB.md) (now marked obsolete).

## Running the backend

```bash
cd ocr_feature
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

First run downloads the stock PaddleOCR detection model (a few hundred MB) —
needs internet, one-time cost. **The fine-tuned recognizer is a separate,
required manual step** — download it from the GitHub Release and unzip it
per `models/README.md` *before* starting the backend, or `ocr_pipeline.py`
raises `FileNotFoundError` on import (there's no stock-model fallback).
Runs on `http://localhost:8000`; the web app expects it there.

## Running the evaluation tool

The evaluators are package modules under `evaluators/`, so run them with `-m`
from `ocr_feature/` (running by file path breaks their imports):

```bash
cd ocr_feature
source .venv/bin/activate
python -m evaluators.evaluate_cer
```

Other evaluators: `python -m evaluators.evaluate_robustness`. Run the tests
with `python run_tests.py`.

Requires every `samples/labels.csv` row to have literal human provenance:
`literal_verified=true`, nonblank `literal_verified_by`, and nonblank
`literal_verified_at` (enforced in `evaluators/evaluation.py`). As of
2026-09-23, all 20 held-out rows pass this check, so the evaluator runs and its
numbers (clean_ws CER 0.099) are citable. The 168 `datasets/verified/` training
rows do not yet carry provenance. The next `import_verified_batch.py
--verified-by` run, for the incoming bond/yellow datasets, populates it. See
[`EVALUATION.md`](EVALUATION.md) for details.

## See also

- [`PIPELINE.md`](PIPELINE.md) — how extraction works and why
- [`EVALUATION.md`](EVALUATION.md) — accuracy measurement, dataset collection
- [`LIMITATIONS.md`](LIMITATIONS.md) — known limitations, what needs fine-tuning
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — environment issues and fixes
- [`CODEBASE_GUIDE.md`](CODEBASE_GUIDE.md) — full file-by-file walkthrough,
  every file's purpose and how to run it
- [`DEFENSE_PREP.md`](DEFENSE_PREP.md) — code-test study guide, including the
  binarization-rescue-attempts writeup (§14) and `compare_config.py`'s role
