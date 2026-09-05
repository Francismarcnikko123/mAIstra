from __future__ import annotations

from dataclasses import dataclass, replace
from difflib import SequenceMatcher
import hashlib
from typing import Any, Sequence

from tree_sitter import Node, Point

try:
    from .logic_checker import (
        C_PARSER,
        node_text,
        walk_tree,
    )
except ImportError:
    from logic_checker import C_PARSER, node_text, walk_tree


_ATOMIC_LITERAL_TYPES = {"char_literal", "string_literal"}
K_GRAM_SIZE = 5
WINNOW_WINDOW_SIZE = 4
MIN_MATCH_TOKENS = 12
MIN_STARTER_MATCH_TOKENS = 8
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


def _declarator_chain(node: Node) -> tuple[Node, ...]:
    chain: list[Node] = []
    current: Node | None = node
    while current is not None:
        chain.append(current)
        nested = current.child_by_field_name("declarator")
        if nested is None and current.type == "parenthesized_declarator":
            nested = next(iter(current.named_children), None)
        current = nested
    return tuple(chain)


def _identifier_replacements(root: Node, source: bytes) -> dict[int, str]:
    """Resolve local references in source order, with block and loop scopes."""
    replacements: dict[int, str] = {}
    for function in (
        node for node in walk_tree(root) if node.type == "function_definition"
    ):
        scopes: list[dict[str, str]] = [{}]
        counts = {"PARAM": 0, "LOCAL": 0}

        def visit_declarator(node: Node, declared_name: Node) -> None:
            # Prototype parameter names do not bind names in the caller's body.
            if node == declared_name or node.type == "parameter_list":
                return
            if node.type == "identifier":
                visit(node)
                return
            for child in node.children:
                visit_declarator(child, declared_name)

        def declare(node: Node, prefix: str) -> None:
            initializer = node.child_by_field_name("value")
            core = (
                node.child_by_field_name("declarator")
                if node.type == "init_declarator"
                else node
            )
            if core is None:
                return
            chain = _declarator_chain(core)
            identifier = chain[-1]
            if identifier.type != "identifier":
                return
            # Array bounds precede the new binding, while its initializer follows
            # it. In `int n[n]`, the bound therefore resolves the outer n.
            visit_declarator(core, identifier)
            name = node_text(identifier, source)
            nearest_derived = next(
                (
                    part.type
                    for part in reversed(chain[:-1])
                    if part.type in {
                        "function_declarator", "pointer_declarator", "array_declarator"
                    }
                ),
                None,
            )
            if prefix == "LOCAL" and nearest_derived == "function_declarator":
                scopes[-1][name] = name
            else:
                counts[prefix] += 1
                replacement = f"{prefix}_{counts[prefix]}"
                replacements[identifier.start_byte] = replacement
                scopes[-1][name] = replacement
            if initializer is not None:
                visit(initializer)

        def visit(node: Node) -> None:
            if node.type in {"type_definition", "parameter_list", "function_definition"}:
                return
            if node.type in {"compound_statement", "for_statement"}:
                scopes.append({})
                for child in node.children:
                    visit(child)
                scopes.pop()
            elif node.type == "declaration":
                for declarator in node.children_by_field_name("declarator"):
                    declare(declarator, "LOCAL")
            elif node.type == "identifier":
                name = node_text(node, source)
                for scope in reversed(scopes):
                    if name in scope:
                        replacements[node.start_byte] = scope[name]
                        break
            else:
                for child in node.children:
                    visit(child)

        declarator = function.child_by_field_name("declarator")
        if declarator is not None:
            function_declarator = next(
                (node for node in reversed(_declarator_chain(declarator))
                 if node.type == "function_declarator"),
                None,
            )
            parameters = (
                function_declarator.child_by_field_name("parameters")
                if function_declarator is not None else None
            )
            if parameters is not None:
                for parameter in parameters.named_children:
                    if parameter.type == "parameter_declaration":
                        for node in parameter.children_by_field_name("declarator"):
                            declare(node, "PARAM")
        body = function.child_by_field_name("body")
        if body is not None:
            visit(body)

    return replacements


def _tokenize(code: str) -> tuple[
    tuple[NormalizedToken, ...],
    bool,
    tuple[SourceRange, ...],
]:
    source = (code or "").encode("utf-8")
    root = C_PARSER.parse(source).root_node
    replacements = _identifier_replacements(root, source)
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
            replacements.get(node.start_byte, original)
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
    if not starter_tokens or not student_tokens:
        return set()

    # Align the supplied sequence once so answers inserted into the template
    # leave separate starter passages, without erasing every repeated occurrence.
    # Original spellings handle added declarations shifting placeholder numbers;
    # normalized spellings handle consistent renaming of supplied variables.
    alignments: list[set[int]] = []
    for attribute in ("original", "value"):
        student_values = tuple(getattr(token, attribute) for token in student_tokens)
        starter_values = tuple(getattr(token, attribute) for token in starter_tokens)
        matcher = SequenceMatcher(None, starter_values, student_values, autojunk=False)
        excluded: set[int] = set()
        for block in matcher.get_matching_blocks():
            if block.size >= MIN_STARTER_MATCH_TOKENS:
                excluded.update(range(block.b, block.b + block.size))
        alignments.append(excluded)
    return max(alignments, key=len)


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
