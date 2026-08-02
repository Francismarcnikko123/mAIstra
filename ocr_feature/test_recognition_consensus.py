import copy
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from recognition_consensus import (
    BASELINE_RECOGNITION,
    CONSENSUS_RECOGNITION,
    DEFAULT_RECOGNITION_CONFIG,
    BODY_GAP_MULTIPLIER,
    PHANTOM_MAX_CHARS,
    PHANTOM_MAX_CONFIDENCE,
    RecognitionConfig,
    TEXT_SUPPORT_MARGIN,
    TEXT_SUPPORT_MIN,
    create_candidate_views,
    select_consensus_lines,
)


LINE_FIXTURE = {
    "text": "int main()",
    "members": [("int main()", 0.90)],
    "scores": [0.90],
    "mean_confidence": 0.90,
    "y_min": 0.20,
    "y_max": 0.24,
}


def line(text="int main()", confidence=0.90, y_min=0.20, y_max=0.24):
    fixture = copy.deepcopy(LINE_FIXTURE)
    fixture.update({
        "text": text,
        "members": [(text, confidence)],
        "scores": [confidence],
        "mean_confidence": confidence,
        "y_min": y_min,
        "y_max": y_max,
    })
    return fixture


class CandidateViewTests(unittest.TestCase):
    def test_recognition_configs_have_explicit_modes_and_angles(self):
        self.assertEqual(BASELINE_RECOGNITION.mode, "baseline")
        self.assertEqual(CONSENSUS_RECOGNITION.mode, "consensus")
        self.assertEqual(CONSENSUS_RECOGNITION.angles, (-0.5, 0.5))
        self.assertEqual(DEFAULT_RECOGNITION_CONFIG, BASELINE_RECOGNITION)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            RecognitionConfig(mode="unexpected")

    def test_invalid_angle_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "angles"):
            RecognitionConfig(angles=(-0.5,))

    def test_non_finite_or_non_numeric_angles_are_rejected(self):
        invalid_angles = (
            "0.5",
            float("nan"),
            float("inf"),
            float("-inf"),
            True,
            10**10000,
        )

        for index, invalid_angle in enumerate(invalid_angles):
            with self.subTest(index=index, value_type=type(invalid_angle).__name__):
                with self.assertRaisesRegex(ValueError, "angles"):
                    RecognitionConfig(angles=(-0.5, invalid_angle))

    def test_create_candidate_views_rotates_pngs_without_changing_source(self):
        image = np.full((40, 80), 255, dtype=np.uint8)
        cv2.line(image, (9, 7), (62, 17), 0, 2)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "page.png"
            output_dir = temp_path / "candidates"
            self.assertTrue(cv2.imwrite(str(source_path), image))
            source_bytes = source_path.read_bytes()
            source_image = cv2.imread(str(source_path), cv2.IMREAD_GRAYSCALE)

            candidates = create_candidate_views(
                source_path, output_dir, CONSENSUS_RECOGNITION
            )

            self.assertEqual([name for name, _path in candidates], ["rotate_neg", "rotate_pos"])
            self.assertEqual(len(candidates), 2)
            self.assertEqual(
                [path.name for _name, path in candidates],
                ["page_rotate_neg.png", "page_rotate_pos.png"],
            )
            expected_by_name = {}
            for name, angle in (("rotate_neg", -0.5), ("rotate_pos", 0.5)):
                matrix = cv2.getRotationMatrix2D((40, 20), angle, 1.0)
                expected_by_name[name] = cv2.warpAffine(
                    source_image,
                    matrix,
                    (80, 40),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=255,
                )

            for name, path in candidates:
                self.assertEqual(path.suffix, ".png")
                generated = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                self.assertIsNotNone(generated)
                self.assertEqual(generated.shape, source_image.shape)
                self.assertEqual(int(generated[0, 0]), 255)
                self.assertTrue(np.array_equal(generated, expected_by_name[name]))

            self.assertEqual(source_path.read_bytes(), source_bytes)
            self.assertTrue(
                np.array_equal(
                    cv2.imread(str(source_path), cv2.IMREAD_GRAYSCALE), source_image
                )
            )

    def test_baseline_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "page.png"
            self.assertTrue(
                cv2.imwrite(str(source_path), np.full((40, 80), 255, dtype=np.uint8))
            )

            with self.assertRaisesRegex(ValueError, "consensus"):
                create_candidate_views(
                    source_path,
                    Path(temp_dir) / "candidates",
                    BASELINE_RECOGNITION,
                )

    def test_unreadable_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "missing.png"
            with self.assertRaisesRegex(ValueError, "unreadable"):
                create_candidate_views(
                    source_path,
                    Path(temp_dir) / "candidates",
                    CONSENSUS_RECOGNITION,
                )


class ConsensusLineSelectionTests(unittest.TestCase):
    def test_thresholds_are_named_and_pinned(self):
        self.assertEqual(TEXT_SUPPORT_MIN, 0.90)
        self.assertEqual(TEXT_SUPPORT_MARGIN, 0.04)
        self.assertEqual(PHANTOM_MAX_CHARS, 2)
        self.assertEqual(PHANTOM_MAX_CONFIDENCE, 0.60)
        self.assertEqual(BODY_GAP_MULTIPLIER, 1.5)

    def test_two_variants_replace_baseline_with_supported_reading(self):
        baseline = [line("return o;", 0.72)]
        negative = [line("return 0;", 0.93)]
        positive = [line("return 0;", 0.91)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, negative)
        self.assertIs(selected[0], negative[0])
        self.assertEqual(decisions, [{
            "action": "replace",
            "baseline": "return o;",
            "selected": "return 0;",
            "reason": "two-variant-support",
            "y_min": 0.20,
            "y_max": 0.24,
        }])

    def test_one_variant_cannot_override_baseline(self):
        baseline = [line("return o;", 0.72)]
        negative = [line("return 0;", 0.93)]

        selected, decisions = select_consensus_lines(baseline, negative, [])

        self.assertEqual(selected, baseline)
        self.assertIs(selected[0], baseline[0])
        self.assertEqual(decisions, [])

    def test_unsafe_variant_confidence_cannot_override_baseline(self):
        baseline = [line("return o;", 0.72)]
        negative = [line("return 0;", None)]
        positive = [line("return 0;", 0.91)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_out_of_domain_variant_confidence_cannot_override_baseline(self):
        for confidence in (-0.01, 1.01):
            with self.subTest(confidence=confidence):
                baseline = [line("return o;", 0.72)]
                negative = [line("return 0;", confidence)]
                positive = [line("return 0;", 0.91)]

                selected, decisions = select_consensus_lines(
                    baseline, negative, positive
                )

                self.assertEqual(selected, baseline)
                self.assertIs(selected[0], baseline[0])
                self.assertEqual(decisions, [])

    def test_conflicting_three_way_readings_keep_baseline(self):
        baseline = [line("return o;", 0.72)]
        negative = [line("return 0;", 0.93)]
        positive = [line("return O;", 0.94)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_variants_on_opposite_edges_of_tall_baseline_cannot_replace(self):
        baseline = [line("return o;", 0.72, 0.20, 0.40)]
        negative = [line("return 0;", 0.93, 0.15, 0.21)]
        positive = [line("return 0;", 0.91, 0.39, 0.45)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertIs(selected[0], baseline[0])
        self.assertEqual(decisions, [])

    def test_incoherent_variant_triplet_cannot_anchor_supported_body(self):
        baseline = [
            line("'", 0.35, 0.01, 0.02),
            line("return o;", 0.72, 0.20, 0.40),
        ]
        negative = [line("return 0;", 0.93, 0.15, 0.21)]
        positive = [line("return 0;", 0.91, 0.39, 0.45)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_empty_or_non_string_variant_text_cannot_replace_baseline(self):
        for candidate_text in ("", "   ", None):
            with self.subTest(candidate_type=type(candidate_text).__name__):
                baseline = [line("return o;", 0.72)]
                negative = [line(candidate_text, 0.93)]
                positive = [line(candidate_text, 0.91)]

                selected, decisions = select_consensus_lines(
                    baseline, negative, positive
                )

                self.assertEqual(selected, baseline)
                self.assertIs(selected[0], baseline[0])
                self.assertEqual(decisions, [])

    def test_two_variant_agreement_without_required_margin_keeps_baseline(self):
        baseline = [line('printf("value=%d", values);', 0.72)]
        negative = [line('printf("value=%d", value);', 0.93)]
        positive = [line('printf("value=%d", value);', 0.94)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_whitespace_is_collapsed_and_negative_wins_confidence_tie(self):
        baseline = [line("return o;", 0.72)]
        negative = [line("return  0;", 0.91)]
        positive = [line("return\t0;", 0.91)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, negative)
        self.assertIs(selected[0], negative[0])
        self.assertEqual(decisions[0]["selected"], "return  0;")

    def test_inserted_top_variant_phantom_does_not_shift_later_alignment(self):
        baseline = [
            line("int main()", 0.90, 0.20, 0.24),
            line("return 0;", 0.88, 0.28, 0.32),
        ]
        negative = [
            line("'", 0.35, 0.01, 0.02),
            line("int main()", 0.92, 0.20, 0.24),
            line("return 0;", 0.91, 0.28, 0.32),
        ]
        positive = [
            line("int main()", 0.91, 0.20, 0.24),
            line("return 0;", 0.90, 0.28, 0.32),
        ]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_aligned_isolated_brace_is_preserved_at_low_confidence(self):
        baseline = [line("}", 0.45, 0.40, 0.44)]
        negative = [line("}", 0.48, 0.40, 0.44)]
        positive = [line("}", 0.47, 0.40, 0.44)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertIs(selected[0], baseline[0])
        self.assertEqual(decisions, [])

    def test_isolated_top_phantom_is_suppressed(self):
        baseline = [
            line("'", 0.35, 0.01, 0.02),
            line("int main()", 0.90, 0.20, 0.24),
            line("return 0;", 0.88, 0.28, 0.32),
        ]
        negative = [
            line("int main()", 0.92, 0.20, 0.24),
            line("return 0;", 0.91, 0.28, 0.32),
        ]
        positive = [
            line("int main()", 0.91, 0.20, 0.24),
            line("return 0;", 0.90, 0.28, 0.32),
        ]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline[1:])
        self.assertEqual(decisions, [{
            "action": "suppress",
            "baseline": "'",
            "selected": None,
            "reason": "unsupported-isolated-phantom",
            "y_min": 0.01,
            "y_max": 0.02,
        }])

    def test_two_variants_add_missing_line_at_inclusive_body_boundary(self):
        baseline = [line("int main()", 0.90, 0.20, 0.24)]
        negative = [
            line("int main()", 0.92, 0.20, 0.24),
            line("return 0;", 0.91, 0.30, 0.34),
        ]
        positive = [
            line("int main()", 0.91, 0.20, 0.24),
            line("return 0;", 0.90, 0.30, 0.34),
        ]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, [baseline[0], negative[1]])
        self.assertIs(selected[1], negative[1])
        self.assertEqual(decisions, [{
            "action": "add",
            "baseline": None,
            "selected": "return 0;",
            "reason": "two-variant-missing-line",
            "y_min": 0.30,
            "y_max": 0.34,
        }])

    def test_sparse_supported_anchors_do_not_admit_distant_added_line(self):
        baseline = [
            line("int main()", 0.90, 0.30, 0.34),
            line("}", 0.88, 0.70, 0.74),
        ]
        negative = [
            line("'", 0.91, 0.01, 0.03),
            line("int main()", 0.92, 0.30, 0.34),
            line("}", 0.91, 0.70, 0.74),
        ]
        positive = [
            line("'", 0.90, 0.01, 0.03),
            line("int main()", 0.91, 0.30, 0.34),
            line("}", 0.90, 0.70, 0.74),
        ]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_malformed_or_missing_geometry_keeps_baseline_unchanged(self):
        for y_min, y_max in ((None, None), (0.30, 0.20), (float("nan"), 0.20)):
            with self.subTest(y_min=y_min, y_max=y_max):
                baseline = [line("return o;", 0.72, y_min, y_max)]
                negative = [line("return 0;", 0.93, y_min, y_max)]
                positive = [line("return 0;", 0.91, y_min, y_max)]

                selected, decisions = select_consensus_lines(
                    baseline, negative, positive
                )

                self.assertEqual(selected, baseline)
                self.assertIs(selected[0], baseline[0])
                self.assertEqual(decisions, [])

    def test_one_unsafe_baseline_geometry_fails_closed_without_reordering(self):
        baseline = [
            line("int main()", 0.90, 0.10, 0.14),
            line("unsafe middle", 0.80, None, None),
            line("return 0;", 0.88, 0.30, 0.34),
        ]
        negative = [
            line("int main()", 0.92, 0.10, 0.14),
            line("return 0;", 0.91, 0.30, 0.34),
        ]
        positive = [
            line("int main()", 0.91, 0.10, 0.14),
            line("return 0;", 0.90, 0.30, 0.34),
        ]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(
            [id(selected_line) for selected_line in selected],
            [id(baseline_line) for baseline_line in baseline],
        )
        self.assertEqual(decisions, [])

    def test_huge_integer_geometry_keeps_baseline_unchanged(self):
        huge = 10**10000
        for y_min, y_max in ((huge, huge + 1), (0.20, huge)):
            with self.subTest(y_min_is_huge=y_min == huge):
                baseline = [line("return o;", 0.72, y_min, y_max)]
                negative = [line("return 0;", 0.93)]
                positive = [line("return 0;", 0.91)]

                selected, decisions = select_consensus_lines(
                    baseline, negative, positive
                )

                self.assertEqual(selected, baseline)
                self.assertIs(selected[0], baseline[0])
                self.assertEqual(decisions, [])

    def test_huge_integer_confidence_keeps_baseline_unchanged(self):
        huge = 10**10000
        baseline = [line("return o;", 0.72)]
        negative = [line("return 0;", huge)]
        positive = [line("return 0;", 0.91)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertIs(selected[0], baseline[0])
        self.assertEqual(decisions, [])

    def test_short_low_confidence_line_inside_supported_body_is_preserved(self):
        baseline = [
            line("int main()", 0.90, 0.20, 0.24),
            line(";", 0.35, 0.25, 0.27),
            line("return 0;", 0.88, 0.28, 0.32),
        ]
        negative = [
            line("int main()", 0.92, 0.20, 0.24),
            line("return 0;", 0.91, 0.28, 0.32),
        ]
        positive = [
            line("int main()", 0.91, 0.20, 0.24),
            line("return 0;", 0.90, 0.28, 0.32),
        ]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_high_confidence_line_outside_supported_body_is_preserved(self):
        baseline = [
            line("x", 0.85, 0.01, 0.02),
            line("int main()", 0.90, 0.20, 0.24),
            line("return 0;", 0.88, 0.28, 0.32),
        ]
        negative = [
            line("int main()", 0.92, 0.20, 0.24),
            line("return 0;", 0.91, 0.28, 0.32),
        ]
        positive = [
            line("int main()", 0.91, 0.20, 0.24),
            line("return 0;", 0.90, 0.28, 0.32),
        ]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_unmatched_single_variant_line_is_not_added(self):
        baseline = [line("int main()", 0.90, 0.20, 0.24)]
        negative = [
            line("int main()", 0.92, 0.20, 0.24),
            line("return 0;", 0.91, 0.30, 0.34),
        ]
        positive = [line("int main()", 0.91, 0.20, 0.24)]

        selected, decisions = select_consensus_lines(baseline, negative, positive)

        self.assertEqual(selected, baseline)
        self.assertEqual(decisions, [])

    def test_inputs_are_not_mutated(self):
        baseline = [
            line("'", 0.35, 0.01, 0.02),
            line("int main()", 0.90, 0.20, 0.24),
        ]
        negative = [
            line("int main()", 0.92, 0.20, 0.24),
            line("return 0;", 0.91, 0.30, 0.34),
        ]
        positive = [
            line("int main()", 0.91, 0.20, 0.24),
            line("return 0;", 0.90, 0.30, 0.34),
        ]
        original = copy.deepcopy((baseline, negative, positive))

        select_consensus_lines(baseline, negative, positive)

        self.assertEqual((baseline, negative, positive), original)


if __name__ == "__main__":
    unittest.main()
