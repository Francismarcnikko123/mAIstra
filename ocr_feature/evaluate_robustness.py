"""Measure OCR sensitivity to deterministic synthetic image stressors.

These results are diagnostics, not real-paper accuracy. The original labeled
images remain the only primary acceptance set.
"""

import csv
import tempfile
from pathlib import Path

import cv2

from evaluation import METRIC_KEYS, evaluate_text_pair, summarize_metrics
from ocr_pipeline import extract_text_from_image
from robustness import TRANSFORMS, apply_transform


SAMPLES_DIR = Path("samples")
LABELS_CSV = SAMPLES_DIR / "labels.csv"
BASELINE_VARIANT = "real_original"


def _average_metrics(rows: list[dict]) -> dict[str, float]:
    return {
        key: sum(row["metrics"][key] for row in rows) / len(rows)
        for key in METRIC_KEYS
    }


def _metric_row(label: str, metrics: dict[str, float], delta: float) -> str:
    return (
        f"{label[:24]:24s} {metrics['raw']:7.3f} {metrics['clean']:7.3f} "
        f"{metrics['raw_ws']:7.3f} {metrics['clean_ws']:9.3f} "
        f"{delta:+9.3f}"
    )


def _load_rows() -> list[dict]:
    if not LABELS_CSV.exists():
        return []
    with LABELS_CSV.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main() -> int:
    rows = _load_rows()
    if not rows:
        print(f"No labeled samples found at {LABELS_CSV}.")
        return 1

    print("SYNTHETIC ROBUSTNESS DIAGNOSTIC — not real-paper accuracy")
    print(f"Evaluating {len(rows)} labeled source image(s).")

    results: dict[str, list[dict]] = {
        variant: [] for variant in (BASELINE_VARIANT, *TRANSFORMS)
    }
    failures = []
    exact_matches = []

    with tempfile.TemporaryDirectory(prefix="maistra_ocr_robustness_") as tmp:
        temp_root = Path(tmp)
        transformed_dir = temp_root / "transformed"
        transformed_dir.mkdir()

        for sample_index, row in enumerate(rows):
            filename = (row.get("filename") or "").strip()
            reference = row.get("ground_truth_text") or ""
            source_path = SAMPLES_DIR / filename
            if not filename or not reference or not source_path.exists():
                failures.append(f"{filename or '(missing filename)'}: invalid pair")
                continue

            source = cv2.imread(str(source_path))
            if source is None:
                failures.append(f"{filename}: image unreadable")
                continue

            for variant in (BASELINE_VARIANT, *TRANSFORMS):
                input_path = source_path
                if variant != BASELINE_VARIANT:
                    transformed = apply_transform(
                        source,
                        variant,
                        seed=20260802 + sample_index,
                    )
                    input_path = transformed_dir / (
                        f"{source_path.stem}__{variant}.png"
                    )
                    if not cv2.imwrite(str(input_path), transformed):
                        failures.append(
                            f"{filename}/{variant}: transformed image write failed"
                        )
                        continue

                try:
                    extraction = extract_text_from_image(
                        str(input_path),
                        output_dir=str(temp_root / "outputs" / variant),
                    )
                except Exception as exc:
                    failures.append(
                        f"{filename}/{variant}: {type(exc).__name__}: {exc}"
                    )
                    continue

                raw = extraction["raw_text"]
                cleaned = extraction["cleaned_text"]
                if raw == reference or cleaned == reference:
                    exact_matches.append(f"{filename}/{variant}")
                results[variant].append({
                    **row,
                    "metrics": evaluate_text_pair(raw, cleaned, reference),
                })

    baseline_rows = results[BASELINE_VARIANT]
    if not baseline_rows:
        print("No valid real-paper baseline samples were evaluated.")
        for failure in failures:
            print(f"  {failure}")
        return 1

    baseline = _average_metrics(baseline_rows)
    print("\nOVERALL")
    print(f"{'variant':24s} {'raw':>7s} {'clean':>7s} {'raw_ws':>7s} "
          f"{'clean_ws':>9s} {'delta':>9s}")
    print("-" * 75)
    for variant in (BASELINE_VARIANT, *TRANSFORMS):
        variant_rows = results[variant]
        if not variant_rows:
            continue
        metrics = _average_metrics(variant_rows)
        print(_metric_row(
            variant,
            metrics,
            metrics["clean_ws"] - baseline["clean_ws"],
        ))

    print("\nBY PAPER TYPE (clean_ws)")
    paper_baseline = summarize_metrics(baseline_rows, "paper_type")
    print(f"{'variant':24s} {'paper':14s} {'clean_ws':>9s} {'delta':>9s}")
    print("-" * 60)
    for variant in (BASELINE_VARIANT, *TRANSFORMS):
        for paper, metrics in sorted(
            summarize_metrics(results[variant], "paper_type").items()
        ):
            baseline_value = paper_baseline.get(paper, {}).get("clean_ws")
            delta = (
                metrics["clean_ws"] - baseline_value
                if baseline_value is not None else 0.0
            )
            print(
                f"{variant[:24]:24s} {paper[:14]:14s} "
                f"{metrics['clean_ws']:9.3f} {delta:+9.3f}"
            )

    if exact_matches:
        print("\nWARNING: exact prediction/reference matches require "
              "ground-truth revalidation:")
        for match in exact_matches:
            print(f"  {match}")
    if failures:
        print("\nFAILED OR SKIPPED CASES")
        for failure in failures:
            print(f"  {failure}")

    print("\nSynthetic variants are diagnostics only and are not included in "
          "the real-paper baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
