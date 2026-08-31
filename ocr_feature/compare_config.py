"""
Terminal comparison: run one image through the production preprocessing
(grayscale + denoise) and through adaptive binarization, side by side, with
each stage's OCR output and confidence. Built to demonstrate -- not just
claim -- why the pipeline ships with threshold=False (see
core/preprocess.py's PreprocessConfig.threshold and docs/ocr/DEFENSE_PREP.md
section 14).

Not part of the pipeline and not imported by anything.

    python compare_config.py                          # default IMAGE
    python compare_config.py path/to/photo.jpg         # any image
    python compare_config.py path/to/photo.jpg --show  # also open both
                                                         # preprocessed images
                                                         # as VS Code tabs

If path/to/photo.txt exists next to the image (same basename), its contents
are used as ground truth and CER is printed for both variants. Otherwise the
comparison runs without CER -- text and confidence only.

--show requires the `code` CLI on PATH (VS Code: Cmd+Shift+P ->
"Shell Command: Install 'code' command in PATH"). It opens each image as a
tab in the current window (-r); VS Code doesn't auto-split editor groups from
the CLI, so drag one tab to the side once for a side-by-side view -- it stays
split for the rest of the session.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from core.preprocess import PreprocessConfig
from core.ocr_pipeline import extract_text_from_image
from evaluators.evaluation import evaluate_text_pair

IMAGE = "samples/nombrado_s06_struct_green_gate.jpeg"

image_args = [a for a in sys.argv[1:] if not a.startswith("--")]
IMAGE = image_args[0] if image_args else IMAGE

VARIANTS = [
    ("grayscale + denoise (shipped default)", PreprocessConfig(), "grayscale_denoise"),
    ("adaptive binarization (threshold=True)", PreprocessConfig(threshold=True), "binarized"),
]

SHOW = "--show" in sys.argv


def _load_reference(image_path: str) -> str | None:
    txt_path = Path(image_path).with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text()
    return None


def main() -> None:
    reference = _load_reference(IMAGE)

    print(f"image: {IMAGE}")
    if reference is not None:
        print(f"ground truth: {Path(IMAGE).with_suffix('.txt')}")
    else:
        print("ground truth: none found (place a matching .txt next to the "
              "image to also print CER)")
    print()

    results = []
    for label, config, tag in VARIANTS:
        result = extract_text_from_image(IMAGE, preprocess_config=config)
        metrics = None
        if reference is not None:
            metrics = evaluate_text_pair(
                result["raw_text"], result["cleaned_text"], reference
            )
        # extract_text_from_image() always writes to the same
        # "<stem>_preprocessed.jpg" path regardless of config, so each
        # variant would overwrite the last one's output. Copy it to a
        # variant-tagged name immediately so both survive to the end.
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
