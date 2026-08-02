"""Conservative test-time consensus candidate generation for OCR."""

from dataclasses import dataclass
from difflib import SequenceMatcher
from math import isclose, isfinite
from numbers import Real
from pathlib import Path
from statistics import median

import cv2


def _is_finite_real(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return isfinite(numeric_value)


@dataclass(frozen=True)
class RecognitionConfig:
    mode: str = "baseline"
    angles: tuple[float, ...] = (-0.5, 0.5)

    def __post_init__(self) -> None:
        if self.mode not in {"baseline", "consensus"}:
            raise ValueError("mode must be 'baseline' or 'consensus'")
        if len(self.angles) != 2:
            raise ValueError("angles must contain exactly two values")
        if any(not _is_finite_real(angle) for angle in self.angles):
            raise ValueError("angles must be finite real numeric values")


BASELINE_RECOGNITION = RecognitionConfig(mode="baseline")
CONSENSUS_RECOGNITION = RecognitionConfig(mode="consensus")
DEFAULT_RECOGNITION_CONFIG = BASELINE_RECOGNITION

TEXT_SUPPORT_MIN = 0.90
TEXT_SUPPORT_MARGIN = 0.04
PHANTOM_MAX_CHARS = 2
PHANTOM_MAX_CONFIDENCE = 0.60
BODY_GAP_MULTIPLIER = 1.5

_OCR_CONFIDENCE_FLOOR = 0.3
_CENTER_DISTANCE_MULTIPLIER = 1.5


def create_candidate_views(
    preprocessed_path: Path,
    output_dir: Path,
    config: RecognitionConfig,
) -> list[tuple[str, Path]]:
    """Write the two fixed-angle grayscale rotations used for consensus OCR."""
    if config.mode != "consensus":
        raise ValueError("candidate views require consensus recognition mode")

    source_path = Path(preprocessed_path)
    image = cv2.imread(str(source_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"unreadable preprocessed image: {source_path}")

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    height, width = image.shape
    matrix_center = (width / 2, height / 2)
    candidates: list[tuple[str, Path]] = []

    for name, angle in zip(("rotate_neg", "rotate_pos"), config.angles):
        matrix = cv2.getRotationMatrix2D(matrix_center, angle, 1.0)
        rotated = cv2.warpAffine(
            image,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
        candidate_path = destination / f"{source_path.stem}_{name}.png"
        if not cv2.imwrite(str(candidate_path), rotated):
            raise OSError(f"failed to write candidate view: {candidate_path}")
        candidates.append((name, candidate_path))

    return candidates


def _safe_geometry(line: dict) -> tuple[float, float, float, float] | None:
    """Return normalized (min, max, center, height), or None if unsafe."""
    y_min = line.get("y_min")
    y_max = line.get("y_max")
    if any(
        isinstance(value, bool) or not isinstance(value, Real)
        for value in (y_min, y_max)
    ):
        return None

    try:
        y_min = float(y_min)
        y_max = float(y_max)
    except (TypeError, ValueError, OverflowError):
        return None
    if (
        not isfinite(y_min)
        or not isfinite(y_max)
        or not 0.0 <= y_min < y_max <= 1.0
    ):
        return None

    height = y_max - y_min
    center = y_min + height / 2.0
    if not isfinite(height) or not isfinite(center):
        return None
    return y_min, y_max, center, height


def _collapsed_text(line: dict) -> str:
    text = line.get("text")
    if not isinstance(text, str):
        return ""
    return " ".join(text.split())


def _text_similarity(first: dict, second: dict) -> float:
    first_text = _collapsed_text(first)
    second_text = _collapsed_text(second)
    if not first_text or not second_text:
        return 0.0
    return SequenceMatcher(
        None,
        first_text,
        second_text,
        autojunk=False,
    ).ratio()


def _confidence(line: dict) -> float | None:
    value = line.get("mean_confidence")
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if isfinite(value) and 0.0 <= value <= 1.0 else None


def _compatible_geometry(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    first_min, first_max, first_center, first_height = first
    second_min, second_max, second_center, second_height = second
    overlap = min(first_max, second_max) - max(first_min, second_min)
    normalized_overlap = overlap / min(first_height, second_height)
    center_distance = abs(first_center - second_center)
    return (
        normalized_overlap > 0.0
        or center_distance
        <= _CENTER_DISTANCE_MULTIPLIER * max(first_height, second_height)
    )


def _normalized_center_distance(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    return abs(first[2] - second[2]) / max(first[3], second[3])


def _positioned_lines(
    lines: list[dict], allowed_indices: set[int] | None = None
) -> list[tuple[int, dict, tuple[float, float, float, float]]]:
    positioned = []
    for index, line in enumerate(lines):
        if allowed_indices is not None and index not in allowed_indices:
            continue
        geometry = _safe_geometry(line)
        if geometry is not None:
            positioned.append((index, line, geometry))
    positioned.sort(key=lambda item: (item[2][2], item[0]))
    return positioned


def _align_lines(
    first_lines: list[dict],
    second_lines: list[dict],
    first_indices: set[int] | None = None,
    second_indices: set[int] | None = None,
) -> dict[int, int]:
    """Return the closest monotonic, one-to-one compatible geometry matches."""
    first = _positioned_lines(first_lines, first_indices)
    second = _positioned_lines(second_lines, second_indices)
    first_count = len(first)
    second_count = len(second)
    match_counts = [
        [0 for _ in range(second_count + 1)]
        for _ in range(first_count + 1)
    ]
    distances = [
        [0.0 for _ in range(second_count + 1)]
        for _ in range(first_count + 1)
    ]
    actions = [
        [None for _ in range(second_count + 1)]
        for _ in range(first_count + 1)
    ]
    for first_position in range(first_count):
        actions[first_position][second_count] = "skip_first"
    for second_position in range(second_count):
        actions[first_count][second_position] = "skip_second"

    for first_position in range(first_count - 1, -1, -1):
        for second_position in range(second_count - 1, -1, -1):
            first_geometry = first[first_position][2]
            second_geometry = second[second_position][2]
            candidates = []
            if _compatible_geometry(first_geometry, second_geometry):
                candidates.append(
                    (
                        match_counts[first_position + 1][second_position + 1]
                        + 1,
                        distances[first_position + 1][second_position + 1]
                        + _normalized_center_distance(
                            first_geometry, second_geometry
                        ),
                        "match",
                    )
                )
            candidates.extend(
                (
                    (
                        match_counts[first_position][second_position + 1],
                        distances[first_position][second_position + 1],
                        "skip_second",
                    ),
                    (
                        match_counts[first_position + 1][second_position],
                        distances[first_position + 1][second_position],
                        "skip_first",
                    ),
                )
            )
            # min() is stable: exact ties prefer match, then skipping a
            # second-side insertion, then skipping a first-side line.
            best_matches, best_distance, best_action = min(
                candidates, key=lambda candidate: (-candidate[0], candidate[1])
            )
            match_counts[first_position][second_position] = best_matches
            distances[first_position][second_position] = best_distance
            actions[first_position][second_position] = best_action

    pairs = {}
    first_position = 0
    second_position = 0
    while first_position < first_count or second_position < second_count:
        action = actions[first_position][second_position]
        if action == "match":
            pairs[first[first_position][0]] = second[second_position][0]
            first_position += 1
            second_position += 1
        elif action == "skip_first":
            first_position += 1
        elif action == "skip_second":
            second_position += 1
        else:
            break
    return pairs


def _choose_supported_variant(negative: dict, positive: dict) -> dict:
    negative_confidence = _confidence(negative)
    positive_confidence = _confidence(positive)
    negative_rank = (
        negative_confidence
        if negative_confidence is not None
        else float("-inf")
    )
    positive_rank = (
        positive_confidence
        if positive_confidence is not None
        else float("-inf")
    )
    return positive if positive_rank > negative_rank else negative


def _supported_body(
    baseline_lines: list[dict],
    negative_lines: list[dict],
    positive_lines: list[dict],
    baseline_to_negative: dict[int, int],
    baseline_to_positive: dict[int, int],
) -> tuple[float, float] | None:
    geometries = []
    for index, line in enumerate(baseline_lines):
        if index not in baseline_to_negative or index not in baseline_to_positive:
            continue
        negative = negative_lines[baseline_to_negative[index]]
        positive = positive_lines[baseline_to_positive[index]]
        negative_geometry = _safe_geometry(negative)
        positive_geometry = _safe_geometry(positive)
        negative_confidence = _confidence(negative)
        positive_confidence = _confidence(positive)
        if (
            negative_geometry is None
            or positive_geometry is None
            or not _compatible_geometry(negative_geometry, positive_geometry)
            or _text_similarity(negative, positive) < TEXT_SUPPORT_MIN
            or negative_confidence is None
            or positive_confidence is None
            or negative_confidence < _OCR_CONFIDENCE_FLOOR
            or positive_confidence < _OCR_CONFIDENCE_FLOOR
        ):
            continue
        geometry = _safe_geometry(line)
        if geometry is not None:
            geometries.append(geometry)
    geometries.sort(key=lambda geometry: geometry[2])
    if not geometries:
        return None

    if len(geometries) == 1:
        padding_unit = geometries[0][3]
    else:
        median_gap = median(
            geometries[index + 1][2] - geometries[index][2]
            for index in range(len(geometries) - 1)
        )
        median_height = median(geometry[3] for geometry in geometries)
        padding_unit = min(median_gap, 2.0 * median_height)
    expansion = BODY_GAP_MULTIPLIER * padding_unit
    return (
        min(geometry[0] for geometry in geometries) - expansion,
        max(geometry[1] for geometry in geometries) + expansion,
    )


def _overlaps_or_touches_body(
    geometry: tuple[float, float, float, float],
    body: tuple[float, float],
) -> bool:
    reaches_lower = geometry[1] >= body[0] or isclose(geometry[1], body[0])
    reaches_upper = geometry[0] <= body[1] or isclose(geometry[0], body[1])
    return reaches_lower and reaches_upper


def select_consensus_lines(
    baseline_lines: list[dict],
    negative_lines: list[dict],
    positive_lines: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Conservatively select whole OCR line readings from three attempts."""
    if any(_safe_geometry(line) is None for line in baseline_lines):
        return list(baseline_lines), []

    baseline_to_negative = _align_lines(baseline_lines, negative_lines)
    baseline_to_positive = _align_lines(baseline_lines, positive_lines)
    matched_negative = set(baseline_to_negative.values())
    matched_positive = set(baseline_to_positive.values())
    unmatched_negative = set(range(len(negative_lines))) - matched_negative
    unmatched_positive = set(range(len(positive_lines))) - matched_positive
    negative_to_positive = _align_lines(
        negative_lines,
        positive_lines,
        unmatched_negative,
        unmatched_positive,
    )
    body = _supported_body(
        baseline_lines,
        negative_lines,
        positive_lines,
        baseline_to_negative,
        baseline_to_positive,
    )

    selected = []
    decisions = []
    for baseline_index, baseline in enumerate(baseline_lines):
        negative_index = baseline_to_negative.get(baseline_index)
        positive_index = baseline_to_positive.get(baseline_index)
        selected_line = baseline

        if negative_index is not None and positive_index is not None:
            negative = negative_lines[negative_index]
            positive = positive_lines[positive_index]
            negative_confidence = _confidence(negative)
            positive_confidence = _confidence(positive)
            negative_geometry = _safe_geometry(negative)
            positive_geometry = _safe_geometry(positive)
            mutual_similarity = _text_similarity(negative, positive)
            if (
                negative_confidence is not None
                and positive_confidence is not None
                and negative_geometry is not None
                and positive_geometry is not None
                and _compatible_geometry(
                    negative_geometry, positive_geometry
                )
                and mutual_similarity >= TEXT_SUPPORT_MIN
                and mutual_similarity - _text_similarity(negative, baseline)
                >= TEXT_SUPPORT_MARGIN
                and mutual_similarity - _text_similarity(positive, baseline)
                >= TEXT_SUPPORT_MARGIN
            ):
                selected_line = _choose_supported_variant(negative, positive)
                selected_geometry = _safe_geometry(selected_line)
                decisions.append(
                    {
                        "action": "replace",
                        "baseline": baseline.get("text"),
                        "selected": selected_line.get("text"),
                        "reason": "two-variant-support",
                        "y_min": selected_geometry[0],
                        "y_max": selected_geometry[1],
                    }
                )
        elif negative_index is None and positive_index is None:
            geometry = _safe_geometry(baseline)
            confidence = _confidence(baseline)
            if (
                body is not None
                and geometry is not None
                and len(_collapsed_text(baseline)) <= PHANTOM_MAX_CHARS
                and confidence is not None
                and confidence <= PHANTOM_MAX_CONFIDENCE
                and not _overlaps_or_touches_body(geometry, body)
            ):
                decisions.append(
                    {
                        "action": "suppress",
                        "baseline": baseline.get("text"),
                        "selected": None,
                        "reason": "unsupported-isolated-phantom",
                        "y_min": geometry[0],
                        "y_max": geometry[1],
                    }
                )
                continue

        selected.append(selected_line)

    if body is not None:
        for negative_index, positive_index in negative_to_positive.items():
            negative = negative_lines[negative_index]
            positive = positive_lines[positive_index]
            negative_geometry = _safe_geometry(negative)
            positive_geometry = _safe_geometry(positive)
            negative_confidence = _confidence(negative)
            positive_confidence = _confidence(positive)
            if (
                negative_geometry is not None
                and positive_geometry is not None
                and _text_similarity(negative, positive) >= TEXT_SUPPORT_MIN
                and negative_confidence is not None
                and positive_confidence is not None
                and negative_confidence >= _OCR_CONFIDENCE_FLOOR
                and positive_confidence >= _OCR_CONFIDENCE_FLOOR
                and _overlaps_or_touches_body(negative_geometry, body)
                and _overlaps_or_touches_body(positive_geometry, body)
            ):
                selected_line = _choose_supported_variant(negative, positive)
                selected_geometry = _safe_geometry(selected_line)
                selected.append(selected_line)
                decisions.append(
                    {
                        "action": "add",
                        "baseline": None,
                        "selected": selected_line.get("text"),
                        "reason": "two-variant-missing-line",
                        "y_min": selected_geometry[0],
                        "y_max": selected_geometry[1],
                    }
                )

    safely_positioned = []
    unsafe_baseline = []
    baseline_ids = {id(line) for line in baseline_lines}
    for original_position, line in enumerate(selected):
        geometry = _safe_geometry(line)
        if geometry is not None:
            safely_positioned.append((geometry[2], original_position, line))
        elif id(line) in baseline_ids:
            unsafe_baseline.append((original_position, line))
    safely_positioned.sort(key=lambda item: (item[0], item[1]))
    unsafe_baseline.sort(key=lambda item: item[0])
    return (
        [line for _center, _position, line in safely_positioned]
        + [line for _position, line in unsafe_baseline],
        decisions,
    )
