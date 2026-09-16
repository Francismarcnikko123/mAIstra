from collections.abc import Iterator
from typing import Any

import tree_sitter_c
from tree_sitter import Language, Node, Parser


C_LANGUAGE = Language(tree_sitter_c.language())
C_PARSER = Parser(C_LANGUAGE)

ARITHMETIC_OPERATORS = {"+", "-", "*", "/", "%"}


def node_text(node: Node, source: bytes) -> str:
    """Return the source-code text represented by a syntax node."""
    return source[node.start_byte:node.end_byte].decode(
        "utf-8",
        errors="replace",
    )


def walk_tree(node: Node) -> Iterator[Node]:
    """Yield a node followed by all of its descendants."""
    yield node

    for child in node.children:
        yield from walk_tree(child)


def find_declarator_identifier(node: Node, source: bytes) -> str | None:
    """Follow nested C declarators until their identifier is reached."""
    current: Node | None = node

    while current is not None:
        if current.type == "identifier":
            return node_text(current, source)

        current = current.child_by_field_name("declarator")

    return None


def binary_operator(node: Node, source: bytes) -> str | None:
    """Return the operator between a binary expression's operands."""
    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")

    if left is None or right is None:
        return None

    return source[left.end_byte:right.start_byte].decode(
        "utf-8",
        errors="replace",
    ).strip()


def extract_logic_features(code: str) -> dict[str, Any]:
    """Parse C code and return the features currently used for grading."""
    source = (code or "").encode("utf-8")
    root = C_PARSER.parse(source).root_node

    defined_functions: set[str] = set()
    called_functions: set[str] = set()
    arithmetic_operators: set[str] = set()

    has_assignment = False
    has_return = False

    for node in walk_tree(root):
        node_type = node.type

        if node_type == "function_definition":
            declarator = node.child_by_field_name("declarator")
            if declarator is not None:
                function_name = find_declarator_identifier(declarator, source)
                if function_name:
                    defined_functions.add(function_name)

        elif node_type == "call_expression":
            function = node.child_by_field_name("function")
            if function is not None and function.type == "identifier":
                called_functions.add(node_text(function, source))

        elif node_type in {"assignment_expression", "init_declarator"}:
            has_assignment = True

        elif node_type == "binary_expression":
            operator = binary_operator(node, source)
            if operator in ARITHMETIC_OPERATORS:
                arithmetic_operators.add(operator)

        elif node_type == "return_statement":
            has_return = True

    return {
        "has_main": "main" in defined_functions,
        "has_printf": "printf" in called_functions,
        "has_scanf": "scanf" in called_functions,
        "has_assignment": has_assignment,
        "uses_addition": "+" in arithmetic_operators,
        "uses_subtraction": "-" in arithmetic_operators,
        "uses_multiplication": "*" in arithmetic_operators,
        "uses_division": "/" in arithmetic_operators,
        "uses_modulo": "%" in arithmetic_operators,
        "has_return": has_return,
        "defined_functions": sorted(defined_functions),
    }


def compare_logic(model_code: str, student_code: str) -> dict[str, Any]:
    """Compare the existing safe structural checks used by the UI."""
    model = extract_logic_features(model_code)
    student = extract_logic_features(student_code)
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, weight: int) -> None:
        checks.append({
            "name": name,
            "passed": passed,
            "weight": weight,
            "score": weight if passed else 0,
        })

    if model["has_main"]:
        add_check("Has main function", student["has_main"], 10)
    if model["has_printf"]:
        add_check("Has output statement", student["has_printf"], 10)
    if model["has_scanf"]:
        add_check("Reads input", student["has_scanf"], 10)
    if model["has_assignment"]:
        add_check("Uses assignment", student["has_assignment"], 10)
    if model["uses_addition"]:
        add_check("Uses addition operator", student["uses_addition"], 10)
    if model["uses_subtraction"]:
        add_check("Uses subtraction operator", student["uses_subtraction"], 10)
    if model["uses_multiplication"]:
        add_check(
            "Uses multiplication operator",
            student["uses_multiplication"],
            10,
        )
    if model["uses_division"]:
        add_check("Uses division operator", student["uses_division"], 10)
    if model["uses_modulo"]:
        add_check("Uses modulo operator", student["uses_modulo"], 10)
    if model["has_return"]:
        add_check("Returns a value", student["has_return"], 10)

    required_functions = set(model["defined_functions"]) - {"main"}
    student_functions = set(student["defined_functions"])
    for function_name in sorted(required_functions):
        add_check(
            f"Defines required function: {function_name}",
            function_name in student_functions,
            20,
        )

    total_weight = sum(check["weight"] for check in checks)
    earned_score = sum(check["score"] for check in checks)
    score = (
        round((earned_score / total_weight) * 100, 2)
        if total_weight
        else 100.0
    )

    return {
        "score": score,
        "checks": checks,
    }
