import unittest

from c_code_suggestions import suggest_c_code


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

    def test_suggests_a_canonical_known_header(self):
        suggestions = suggest_c_code(" include <std1o.n>")

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["candidate"], "#include <stdio.h>")
        self.assertEqual(suggestions[0]["rule_id"], "known-header")

    def test_suggests_narrow_known_c_token_confusions(self):
        suggestions = suggest_c_code("1nt ma1n() { retvrn 0; }")

        pairs = [
            (item["original"], item["candidate"]) for item in suggestions
        ]
        self.assertEqual(
            pairs,
            [("1nt", "int"), ("ma1n", "main"), ("retvrn", "return")],
        )

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


if __name__ == "__main__":
    unittest.main()
