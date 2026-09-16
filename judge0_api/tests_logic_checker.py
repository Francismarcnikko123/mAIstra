from logic_checker import compare_logic, extract_logic_features


def check_names(result: dict) -> set[str]:
      """Return the names of the generated grading checks."""
      return {check["name"] for check in result["checks"]}


def test_distinguishes_comparison_from_assignment():
      code = """
      int main(void) {
          int a = 2;
          int b = 3;

          if (a == b) {
              a = a + b;
          }

          return 0;
      }
      """

      features = extract_logic_features(code)

      assert features["has_assignment"] is True
      assert features["uses_addition"] is True


def test_comparison_alone_is_not_an_assignment():
      code = """
      int equal(int a, int b) {
          return a == b;
      }
      """

      features = extract_logic_features(code)

      assert features["has_assignment"] is False
      assert features["uses_addition"] is False


def test_operators_inside_strings_are_not_treated_as_logic():
      code = """
      int main(void) {
          printf("a + b = 3");
          return 0;
      }
      """

      features = extract_logic_features(code)

      assert features["has_printf"] is True
      assert features["has_assignment"] is False
      assert features["uses_addition"] is False


def test_detects_defined_functions():
      code = """
      int add(int a, int b) {
          return a + b;
      }

      int main(void) {
          int result = add(2, 3);
          printf("%d", result);
          return 0;
      }
      """

      features = extract_logic_features(code)

      assert features["has_main"] is True
      assert "add" in features["defined_functions"]
      assert "main" in features["defined_functions"]


def test_exposes_only_features_used_by_grading():
      features = extract_logic_features(
          "int main(void) { printf(\"%d\", 8 / 2 + 3 - 1); return 0; }"
      )

      assert set(features) == {
          "has_main",
          "has_printf",
          "has_scanf",
          "has_assignment",
          "uses_addition",
          "uses_subtraction",
          "uses_multiplication",
          "uses_division",
          "uses_modulo",
          "has_return",
          "defined_functions",
      }


def test_pointer_declaration_is_not_multiplication():
      code = """
      int first_value(int *numbers) {
          return numbers[0];
      }
      """

      features = extract_logic_features(code)

      assert features["uses_multiplication"] is False


def test_compares_required_function_without_requiring_same_variables():
      model_code = """
      int add(int first, int second) {
          return first + second;
      }
      """

      student_code = """
      int add(int x, int y) {
          return x + y;
      }
      """

      result = compare_logic(model_code, student_code)

      assert result["score"] == 100
      assert "Defines required function: add" in check_names(result)


def test_numeric_constants_are_not_scored_as_required_logic():
      model_code = """
      int add_five(int value) {
          return value + 5;
      }
      """

      student_code = """
      int add_five(int value) {
          return value + (10 / 2);
      }
      """

      result = compare_logic(model_code, student_code)

      assert "Uses required numeric values" not in check_names(result)
