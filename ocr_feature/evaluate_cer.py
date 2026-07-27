"""
Character Error Rate (CER) evaluation for the OCR pipeline.

CER is the standard OCR accuracy metric: the edit distance (insertions +
deletions + substitutions) between the OCR output and the correct text,
divided by the length of the correct text. Lower is better; 0.0 = perfect,
1.0 = as many errors as there are characters.

This is a developer/research tool, not part of the live backend. Run it
whenever you want a fresh accuracy number -- e.g. a baseline before
fine-tuning, then again after, to measure the improvement.

Usage (from the ocr_feature/ directory, with the venv active):
    python evaluate_cer.py

It reads samples/labels.csv (filename,ground_truth_text), runs every image
through the real pipeline, and reports:
  - CER of raw_text     (before the keyword cleanup layer)
  - CER of cleaned_text  (what the teacher actually sees)
both strict and whitespace-normalized (whitespace differences aren't
recognition errors -- the teacher reformats anyway).
"""
import csv
from pathlib import Path

from ocr_pipeline import extract_text_from_image

SAMPLES_DIR = Path("samples")
LABELS_CSV = SAMPLES_DIR / "labels.csv"


def edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings (pure Python)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(
                prev[j] + 1,       # deletion
                curr[j - 1] + 1,   # insertion
                prev[j - 1] + cost # substitution
            ))
        prev = curr
    return prev[-1]


def cer(prediction: str, reference: str) -> float:
    """Character Error Rate = edit_distance / len(reference)."""
    if not reference:
        return 0.0 if not prediction else 1.0
    return edit_distance(prediction, reference) / len(reference)


def normalize_ws(text: str) -> str:
    """Collapse all whitespace runs to a single space and strip. Lets us
    measure recognition errors without penalizing formatting differences."""
    return " ".join(text.split())


def main() -> None:
    if not LABELS_CSV.exists():
        print(f"No labels file at {LABELS_CSV}. Add samples + labels first.")
        return

    with LABELS_CSV.open(newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("labels.csv has no rows yet.")
        return

    print(f"Evaluating {len(rows)} sample(s)...\n")
    print(f"{'file':26s} {'raw':>7s} {'clean':>7s} {'raw_ws':>7s} {'clean_ws':>9s}")
    print("-" * 62)

    totals = {"raw": [], "clean": [], "raw_ws": [], "clean_ws": []}

    for row in rows:
        fname = row["filename"].strip()
        truth = row["ground_truth_text"]
        img_path = SAMPLES_DIR / fname
        if not img_path.exists():
            print(f"{fname[:26]:26s}  (image file not found -- skipped)")
            continue

        result = extract_text_from_image(str(img_path))
        raw = result["raw_text"]
        clean = result["cleaned_text"]

        r_cer = cer(raw, truth)
        c_cer = cer(clean, truth)
        r_ws = cer(normalize_ws(raw), normalize_ws(truth))
        c_ws = cer(normalize_ws(clean), normalize_ws(truth))

        totals["raw"].append(r_cer)
        totals["clean"].append(c_cer)
        totals["raw_ws"].append(r_ws)
        totals["clean_ws"].append(c_ws)

        print(f"{fname[:26]:26s} {r_cer:7.3f} {c_cer:7.3f} {r_ws:7.3f} {c_ws:9.3f}")

    if not totals["raw"]:
        print("\nNo images were evaluated.")
        return

    def avg(key):
        return sum(totals[key]) / len(totals[key])

    print("-" * 62)
    print(f"{'AVERAGE CER':26s} {avg('raw'):7.3f} {avg('clean'):7.3f} "
          f"{avg('raw_ws'):7.3f} {avg('clean_ws'):9.3f}")
    print("\nLower is better. Columns:")
    print("  raw       = raw OCR output vs ground truth (strict)")
    print("  clean     = after keyword cleanup vs ground truth (strict)")
    print("  raw_ws    = raw, whitespace-normalized (recognition errors only)")
    print("  clean_ws  = cleaned, whitespace-normalized")


if __name__ == "__main__":
    main()
