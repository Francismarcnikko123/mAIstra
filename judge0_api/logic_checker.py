from collections.abc import Iterator
from typing import Any

import tree_sitter_c
from tree_sitter import Language, Node, Parser


C_LANGUAGE = Language(tree_sitter_c.language())
C_PARSER = Parser(C_LANGUAGE)

ARITHMETIC_OPERATORS = {"+", "-", "*", "/", "%"}
COMPARISON_OPERATORS = {"==", "!=", "<", "<=", ">", ">="}
LOGICAL_OPERATORS = {"&&", "||"}


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


def unary_operator(node: Node, source: bytes) -> str | None:
    """Return the operator before a unary expression's argument."""
    argument = node.child_by_field_name("argument")

    if argument is None:
        return None

    return source[node.start_byte:argument.start_byte].decode(
        "utf-8",
        errors="replace",
    ).strip()


def extract_logic_features(code: str) -> dict[str, Any]:
    """Parse C code and return beginner-level structural features."""
    source = (code or "").encode("utf-8")
    root = C_PARSER.parse(source).root_node

    defined_functions: set[str] = set()
    called_functions: set[str] = set()
    numeric_literals: set[str] = set()
    arithmetic_operators: set[str] = set()
    comparison_operators: set[str] = set()
    logical_operators: set[str] = set()

    has_variable_declaration = False
    has_assignment = False
    has_return = False
    has_if = False
    has_else = False
    has_switch = False
    has_case = False
    has_for_loop = False
    has_while_loop = False
    has_do_while_loop = False
    has_break = False
    has_continue = False
    uses_increment = False
    uses_decrement = False
    uses_logical_not = False
    has_array_declaration = False
    has_array_access = False

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

        elif node_type == "declaration":
            has_variable_declaration = True

        elif node_type in {"assignment_expression", "init_declarator"}:
            has_assignment = True

        elif node_type == "binary_expression":
            operator = binary_operator(node, source)
            if operator in ARITHMETIC_OPERATORS:
                arithmetic_operators.add(operator)
            elif operator in COMPARISON_OPERATORS:
                comparison_operators.add(operator)
            elif operator in LOGICAL_OPERATORS:
                logical_operators.add(operator)

        elif node_type == "unary_expression":
            if unary_operator(node, source) == "!":
                uses_logical_not = True

        elif node_type == "update_expression":
            update_text = node_text(node, source)
            uses_increment = uses_increment or "++" in update_text
            uses_decrement = uses_decrement or "--" in update_text

        elif node_type == "return_statement":
            has_return = True

        elif node_type == "if_statement":
            has_if = True
            has_else = (
                has_else
                or node.child_by_field_name("alternative") is not None
            )

        elif node_type == "switch_statement":
            has_switch = True

        elif node_type == "case_statement":
            has_case = True

        elif node_type == "for_statement":
            has_for_loop = True

        elif node_type == "while_statement":
            has_while_loop = True

        elif node_type == "do_statement":
            has_do_while_loop = True

        elif node_type == "break_statement":
            has_break = True

        elif node_type == "continue_statement":
            has_continue = True

        elif node_type == "array_declarator":
            has_array_declaration = True

        elif node_type == "subscript_expression":
            has_array_access = True

        elif node_type == "number_literal":
            numeric_literals.add(node_text(node, source))

    return {
        "has_main": "main" in defined_functions,
        "has_variable_declaration": has_variable_declaration,
        "has_printf": "printf" in called_functions,
        "has_scanf": "scanf" in called_functions,
        "has_assignment": has_assignment,
        "uses_addition": "+" in arithmetic_operators,
        "uses_subtraction": "-" in arithmetic_operators,
        "uses_multiplication": "*" in arithmetic_operators,
        "uses_division": "/" in arithmetic_operators,
        "uses_modulo": "%" in arithmetic_operators,
        "uses_comparison": bool(comparison_operators),
        "comparison_operators": sorted(comparison_operators),
        "uses_logical_and": "&&" in logical_operators,
        "uses_logical_or": "||" in logical_operators,
        "uses_logical_not": uses_logical_not,
        "has_return": has_return,
        "has_if": has_if,
        "has_else": has_else,
        "has_switch": has_switch,
        "has_case": has_case,
        "has_for_loop": has_for_loop,
        "has_while_loop": has_while_loop,
        "has_do_while_loop": has_do_while_loop,
        "has_loop": has_for_loop or has_while_loop or has_do_while_loop,
        "has_break": has_break,
        "has_continue": has_continue,
        "uses_increment": uses_increment,
        "uses_decrement": uses_decrement,
        "has_array_declaration": has_array_declaration,
        "has_array_access": has_array_access,
        "has_parse_errors": root.has_error,
        "defined_functions": sorted(defined_functions),
        "called_functions": sorted(called_functions),
        "numbers": sorted(numeric_literals),
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
        "model_features": model,
        "student_features": student,
    }
