# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_evaluation
import unittest

from evaluators.evaluation import (
    cer,
    edit_distance,
    edit_operations,
    evaluate_text_pair,
    evaluate_word_token_pair,
    literal_provenance_issues,
    normalize_ws,
    suggestion_improves_reference,
    summarize_metrics,
    token_accuracy,
    tokenize_c,
    wer,
)


class EvaluationTests(unittest.TestCase):
    def test_literal_provenance_accepts_explicit_true_with_audit_fields(self):
        issues = literal_provenance_issues([{
            "filename": "page.png",
            "literal_verified": " TRUE ",
            "literal_verified_by": "human-reviewer",
            "literal_verified_at": "2026-08-02",
        }])

        self.assertEqual(issues, [])

    def test_literal_provenance_rejects_non_true_and_blank_audit_fields(self):
        issues = literal_provenance_issues([{
            "filename": "page.png",
            "literal_verified": "yes",
            "literal_verified_by": "",
            "literal_verified_at": None,
        }])

        self.assertEqual(len(issues), 3)
        self.assertIn("literal_verified must be true", issues[0])
        self.assertIn("literal_verified_by is required", issues[1])
        self.assertIn("literal_verified_at is required", issues[2])

    def test_edit_operations_for_exact_match_are_all_zero(self):
        self.assertEqual(
            edit_operations("int", "int"),
            {"insertions": 0, "deletions": 0, "substitutions": 0},
        )

    def test_edit_operations_counts_extra_prediction_characters_as_insertions(self):
        self.assertEqual(
            edit_operations("' int", "int"),
            {"insertions": 2, "deletions": 0, "substitutions": 0},
        )

    def test_edit_operations_counts_missing_prediction_characters_as_deletions(self):
        self.assertEqual(
            edit_operations("retun", "return"),
            {"insertions": 0, "deletions": 1, "substitutions": 0},
        )

    def test_edit_operations_counts_wrong_characters_as_substitutions(self):
        self.assertEqual(
            edit_operations("return o;", "return 0;"),
            {"insertions": 0, "deletions": 0, "substitutions": 1},
        )

    def test_edit_operations_prefers_substitutions_over_insertions_and_deletions(self):
        self.assertEqual(
            edit_operations("ab", "ba"),
            {"insertions": 0, "deletions": 0, "substitutions": 2},
        )

    def test_edit_operations_prefers_insertions_over_deletions_on_ties(self):
        self.assertEqual(
            edit_operations("abab", "baaba"),
            {"insertions": 1, "deletions": 2, "substitutions": 0},
        )

    def test_edit_distance_handles_insert_delete_and_replace(self):
        self.assertEqual(edit_distance("kitten", "sitting"), 3)
        self.assertEqual(edit_distance("", "abc"), 3)
        self.assertEqual(edit_distance("same", "same"), 0)

    def test_cer_handles_empty_reference(self):
        self.assertEqual(cer("", ""), 0.0)
        self.assertEqual(cer("x", ""), 1.0)

    def test_normalize_ws_collapses_all_whitespace(self):
        self.assertEqual(normalize_ws("  int\n\tx  "), "int x")

    def test_evaluate_text_pair_reports_all_four_metrics(self):
        metrics = evaluate_text_pair("int  x", "int x", "int  x")

        self.assertEqual(
            set(metrics), {"raw", "clean", "raw_ws", "clean_ws"}
        )
        self.assertEqual(metrics["raw"], 0.0)
        self.assertEqual(metrics["raw_ws"], 0.0)

    def test_summarize_metrics_groups_by_metadata(self):
        rows = [
            {
                "paper_type": "bond",
                "metrics": {"raw": 0.2, "clean_ws": 0.1},
            },
            {
                "paper_type": "bond",
                "metrics": {"raw": 0.4, "clean_ws": 0.3},
            },
            {
                "paper_type": "greenbook",
                "metrics": {"raw": 0.6, "clean_ws": 0.5},
            },
        ]

        summary = summarize_metrics(rows, "paper_type")

        self.assertAlmostEqual(summary["bond"]["raw"], 0.3)
        self.assertAlmostEqual(summary["bond"]["clean_ws"], 0.2)
        self.assertAlmostEqual(summary["greenbook"]["raw"], 0.6)
        self.assertNotIn("clean", summary["bond"])

    def test_summarize_metrics_uses_unknown_for_missing_metadata(self):
        summary = summarize_metrics(
            [{"metrics": {"clean_ws": 0.25}}], "paper_type"
        )

        self.assertEqual(summary, {"unknown": {"clean_ws": 0.25}})

    def test_summarize_metrics_ignores_empty_input(self):
        self.assertEqual(summarize_metrics([], "paper_type"), {})

    def test_suggestion_improves_reference_without_mutating_raw_text(self):
        raw = 'printe("x");\nreturn 0;'
        suggestion = {
            "line": 1,
            "start": 0,
            "end": 6,
            "original": "printe",
            "candidate": "printf",
        }

        helpful = suggestion_improves_reference(
            raw,
            'printf("x");\nreturn 0;',
            suggestion,
        )

        self.assertTrue(helpful)
        self.assertEqual(raw, 'printe("x");\nreturn 0;')

    def test_suggestion_that_does_not_improve_reference_is_rejected(self):
        suggestion = {
            "line": 1,
            "start": 0,
            "end": 6,
            "original": "printe",
            "candidate": "printf",
        }

        self.assertFalse(suggestion_improves_reference(
            'printe("x");',
            'printe("x");',
            suggestion,
        ))

    def test_suggestion_with_invalid_location_is_rejected(self):
        suggestion = {
            "line": 3,
            "start": 0,
            "end": 6,
            "original": "printe",
            "candidate": "printf",
        }

        self.assertFalse(suggestion_improves_reference(
            'printe("x");',
            'printf("x");',
            suggestion,
        ))

    def test_wer_counts_whole_word_errors(self):
        self.assertEqual(wer("int main", "int main"), 0.0)
        # one of two words wrong
        self.assertEqual(wer("int mian", "int main"), 0.5)

    def test_wer_ignores_spacing_since_split_collapses_whitespace(self):
        # Extra/leading/trailing whitespace must not create phantom tokens.
        self.assertEqual(wer("  int   main  ", "int main"), 0.0)

    def test_wer_empty_reference_boundaries(self):
        self.assertEqual(wer("", ""), 0.0)
        self.assertEqual(wer("x", ""), 1.0)

    def test_tokenize_c_is_insensitive_to_operator_spacing(self):
        self.assertEqual(tokenize_c("x=5"), tokenize_c("x = 5"))
        self.assertEqual(tokenize_c("x=5"), ["x", "=", "5"])

    def test_tokenize_c_keeps_multichar_operators_whole(self):
        self.assertEqual(tokenize_c("a<<=b"), ["a", "<<=", "b"])
        self.assertEqual(tokenize_c("i++"), ["i", "++"])

    def test_tokenize_c_keeps_string_literals_atomic(self):
        # A brace inside a string must not become its own token.
        self.assertEqual(tokenize_c('printf("hi {}")'),
                         ["printf", "(", '"hi {}"', ")"])

    def test_token_accuracy_perfect_and_spacing_invariant(self):
        self.assertEqual(token_accuracy("int x = 5;", "int x = 5;"), 1.0)
        # Spacing difference alone must still score a perfect 1.0.
        self.assertEqual(token_accuracy("int x=5;", "int x = 5;"), 1.0)

    def test_token_accuracy_one_wrong_token_of_five(self):
        # tokens: int x = 5 ; -> one substituted, 4/5 correct.
        self.assertAlmostEqual(
            token_accuracy("int x = S;", "int x = 5;"), 0.8
        )

    def test_token_accuracy_empty_reference_boundaries(self):
        self.assertEqual(token_accuracy("", ""), 1.0)
        self.assertEqual(token_accuracy("x", ""), 0.0)

    def test_evaluate_word_token_pair_returns_all_four_keys(self):
        metrics = evaluate_word_token_pair("int x", "int x", "int x")
        self.assertEqual(
            set(metrics),
            {"raw_wer", "clean_wer", "raw_token_accuracy", "clean_token_accuracy"},
        )
        self.assertEqual(metrics["raw_wer"], 0.0)
        self.assertEqual(metrics["raw_token_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
