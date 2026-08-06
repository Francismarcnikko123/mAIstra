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

from evaluators.evaluation import (
    METRIC_KEYS,
    evaluate_text_pair,
    literal_provenance_issues,
    suggestion_improves_reference,
    summarize_metrics,
)

SAMPLES_DIR = Path("samples")
LABELS_CSV = SAMPLES_DIR / "labels.csv"


def _load_extractor():
    """Import the model-owning OCR pipeline only after label preflight."""
    from core.ocr_pipeline import extract_text_from_image

    return extract_text_from_image


def _format_metric_row(label: str, metrics: dict[str, float]) -> str:
    return (
        f"{label[:26]:26s} "
        f"{metrics['raw']:7.3f} {metrics['clean']:7.3f} "
        f"{metrics['raw_ws']:7.3f} {metrics['clean_ws']:9.3f}"
    )


def _print_group_summary(
    title: str,
    evaluated: list[dict],
    group_key: str,
) -> None:
    print(f"\n{title}")
    print(f"{'group':26s} {'raw':>7s} {'clean':>7s} "
          f"{'raw_ws':>7s} {'clean_ws':>9s}")
    print("-" * 62)
    for group, metrics in sorted(
        summarize_metrics(evaluated, group_key).items()
    ):
        print(_format_metric_row(group, metrics))


def main() -> int:
    if not LABELS_CSV.exists():
        print(f"No labels file at {LABELS_CSV}. Add samples + labels first.")
        return 1

    with LABELS_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("labels.csv has no rows yet.")
        return 1

    provenance_issues = literal_provenance_issues(rows)
    if provenance_issues:
        print("Ground-truth provenance is incomplete:")
        for issue in provenance_issues:
            print(f"  {issue}")
        return 1

    extract = _load_extractor()

    print(f"Evaluating {len(rows)} sample(s)...\n")
    print(f"{'file':26s} {'raw':>7s} {'clean':>7s} {'raw_ws':>7s} {'clean_ws':>9s}")
    print("-" * 62)

    evaluated = []
    exact_matches = []
    suggestion_results = []
    samples_with_suggestions = 0

    for row in rows:
        fname = row["filename"].strip()
        truth = row["ground_truth_text"]
        img_path = SAMPLES_DIR / fname
        if not truth:
            print(f"{fname[:26]:26s}  (ground truth missing -- skipped)")
            continue
        if not img_path.exists():
            print(f"{fname[:26]:26s}  (image file not found -- skipped)")
            continue

        result = extract(str(img_path))
        raw = result["raw_text"]
        clean = result["cleaned_text"]

        metrics = evaluate_text_pair(raw, clean, truth)
        evaluated.append({
            **row,
            "metrics": metrics,
        })
        suggestions = result.get("review_suggestions") or []
        if suggestions:
            samples_with_suggestions += 1
        for suggestion in suggestions:
            suggestion_results.append({
                "filename": fname,
                "suggestion": suggestion,
                "helpful": suggestion_improves_reference(
                    raw,
                    truth,
                    suggestion,
                ),
            })
        if raw == truth:
            exact_matches.append(f"{fname} (raw)")
        if clean == truth:
            exact_matches.append(f"{fname} (cleaned)")

        print(_format_metric_row(fname, metrics))

    if not evaluated:
        print("\nNo images were evaluated.")
        return 1

    overall = {
        key: sum(row["metrics"][key] for row in evaluated) / len(evaluated)
        for key in METRIC_KEYS
    }
    print("-" * 62)
    print(_format_metric_row("AVERAGE CER", overall))
    _print_group_summary("BY PAPER TYPE", evaluated, "paper_type")
    _print_group_summary("BY WRITER", evaluated, "writer")

    helpful_count = sum(item["helpful"] for item in suggestion_results)
    suggestion_count = len(suggestion_results)
    non_improving = [
        item for item in suggestion_results if not item["helpful"]
    ]
    precision = (
        helpful_count / suggestion_count if suggestion_count else None
    )
    print("\nREVIEW SUGGESTIONS")
    precision_text = f"{precision:.3f}" if precision is not None else "n/a"
    print(
        f"total: {suggestion_count}  helpful: {helpful_count}  "
        f"non-improving: {len(non_improving)}  precision: {precision_text}"
    )
    print(
        f"sample coverage: {samples_with_suggestions}/{len(evaluated)}"
    )
    for item in non_improving:
        suggestion = item["suggestion"]
        print(
            f"  {item['filename']}: {suggestion.get('original')!r} -> "
            f"{suggestion.get('candidate')!r} "
            f"({suggestion.get('rule_id')})"
        )

    if exact_matches:
        print("\nWARNING: exact prediction/reference matches require "
              "ground-truth revalidation:")
        for match in exact_matches:
            print(f"  {match}")

    print("\nLower is better. Columns:")
    print("  raw       = raw OCR output vs ground truth (strict)")
    print("  clean     = after keyword cleanup vs ground truth (strict)")
    print("  raw_ws    = raw, whitespace-normalized (recognition errors only)")
    print("  clean_ws  = cleaned, whitespace-normalized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
