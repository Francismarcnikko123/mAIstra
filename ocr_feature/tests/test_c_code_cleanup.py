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
