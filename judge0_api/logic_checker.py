import re


def remove_comments(code: str) -> str:
    """Remove C single-line and multi-line comments."""
    code = re.sub(r"//.*", "", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return code


def normalize_code(code: str) -> str:
    """Make C code easier to compare."""
    code = remove_comments(code)
    code = code.lower()
    code = re.sub(r"\s+", " ", code)
    return code.strip()


def extract_logic_features(code: str) -> dict:
    """
    Extract simple logic features from C code.

    This does not require exact variable names.
    It checks what the code is doing.
    """
    normalized = normalize_code(code)

    numbers = re.findall(r"\b\d+\b", normalized)

    features = {
        "has_main": "main" in normalized,
        "has_printf": "printf" in normalized,
        "has_scanf": "scanf" in normalized,
        "has_assignment": "=" in normalized,
        "uses_addition": "+" in normalized,
        "uses_subtraction": "-" in normalized,
        "uses_multiplication": "*" in normalized,
        "uses_division": "/" in normalized,
        "has_return": "return" in normalized,
        "numbers": set(numbers),
    }

    return features


def compare_logic(model_code: str, student_code: str) -> dict:
    model = extract_logic_features(model_code)
    student = extract_logic_features(student_code)

    checks = []

    def add_check(name: str, passed: bool, weight: int):
        checks.append({
            "name": name,
            "passed": passed,
            "weight": weight,
            "score": weight if passed else 0,
        })

    add_check("Has main function", student["has_main"], 10)
    add_check("Has output statement", student["has_printf"], 10)
    add_check("Uses assignment", student["has_assignment"], 15)

    if model["uses_addition"]:
        add_check("Uses addition operator", student["uses_addition"], 25)

    if model["uses_subtraction"]:
        add_check("Uses subtraction operator", student["uses_subtraction"], 25)

    if model["uses_multiplication"]:
        add_check("Uses multiplication operator", student["uses_multiplication"], 25)

    if model["uses_division"]:
        add_check("Uses division operator", student["uses_division"], 25)

    # Check if important numeric constants from model answer appear in student answer
    model_numbers = model["numbers"]
    student_numbers = student["numbers"]

    if model_numbers:
        same_numbers = model_numbers.issubset(student_numbers)
        add_check("Uses required numeric values", same_numbers, 25)

    total_weight = sum(check["weight"] for check in checks)
    earned_score = sum(check["score"] for check in checks)

    score = round((earned_score / total_weight) * 100, 2) if total_weight else 0

    return {
        "score": score,
        "checks": checks,
        "model_features": model,
        "student_features": student,
    }