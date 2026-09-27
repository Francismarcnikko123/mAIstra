"""OCR accuracy metrics: CER, WER and C-token accuracy. Used by
evaluate_cer.py and evaluate_robustness.py."""

import re
from collections import defaultdict

from core.c_literals import C_LITERAL


METRIC_KEYS = ("raw", "clean", "raw_ws", "clean_ws")
WORD_TOKEN_METRIC_KEYS = (
    "raw_wer", "clean_wer", "raw_token_accuracy", "clean_token_accuracy",
)
LITERAL_VERIFICATION_VALUE = "true"
LITERAL_PROVENANCE_FIELDS = (
    "literal_verified_by",
    "literal_verified_at",
)


def literal_provenance_issues(rows: list[dict]) -> list[str]:
    """List rows missing proof that a person checked the text against the
    paper (literal_verified=true, plus who and when)."""
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


def wer(prediction: str, reference: str) -> float:
    """Word error rate: edit distance over whitespace-separated words,
    divided by the reference's word count."""
    reference_tokens = reference.split()
    prediction_tokens = prediction.split()
    if not reference_tokens:
        return 0.0 if not prediction_tokens else 1.0
    return edit_distance(prediction_tokens, reference_tokens) / len(reference_tokens)


# A simple C tokenizer for token accuracy, so "x=5" and "x = 5" give the same
# tokens. Longer operators come first, so "<<=" isn't split. Not a full C
# lexer (no hex numbers or L"..." strings).
_MULTI_CHAR_OPERATORS = (
    r"<<=|>>=|<<|>>|<=|>=|==|!=|&&|\|\||"
    r"\+=|-=|\*=|/=|%=|&=|\|=|\^=|->|\+\+|--"
)
_NUMBER = r"\d+\.\d+|\.\d+|\d+"
_IDENTIFIER = r"[A-Za-z_]\w*"
_SINGLE_CHAR = r"[^\sA-Za-z0-9_]"
_C_TOKEN = re.compile(
    "|".join(
        [C_LITERAL.pattern, _MULTI_CHAR_OPERATORS, _NUMBER, _IDENTIFIER, _SINGLE_CHAR]
    )
)


def tokenize_c(text: str) -> list[str]:
    """Split C code into tokens: string and character literals, operators,
    numbers, names and single symbols. Whitespace only separates tokens."""
    return _C_TOKEN.findall(text)


def token_accuracy(prediction: str, reference: str) -> float:
    """1 - (edit distance over C tokens / reference token count), at least 0.
    Unlike wer(), spacing around an operator never counts as an error."""
    reference_tokens = tokenize_c(reference)
    prediction_tokens = tokenize_c(prediction)
    if not reference_tokens:
        return 1.0 if not prediction_tokens else 0.0
    error_rate = edit_distance(prediction_tokens, reference_tokens) / len(
        reference_tokens
    )
    return max(0.0, 1.0 - error_rate)


def evaluate_word_token_pair(
    raw: str,
    cleaned: str,
    reference: str,
) -> dict[str, float]:
    """Return the WER and token-level-accuracy metrics, raw vs. cleaned."""
    return {
        "raw_wer": wer(raw, reference),
        "clean_wer": wer(cleaned, reference),
        "raw_token_accuracy": token_accuracy(raw, reference),
        "clean_token_accuracy": token_accuracy(cleaned, reference),
    }


def summarize_metrics(
    rows: list[dict],
    group_key: str,
    metric_keys: tuple[str, ...] = METRIC_KEYS,
    metrics_field: str = "metrics",
) -> dict[str, dict[str, float]]:
    """Average each metric per group, e.g. per paper type. Defaults to the
    CER metrics; pass WORD_TOKEN_METRIC_KEYS and
    metrics_field="word_token_metrics" for WER and token accuracy."""
    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {key: [] for key in metric_keys}
    )
    for row in rows:
        group = str(row.get(group_key) or "unknown")
        for key, value in row.get(metrics_field, {}).items():
            if key in metric_keys:
                grouped[group][key].append(float(value))

    return {
        group: {
            key: sum(values) / len(values)
            for key, values in metric_values.items()
            if values
        }
        for group, metric_values in grouped.items()
    }
