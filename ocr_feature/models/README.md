# Models

Large model weights are **not committed** to this repo (they bloat git history
and are reproducible). They are distributed via a **GitHub Release** and are
regenerable from `notebooks/finetune_ppocrv6_rec_colab.ipynb`.

## `fine_tuned_rec/` — fine-tuned PP-OCRv6 recognizer

**Required — the backend will not start without this.** `core/ocr_pipeline.py`
has no stock-model fallback; it raises `FileNotFoundError` at import time if
this folder is missing, telling you to come back here.

First real fine-tune (2026-08-30): trained on 2,491 handwritten C-code line
crops, 40 epochs. On the held-out `samples/` test set it reduced recognition
CER (`clean_ws`) from **0.274 (stock) → 0.126 (−54%)**, improving every sample.
Full result + methodology: `docs/ocr/EVALUATION.md`.

### Setup (do this before running the backend or any evaluator)

1. Download `fine_tuned_rec_model.zip` from the repo's GitHub **Releases**
   page (release tag: `ocr-rec-v1` — update this if the tag differs).
2. From the `ocr_feature/` directory, unzip it into
   `models/fine_tuned_rec/inference/`:
   ```bash
   cd ocr_feature
   unzip fine_tuned_rec_model.zip -d models/fine_tuned_rec/inference
   ```
3. Verify the layout — you should have exactly these three files, directly
   inside `inference/` (no extra nested folder):
   ```bash
   ls models/fine_tuned_rec/inference
   # inference.json  inference.pdiparams  inference.yml
   ```
   If `unzip` instead created a nested folder (e.g.
   `inference/fine_tuned_rec_model/inference.json`), move the three files up
   one level so they sit directly in `inference/`.
4. Confirm it's picked up — start the backend (`uvicorn main:app --reload`
   from `ocr_feature/`) and check the first console lines for:
   ```
   [ocr_pipeline] recognizer: fine-tuned (models/fine_tuned_rec/inference)
   ```
   No such line, or a `FileNotFoundError` on startup, means step 2 or 3 above
   didn't produce the expected layout.

`core/ocr_pipeline.py` points the recognizer at this directory via
`text_recognition_model_dir="models/fine_tuned_rec/inference"` — no other
code change is needed once the files are in place.

### To regenerate it from scratch

Follow `docs/ocr/COLAB_SETUP_WORKING.md` (Colab, GPU) — build the crop dataset,
train, export, download `fine_tuned_rec_model.zip`, then install as above.
