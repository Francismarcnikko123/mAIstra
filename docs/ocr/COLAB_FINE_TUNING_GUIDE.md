# Colab fine-tuning dry run — step-by-step (verified 2026-08-09)

> **Historical dry run:** A real fine-tuned recognizer later shipped. The
> 140-crop volume and `0.149` baseline below describe this August practice
> run, not the current production dataset or accuracy. As of 2026-09-24 the
> 20-page evaluator reports clean_ws CER 0.099 / WER 0.328 / token accuracy
> 0.716. Use [NEXT_STEPS.md](../NEXT_STEPS.md) and
> [EVALUATION.md](EVALUATION.md) before planning another fine-tune.

Extracted from `NEXT_STEPS.md` into its own doc so it's a standalone
reference you can follow top-to-bottom without hunting through the
checkpoint doc. `NEXT_STEPS.md` links here rather than duplicating this.

**OS scope:** Parts 2–5 (everything that runs *inside* Colab, prefixed `!` or
`%`) are identical regardless of your local OS — they execute on Colab's own
Linux backend, not your machine. Only Parts 1 and 6 (the steps that run on
your own computer) differ by OS, so those two sections give both a **macOS**
and a **Windows** command block. The macOS commands are marked
**[verified]** where checked directly against this repo's own `.venv`; the
Windows commands follow standard `venv`/PowerShell convention but were not
checked against a live Windows install — if a path doesn't match what you
see locally, trust what's actually on your disk over this doc.

**Read this caveat before running any of it:** at current volume (140 crops —
120 train / 20 val, well below the 200–500 minimum-viable tier) this is a
**pipeline-mechanics proof**, not a real fine-tuning attempt. The point is to
confirm the whole chain (crop dataset → PaddleX training config → a trained
checkpoint → swapped back into `ocr_pipeline.py`) actually works end-to-end,
not to produce a model worth deploying. A 14-line val set can't reliably
detect overfitting.

Everything below marked **[verified]** was checked directly against this
repo's `.venv` on 2026-08-09 (exact file exists / exact version installed /
exact constructor accepts this kwarg) — not copied from memory. Steps 7–9
(the actual plugin install + train + export) are **not run yet** — they
require a live Colab session with GPU and a large one-time repo clone, so
they're written from PaddleX's own documented command shape, verified partly
via `repo_apis/PaddleOCR_api/text_rec/runner.py:48` in the installed package,
but not executed end-to-end. If any of steps 7–9 error, paste the actual
output back rather than assuming the fix — same discipline as everything
else in this project.

## Part 1 — Local (build + package the dataset)

1. **Build the crop dataset** (the builder now clears stale output itself):

   **macOS [verified]:**
   ```bash
   cd ocr_feature
   .venv/bin/python -m evaluators.build_recognition_dataset
   ```

   **Windows (PowerShell or cmd):**
   ```powershell
   cd ocr_feature
   .venv\Scripts\python -m evaluators.build_recognition_dataset
   ```

   Produces `datasets/recognition/{images/, train.txt, val.txt}` — currently
   120 train / 20 val pairs (split by whole page, so the exact ratio depends
   on which pages land in val).

2. **Zip it:**

   **macOS [verified]:**
   ```bash
   cd ocr_feature
   zip -r recognition_dataset.zip datasets/recognition
   ```

   **Windows (PowerShell — `zip` isn't a built-in Windows command, use
   `Compress-Archive` instead):**
   ```powershell
   cd ocr_feature
   Compress-Archive -Path datasets\recognition -DestinationPath recognition_dataset.zip
   ```
   (If you're in Git Bash or WSL instead of PowerShell/cmd, the macOS `zip`
   command above works as-is there too.)

3. **Grab the real PP-OCRv6 recognition config** — it already exists inside
   the installed `paddlex` package in your `.venv`, no need to hand-write
   one. **The path differs by OS, not just the slash direction** — a macOS/
   Linux `venv` nests site-packages under a Python-version folder
   (`lib/python3.12/...`), but a Windows `venv` does not:

   **macOS [verified]:**
   ```bash
   cp .venv/lib/python3.12/site-packages/paddlex/configs/modules/text_recognition/PP-OCRv6_medium_rec.yaml \
      PP-OCRv6_medium_rec.yaml
   ```

   **Windows (PowerShell):**
   ```powershell
   Copy-Item .venv\Lib\site-packages\paddlex\configs\modules\text_recognition\PP-OCRv6_medium_rec.yaml `
     PP-OCRv6_medium_rec.yaml
   ```
   **Windows (cmd.exe):**
   ```cmd
   copy .venv\Lib\site-packages\paddlex\configs\modules\text_recognition\PP-OCRv6_medium_rec.yaml PP-OCRv6_medium_rec.yaml
   ```
   If that exact path doesn't exist on your machine, `dir /s /b PP-OCRv6_medium_rec.yaml`
   (cmd) or `Get-ChildItem -Recurse -Filter PP-OCRv6_medium_rec.yaml` (PowerShell)
   from inside `.venv` will find its real location — the Python version
   folder name changes with whatever Python version created the venv.

   **[verified]** actual file content as of 2026-08-09 (same file, same
   content, regardless of OS — only the path to find it differs):
   ```yaml
   Global:
     model: PP-OCRv6_medium_rec
     mode: check_dataset   # check_dataset/train/evaluate/predict
     dataset_dir: "/paddle/dataset/paddlex/ocr_rec/ocr_rec_dataset_examples"
     device: gpu:0,1,2,3
     output: "output"

   CheckDataset:
     convert:
       enable: False
       src_dataset_type: null
     split:
       enable: False
       train_percent: null
       val_percent: null

   Train:
     epochs_iters: 20
     batch_size: 8
     learning_rate: 0.001
     pretrain_weight_path: https://paddle-model-ecology.bj.bcebos.com/paddlex/official_pretrained_model/PP-OCRv6_medium_rec_pretrained.pdparams
     resume_path: null
     log_interval: 20
     eval_interval: 1
     save_interval: 1

   Evaluate:
     weight_path: "output/best_accuracy/best_accuracy.pdparams"
     log_interval: 1

   Export:
     weight_path: https://paddle-model-ecology.bj.bcebos.com/paddlex/official_pretrained_model/PP-OCRv6_medium_rec_pretrained.pdparams
   ```
   You'll override `dataset_dir`, `device`, and the `Train` block's values
   via `-o` flags at train time (step 10) — don't hand-edit the file, keep it
   as the untouched reference.

## Part 2 — Colab setup

4. **New notebook** at colab.research.google.com → Runtime → Change runtime
   type → **GPU** (T4 is enough for a dry run).

5. **Upload both files** (`recognition_dataset.zip`, `PP-OCRv6_medium_rec.yaml`):
   ```python
   from google.colab import files
   uploaded = files.upload()   # select both in the dialog
   ```

6. **Unzip and sanity-check:**
   ```bash
   !unzip -q recognition_dataset.zip -d /content/
   !ls /content/datasets/recognition/          # expect images/ train.txt val.txt
   !wc -l /content/datasets/recognition/train.txt /content/datasets/recognition/val.txt
   ```
   Expect `120 train.txt` / `20 val.txt` (must match whatever step 1 printed
   locally — if the counts differ from your own step-1 build, the zip/upload
   step went wrong, stop and check).

## Part 3 — Install PaddleOCR's real training code

> ⚠️ **This Part 3 install path is broken on Colab's Python 3.13 runtime
> (confirmed 2026-08-30).** `paddlex --install PaddleOCR -y` cannot resolve
> its bundled dependency set on 3.13 and fails no matter how the pins are
> patched. Use **`COLAB_SETUP_WORKING.md`** instead — it skips the plugin
> installer and runs `tools/train.py` directly, which is what actually
> started fine-tuning. Parts 1–2 and 6 of this guide are still correct;
> only this install-and-train section (Parts 3–5) is superseded.

7. **[verified] Install the exact pinned version this repo uses:**
   ```bash
   !pip install -q paddlepaddle-gpu paddleocr==3.7.0
   ```

8. **Install the training plugin** — `paddlex --install PaddleOCR -y` clones
   the actual PaddleOCR repo (the one containing `tools/train.py`) into the
   PaddleX install. **Not run yet** — this is a real network operation that
   clones a large repo, only worth doing inside the live Colab session:
   ```bash
   !paddlex --install PaddleOCR -y
   ```

9. **Find where it landed** — the exact path depends on the Colab session
   and isn't knowable in advance:
   ```bash
   !find / -maxdepth 6 -iname "train.py" -path "*PaddleOCR*" 2>/dev/null
   ```
   Call whatever directory that prints `<REPO_DIR>` below (expect something
   like `/root/.paddlex/official_plugins/PaddleOCR`).

## Part 4 — Train

10. **Run training** — command shape (`tools/train.py -c <config> -o
    <overrides>`) matches PaddleX's own `runner.py`; the exact `-o` keys
    below come directly from the config dumped in step 3:
    ```bash
    %cd <REPO_DIR>
    !python tools/train.py \
      -c /content/PP-OCRv6_medium_rec.yaml \
      -o Global.mode=train \
      -o Global.dataset_dir=/content/datasets/recognition \
      -o Train.epochs_iters=20 \
      -o Train.batch_size=8 \
      -o Global.device=gpu:0
    ```
    It will download the pretrained starting weights (the
    `pretrain_weight_path` URL in the config) before training actually
    starts — expected on the first run, not an error.

## Part 5 — Export the trained model

11. **Export to inference format** (what the live pipeline actually loads):
    ```bash
    !python tools/export_model.py -c /content/PP-OCRv6_medium_rec.yaml \
      -o Global.mode=export \
      -o Export.weight_path=output/best_accuracy/best_accuracy.pdparams
    ```
    Produces `output/best_accuracy/inference/` — the finished model.

12. **Download it back:**
    ```bash
    !zip -r fine_tuned_rec_model.zip output/best_accuracy/inference
    from google.colab import files
    files.download('fine_tuned_rec_model.zip')
    ```

## Part 6 — Local: swap it in and re-measure

13. **Unzip locally** into `ocr_feature/models/fine_tuned_rec/`:

    **macOS [verified]** (`unzip` is preinstalled):
    ```bash
    cd ocr_feature
    unzip fine_tuned_rec_model.zip -d models/fine_tuned_rec
    ```

    **Windows (PowerShell — `unzip` isn't built in, use
    `Expand-Archive`):**
    ```powershell
    cd ocr_feature
    Expand-Archive -Path fine_tuned_rec_model.zip -DestinationPath models\fine_tuned_rec
    ```
    (Right-click → "Extract All" in File Explorer works identically if you
    prefer the GUI.)

    Then in `core/ocr_pipeline.py`, **[verified]** `PaddleOCR()` accepts a
    `text_recognition_model_dir` kwarg that overrides the named model — this
    Python code is identical on every OS, only the path string's slash
    direction is a local convention (forward slashes work fine in Python
    strings on Windows too, so no change needed here):
    ```python
    ocr = PaddleOCR(
        text_detection_model_name="PP-OCRv6_medium_det",
        text_recognition_model_dir="models/fine_tuned_rec/inference",  # <- add this
        # text_recognition_model_name="PP-OCRv6_medium_rec",           # <- remove/comment this
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
    )
    ```
    This is a local experiment edit only — don't commit it as the default
    until a real (non-dry-run) fine-tune earns it.

14. **Re-measure, don't assume:**

    **macOS [verified]:**
    ```bash
    cd ocr_feature
    .venv/bin/python -m evaluators.evaluate_cer
    ```

    **Windows:**
    ```powershell
    cd ocr_feature
    .venv\Scripts\python -m evaluators.evaluate_cer
    ```

    Compare the new metrics against the current baselines: `clean_ws 0.149`
    CER, `0.656` WER (clean), `0.729` token accuracy (clean) — see
    `EVALUATION.md`. Given the volume caveat, report this as "the pipeline
    runs end-to-end," not as an accuracy result either direction — a 14-line
    val set moving any of these numbers up or down is not a meaningful signal
    at this scale.

**What this dry run is genuinely useful for:** it proves the entire chain
works (crop-conversion → Colab → PaddleX training → export → swap back in) —
real, citable engineering evidence that "the pipeline is ready to accept a
fine-tuned model," which is a legitimate claim even before real volume
exists. It is not evidence that fine-tuning improved accuracy — that claim
needs the 200–500+ line minimum tier and a real val set.
