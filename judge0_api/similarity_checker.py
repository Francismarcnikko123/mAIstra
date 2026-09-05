from __future__ import annotations

from dataclasses import dataclass, replace

from tree_sitter import Node, Point

from logic_checker import C_PARSER, find_declarator_identifier, node_text, walk_tree


_ATOMIC_LITERAL_TYPES = {"char_literal", "string_literal"}


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
