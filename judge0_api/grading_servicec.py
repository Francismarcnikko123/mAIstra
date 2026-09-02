from logic_checker import compare_logic
from output_checker import compare_output


def grade_submission(
    model_code: str,
    student_code: str,
    expected_output: str,
    actual_output: str,
    compilation_passed: bool,
) -> dict:
    """
    Final grading formula:

    50% logic similarity
    40% output correctness
    10% compilation
    """

    compilation_score = 100 if compilation_passed else 0

    logic_result = compare_logic(model_code, student_code)
    output_result = compare_output(expected_output, actual_output)

    final_score = (
        logic_result["score"] * 0.50
        + output_result["score"] * 0.40
        + compilation_score * 0.10
    )

    return {
        "final_score": round(final_score, 2),
        "compilation_score": compilation_score,
        "logic_score": logic_result["score"],
        "output_score": output_result["score"],
        "logic_details": logic_result["checks"],
        "output_details": output_result,
    }