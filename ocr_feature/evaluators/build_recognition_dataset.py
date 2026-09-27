"""Build the training set for fine-tuning the recognizer.

Turns each verified page into one cropped image per handwritten line, paired
with its correct text, in PaddleX's train.txt / val.txt format
("image_path<TAB>label").

- Only datasets/verified/ is used. samples/ is the test set and never
  becomes training data.
- OCR lines and the verified lines are paired 1:1 when their counts match.
  Otherwise they are aligned by text similarity, and a page is used only if
  at least MIN_PAGE_COVERAGE of its lines match.
- A landscape photo of two pages is split at the fold and read left page
  first.
- Train and val are split by page, so no page is in both.

Run from ocr_feature/:
    .venv/bin/python -m evaluators.build_recognition_dataset

Output in datasets/recognition/: images/<page>_line<N>.jpg, train.txt and
val.txt (about 90/10).
"""
import csv
import difflib
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
from evaluators.labels_schema import program_blocks

OUTPUT_DIR = Path("datasets/recognition")
IMAGES_DIR = OUTPUT_DIR / "images"
TRAIN_TXT = OUTPUT_DIR / "train.txt"
VAL_TXT = OUTPUT_DIR / "val.txt"

# Pixels added around each line box, so letters at the edge aren't cut off.
CROP_PADDING = 4

# About 10% of lines go to validation. Whole pages are assigned, so the
# share is approximate.
VAL_FRACTION = 0.1
RANDOM_SEED = 0

# A matched pair must be at least this similar to be used.
MIN_LINE_SIMILARITY = 0.35

# A page is used only if at least 65% of its lines find a match. (0.8
# excluded pages whose matched lines were fine.)
MIN_PAGE_COVERAGE = 0.65

# Small cost for leaving a line unmatched, so similar lines get matched but
# a bad match is never forced.
_SKIP_PENALTY = 0.05


# OCR usually misreads a lone brace as a short token such as "3", so a brace
# line counts as matching any detected text of 1-2 characters.
_BRACE_CHARS = {"{", "}"}
_BRACE_MISREAD_MAX_LEN = 2


def _line_similarity(a: str, b: str) -> float:
    """Text similarity of two lines, from 0 to 1 (with the brace rule above)."""
    a_stripped, b_stripped = a.strip(), b.strip()
    if a_stripped in _BRACE_CHARS and len(b_stripped) <= _BRACE_MISREAD_MAX_LEN:
        return 1.0
    if b_stripped in _BRACE_CHARS and len(a_stripped) <= _BRACE_MISREAD_MAX_LEN:
        return 1.0
    return difflib.SequenceMatcher(None, a_stripped.lower(), b_stripped.lower()).ratio()


def _align_lines(gt_lines, detected_lines):
    """Match verified lines to detected lines in order (both top to bottom).
    Returns (verified_index, detected_index) pairs that are similar enough.
    Lines without a good match are left out, never forced."""
    n, m = len(gt_lines), len(detected_lines)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] - _SKIP_PENALTY
        back[i][0] = "skip_gt"
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] - _SKIP_PENALTY
        back[0][j] = "skip_det"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + _line_similarity(gt_lines[i - 1], detected_lines[j - 1][4])
            up = dp[i - 1][j] - _SKIP_PENALTY
            left = dp[i][j - 1] - _SKIP_PENALTY
            best = max(diag, up, left)
            dp[i][j] = best
            back[i][j] = "match" if best == diag else ("skip_gt" if best == up else "skip_det")

    pairs = []
    i, j = n, m
    while i > 0 or j > 0:
        move = back[i][j]
        if move == "match":
            if _line_similarity(gt_lines[i - 1], detected_lines[j - 1][4]) >= MIN_LINE_SIMILARITY:
                pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif move == "skip_gt":
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def _pair_lines(gt_blocks, detected_lines):
    """Pair a page's verified lines with its detected lines.

    `gt_blocks` is the page's text, or one text per program if the teacher
    split the page. Returns ([(verified_line, detected_index), ...], None),
    or (None, reason) if too few lines match.

    For a split page, each program is aligned against all detected lines,
    because the tab order says nothing about where a program sits on the
    page. A detected line matched by two programs is dropped.
    """
    blocks = [[line for line in text.split("\n") if line.strip()] for text in gt_blocks]
    total_gt = sum(len(lines) for lines in blocks)

    if len(blocks) == 1:
        gt_lines = blocks[0]
        if len(detected_lines) == len(gt_lines):
            # Same number of lines: pair by position. A similarity check
            # here would reject correct pairs whose OCR text is noisy.
            return [(gt_lines[i], i) for i in range(len(gt_lines))], None
        index_pairs = _align_lines(gt_lines, detected_lines)
        coverage = len(index_pairs) / len(gt_lines) if gt_lines else 0.0
        if coverage < MIN_PAGE_COVERAGE:
            return None, (
                f"line count mismatch (OCR found {len(detected_lines)}, "
                f"ground truth has {len(gt_lines)}); alignment matched only "
                f"{len(index_pairs)}/{len(gt_lines)} lines"
            )
        return [(gt_lines[g], d) for g, d in index_pairs], None

    claims = {}  # detected_index -> [gt_text, ...] from every block that matched it
    for gt_lines in blocks:
        for g, d in _align_lines(gt_lines, detected_lines):
            claims.setdefault(d, []).append(gt_lines[g])
    pairs = [(texts[0], d) for d, texts in sorted(claims.items()) if len(texts) == 1]
    coverage = len(pairs) / total_gt if total_gt else 0.0
    if coverage < MIN_PAGE_COVERAGE:
        return None, (
            f"split page ({len(blocks)} programs): alignment matched only "
            f"{len(pairs)}/{total_gt} lines (OCR found {len(detected_lines)})"
        )
    return pairs, None


def _detect_lines_with_boxes(preprocessed_path: str):
    """Run OCR on a preprocessed image. Returns its lines as
    (x_min, y_min, x_max, y_max, text), or None if any box is invalid."""
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


# A photo wider than 1.15 x its height shows two pages.
LANDSCAPE_ASPECT_THRESHOLD = 1.15

# Temporary half-page images.
LANDSCAPE_SPLIT_DIR = Path("outputs") / "landscape_splits"


def _find_gutter_x(gray_image) -> int:
    """The x position of the darkest vertical strip between 35% and 65% of
    the width: the fold between the two pages. The center if the image is
    too narrow."""
    height, width = gray_image.shape[:2]
    lo, hi = int(width * 0.35), int(width * 0.65)
    if hi <= lo:
        return width // 2
    col_means = gray_image[:, lo:hi].mean(axis=0)
    return lo + int(col_means.argmin())


def _split_landscape_page(image_path: str) -> list[str]:
    """If the photo shows two pages, save its left and right halves and
    return their paths, left first. Otherwise return [image_path]."""
    image = cv2.imread(image_path)
    if image is None:
        return [image_path]
    height, width = image.shape[:2]
    if height == 0 or width / height < LANDSCAPE_ASPECT_THRESHOLD:
        return [image_path]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gutter_x = _find_gutter_x(gray)

    LANDSCAPE_SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(image_path).stem
    left_path = LANDSCAPE_SPLIT_DIR / f"{stem}_left.jpg"
    right_path = LANDSCAPE_SPLIT_DIR / f"{stem}_right.jpg"
    cv2.imwrite(str(left_path), image[:, :gutter_x])
    cv2.imwrite(str(right_path), image[:, gutter_x:])
    return [str(left_path), str(right_path)]


def _crop(image, x_min, y_min, x_max, y_max):
    """Cut out one line, with CROP_PADDING pixels around it."""
    height, width = image.shape[:2]
    x0 = max(0, int(x_min) - CROP_PADDING)
    y0 = max(0, int(y_min) - CROP_PADDING)
    x1 = min(width, int(x_max) + CROP_PADDING)
    y1 = min(height, int(y_max) + CROP_PADDING)
    return image[y0:y1, x0:x1]


def _load_rows():
    """Yield (name, image_path, text_blocks) for each page in
    datasets/verified/. samples/, the test set, is never read. text_blocks is
    [verified_text], or one text per program if the teacher split the page."""
    verified_csv = Path("datasets/verified/labels.csv")
    if verified_csv.exists():
        for row in csv.DictReader(verified_csv.open(encoding="utf-8")):
            image_path = row.get("image_path", "").strip()
            path = Path("datasets/verified") / image_path if image_path else None
            if path and path.exists() and row.get("verified_text"):
                name = Path(image_path).stem
                yield name, path, program_blocks(row) or [row["verified_text"]]


def main() -> int:
    # Start from an empty folder, so no crops from an earlier run are left.
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Crops grouped by page, so each page stays on one side of the split.
    pages = {}  # source_name -> [(crop_path, label_text), ...]
    skipped = []

    for source_name, image_path, ground_truth_blocks in _load_rows():

        # One part, or two for a photo of two pages (left page first).
        part_paths = _split_landscape_page(str(image_path))

        detected_lines = []
        line_images = []  # parallel to detected_lines: which array to crop from
        detection_failed = False
        for part_path in part_paths:
            preprocessed_path = preprocess_image(
                image_path=part_path,
                output_dir="outputs",
                config=DEFAULT_CONFIG,
            )
            part_lines = _detect_lines_with_boxes(preprocessed_path)
            if part_lines is None:
                detection_failed = True
                break
            part_image = cv2.imread(preprocessed_path, cv2.IMREAD_GRAYSCALE)
            if part_image is None:
                detection_failed = True
                break
            detected_lines.extend(part_lines)
            line_images.extend([part_image] * len(part_lines))

        if detection_failed:
            skipped.append((source_name, "unsafe detection geometry or unreadable preprocessed image"))
            continue

        pairs, reason = _pair_lines(ground_truth_blocks, detected_lines)
        if pairs is None:
            skipped.append((source_name, reason))
            continue

        for i, (gt_text, det_index) in enumerate(pairs, start=1):
            x_min, y_min, x_max, y_max, _ocr_text = detected_lines[det_index]
            crop = _crop(line_images[det_index], x_min, y_min, x_max, y_max)
            if crop.size == 0:
                continue
            crop_name = f"{source_name}_line{i}.jpg"
            cv2.imwrite(str(IMAGES_DIR / crop_name), crop)
            pages.setdefault(source_name, []).append(
                (f"images/{crop_name}", gt_text.strip())
            )

    if not pages:
        print("No line pairs produced. See skipped pages below.")
    else:
        # Split by page, not by line: lines of one page share handwriting and
        # lighting, so splitting a page would make validation look better
        # than it is. At least one page always stays in train.
        page_names = list(pages.keys())
        random.Random(RANDOM_SEED).shuffle(page_names)
        total_lines = sum(len(pages[name]) for name in page_names)
        target_val = total_lines * VAL_FRACTION

        val_names = set()
        val_lines = 0
        for name in page_names:
            if val_lines >= target_val:
                break
            if len(val_names) >= len(page_names) - 1:
                break  # never leave train empty
            val_names.add(name)
            val_lines += len(pages[name])

        train_entries = []
        val_entries = []
        for name in page_names:
            bucket = val_entries if name in val_names else train_entries
            bucket.extend(pages[name])

        with TRAIN_TXT.open("w", encoding="utf-8") as f:
            for path, label in train_entries:
                f.write(f"{path}\t{label}\n")
        with VAL_TXT.open("w", encoding="utf-8") as f:
            for path, label in val_entries:
                f.write(f"{path}\t{label}\n")

        print(f"Wrote {len(train_entries)} train / {len(val_entries)} val "
              f"line pairs from {len(page_names)} page(s), "
              f"{len(val_names)} held out for val, to {OUTPUT_DIR}/")
        if not val_entries:
            print("  WARNING: only one page available -- no page-isolated val "
                  "set is possible; all lines went to train.")

    if skipped:
        print(f"\nSkipped {len(skipped)} page(s) -- not auto-alignable:")
        for name, reason in skipped:
            print(f"  {name}: {reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
