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
      assert features["has_if"] is True


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


def test_detects_functions_and_function_calls():
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
      assert "add" in features["called_functions"]
      assert "printf" in features["called_functions"]


def test_pointer_declaration_is_not_multiplication():
      code = """
      int first_value(int *numbers) {
          return numbers[0];
      }
      """

      features = extract_logic_features(code)

      assert features["uses_multiplication"] is False


def test_detects_control_flow():
      code = """
      int main(void) {
          int total = 0;

          for (int i = 0; i < 5; i++) {
              if (i > 2) {
                  total += i;
              }
          }

          return total;
      }
      """

      features = extract_logic_features(code)

      assert features["has_loop"] is True
      assert features["has_if"] is True
      assert features["has_assignment"] is True


def test_reports_parser_errors_for_incomplete_ocr_code():
      code = """
      int main(void) {
          int total =
      """

      features = extract_logic_features(code)

      assert features["has_parse_errors"] is True


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


def test_detects_a_declaration_without_treating_it_as_assignment():
      features = extract_logic_features("int main(void) { int value; return 0; }")

      assert features["has_variable_declaration"] is True
      assert features["has_assignment"] is False


def test_detects_else_comparisons_and_logical_operators():
      code = """
      int classify(int value, int limit) {
          if (value >= 0 && value != limit) {
              return 1;
          } else {
              return 0;
          }
      }
      """

      features = extract_logic_features(code)

      assert features["has_if"] is True
      assert features["has_else"] is True
      assert features["uses_comparison"] is True
      assert features["comparison_operators"] == ["!=", ">="]
      assert features["uses_logical_and"] is True


def test_detects_switch_case_and_break():
      code = """
      int label(int value) {
          switch (value) {
              case 1:
                  break;
              default:
                  return 0;
          }
          return 1;
      }
      """

      features = extract_logic_features(code)

      assert features["has_switch"] is True
      assert features["has_case"] is True
      assert features["has_break"] is True


def test_distinguishes_each_beginner_loop_type_and_continue():
      code = """
      int main(void) {
          for (int i = 0; i < 2; i++) { continue; }
          while (0) { break; }
          do { break; } while (0);
          return 0;
      }
      """

      features = extract_logic_features(code)

      assert features["has_for_loop"] is True
      assert features["has_while_loop"] is True
      assert features["has_do_while_loop"] is True
      assert features["has_loop"] is True
      assert features["has_continue"] is True


def test_detects_increment_decrement_and_logical_not():
      code = """
      int update(int value) {
          if (!value) { value++; }
          value--;
          return value;
      }
      """

      features = extract_logic_features(code)

      assert features["uses_increment"] is True
      assert features["uses_decrement"] is True
      assert features["uses_logical_not"] is True


def test_detects_array_declaration_and_access():
      code = """
      int first(void) {
          int values[2] = {4, 8};
          return values[0];
      }
      """

      features = extract_logic_features(code)

      assert features["has_array_declaration"] is True
      assert features["has_array_access"] is True
