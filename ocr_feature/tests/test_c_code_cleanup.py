# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_c_code_cleanup
import unittest

from core.c_code_cleanup import clean_c_code


class CCodeCleanupTests(unittest.TestCase):
    def test_preserves_string_and_character_literals(self):
        text = 'printf("pr1ntf"); char digit = \'1\';'

        self.assertEqual(clean_c_code(text), text)

    def test_preserves_ordinary_identifiers(self):
        text = "int pr1ntf_count = 0; int printe = 1;"

        self.assertEqual(clean_c_code(text), text)

    def test_normalizes_known_headers(self):
        self.assertEqual(
            clean_c_code("include <std1o.n>"),
            "#include <stdio.h>",
        )

    def test_corrects_only_known_whole_tokens(self):
        self.assertEqual(clean_c_code("1nt ma1n()"), "int main()")
        self.assertEqual(clean_c_code("my1nt ma1n_value"), "my1nt ma1n_value")

    def test_preserves_float_suffixes_and_digit_tokens_inside_expressions(self):
        text = "float x = 1.1f;\ny = b-1f + 0.1f;"

        self.assertEqual(clean_c_code(text), text)

    def test_still_fixes_digit_misreads_at_statement_start(self):
        self.assertEqual(clean_c_code("{1f (x) return;"), "{if (x) return;")
        self.assertEqual(clean_c_code("f(1nt a, 1nt b)"), "f(int a, int b)")

    def test_cleanup_is_idempotent(self):
        once = clean_c_code("#inc1ude <std1o.n>\n1nt ma1n()")

        self.assertEqual(clean_c_code(once), once)

    def test_preserves_a_genuine_student_mistake_without_a_known_rule(self):
        text = 'printe("x"); return o;'

        self.assertEqual(clean_c_code(text), text)

    def test_preserves_empty_input_and_line_structure(self):
        self.assertEqual(clean_c_code(""), "")
        self.assertEqual(clean_c_code("\n\n"), "\n\n")


if __name__ == "__main__":
    unittest.main()
