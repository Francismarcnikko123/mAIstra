"""
Character Error Rate (CER) against samples/labels.csv -- edit distance
between OCR output and the correct text, divided by the correct text's
length. Lower is better, 0 = perfect.

Dev tool, not used by the live backend. Run it after any pipeline change,
and before/after fine-tuning to measure the actual difference:

    python evaluate_cer.py

Reports raw vs. cleaned text, each strict and whitespace-normalized (the
latter isolates recognition errors from formatting, since the teacher
reformats anyway).
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
