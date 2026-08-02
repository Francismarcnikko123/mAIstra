"""Offline baseline-versus-consensus raw OCR evaluator.

This engineering tool never changes the live OCR default. It runs both
recognition modes independently against ``samples/labels.csv`` and applies the
numeric promotion criteria used for the raw recognition experiment.
"""

import csv
import statistics
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Callable, NamedTuple

from evaluation import (
    cer,
    edit_operations,
    literal_provenance_issues,
    normalize_ws,
)


SAMPLES_DIR = Path("samples")
LABELS_CSV = SAMPLES_DIR / "labels.csv"

RAW_WS_TARGET = .181
RAW_STRICT_BASELINE = .227
SUBGROUP_REGRESSION_LIMIT = .005
EXPECTED_SAMPLE_COUNT = 13
REQUIRED_SUBGROUP_KEYS = {
    "paper:bond",
    "paper:greenbook",
    "writer:nikko",
    "writer:nombrado",
}

MODES = ("baseline", "consensus")
METRICS = ("raw", "raw_ws")
GROUP_KEYS = ("paper_type", "writer")


class OCRRuntime(NamedTuple):
    """OCR dependencies loaded only after the acceptance cohort is valid."""

    extractor: Callable
    warmup: Callable[[], None]
    baseline_config: object
    consensus_config: object


def _load_ocr_runtime() -> OCRRuntime:
    """Import model-owning modules only after labels pass preflight."""
    from ocr_pipeline import extract_text_from_image, warmup
    from recognition_consensus import BASELINE_RECOGNITION, CONSENSUS_RECOGNITION

    return OCRRuntime(
        extractor=extract_text_from_image,
        warmup=warmup,
        baseline_config=BASELINE_RECOGNITION,
        consensus_config=CONSENSUS_RECOGNITION,
    )


def promotion_gate(
    baseline: dict[str, float],
    consensus: dict[str, float],
    subgroup_deltas: dict[str, float],
    cohort_complete: bool = False,
) -> dict:
    """Return the numeric decision for the offline recognition experiment."""
    required_subgroups_present = (
        REQUIRED_SUBGROUP_KEYS <= set(subgroup_deltas)
    )
    baseline_raw = baseline.get("raw", RAW_STRICT_BASELINE)
    max_subgroup_delta = max(subgroup_deltas.values(), default=None)
    checks = {
        "raw_ws_target": consensus["raw_ws"] <= RAW_WS_TARGET,
        "strict_raw_non_regression": consensus["raw"] <= baseline_raw,
        "subgroup_non_regression": (
            required_subgroups_present
            and all(
                delta <= SUBGROUP_REGRESSION_LIMIT
                for delta in subgroup_deltas.values()
            )
        ),
        "cohort_complete": cohort_complete and required_subgroups_present,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "observed": {
            "consensus_raw_ws": consensus["raw_ws"],
            "consensus_raw": consensus["raw"],
            "baseline_raw": baseline_raw,
            "max_subgroup_delta": max_subgroup_delta,
        },
    }


def preflight_cohort(rows: list[dict], samples_dir: Path) -> dict:
    """Validate the frozen acceptance cohort without touching OCR modules."""
    issues = []
    if len(rows) != EXPECTED_SAMPLE_COUNT:
        issues.append(
            f"expected {EXPECTED_SAMPLE_COUNT} label rows; found {len(rows)}"
        )

    filenames = []
    subgroup_keys = set()
    for row_number, row in enumerate(rows, 2):
        filename_value = row.get("filename")
        filename = (
            filename_value.strip()
            if isinstance(filename_value, str)
            else ""
        )
        truth = row.get("ground_truth_text")
        if not filename:
            issues.append(f"row {row_number}: filename missing")
        else:
            filenames.append(filename)
            if not (samples_dir / filename).is_file():
                issues.append(f"{filename}: image file not found")
        if not isinstance(truth, str) or not truth.strip():
            issues.append(
                f"{filename or f'row {row_number}'}: ground truth missing"
            )

        paper_type = str(row.get("paper_type") or "").strip()
        writer = str(row.get("writer") or "").strip()
        if paper_type:
            subgroup_keys.add(f"paper:{paper_type}")
        if writer:
            subgroup_keys.add(f"writer:{writer}")

    issues.extend(literal_provenance_issues(rows))

    filename_counts = Counter(filenames)
    for filename, count in sorted(filename_counts.items()):
        if count > 1:
            issues.append(f"duplicate filename: {filename} ({count} rows)")
    if len(filename_counts) != EXPECTED_SAMPLE_COUNT:
        issues.append(
            f"expected {EXPECTED_SAMPLE_COUNT} unique filenames; "
            f"found {len(filename_counts)}"
        )

    for subgroup in sorted(REQUIRED_SUBGROUP_KEYS - subgroup_keys):
        issues.append(f"missing required subgroup: {subgroup}")

    return {"complete": not issues, "issues": issues}


def _mean_metrics(rows: list[dict], mode: str) -> dict[str, float]:
    return {
        metric: sum(row[mode]["metrics"][metric] for row in rows) / len(rows)
        for metric in METRICS
    }


def aggregate_metrics(rows: list[dict]) -> dict[str, dict[str, float]]:
    """Macro-average page metrics for baseline and consensus."""
    if not rows:
        return {mode: {} for mode in MODES}
    return {mode: _mean_metrics(rows, mode) for mode in MODES}


def subgroup_summaries(rows: list[dict]) -> dict:
    """Macro-average both modes by paper type and writer."""
    summaries = {}
    for group_key in GROUP_KEYS:
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            group = str(row.get(group_key) or "unknown")
            grouped.setdefault(group, []).append(row)
        summaries[group_key] = {
            group: aggregate_metrics(group_rows)
            for group, group_rows in grouped.items()
        }
    return summaries


def subgroup_deltas(summaries: dict) -> dict[str, float]:
    """Return consensus-minus-baseline raw_ws for every metadata subgroup."""
    deltas = {}
    prefixes = {"paper_type": "paper", "writer": "writer"}
    for group_key, groups in summaries.items():
        prefix = prefixes[group_key]
        for group, metrics in groups.items():
            deltas[f"{prefix}:{group}"] = (
                metrics["consensus"]["raw_ws"]
                - metrics["baseline"]["raw_ws"]
            )
    return deltas


def _raw_metrics(prediction: str, truth: str) -> dict[str, float]:
    normalized_prediction = normalize_ws(prediction)
    normalized_truth = normalize_ws(truth)
    return {
        "raw": cer(prediction, truth),
        "raw_ws": cer(normalized_prediction, normalized_truth),
    }


def _diagnostics(result: dict) -> list[str]:
    collected = []
    for key in ("recognition_diagnostics", "review_diagnostics"):
        values = result.get(key) or []
        if isinstance(values, (list, tuple)):
            collected.extend(f"{key}: {value}" for value in values)
        else:
            collected.append(f"{key}: {values}")
    return collected


def _evaluate_mode(
    image_path: Path,
    truth: str,
    extractor: Callable,
    recognition_config,
    clock: Callable[[], float],
) -> dict:
    with tempfile.TemporaryDirectory(prefix="raw-consensus-") as output_dir:
        started = clock()
        result = extractor(
            str(image_path),
            output_dir=output_dir,
            recognition_config=recognition_config,
        )
        elapsed = clock() - started

    raw_text = result.get("raw_text", "")
    if not isinstance(raw_text, str):
        raw_text = ""
    normalized_prediction = normalize_ws(raw_text)
    normalized_truth = normalize_ws(truth)
    return {
        "raw_text": raw_text,
        "metrics": _raw_metrics(raw_text, truth),
        "operations": edit_operations(
            normalized_prediction,
            normalized_truth,
        ),
        "seconds": elapsed,
        "decisions": list(result.get("consensus_decisions") or []),
        "diagnostics": _diagnostics(result),
    }


def evaluate_rows(
    rows: list[dict],
    samples_dir: Path,
    runtime: OCRRuntime,
    clock: Callable[[], float],
) -> list[dict]:
    """Evaluate every row after the full frozen cohort passes preflight."""
    evaluated = []
    for row in rows:
        filename = row["filename"].strip()
        truth = row["ground_truth_text"]
        image_path = samples_dir / filename

        baseline = _evaluate_mode(
            image_path,
            truth,
            runtime.extractor,
            runtime.baseline_config,
            clock,
        )
        consensus = _evaluate_mode(
            image_path,
            truth,
            runtime.extractor,
            runtime.consensus_config,
            clock,
        )
        evaluated.append({
            **row,
            "filename": filename,
            "truth": truth,
            "baseline": baseline,
            "consensus": consensus,
        })
    return evaluated


def _print_page_results(rows: list[dict]) -> None:
    print("\nPER-PAGE RAW CER")
    print(
        f"{'file':26s} {'mode':10s} {'raw':>10s} {'raw_ws':>10s} "
        f"{'delta_ws':>11s} {'time':>8s}"
    )
    print("-" * 82)
    for row in rows:
        baseline = row["baseline"]
        consensus = row["consensus"]
        delta = (
            consensus["metrics"]["raw_ws"]
            - baseline["metrics"]["raw_ws"]
        )
        print(
            f"{row['filename'][:26]:26s} {'baseline':10s} "
            f"{baseline['metrics']['raw']:10.6f} "
            f"{baseline['metrics']['raw_ws']:10.6f} "
            f"{'-':>11s} {baseline['seconds']:7.3f}s"
        )
        print(
            f"{'':26s} {'consensus':10s} "
            f"{consensus['metrics']['raw']:10.6f} "
            f"{consensus['metrics']['raw_ws']:10.6f} "
            f"{delta:+11.6f} {consensus['seconds']:7.3f}s"
        )


def _print_aggregate(overall: dict) -> None:
    print("\nOVERALL MACRO-AVERAGE RAW CER")
    print(f"{'mode':12s} {'raw':>12s} {'raw_ws':>12s}")
    print("-" * 38)
    for mode in MODES:
        print(
            f"{mode:12s} {overall[mode]['raw']:12.6f} "
            f"{overall[mode]['raw_ws']:12.6f}"
        )
    print(
        "delta (consensus - baseline): "
        f"raw={overall['consensus']['raw'] - overall['baseline']['raw']:+.6f} "
        "raw_ws="
        f"{overall['consensus']['raw_ws'] - overall['baseline']['raw_ws']:+.6f}"
    )


def _print_subgroups(summaries: dict) -> None:
    for group_key, title in (
        ("paper_type", "BY PAPER TYPE"),
        ("writer", "BY WRITER"),
    ):
        print(f"\n{title} (macro-average raw_ws)")
        print(
            f"{'group':26s} {'baseline':>12s} {'consensus':>12s} {'delta':>12s}"
        )
        print("-" * 66)
        for group, metrics in sorted(summaries[group_key].items()):
            baseline = metrics["baseline"]["raw_ws"]
            consensus = metrics["consensus"]["raw_ws"]
            print(
                f"{group[:26]:26s} {baseline:12.6f} {consensus:12.6f} "
                f"{consensus - baseline:+12.6f}"
            )


def _print_operations(rows: list[dict]) -> None:
    print("\nINSERTIONS / DELETIONS / SUBSTITUTIONS")
    for mode in MODES:
        totals = Counter()
        for row in rows:
            totals.update(row[mode]["operations"])
        print(
            f"{mode}: {totals['insertions']} / {totals['deletions']} / "
            f"{totals['substitutions']}"
        )


def _print_decisions(rows: list[dict]) -> None:
    decisions = [
        (row["filename"], decision)
        for row in rows
        for decision in row["consensus"]["decisions"]
        if isinstance(decision, dict)
    ]
    counts = Counter(decision.get("action", "unknown") for _, decision in decisions)
    print("\nCONSENSUS DECISION AUDIT")
    print(f"total decisions: {len(decisions)}")
    print("types: " + (
        ", ".join(f"{action}={count}" for action, count in sorted(counts.items()))
        if counts else "none"
    ))
    for filename, decision in decisions:
        action = decision.get("action", "unknown")
        print(
            f"  {filename}: {action} {decision.get('baseline')!r} -> "
            f"{decision.get('selected')!r} ({decision.get('reason', 'unknown')})"
        )


def _print_regressions(rows: list[dict]) -> None:
    print("\nPER-PAGE REGRESSIONS (raw_ws)")
    regressions = 0
    for row in rows:
        baseline = row["baseline"]["metrics"]["raw_ws"]
        consensus = row["consensus"]["metrics"]["raw_ws"]
        if consensus > baseline:
            regressions += 1
            print(
                f"  {row['filename']}: {baseline:.6f} -> {consensus:.6f} "
                f"({consensus - baseline:+.6f})"
            )
    if not regressions:
        print("  none")


def _print_diagnostics(rows: list[dict]) -> None:
    print("\nDIAGNOSTICS")
    count = 0
    for row in rows:
        for mode in MODES:
            for diagnostic in row[mode]["diagnostics"]:
                count += 1
                print(f"  {row['filename']} [{mode}] {diagnostic}")
    if not count:
        print("  none")


def _print_timings(rows: list[dict]) -> None:
    timings = {
        mode: [row[mode]["seconds"] for row in rows]
        for mode in MODES
    }
    overheads = [
        row["consensus"]["seconds"] - row["baseline"]["seconds"]
        for row in rows
    ]
    baseline_mean = statistics.mean(timings["baseline"])
    consensus_mean = statistics.mean(timings["consensus"])
    print("\nTIMING")
    for mode in MODES:
        print(
            f"{mode}: mean={statistics.mean(timings[mode]):.3f}s "
            f"median={statistics.median(timings[mode]):.3f}s"
        )
    percent = (
        f" ({(consensus_mean / baseline_mean - 1) * 100:+.1f}%)"
        if baseline_mean > 0 else ""
    )
    print(
        f"consensus overhead: mean={statistics.mean(overheads):+.3f}s{percent} "
        f"median={statistics.median(overheads):+.3f}s"
    )


def _print_gate(gate: dict) -> None:
    checks = gate["checks"]
    observed = gate["observed"]

    def status(passed: bool) -> str:
        return "PASS" if passed else "FAIL"

    def metric(value, *, signed: bool = False) -> str:
        if value is None:
            return "n/a"
        return f"{value:+.6f}" if signed else f"{value:.6f}"

    print(
        "\nThis is not a capture-quality gate; "
        "it evaluates offline OCR engineering only."
    )
    print("Manual review of every consensus decision remains required.\n")
    print(
        "observed consensus raw_ws: "
        f"{metric(observed['consensus_raw_ws'])}"
    )
    print(
        "observed consensus strict raw: "
        f"{metric(observed['consensus_raw'])} "
        f"(baseline: {metric(observed['baseline_raw'])})"
    )
    print(
        "observed max subgroup delta: "
        f"{metric(observed['max_subgroup_delta'], signed=True)}\n"
    )
    print("PROMOTION GATE (offline OCR engineering only)")
    print(f"raw_ws <= 0.181: {status(checks['raw_ws_target'])}")
    print(
        "strict raw non-regression: "
        f"{status(checks['strict_raw_non_regression'])}"
    )
    print(
        "subgroup regression <= 0.005: "
        f"{status(checks['subgroup_non_regression'])}"
    )
    print(
        "acceptance cohort complete: "
        f"{status(checks['cohort_complete'])}"
    )
    print("decision audit: MANUAL REVIEW REQUIRED")
    print(f"numeric gate: {status(gate['passed'])}")


def _failed_gate() -> dict:
    return {
        "passed": False,
        "checks": {
            "raw_ws_target": False,
            "strict_raw_non_regression": False,
            "subgroup_non_regression": False,
            "cohort_complete": False,
        },
        "observed": {
            "consensus_raw_ws": None,
            "consensus_raw": None,
            "baseline_raw": None,
            "max_subgroup_delta": None,
        },
    }


def main(
    runtime_loader: Callable[[], OCRRuntime] | None = None,
    clock: Callable[[], float] | None = None,
) -> int:
    if not LABELS_CSV.exists():
        print(f"No labels file at {LABELS_CSV}. Add samples + labels first.")
        _print_gate(_failed_gate())
        return 1

    with LABELS_CSV.open(newline="", encoding="utf-8") as labels_file:
        rows = list(csv.DictReader(labels_file))

    if not rows:
        print("labels.csv has no rows yet.")
        _print_gate(_failed_gate())
        return 1

    preflight = preflight_cohort(rows, SAMPLES_DIR)
    if not preflight["complete"]:
        print("Acceptance cohort is incomplete:")
        for issue in preflight["issues"]:
            print(f"  {issue}")
        _print_gate(_failed_gate())
        return 1

    load_runtime = runtime_loader or _load_ocr_runtime
    timer = clock or time.perf_counter
    try:
        runtime = load_runtime()
        # Model initialization and warmup are cohort-level setup. Keeping this
        # outside _evaluate_mode ensures neither is included in page timings.
        runtime.warmup()
    except Exception as exc:
        print(f"OCR runtime setup failed: {type(exc).__name__}")
        _print_gate(_failed_gate())
        return 1

    print(f"Evaluating {len(rows)} sample(s) in baseline and consensus modes...")
    try:
        evaluated = evaluate_rows(rows, SAMPLES_DIR, runtime, timer)
    except Exception as exc:
        print(f"\nOCR evaluation failed: {type(exc).__name__}")
        _print_gate(_failed_gate())
        return 1

    overall = aggregate_metrics(evaluated)
    summaries = subgroup_summaries(evaluated)
    deltas = subgroup_deltas(summaries)
    cohort_complete = (
        preflight["complete"]
        and len(evaluated) == EXPECTED_SAMPLE_COUNT
        and len({row["filename"] for row in evaluated})
        == EXPECTED_SAMPLE_COUNT
    )
    gate = promotion_gate(
        overall["baseline"],
        overall["consensus"],
        deltas,
        cohort_complete=cohort_complete,
    )

    _print_page_results(evaluated)
    _print_aggregate(overall)
    _print_subgroups(summaries)
    _print_operations(evaluated)
    _print_decisions(evaluated)
    _print_regressions(evaluated)
    _print_diagnostics(evaluated)
    _print_timings(evaluated)
    _print_gate(gate)
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
