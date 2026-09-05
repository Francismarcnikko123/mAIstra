from similarity_checker import normalize_c_code


def token_values(program):
    return [token.value for token in program.tokens if not token.excluded]


def test_comments_and_formatting_do_not_change_comparable_tokens():
    compact = "int add(int a,int b){return a+b;}"
    formatted = """
    int add(int a, int b) {
        /* Keep the addition readable. */
        return a + b; // result
    }
    """

    assert token_values(normalize_c_code(compact)) == token_values(
        normalize_c_code(formatted)
    )


def test_literals_function_names_operators_and_library_calls_are_preserved():
    program = normalize_c_code(
        'int main(void) { int answer = 42; printf("value=%d", answer); return answer + 1; }'
    )
    values = token_values(program)

    assert "main" in values
    assert "printf" in values
    assert '"value=%d"' in values
    assert "42" in values
    assert "1" in values
    assert "+" in values


def test_parameters_and_locals_use_stable_function_scoped_placeholders():
    left = normalize_c_code(
        "int add(int first, int second) { int total = first + second; return total; }"
    )
    right = normalize_c_code(
        "int add(int x, int y) { int result = x + y; return result; }"
    )

    assert token_values(left) == token_values(right)
    assert "PARAM_1" in token_values(left)
    assert "PARAM_2" in token_values(left)
    assert "LOCAL_1" in token_values(left)


def test_each_token_retains_its_original_source_range():
    program = normalize_c_code("int main(void) {\n  return 7;\n}")
    return_token = next(token for token in program.tokens if token.value == "return")

    assert return_token.source_range.start.row == 1
    assert return_token.source_range.start.column == 2
    assert return_token.source_range.end.column == 8
    assert return_token.original == "return"


def test_starter_code_is_excluded_without_removing_similar_student_logic():
    starter = "int helper(void) { return 7; }"
    student = """
    int helper(void) { return 7; }
    int independent(void) { return 7; }
    """

    program = normalize_c_code(student, starter_code=starter)
    excluded_values = [token.value for token in program.tokens if token.excluded]
    remaining_values = token_values(program)

    assert excluded_values == token_values(normalize_c_code(starter))
    assert "helper" not in remaining_values
    assert "independent" in remaining_values
    assert "7" in remaining_values
    assert all(
        not token.excluded
        for segment in program.comparison_segments
        for token in segment
    )


def test_parse_errors_are_reported_with_source_locations():
    program = normalize_c_code("int main(void) { int total =")

    assert program.has_parse_errors is True
    assert program.parse_error_ranges
    assert program.parse_error_ranges[0].start.row >= 0
