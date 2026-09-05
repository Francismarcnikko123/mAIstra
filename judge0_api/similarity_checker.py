from __future__ import annotations

from dataclasses import dataclass, replace
from difflib import SequenceMatcher
import hashlib
from typing import Any, Sequence

from tree_sitter import Node, Point

from logic_checker import C_PARSER, find_declarator_identifier, node_text, walk_tree


_ATOMIC_LITERAL_TYPES = {"char_literal", "string_literal"}
K_GRAM_SIZE = 5
WINNOW_WINDOW_SIZE = 4
MIN_MATCH_TOKENS = 12
REVIEW_COVERAGE_THRESHOLD = 0.60


@dataclass(frozen=True)
class SourcePoint:
    row: int
    column: int


@dataclass(frozen=True)
class SourceRange:
    start: SourcePoint
    end: SourcePoint


@dataclass(frozen=True)
class NormalizedToken:
    value: str
    original: str
    kind: str
    source_range: SourceRange
    excluded: bool = False


@dataclass(frozen=True)
class NormalizedProgram:
    tokens: tuple[NormalizedToken, ...]
    comparison_segments: tuple[tuple[NormalizedToken, ...], ...]
    has_parse_errors: bool
    parse_error_ranges: tuple[SourceRange, ...]


@dataclass(frozen=True)
class Fingerprint:
    hash_value: int
    token_index: int


@dataclass(frozen=True)
class PreparedProgram:
    source: str
    normalized: NormalizedProgram
    fingerprints: tuple[Fingerprint, ...]
    comparable_token_count: int


@dataclass(frozen=True)
class _MatchingBlock:
    left_indexes: tuple[int, ...]
    right_indexes: tuple[int, ...]
    left_range: SourceRange
    right_range: SourceRange

    @property
    def length(self) -> int:
        return len(self.left_indexes)


@dataclass(frozen=True)
class _FunctionScope:
    start_byte: int
    end_byte: int
    replacements: dict[str, str]


def _source_point(point: Point) -> SourcePoint:
    return SourcePoint(row=point.row, column=point.column)


def _source_range(node: Node) -> SourceRange:
    return SourceRange(
        start=_source_point(node.start_point),
        end=_source_point(node.end_point),
    )


def _is_inside_skipped_node(node: Node) -> bool:
    current: Node | None = node
    while current is not None:
        if current.type in {"comment", "preproc_include"}:
            return True
        current = current.parent
    return False


def _is_inside_atomic_literal(node: Node) -> bool:
    current = node.parent
    while current is not None:
        if current.type in _ATOMIC_LITERAL_TYPES:
            return True
        current = current.parent
    return False


def _declared_names(node: Node, source: bytes) -> list[str]:
    names: list[str] = []
    for declarator in node.children_by_field_name("declarator"):
        name = find_declarator_identifier(declarator, source)
        if name:
            names.append(name)
    return names


def _function_scopes(root: Node, source: bytes) -> tuple[_FunctionScope, ...]:
    scopes: list[_FunctionScope] = []

    for function in (
        node for node in walk_tree(root) if node.type == "function_definition"
    ):
        replacements: dict[str, str] = {}
        declarator = function.child_by_field_name("declarator")
        body = function.child_by_field_name("body")

        parameter_names: list[str] = []
        if declarator is not None:
            for node in walk_tree(declarator):
                if node.type == "parameter_declaration":
                    parameter_names.extend(_declared_names(node, source))

        for name in parameter_names:
            if name not in replacements:
                replacements[name] = f"PARAM_{len(replacements) + 1}"

        local_count = 0
        if body is not None:
            for node in walk_tree(body):
                if node.type != "declaration":
                    continue
                for name in _declared_names(node, source):
                    if name in replacements:
                        continue
                    local_count += 1
                    replacements[name] = f"LOCAL_{local_count}"

        scopes.append(
            _FunctionScope(
                start_byte=function.start_byte,
                end_byte=function.end_byte,
                replacements=replacements,
            )
        )

    return tuple(scopes)


def _replacement_for_identifier(
    node: Node,
    original: str,
    scopes: tuple[_FunctionScope, ...],
) -> str:
    for scope in scopes:
        if scope.start_byte <= node.start_byte and node.end_byte <= scope.end_byte:
            return scope.replacements.get(original, original)
    return original


def _tokenize(code: str) -> tuple[
    tuple[NormalizedToken, ...],
    bool,
    tuple[SourceRange, ...],
]:
    source = (code or "").encode("utf-8")
    root = C_PARSER.parse(source).root_node
    scopes = _function_scopes(root, source)
    tokens: list[NormalizedToken] = []

    for node in walk_tree(root):
        is_atomic_literal = node.type in _ATOMIC_LITERAL_TYPES
        if (
            (node.child_count and not is_atomic_literal)
            or node.is_missing
            or _is_inside_skipped_node(node)
            or _is_inside_atomic_literal(node)
        ):
            continue

        original = node_text(node, source)
        if not original:
            continue

        value = (
            _replacement_for_identifier(node, original, scopes)
            if node.type == "identifier"
            else original
        )
        tokens.append(
            NormalizedToken(
                value=value,
                original=original,
                kind=node.type,
                source_range=_source_range(node),
            )
        )

    parse_errors = tuple(
        _source_range(node)
        for node in walk_tree(root)
        if node.type == "ERROR" or node.is_missing
    )
    if root.has_error and not parse_errors:
        parse_errors = (_source_range(root),)

    return tuple(tokens), root.has_error, parse_errors


def _starter_token_indexes(
    student_tokens: tuple[NormalizedToken, ...],
    starter_tokens: tuple[NormalizedToken, ...],
) -> set[int]:
    if not starter_tokens or len(starter_tokens) > len(student_tokens):
        return set()

    student_values = tuple(token.value for token in student_tokens)
    starter_values = tuple(token.value for token in starter_tokens)
    excluded: set[int] = set()
    index = 0

    while index <= len(student_values) - len(starter_values):
        end = index + len(starter_values)
        if student_values[index:end] == starter_values:
            excluded.update(range(index, end))
            index = end
        else:
            index += 1

    return excluded


def _comparison_segments(
    tokens: tuple[NormalizedToken, ...],
) -> tuple[tuple[NormalizedToken, ...], ...]:
    segments: list[tuple[NormalizedToken, ...]] = []
    current: list[NormalizedToken] = []

    for token in tokens:
        if token.excluded:
            if current:
                segments.append(tuple(current))
                current = []
        else:
            current.append(token)

    if current:
        segments.append(tuple(current))

    return tuple(segments)


def normalize_c_code(code: str, starter_code: str = "") -> NormalizedProgram:
    """Normalize comparable C tokens while retaining source evidence."""
    tokens, has_parse_errors, parse_error_ranges = _tokenize(code)

    if starter_code.strip():
        starter_tokens, _, _ = _tokenize(starter_code)
        excluded_indexes = _starter_token_indexes(tokens, starter_tokens)
        tokens = tuple(
            replace(token, excluded=True) if index in excluded_indexes else token
            for index, token in enumerate(tokens)
        )

    return NormalizedProgram(
        tokens=tokens,
        comparison_segments=_comparison_segments(tokens),
        has_parse_errors=has_parse_errors,
        parse_error_ranges=parse_error_ranges,
    )


def stable_kgram_hash(values: Sequence[str]) -> int:
    """Return a process-independent digest for one normalized token k-gram."""
    digest = hashlib.blake2b(digest_size=8)
    for value in values:
        encoded = value.encode("utf-8", errors="replace")
        digest.update(len(encoded).to_bytes(4, byteorder="big"))
        digest.update(encoded)
    return int.from_bytes(digest.digest(), byteorder="big")


def winnow_fingerprints(
    values: Sequence[str],
    *,
    k_gram_size: int = K_GRAM_SIZE,
    window_size: int = WINNOW_WINDOW_SIZE,
) -> tuple[Fingerprint, ...]:
    """Select the rightmost minimum hash from each Winnowing window."""
    if k_gram_size <= 0 or window_size <= 0:
        raise ValueError("Winnowing sizes must be positive")
    if len(values) < k_gram_size:
        return ()

    hashes = [
        stable_kgram_hash(values[index : index + k_gram_size])
        for index in range(len(values) - k_gram_size + 1)
    ]
    effective_window = min(window_size, len(hashes))
    selected: list[Fingerprint] = []
    seen: set[tuple[int, int]] = set()

    for start in range(len(hashes) - effective_window + 1):
        window = hashes[start : start + effective_window]
        minimum = min(window)
        relative_index = max(
            index for index, value in enumerate(window) if value == minimum
        )
        token_index = start + relative_index
        key = (minimum, token_index)
        if key not in seen:
            selected.append(
                Fingerprint(hash_value=minimum, token_index=token_index)
            )
            seen.add(key)

    return tuple(selected)


def _program_fingerprints(
    program: NormalizedProgram,
) -> tuple[Fingerprint, ...]:
    token_indexes = {id(token): index for index, token in enumerate(program.tokens)}
    fingerprints: list[Fingerprint] = []

    for segment in program.comparison_segments:
        values = [token.value for token in segment]
        for fingerprint in winnow_fingerprints(values):
            fingerprints.append(
                Fingerprint(
                    hash_value=fingerprint.hash_value,
                    token_index=token_indexes[id(segment[fingerprint.token_index])],
                )
            )

    return tuple(fingerprints)


def prepare_c_code(code: str, starter_code: str = "") -> PreparedProgram:
    normalized = normalize_c_code(code, starter_code=starter_code)
    return PreparedProgram(
        source=code or "",
        normalized=normalized,
        fingerprints=_program_fingerprints(normalized),
        comparable_token_count=sum(
            len(segment) for segment in normalized.comparison_segments
        ),
    )


def _range_for_tokens(tokens: Sequence[NormalizedToken]) -> SourceRange:
    return SourceRange(
        start=tokens[0].source_range.start,
        end=tokens[-1].source_range.end,
    )


def _range_dict(source_range: SourceRange) -> dict[str, dict[str, int]]:
    return {
        "start": {
            "row": source_range.start.row,
            "column": source_range.start.column,
        },
        "end": {
            "row": source_range.end.row,
            "column": source_range.end.column,
        },
    }


def _matching_blocks(
    left: PreparedProgram,
    right: PreparedProgram,
) -> tuple[_MatchingBlock, ...]:
    common_hashes = {fingerprint.hash_value for fingerprint in left.fingerprints} & {
        fingerprint.hash_value for fingerprint in right.fingerprints
    }
    if not common_hashes:
        return ()

    left_global_indexes = {
        id(token): index for index, token in enumerate(left.normalized.tokens)
    }
    right_global_indexes = {
        id(token): index for index, token in enumerate(right.normalized.tokens)
    }
    candidates: list[_MatchingBlock] = []

    for left_segment in left.normalized.comparison_segments:
        left_fingerprints = winnow_fingerprints(
            [token.value for token in left_segment]
        )
        left_hashes = {fingerprint.hash_value for fingerprint in left_fingerprints}
        if not left_hashes & common_hashes:
            continue

        for right_segment in right.normalized.comparison_segments:
            right_fingerprints = winnow_fingerprints(
                [token.value for token in right_segment]
            )
            right_hashes = {
                fingerprint.hash_value for fingerprint in right_fingerprints
            }
            if not left_hashes & right_hashes:
                continue

            matcher = SequenceMatcher(
                None,
                [token.value for token in left_segment],
                [token.value for token in right_segment],
                autojunk=False,
            )
            for block in matcher.get_matching_blocks():
                if block.size < MIN_MATCH_TOKENS:
                    continue
                left_tokens = left_segment[block.a : block.a + block.size]
                right_tokens = right_segment[block.b : block.b + block.size]
                candidates.append(
                    _MatchingBlock(
                        left_indexes=tuple(
                            left_global_indexes[id(token)] for token in left_tokens
                        ),
                        right_indexes=tuple(
                            right_global_indexes[id(token)] for token in right_tokens
                        ),
                        left_range=_range_for_tokens(left_tokens),
                        right_range=_range_for_tokens(right_tokens),
                    )
                )

    selected: list[_MatchingBlock] = []
    used_left: set[int] = set()
    used_right: set[int] = set()
    for block in sorted(
        candidates,
        key=lambda candidate: (
            -candidate.length,
            candidate.left_indexes[0],
            candidate.right_indexes[0],
        ),
    ):
        if used_left.intersection(block.left_indexes) or used_right.intersection(
            block.right_indexes
        ):
            continue
        selected.append(block)
        used_left.update(block.left_indexes)
        used_right.update(block.right_indexes)

    return tuple(sorted(selected, key=lambda block: block.left_indexes[0]))


def _duplicate_ranges(
    program: PreparedProgram,
) -> list[dict[str, dict[str, int]]]:
    return [
        _range_dict(_range_for_tokens(segment))
        for segment in program.normalized.comparison_segments
        if segment
    ]


def compare_c_code(
    left: str | PreparedProgram,
    right: str | PreparedProgram,
    starter_code: str = "",
) -> dict[str, Any]:
    """Compare two verified C programs and return review evidence."""
    left_program = (
        left if isinstance(left, PreparedProgram) else prepare_c_code(left, starter_code)
    )
    right_program = (
        right
        if isinstance(right, PreparedProgram)
        else prepare_c_code(right, starter_code)
    )
    left_values = tuple(
        token.value
        for segment in left_program.normalized.comparison_segments
        for token in segment
    )
    right_values = tuple(
        token.value
        for segment in right_program.normalized.comparison_segments
        for token in segment
    )
    has_parse_errors = (
        left_program.normalized.has_parse_errors
        or right_program.normalized.has_parse_errors
    )
    analysis_state = "partial_analysis" if has_parse_errors else "complete"
    duplicate = bool(left_values) and left_values == right_values

    if duplicate:
        match_type = (
            "exact_duplicate"
            if left_program.source.strip() == right_program.source.strip()
            else "normalized_duplicate"
        )
        matched_token_count = len(left_values)
        left_coverage = 1.0
        right_coverage = 1.0
        left_ranges = _duplicate_ranges(left_program)
        right_ranges = _duplicate_ranges(right_program)
        review_recommended = True
    else:
        blocks = _matching_blocks(left_program, right_program)
        matched_token_count = sum(block.length for block in blocks)
        left_coverage = (
            matched_token_count / left_program.comparable_token_count
            if left_program.comparable_token_count
            else 0.0
        )
        right_coverage = (
            matched_token_count / right_program.comparable_token_count
            if right_program.comparable_token_count
            else 0.0
        )
        left_ranges = [_range_dict(block.left_range) for block in blocks]
        right_ranges = [_range_dict(block.right_range) for block in blocks]
        review_recommended = (
            matched_token_count >= MIN_MATCH_TOKENS
            and max(left_coverage, right_coverage) >= REVIEW_COVERAGE_THRESHOLD
        )

        if review_recommended:
            match_type = "similar_code"
        elif has_parse_errors:
            match_type = "partial_analysis"
        elif (
            min(
                left_program.comparable_token_count,
                right_program.comparable_token_count,
            )
            < MIN_MATCH_TOKENS
        ):
            match_type = "insufficient_evidence"
        else:
            match_type = "no_match"

    return {
        "match_type": match_type,
        "review_recommended": review_recommended,
        "matched_token_count": matched_token_count,
        "left_coverage": round(left_coverage, 4),
        "right_coverage": round(right_coverage, 4),
        "left_ranges": left_ranges,
        "right_ranges": right_ranges,
        "analysis_state": analysis_state,
        "left_token_count": left_program.comparable_token_count,
        "right_token_count": right_program.comparable_token_count,
    }
