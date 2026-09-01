"""Build the WRITER-DISJOINT (cross-writer) measurement dataset.

Purpose: measure how the fine-tune generalizes to writers it has NEVER seen.
We hold out a few greenbook writers ENTIRELY (all their pages), retrain on the
rest, and evaluate the retrained model on those held-out writers' pages.

This is a MEASUREMENT experiment, separate from the shipped model. The shipped
model (models/fine_tuned_rec/) trains on ALL writers; this excludes 4 of them
purely to get an honest new-writer number. See docs/ocr/EVALUATION.md.

Why greenbook writers 7/8/20/27: they are training-only (not in samples/), so
excluding them leaves the held-out samples/ test set (and its 0.126 result)
untouched, and greenbook has enough writers (~39) that removing 4 barely dents
training. Bond/yellow have too few writers to hold out this way.

Writer identity here uses number + batch (green_writerN_B<batch>): numbering
resets per batch, so batch is part of the identity -- see
docs/ocr/EVALUATION.md and the test-set-writer-overlap memory. These 4 holdouts
have no batch collisions with any kept writer.

Run from the ocr_feature/ directory:

    .venv/bin/python -m evaluators.build_crosswriter_dataset

Outputs:
    <home>/Downloads/recognition_dataset_crosswriter.zip   upload to Colab, retrain
    evaluators/crosswriter_test_manifest.json              the 15 held-out test pages
"""
import csv
import json
import re
import shutil
from pathlib import Path

# 4 greenbook writers held out ENTIRELY from training (number+batch identity).
HOLDOUT_WRITERS = {"green_writer7", "green_writer8", "green_writer20", "green_writer27"}

RECOGNITION_DIR = Path("datasets/recognition")
VERIFIED_LABELS = Path("datasets/verified/labels.csv")
VERIFIED_ROOT = Path("datasets/verified")
MANIFEST_OUT = Path("evaluators/crosswriter_test_manifest.json")
ZIP_OUT = Path.home() / "Downloads" / "recognition_dataset_crosswriter"


def _writer_of_crop(line: str) -> str | None:
    # crop line: images/green_writer19_B2_1_line3.jpg\t<text>
    m = re.match(r"(green_writer\d+)", line.split("/")[-1])
    return m.group(1) if m else None


def _writer_of_page(image_path: str) -> str | None:
    m = re.search(r"(green_writer\d+)", image_path)
    return m.group(1) if m else None


def build_training_zip(stage: Path) -> tuple[int, int]:
    """Write filtered train/val (holdout writers removed) + their crops under
    stage/datasets/recognition/, then zip so unzip -d /content/ nests as the
    notebook expects. Returns (train_kept, val_kept)."""
    target = stage / "datasets" / "recognition"
    (target / "images").mkdir(parents=True, exist_ok=True)

    kept_counts = {}
    referenced = set()
    for split in ("train.txt", "val.txt"):
        lines = (RECOGNITION_DIR / split).read_text().splitlines()
        keep = [l for l in lines if _writer_of_crop(l) not in HOLDOUT_WRITERS]
        (target / split).write_text("\n".join(keep) + "\n")
        kept_counts[split] = len(keep)
        for l in keep:
            referenced.add(l.split("\t")[0])  # images/xxx.jpg
        print(f"{split}: {len(lines)} -> {len(keep)} crops "
              f"(removed {len(lines) - len(keep)})")

    for img in referenced:
        src = RECOGNITION_DIR / img
        if src.exists():
            shutil.copy(src, target / img)

    if ZIP_OUT.with_suffix(".zip").exists():
        ZIP_OUT.with_suffix(".zip").unlink()
    shutil.make_archive(str(ZIP_OUT), "zip", str(stage))
    print(f"wrote {ZIP_OUT.with_suffix('.zip')}")
    return kept_counts["train.txt"], kept_counts["val.txt"]


def build_test_manifest() -> int:
    """Build the held-out test manifest (the 4 writers' full pages + ground
    truth) from the verified labels. Returns page count."""
    rows = []
    for row in csv.DictReader(VERIFIED_LABELS.open(encoding="utf-8")):
        ip = row["image_path"]
        w = _writer_of_page(ip)
        if w in HOLDOUT_WRITERS:
            rows.append({
                "filename": Path(ip).name,
                "writer": w,
                "image_path": str(VERIFIED_ROOT / ip),
                "ground_truth_text": row["verified_text"],
            })
    MANIFEST_OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"wrote {MANIFEST_OUT} ({len(rows)} test pages)")
    return len(rows)


def main() -> int:
    stage = Path("outputs") / "crosswriter_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    train_kept, val_kept = build_training_zip(stage)
    n_pages = build_test_manifest()
    shutil.rmtree(stage, ignore_errors=True)
    print(f"\nholdout writers: {sorted(HOLDOUT_WRITERS)}")
    print(f"cross-writer training: {train_kept} train / {val_kept} val crops")
    print(f"cross-writer test: {n_pages} held-out pages")
    print("Next: upload the zip to Colab, retrain, then run evaluators.crosswriter_eval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
