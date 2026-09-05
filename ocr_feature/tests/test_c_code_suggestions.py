# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_c_code_suggestions
import unittest

from core.c_code_suggestions import suggest_c_code


class CCodeSuggestionTests(unittest.TestCase):
    def test_suggests_printf_only_when_misspelling_is_used_as_a_call(self):
        suggestions = suggest_c_code('printe("x");')

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["original"], "printe")
        self.assertEqual(suggestions[0]["candidate"], "printf")
        self.assertEqual(suggestions[0]["rule_id"], "function-call-printf")

        self.assertEqual(suggest_c_code("int printe = 0;"), [])

    def test_ignores_tokens_inside_string_and_character_literals(self):
        text = 'printf("printe(1nt)"); char *s = \'ma1n\';'

        suggestions = suggest_c_code(text)

        self.assertEqual(suggestions, [])

    def test_reports_stable_line_and_character_locations(self):
        text = "int x;\n  printe(\"x\");"

        suggestion = suggest_c_code(text)[0]

        self.assertEqual(suggestion["line"], 2)
        self.assertEqual(suggestion["start"], 2)
        self.assertEqual(suggestion["end"], 8)
        self.assertEqual(text.splitlines()[1][2:8], "printe")

    def test_does_not_suggest_keywords_or_headers_owned_by_cleanup(self):
        # Keyword and #include fixes are the safe, auto-applied vocabulary of
        # c_code_cleanup.py. This module must not also propose them, or the
        # same fix would surface twice.
        self.assertEqual(suggest_c_code("1nt ma1n() { retvrn 0; }"), [])
        self.assertEqual(suggest_c_code(" include <std1o.n>"), [])

    def test_does_not_modify_input_or_guess_at_ordinary_identifiers(self):
        text = "int printf_count = 0; int printe = 1;"

        suggestions = suggest_c_code(text)

        self.assertEqual(text, "int printf_count = 0; int printe = 1;")
        self.assertEqual(suggestions, [])

    def test_uses_valid_line_confidence_and_ignores_malformed_context(self):
        details = [
            {"line": 1, "mean_confidence": 0.91},
            {"line": 2, "mean_confidence": "bad"},
        ]

        suggestions = suggest_c_code("printe();\nscant();", details)

        self.assertEqual(suggestions[0]["confidence"], 0.91)
        self.assertIsNone(suggestions[1]["confidence"])

    def test_empty_input_returns_no_suggestions(self):
        self.assertEqual(suggest_c_code(""), [])

    def test_flags_misread_word_inside_a_message_literal(self):
        # A word inside the printed message that is one edit from a common
        # word is flagged for the teacher to compare with the paper. It is a
        # flag, never an edit, and the reason must not assert the OCR is wrong
        # (it could be the student's own spelling).
        suggestions = suggest_c_code('printf("Please enter a valind number");')

        literal = [s for s in suggestions if s["rule_id"] == "literal-word-misread"]
        self.assertEqual(len(literal), 1)
        self.assertEqual(literal[0]["original"], "valind")
        self.assertEqual(literal[0]["candidate"], "valid")
        self.assertIn("OCR misread or the student", literal[0]["reason"])

    def test_does_not_flag_correct_or_distant_message_words(self):
        # Correct words and words that are NOT within one edit of a common
        # word are left alone -- no false positives on ordinary messages.
        self.assertEqual(
            [
                s
                for s in suggest_c_code('printf("enter a five digit number");')
                if s["rule_id"] == "literal-word-misread"
            ],
            [],
        )

    def test_message_word_check_never_touches_code_identifiers(self):
        # `valind` as a bare identifier in code (not in a literal) is the
        # student's variable name and must never be flagged as a message typo.
        suggestions = suggest_c_code("int valind = 0;")
        self.assertEqual(
            [s for s in suggestions if s["rule_id"] == "literal-word-misread"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
