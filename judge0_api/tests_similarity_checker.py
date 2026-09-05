import os
from pathlib import Path
import subprocess
import sys

from similarity_checker import (
    compare_c_code,
    normalize_c_code,
    prepare_c_code,
    stable_kgram_hash,
    winnow_fingerprints,
)


FIXTURES = Path(__file__).parent / "tests" / "fixtures" / "similarity"


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


def test_nested_shadowing_is_equivalent_to_consistent_lexical_renaming():
    left = "int f(int x) { { int x=3; x++; } return x; }"
    right = "int f(int a) { { int b=3; b++; } return a; }"

    result = compare_c_code(left, right)

    assert result["match_type"] == "normalized_duplicate"
    assert result["left_coverage"] == 1.0


def test_local_declarations_do_not_rename_earlier_global_references():
    program = normalize_c_code(
        "int value; int f(void) { int saved=value; { int value=3; value++; } return saved; }"
    )
    values = [token.value for token in program.tokens if token.original == "value"]

    assert values == ["value", "value", "LOCAL_2", "LOCAL_2"]


def test_for_initializer_binding_ends_at_the_end_of_its_loop():
    left = "int f(int i) { for (int i=0; i<3; i++) {} return i; }"
    right = "int f(int x) { for (int j=0; j<3; j++) {} return x; }"

    assert token_values(normalize_c_code(left)) == token_values(normalize_c_code(right))


def test_function_declarations_and_type_names_are_preserved():
    program = normalize_c_code(
        "int f(int x) { typedef int Count; int helper(int x); Count result=helper(x); return result; }"
    )

    assert [token.value for token in program.tokens if token.original == "helper"] == [
        "helper", "helper"
    ]
    assert [token.value for token in program.tokens if token.original == "Count"] == [
        "Count", "Count"
    ]
    assert [token.value for token in program.tokens if token.original == "x"] == [
        "PARAM_1", "x", "PARAM_1"
    ]


def test_function_pointer_variables_are_normalized_without_binding_prototype_names():
    left = "int f(int a) { int (*callback)(int a); callback=0; return a; }"
    right = "int f(int x) { int (*operation)(int a); operation=0; return x; }"

    assert token_values(normalize_c_code(left)) == token_values(normalize_c_code(right))


def test_declarator_array_bounds_use_the_preceding_binding():
    program = normalize_c_code("int f(int n) { { int n[n]; } return n; }")

    assert [token.value for token in program.tokens if token.original == "n"] == [
        "PARAM_1", "LOCAL_1", "PARAM_1", "PARAM_1"
    ]


def test_function_typed_parameters_bind_as_parameters_not_external_functions():
    left = "int f(int callback(int)) { return callback(1); }"
    right = "int f(int operation(int)) { return operation(1); }"

    assert token_values(normalize_c_code(left)) == token_values(normalize_c_code(right))


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


def test_starter_passages_are_excluded_when_student_logic_is_inserted():
    starter = (
        'int main(void) { int a=0,b=0; scanf("%d %d",&a,&b); '
        'printf("%d",a); return 0; }'
    )
    left = starter.replace("printf", "a=a+b; printf")
    right = starter.replace("printf", "a=a*b; printf")

    normalized = normalize_c_code(left, starter)
    result = compare_c_code(left, right, starter)

    assert sum(token.excluded for token in normalized.tokens) > 20
    assert "+" in token_values(normalized)
    assert result["review_recommended"] is False
    assert result["match_type"] == "insufficient_evidence"


def test_short_common_starter_fragments_do_not_erase_student_logic():
    student = "int answer(void) { return 0; }"

    program = normalize_c_code(student, "return 0;")

    assert not any(token.excluded for token in program.tokens)


def test_added_local_declarations_do_not_prevent_unchanged_starter_exclusion():
    starter = (
        'int main(void) { int a=0,b=0; scanf("%d %d",&a,&b); '
        'printf("%d",a); return 0; }'
    )
    student = starter.replace("int a", "int extra=1; int a")

    program = normalize_c_code(student, starter)

    assert sum(token.excluded for token in program.tokens) >= 25
    assert "extra" in [token.original for token in program.tokens if not token.excluded]


def test_starter_alignment_does_not_remove_a_second_identical_student_passage():
    starter = "int helper(void) { return 7; }"
    student = starter + starter

    program = normalize_c_code(student, starter)

    assert sum(token.excluded for token in program.tokens) == len(
        normalize_c_code(starter).tokens
    )


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_exact_text_is_an_exact_duplicate_with_full_coverage():
    code = fixture("exact_a.c")

    result = compare_c_code(code, fixture("exact_b.c"))

    assert result["match_type"] == "exact_duplicate"
    assert result["review_recommended"] is True
    assert result["left_coverage"] == 1.0
    assert result["right_coverage"] == 1.0


def test_comment_and_format_only_changes_are_normalized_duplicates():
    left = "int add(int a,int b){return a+b;}"
    right = """
    int add(int a, int b) {
        // The same solution with different presentation.
        return a + b;
    }
    """

    result = compare_c_code(left, right)

    assert result["match_type"] == "normalized_duplicate"
    assert result["review_recommended"] is True
    assert result["matched_token_count"] == result["left_token_count"]


def test_consistent_local_renaming_produces_a_normalized_duplicate():
    result = compare_c_code(fixture("renamed_a.c"), fixture("renamed_b.c"))

    assert result["match_type"] == "normalized_duplicate"
    assert result["left_coverage"] == 1.0
    assert result["right_coverage"] == 1.0


def test_stable_kgram_hash_is_independent_of_python_hash_seed():
    expected = stable_kgram_hash(["int", "LOCAL_1", "=", "7", ";"])
    script = (
        "from similarity_checker import stable_kgram_hash; "
        "print(stable_kgram_hash(['int','LOCAL_1','=','7',';']))"
    )
    values = []
    for seed in ("1", "98765"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        values.append(
            int(
                subprocess.check_output(
                    [sys.executable, "-c", script],
                    cwd=Path(__file__).parent,
                    env=environment,
                    text=True,
                ).strip()
            )
        )

    assert values == [expected, expected]


def test_selected_fingerprints_are_stable_across_python_runs():
    script = (
        "from similarity_checker import winnow_fingerprints; "
        "values=['int','LOCAL_1','=','7',';','return','LOCAL_1',';']; "
        "print([(item.hash_value,item.token_index) for item in winnow_fingerprints(values)])"
    )
    outputs = []
    for seed in ("2", "24680"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        outputs.append(
            subprocess.check_output(
                [sys.executable, "-c", script],
                cwd=Path(__file__).parent,
                env=environment,
                text=True,
            ).strip()
        )

    assert outputs[0] == outputs[1]


def test_winnowing_chooses_the_rightmost_minimum_when_hashes_tie():
    fingerprints = winnow_fingerprints(["same"] * 12)

    assert [fingerprint.token_index for fingerprint in fingerprints] == [3, 4, 5, 6, 7]


def test_matching_blocks_do_not_overlap_or_double_count_tokens():
    result = compare_c_code(
        "int sum(int a, int b) { int value = a + b; return value + value; }",
        "int sum(int x, int y) { int total = x + y; return total + total; }",
    )

    assert result["matched_token_count"] <= result["left_token_count"]
    assert result["matched_token_count"] <= result["right_token_count"]
    left_ranges = result["left_ranges"]
    for previous, current in zip(left_ranges, left_ranges[1:]):
        assert (previous["end"]["row"], previous["end"]["column"]) <= (
            current["start"]["row"],
            current["start"]["column"],
        )


def test_copied_passage_has_separate_coverage_and_valid_source_ranges():
    left = """
    int shared(int first, int second) {
        int total = first + second;
        if (total > 10) { total = total - 1; }
        return total;
    }
    int only_left(void) { return 99; }
    """
    right = """
    int shared(int x, int y) {
        int result = x + y;
        if (result > 10) { result = result - 1; }
        return result;
    }
    """

    result = compare_c_code(left, right)

    assert result["match_type"] == "similar_code"
    assert result["left_coverage"] < result["right_coverage"]
    assert result["right_coverage"] >= 0.6
    assert result["left_ranges"]
    assert result["right_ranges"]
    assert result["left_ranges"][0]["start"]["row"] >= 0


def test_different_literals_reduce_matching_evidence():
    same = compare_c_code(
        "int score(void) { int a = 10; int b = 20; int c = 30; return a + b + c; }",
        "int score(void) { int x = 10; int y = 20; int z = 30; return x + y + z; }",
    )
    changed = compare_c_code(
        "int score(void) { int a = 10; int b = 20; int c = 30; return a + b + c; }",
        "int score(void) { int x = 91; int y = 82; int z = 73; return x + y + z; }",
    )

    assert changed["matched_token_count"] < same["matched_token_count"]


def test_starter_only_overlap_does_not_recommend_review():
    starter = fixture("starter.c")
    left = starter + "\nint left_answer(void) { return 1; }\n"
    right = starter + "\nint right_answer(void) { return 2; }\n"

    result = compare_c_code(left, right, starter_code=starter)

    assert result["review_recommended"] is False
    assert result["match_type"] == "insufficient_evidence"


def test_unrelated_correct_answers_remain_below_review_threshold():
    result = compare_c_code(
        fixture("independent_a.c"),
        fixture("independent_b.c"),
    )

    assert result["review_recommended"] is False
    assert max(result["left_coverage"], result["right_coverage"]) < 0.6


def test_short_non_duplicates_report_insufficient_evidence():
    result = compare_c_code("int first;", "int second;")

    assert result["match_type"] == "insufficient_evidence"
    assert result["analysis_state"] == "complete"


def test_parser_errors_return_partial_analysis_and_never_no_match():
    left = prepare_c_code("int main(void) { int total =")
    right = prepare_c_code("int main(void) { return 0; }")

    result = compare_c_code(left, right)

    assert result["analysis_state"] == "partial_analysis"
    assert result["match_type"] != "no_match"
