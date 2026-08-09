import re


def normalize_output(output: str) -> str:
    """
    Normalizes output so small spacing differences do not fail the answer.

    Example:
    'sum:15'
    'sum: 15'
    """
    if output is None:
        return ""

    output = output.strip().lower()

    # Remove spaces around colon
    output = re.sub(r"\s*:\s*", ":", output)

    # Convert many spaces/newlines/tabs into one space
    output = re.sub(r"\s+", " ", output)

    return output


def compare_output(expected_output: str, actual_output: str) -> dict:
    expected = normalize_output(expected_output)
    actual = normalize_output(actual_output)

    passed = expected == actual

    return {
        "passed": passed,
        "score": 100 if passed else 0,
        "expected_normalized": expected,
        "actual_normalized": actual,
    }