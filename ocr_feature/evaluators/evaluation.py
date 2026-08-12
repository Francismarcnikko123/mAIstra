# Library module, not runnable on its own (no __main__) -- imported by
# evaluate_cer.py and evaluate_robustness.py. Run those instead.
"""Pure evaluation helpers shared by real and synthetic OCR measurements."""

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


def wer(prediction: str, reference: str) -> float:
    """Word error rate: edit distance over whitespace-split tokens, relative
    to the reference's token count. Unlike cer(), there is no separate
    whitespace-normalized variant to report -- str.split() already treats any
    run of whitespace as one separator and ignores leading/trailing
    whitespace, so a raw split and a normalize_ws()'d split produce identical
    tokens. edit_distance() works unchanged on lists (it compares elements
    with !=, not just characters), so this reuses the same algorithm as cer().
    """
    reference_tokens = reference.split()
    prediction_tokens = prediction.split()
    if not reference_tokens:
        return 0.0 if not prediction_tokens else 1.0
    return edit_distance(prediction_tokens, reference_tokens) / len(reference_tokens)


# A lightweight C lexer for token-level scoring -- NOT a full standards-
# compliant tokenizer (no hex/octal/suffix number forms, no wide/prefixed
# string literals like L"..." or u8"..."). Good enough to make "x=5" and
# "x = 5" tokenize identically, which is the point: token boundaries come
# from C syntax, not from the incidental spacing OCR/the transcriber used.
# Longest-match-first ordering matters here: multi-character operators are
# listed longest-first so e.g. "<<=" isn't cut short into "<<" plus "=".
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
    """Split C source into lexical tokens: string/char literals stay atomic
    (via the same C_LITERAL pattern the cleanup layer uses to shield them),
    multi-character operators are matched before single characters, and
    identifiers/keywords/numbers are whole tokens. Whitespace carries no
    information and is a pure separator, exactly like in C itself."""
    return _C_TOKEN.findall(text)


def token_accuracy(prediction: str, reference: str) -> float:
    """Token-level recognition accuracy: 1 - (edit distance over C-lexical
    tokens / reference token count), floored at 0. Distinct from wer(): token
    boundaries follow C syntax rather than whitespace, so a difference in
    spacing around an operator never counts as an error -- only genuinely
    different tokens do."""
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
    """Average available metrics by a metadata field. `metric_keys`/
    `metrics_field` default to the CER metrics for backward compatibility;
    pass `WORD_TOKEN_METRIC_KEYS, metrics_field="word_token_metrics"` to
    summarize those instead."""
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
