"""Convert whole-page labeled samples into a PaddleX text-recognition
dataset: one cropped image per handwritten line, paired with its correct
text, in the train.txt/val.txt format PaddleX's recognition trainer expects
(tab-delimited "image_path<TAB>label", verified against
paddlex/modules/text_recognition/dataset_checker).

This is the missing conversion step FINE_TUNING_READINESS.md lists as
unwritten -- our labels are per-page (a whole C program), but the
recognizer trains on per-line crops.

TEST-SET ISOLATION: only datasets/verified/labels.csv feeds train.txt/
val.txt. samples/labels.csv is deliberately EXCLUDED here -- it is the
held-out set evaluate_cer.py measures the baseline (and, later, the
fine-tuned model) against, per FINE_TUNING_READINESS.md's stated design
("test set...never touched in training"). Earlier versions of this script
pooled both label sources into the same train/val split, which would have
let most of samples/ end up in train.txt -- any CER re-measured against
samples/ after fine-tuning would then be scoring the model on data it just
trained on, invalidating the before/after comparison. Found and fixed
2026-08-25, before real training volume existed, specifically so this
never happens on a real run. If samples/ ever needs to grow into training
data, it must first be copied into datasets/verified/-style storage under
a policy that retires it from being used as the test set -- never done
silently by this script.

HOW LINES ARE MATCHED: OCR detects and groups lines from the image (already
in top-to-bottom order -- see _group_detection_records's vertical sweep);
the human ground truth is the page's text split on newlines. When the two
line counts match exactly, lines are paired 1:1 in order. When they don't
(most commonly because a lone brace line's low-confidence detection got
filtered out before grouping, per docs/ocr/ocr-error-profile-braces), a
monotonic sequence alignment (_align_lines) matches each ground-truth line
to its most similar nearby detected line, allowing either side to have
unmatched entries -- an unmatched ground-truth line just contributes no
crop; the page still contributes every line that *did* align confidently.
A page is only skipped outright if fewer than MIN_PAGE_COVERAGE of its
ground-truth lines find a confident match -- past that point there isn't
enough of the page left to trust the alignment. This never guesses at a
pairing: every pair used still has to clear MIN_LINE_SIMILARITY. Re-run
after fixing (re-transcribing, or accepting the skip) -- this script never
modifies labels.csv or the sample images.

LANDSCAPE (TWO-PAGE SPREAD) PHOTOS: a page photographed as a landscape
two-page spread is split into independent left/right halves at the darkest
vertical band near the center (_find_gutter_x -- the notebook's shadowed
crease), each half OCR'd separately, and their detected lines concatenated
left-then-right (_split_landscape_page). This matters for two reasons: (1)
the right-hand page of a spread gets meaningfully less effective resolution
and often uneven lighting near the spine, which can silently zero out
detection there if processed as part of one wide frame; (2) a single sweep
across the full wide frame sorts purely by vertical position and would
interleave left- and right-page lines that happen to sit at similar
heights, whereas the ground-truth text always reads the whole left page
before the whole right page. A page whose photo happens to be landscape but
has no real content on the second half (e.g. a spread with blank facing
page) still passes through unaffected -- splitting it just means OCR-ing an
empty half, which contributes nothing and costs nothing.

Run from the ocr_feature/ directory:

    .venv/bin/python -m evaluators.build_recognition_dataset

Output (datasets/recognition/):
    images/<source>_line<N>.jpg   one crop per matched line
    train.txt / val.txt           tab-delimited, ~90/10 split by PAGE
                                  (all of one page's lines go to one side)
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

OUTPUT_DIR = Path("datasets/recognition")
IMAGES_DIR = OUTPUT_DIR / "images"
TRAIN_TXT = OUTPUT_DIR / "train.txt"
VAL_TXT = OUTPUT_DIR / "val.txt"

# Small margin around each detected line's box so a crop doesn't clip
# ascenders/descenders right at the edge.
CROP_PADDING = 4

# Target share of total LINES held out for validation. The split assigns
# whole pages (see main()), so the realized val share lands near this rather
# than exactly on it -- a page is never split across train and val.
VAL_FRACTION = 0.1
RANDOM_SEED = 0

# Below this per-line text similarity, a diagonal (matched) step in the
# alignment isn't trusted even if the DP picked it -- the two lines just
# don't look alike enough to be the same content.
MIN_LINE_SIMILARITY = 0.35

# A page needs at least this fraction of its ground-truth lines to find a
# confident match before it's used at all. Below this, too little of the
# page survived alignment to trust it. Lowered from 0.8 to 0.65 after
# inspecting the pages it was excluding: lines that DO align at 68-76%
# coverage still clear MIN_LINE_SIMILARITY on real text overlap (verified
# against green_writer4_B2_2, green_writer5_B1_2, green_writer6_B3_2's raw
# OCR output) -- they were just a larger-than-usual minority of scattered
# garbled/dropped lines away from the old 80% bar, not unreliable pages.
# This only changes how much of a page must survive to be used at all; the
# per-line similarity gate below is untouched, so no pair used here is any
# less trustworthy than before.
MIN_PAGE_COVERAGE = 0.65

# Small cost for skipping a line on either side, so the DP prefers matching
# similar lines over skipping them, but still skips rather than force a
# bad match when nothing lines up.
_SKIP_PENALTY = 0.05


# Handwritten braces are almost never transcribed correctly (see
# docs/ocr/ocr-error-profile-braces) -- not dropped, but misread as an
# unrelated short token, most often the digit "3" (the stroke resembles a
# cursive 3). A lone-brace ground-truth line therefore never scores well
# against its true match under plain text similarity, even when they're in
# the right position. Confirmed against bond_writer4_1's raw OCR output,
# where four consecutive "}" ground-truth lines came back as "3", "3", "3",
# then the next real line -- one brace silently dropped, the other three
# misread, all four scoring 0 similarity despite being correctly placed.
_BRACE_CHARS = {"{", "}"}
_BRACE_MISREAD_MAX_LEN = 2


def _line_similarity(a: str, b: str) -> float:
    a_stripped, b_stripped = a.strip(), b.strip()
    if a_stripped in _BRACE_CHARS and len(b_stripped) <= _BRACE_MISREAD_MAX_LEN:
        return 1.0
    if b_stripped in _BRACE_CHARS and len(a_stripped) <= _BRACE_MISREAD_MAX_LEN:
        return 1.0
    return difflib.SequenceMatcher(None, a_stripped.lower(), b_stripped.lower()).ratio()


def _align_lines(gt_lines, detected_lines):
    """Monotonic alignment between a page's ground-truth lines and its
    OCR-detected lines (both already top-to-bottom). Returns a list of
    (gt_index, detected_index) pairs confident enough to use as a
    crop/label pair -- a line unmatched on either side (a genuinely dropped
    detection, or a spurious extra one) is simply absent from the result,
    never force-paired with something that doesn't match."""
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


# width/height above this is treated as a two-page spread rather than a
# single portrait page (every genuine single-page capture in this dataset
# is portrait; a spread is comfortably wider than tall).
LANDSCAPE_ASPECT_THRESHOLD = 1.15

# Directory for the temporary left/right half images a landscape split
# produces -- these are intermediate files, not part of the derived output
# tracked in OUTPUT_DIR.
LANDSCAPE_SPLIT_DIR = Path("outputs") / "landscape_splits"


def _find_gutter_x(gray_image) -> int:
    """Return the x-coordinate of the darkest vertical band within the
    middle third of a landscape page image -- the shadowed crease between
    two pages -- so a spread can be split without cutting into either
    page's content. Falls back to the exact midpoint if the image is too
    narrow for a middle-third search to make sense."""
    height, width = gray_image.shape[:2]
    lo, hi = int(width * 0.35), int(width * 0.65)
    if hi <= lo:
        return width // 2
    col_means = gray_image[:, lo:hi].mean(axis=0)
    return lo + int(col_means.argmin())


def _split_landscape_page(image_path: str) -> list[str]:
    """If image_path looks like a two-page spread, split it into left/right
    half images at the notebook's crease and return both paths in
    left-to-right reading order. Otherwise return [image_path] unchanged,
    so a normal single-page photo takes exactly the prior code path."""
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
    height, width = image.shape[:2]
    x0 = max(0, int(x_min) - CROP_PADDING)
    y0 = max(0, int(y_min) - CROP_PADDING)
    x1 = min(width, int(x_max) + CROP_PADDING)
    y1 = min(height, int(y_max) + CROP_PADDING)
    return image[y0:y1, x0:x1]


def _load_rows():
    """Yield (source_name, image_path, ground_truth_text) from
    datasets/verified/ only -- the training-data source. samples/ is
    deliberately NOT read here; it is the held-out test set and must never
    contribute a crop to train.txt or val.txt (see the module docstring's
    TEST-SET ISOLATION note)."""
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

    # Grouped by source page so the train/val split can keep every crop from
    # one page on the same side (see the split logic below).
    pages = {}  # source_name -> [(crop_path, label_text), ...]
    skipped = []

    for source_name, image_path, ground_truth in _load_rows():
        gt_lines = [line for line in ground_truth.split("\n") if line.strip()]

        # Normally one part (the page itself); a landscape two-page spread
        # yields two independent parts (left half, right half) processed
        # separately and concatenated in reading order -- see the module
        # docstring's LANDSCAPE section.
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

        if len(detected_lines) == len(gt_lines):
            # Counts already agree -- trust positional 1:1 pairing directly,
            # same as before _align_lines existed. Running the similarity
            # gate here too would second-guess correct pairs on pages where
            # OCR's text is just noisy despite being in the right place.
            pairs = list(enumerate(range(len(gt_lines))))
        else:
            pairs = _align_lines(gt_lines, detected_lines)
            coverage = len(pairs) / len(gt_lines) if gt_lines else 0.0
            if coverage < MIN_PAGE_COVERAGE:
                skipped.append((
                    source_name,
                    f"line count mismatch (OCR found {len(detected_lines)}, "
                    f"ground truth has {len(gt_lines)}); alignment matched only "
                    f"{len(pairs)}/{len(gt_lines)} lines",
                ))
                continue

        for i, (gt_index, det_index) in enumerate(pairs, start=1):
            x_min, y_min, x_max, y_max, _ocr_text = detected_lines[det_index]
            gt_text = gt_lines[gt_index]
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
        # Split by PAGE, not by line. Shuffling individual lines would scatter
        # lines from the same page across train and val -- and lines from one
        # page share handwriting, paper texture, lighting, and reused tokens
        # (printf, variable names), so the model would effectively see the val
        # page during training and report an inflated val accuracy. Instead,
        # whole pages are assigned to val until val reaches ~VAL_FRACTION of all
        # lines, always leaving at least one page for training.
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
