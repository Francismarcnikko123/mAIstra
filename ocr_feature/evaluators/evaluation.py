"""Pure evaluation helpers shared by real and synthetic OCR measurements."""

from collections import defaultdict


METRIC_KEYS = ("raw", "clean", "raw_ws", "clean_ws")
LITERAL_VERIFICATION_VALUE = "true"
LITERAL_PROVENANCE_FIELDS = (
    "literal_verified_by",
    "literal_verified_at",
)


def literal_provenance_issues(rows: list[dict]) -> list[str]:
    """Return failures in human source-paper transcription provenance."""
    issues = []
    for row_number, row in enumerate(rows, 2):
        filename = str(row.get("filename") or "").strip()
        row_name = filename or f"row {row_number}"
        literal_verified = str(row.get("literal_verified") or "").strip()
        if literal_verified.casefold() != LITERAL_VERIFICATION_VALUE:
            issues.append(
                f"{row_name}: literal_verified must be true; this confirms "
                "a human transcription from the source paper"
            )
        for field in LITERAL_PROVENANCE_FIELDS:
            if not str(row.get(field) or "").strip():
                issues.append(
                    f"{row_name}: {field} is required for auditable human "
                    "source-paper transcription"
                )
    return issues


def edit_distance(a: str, b: str) -> int:
    """Return the Levenshtein edit distance between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for row_number, left_char in enumerate(a, 1):
        current = [row_number]
        for column_number, right_char in enumerate(b, 1):
            current.append(min(
                previous[column_number] + 1,
                current[column_number - 1] + 1,
                previous[column_number - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def edit_operations(prediction: str, reference: str) -> dict[str, int]:
    """Count the edits in a minimum script from reference to prediction."""
    distances = [list(range(len(prediction) + 1))]
    for reference_index, reference_char in enumerate(reference, 1):
        current = [reference_index]
        for prediction_index, prediction_char in enumerate(prediction, 1):
            current.append(min(
                distances[-1][prediction_index] + 1,
                current[prediction_index - 1] + 1,
                distances[-1][prediction_index - 1]
                + (reference_char != prediction_char),
            ))
        distances.append(current)

    operations = {"insertions": 0, "deletions": 0, "substitutions": 0}
    reference_index = len(reference)
    prediction_index = len(prediction)
    while reference_index or prediction_index:
        if (
            reference_index
            and prediction_index
            and reference[reference_index - 1] == prediction[prediction_index - 1]
        ):
            reference_index -= 1
            prediction_index -= 1
        elif (
            reference_index
            and prediction_index
            and reference[reference_index - 1] != prediction[prediction_index - 1]
            and distances[reference_index][prediction_index]
            == distances[reference_index - 1][prediction_index - 1] + 1
        ):
            operations["substitutions"] += 1
            reference_index -= 1
            prediction_index -= 1
        elif (
            prediction_index
            and distances[reference_index][prediction_index]
            == distances[reference_index][prediction_index - 1] + 1
        ):
            operations["insertions"] += 1
            prediction_index -= 1
        elif reference_index:
            operations["deletions"] += 1
            reference_index -= 1

    return operations


def cer(prediction: str, reference: str) -> float:
    """Return character error rate relative to the reference length."""
    if not reference:
        return 0.0 if not prediction else 1.0
    return edit_distance(prediction, reference) / len(reference)


def normalize_ws(text: str) -> str:
    """Collapse whitespace so recognition can be scored without formatting."""
    return " ".join(text.split())


def evaluate_text_pair(
    raw: str,
    cleaned: str,
    reference: str,
) -> dict[str, float]:
    """Return the four CER metrics used by the project."""
    normalized_reference = normalize_ws(reference)
    return {
        "raw": cer(raw, reference),
        "clean": cer(cleaned, reference),
        "raw_ws": cer(normalize_ws(raw), normalized_reference),
        "clean_ws": cer(normalize_ws(cleaned), normalized_reference),
    }


def summarize_metrics(
    rows: list[dict],
    group_key: str,
) -> dict[str, dict[str, float]]:
    """Average available metrics by a metadata field."""
    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {key: [] for key in METRIC_KEYS}
    )
    for row in rows:
        group = str(row.get(group_key) or "unknown")
        for key, value in row.get("metrics", {}).items():
            if key in METRIC_KEYS:
                grouped[group][key].append(float(value))

    return {
        group: {
            key: sum(values) / len(values)
            for key, values in metric_values.items()
            if values
        }
        for group, metric_values in grouped.items()
    }


def suggestion_improves_reference(
    raw_text: str,
    reference: str,
    suggestion: dict,
) -> bool:
    """Return whether one suggested replacement reduces normalized edits."""
    try:
        line_number = int(suggestion["line"])
        start = int(suggestion["start"])
        end = int(suggestion["end"])
        original = str(suggestion["original"])
        candidate = str(suggestion["candidate"])
    except (KeyError, TypeError, ValueError):
        return False

    lines = raw_text.splitlines(keepends=True)
    if line_number < 1 or line_number > len(lines) or start < 0 or end < start:
        return False

    line = lines[line_number - 1]
    if end > len(line) or line[start:end] != original:
        return False

    lines[line_number - 1] = line[:start] + candidate + line[end:]
    candidate_text = "".join(lines)
    before = edit_distance(normalize_ws(raw_text), normalize_ws(reference))
    after = edit_distance(normalize_ws(candidate_text), normalize_ws(reference))
    return after < before
