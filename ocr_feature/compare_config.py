"""Compare the shipped preprocessing (grayscale + denoise) with black-and-white
thresholding on one photo: the OCR text, confidence and, if the photo is in
a labels.csv, the CER of each. Shows why thresholding is off.

    python compare_config.py                           # default photo
    python compare_config.py path/to/photo.jpg
    python compare_config.py path/to/photo.jpg --show  # also open both images in VS Code

--show needs VS Code's `code` command on PATH.
"""
import csv
import shutil
import subprocess
import sys
from pathlib import Path

from core.preprocess import PreprocessConfig
from core.ocr_pipeline import extract_text_from_image
from evaluators.evaluation import evaluate_text_pair
from evaluators.labels_schema import is_split_page

_SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE = str(_SCRIPT_DIR / "samples/greenbook/green_writer10_B2_1.jpg")

image_args = [a for a in sys.argv[1:] if not a.startswith("--")]
IMAGE = image_args[0] if image_args else IMAGE

VARIANTS = [
    ("grayscale + denoise (shipped default)", PreprocessConfig(), "grayscale_denoise"),
    ("adaptive binarization (threshold=True)", PreprocessConfig(threshold=True), "binarized"),
]

SHOW = "--show" in sys.argv


# Where the correct text is looked up by file name:
# (csv path, filename column, text column).
_LABEL_SOURCES = [
    ("samples/labels.csv", "filename", "ground_truth_text"),
    ("datasets/verified/labels.csv", "image_path", "verified_text"),
]


def _load_reference(image_path: str) -> tuple[str, str] | None:
    """(correct text, where it was found) for the photo, or None."""
    base = Path(image_path).name
    for csv_path, name_col, text_col in _LABEL_SOURCES:
        p = _SCRIPT_DIR / csv_path
        if not p.exists():
            continue
        with p.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if Path(row.get(name_col, "")).name == base:
                    # A page split into several programs stores them in tab
                    # order, not reading order: not a whole-page reference.
                    if is_split_page(row):
                        continue
                    text = row.get(text_col)
                    if text:
                        return text, f"{csv_path} ({name_col}={base})"
    return None


def main() -> None:
    loaded = _load_reference(IMAGE)
    reference = loaded[0] if loaded else None

    print(f"image: {IMAGE}")
    if loaded is not None:
        print(f"ground truth: {loaded[1]}")
    else:
        print("ground truth: none found (not in samples/labels.csv or "
              "datasets/verified/labels.csv, and no matching .txt beside the "
              "image) -- text and confidence only, no CER")
    print()

    results = []
    for label, config, tag in VARIANTS:
        result = extract_text_from_image(IMAGE, preprocess_config=config)
        metrics = None
        if reference is not None:
            metrics = evaluate_text_pair(
                result["raw_text"], result["cleaned_text"], reference
            )
        # Every run writes the same <name>_preprocessed.jpg, so keep a copy
        # per variant.
        preprocessed_src = Path(result["preprocessed_image"])
        preprocessed_copy = preprocessed_src.with_name(
            f"{Path(IMAGE).stem}_{tag}{preprocessed_src.suffix}"
        )
        shutil.copyfile(preprocessed_src, preprocessed_copy)
        results.append((label, result, metrics, preprocessed_copy))

    for label, result, metrics, preprocessed_copy in results:
        conf = result["average_confidence"]
        print("=" * 72)
        print(label)
        print("=" * 72)
        print(f"preprocessed image : {preprocessed_copy}")
        print(f"avg confidence     : {conf:.3f}" if conf is not None
              else "avg confidence     : n/a")
        if metrics is not None:
            print(f"CER (clean, ws)    : {metrics['clean_ws']:.3f}")
            print(f"CER (clean, strict): {metrics['clean']:.3f}")
        print("-" * 72)
        print(result["cleaned_text"])
        print()

    if len(results) == 2 and results[0][2] is not None:
        gray_metrics = results[0][2]
        bin_metrics = results[1][2]
        delta = bin_metrics["clean_ws"] - gray_metrics["clean_ws"]
        verdict = "worse" if delta > 0 else "better" if delta < 0 else "same"
        print("=" * 72)
        print(
            f"binarization CER is {abs(delta):.3f} {verdict} than "
            f"grayscale + denoise (clean, ws-normalized)"
        )
        print("=" * 72)

    if SHOW:
        if shutil.which("code") is None:
            print("--show requested but the `code` CLI isn't on PATH -- "
                  "see the module docstring for how to install it.")
        else:
            for _, _, _, preprocessed_copy in results:
                subprocess.run(["code", "-r", str(preprocessed_copy)])


if __name__ == "__main__":
    main()
