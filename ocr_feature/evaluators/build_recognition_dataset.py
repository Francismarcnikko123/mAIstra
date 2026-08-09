"""Convert whole-page labeled samples into a PaddleX text-recognition
dataset: one cropped image per handwritten line, paired with its correct
text, in the train.txt/val.txt format PaddleX's recognition trainer expects
(tab-delimited "image_path<TAB>label", verified against
paddlex/modules/text_recognition/dataset_checker).

This is the missing conversion step FINE_TUNING_READINESS.md lists as
unwritten -- our labels are per-page (a whole C program), but the
recognizer trains on per-line crops.

HOW LINES ARE MATCHED: OCR detects and groups lines from the image; the
human ground truth is the page's text split on newlines. These two line
counts are compared -- if they don't match exactly, the page is SKIPPED and
reported, never guessed at. A silently-misaligned crop/label pair would
train the model on a wrong answer, which is worse than not using that page
at all. Re-run after fixing (re-transcribing, or accepting the skip) --
this script never modifies labels.csv or the sample images.

Run from the ocr_feature/ directory:

    .venv/bin/python -m evaluators.build_recognition_dataset

Output (datasets/recognition/):
    images/<source>_line<N>.jpg   one crop per matched line
    train.txt / val.txt           tab-delimited, ~90/10 split by line
"""
import csv
import random
import shutil
from pathlib import Path

import cv2

from core.ocr_pipeline import (
    ocr,
    _filter_low_confidence,
    _group_detection_records,
    line_member_bounds,
)
from core.preprocess import preprocess_image, DEFAULT_CONFIG

OUTPUT_DIR = Path("datasets/recognition")
IMAGES_DIR = OUTPUT_DIR / "images"
TRAIN_TXT = OUTPUT_DIR / "train.txt"
VAL_TXT = OUTPUT_DIR / "val.txt"

# Small margin around each detected line's box so a crop doesn't clip
# ascenders/descenders right at the edge.
CROP_PADDING = 4

VAL_FRACTION = 0.1
RANDOM_SEED = 0


def _detect_lines_with_boxes(preprocessed_path: str):
    """Run OCR on a preprocessed image and return grouped lines, each a
    (x_min, y_min, x_max, y_max, text) tuple -- the union box of every
    detection grouped into that line. Returns None if geometry was unsafe
    for any detection (grouping fell back to original order; box math
    would be invalid)."""
    results = ocr.predict(preprocessed_path)
    lines = []
    for page in results:
        result_data = page.json.get("res", {})
        rec_texts = result_data.get("rec_texts", [])
        rec_scores = result_data.get("rec_scores", [])
        rec_boxes = result_data.get("rec_boxes", [])
        rec_texts, rec_scores, rec_boxes, _dropped = _filter_low_confidence(
            rec_texts, rec_scores, rec_boxes
        )
        grouped, geometry_safe = _group_detection_records(
            rec_texts, rec_scores, rec_boxes
        )
        if not geometry_safe:
            return None
        for members in grouped:
            text = " ".join(
                member["text"].strip() for member in members
                if member["text"] and member["text"].strip()
            )
            if not text:
                continue
            x_min, y_min, x_max, y_max = line_member_bounds(members)
            lines.append((x_min, y_min, x_max, y_max, text))
    return lines


def _crop(image, x_min, y_min, x_max, y_max):
    height, width = image.shape[:2]
    x0 = max(0, int(x_min) - CROP_PADDING)
    y0 = max(0, int(y_min) - CROP_PADDING)
    x1 = min(width, int(x_max) + CROP_PADDING)
    y1 = min(height, int(y_max) + CROP_PADDING)
    return image[y0:y1, x0:x1]


def _load_rows():
    """Yield (source_name, image_path, ground_truth_text) from both label
    sets -- samples/ (test) and datasets/verified/ (train). Both are read
    only to build crops; nothing here changes which set a page belongs to."""
    samples_csv = Path("samples/labels.csv")
    if samples_csv.exists():
        for row in csv.DictReader(samples_csv.open(encoding="utf-8")):
            filename = row["filename"].strip()
            path = Path("samples") / filename
            if path.exists() and row.get("ground_truth_text"):
                # Use the extension-less stem so crop names match the
                # datasets/verified/ branch below (which already uses .stem);
                # otherwise samples/ crops embed the source extension, e.g.
                # "<name>.jpeg_line3.jpg".
                yield Path(filename).stem, path, row["ground_truth_text"]

    verified_csv = Path("datasets/verified/labels.csv")
    if verified_csv.exists():
        for row in csv.DictReader(verified_csv.open(encoding="utf-8")):
            image_path = row.get("image_path", "").strip()
            path = Path("datasets/verified") / image_path if image_path else None
            if path and path.exists() and row.get("verified_text"):
                name = Path(image_path).stem
                yield name, path, row["verified_text"]


def main() -> int:
    # Rebuild from scratch every run: the whole directory is derived output, so
    # clearing it first prevents crops from a prior run (a page whose line count
    # changed after a retake, or one dropped from the label set) lingering
    # unreferenced by the freshly written train.txt/val.txt.
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    entries = []  # (crop_path, label_text)
    skipped = []

    for source_name, image_path, ground_truth in _load_rows():
        gt_lines = [line for line in ground_truth.split("\n") if line.strip()]

        preprocessed_path = preprocess_image(
            image_path=str(image_path),
            output_dir="outputs",
            config=DEFAULT_CONFIG,
        )
        detected_lines = _detect_lines_with_boxes(preprocessed_path)

        if detected_lines is None:
            skipped.append((source_name, "unsafe detection geometry"))
            continue
        if len(detected_lines) != len(gt_lines):
            skipped.append((
                source_name,
                f"line count mismatch (OCR found {len(detected_lines)}, "
                f"ground truth has {len(gt_lines)})",
            ))
            continue

        image = cv2.imread(preprocessed_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            skipped.append((source_name, "could not reload preprocessed image"))
            continue

        for i, ((x_min, y_min, x_max, y_max, _ocr_text), gt_text) in enumerate(
            zip(detected_lines, gt_lines), start=1
        ):
            crop = _crop(image, x_min, y_min, x_max, y_max)
            if crop.size == 0:
                continue
            crop_name = f"{source_name}_line{i}.jpg"
            cv2.imwrite(str(IMAGES_DIR / crop_name), crop)
            entries.append((f"images/{crop_name}", gt_text.strip()))

    if not entries:
        print("No line pairs produced. See skipped pages below.")
    else:
        random.Random(RANDOM_SEED).shuffle(entries)
        split_at = max(1, int(len(entries) * (1 - VAL_FRACTION)))
        train_entries = entries[:split_at]
        val_entries = entries[split_at:]

        with TRAIN_TXT.open("w", encoding="utf-8") as f:
            for path, label in train_entries:
                f.write(f"{path}\t{label}\n")
        with VAL_TXT.open("w", encoding="utf-8") as f:
            for path, label in val_entries:
                f.write(f"{path}\t{label}\n")

        print(f"Wrote {len(train_entries)} train / {len(val_entries)} val "
              f"line pairs to {OUTPUT_DIR}/")

    if skipped:
        print(f"\nSkipped {len(skipped)} page(s) -- not auto-alignable:")
        for name, reason in skipped:
            print(f"  {name}: {reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
