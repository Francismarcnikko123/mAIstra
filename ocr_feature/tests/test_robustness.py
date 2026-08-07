# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_robustness
import unittest

import cv2
import numpy as np

from evaluators.robustness import TRANSFORMS, apply_transform


def make_test_page(channels=3):
    shape = (80, 120) if channels == 1 else (80, 120, channels)
    page = np.full(shape, 255, dtype=np.uint8)
    color = 0 if channels == 1 else (0, 0, 0)
    cv2.putText(
        page,
        "int x;",
        (8, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2,
    )
    return page


class RobustnessTests(unittest.TestCase):
    def test_each_transform_is_deterministic_and_preserves_source(self):
        source = make_test_page()
        original = source.copy()

        for name in TRANSFORMS:
            with self.subTest(name=name):
                first = apply_transform(source, name, seed=20260802)
                second = apply_transform(source, name, seed=20260802)
                self.assertEqual(first.shape, source.shape)
                self.assertEqual(first.dtype, source.dtype)
                self.assertTrue(np.array_equal(first, second))
                self.assertFalse(np.shares_memory(first, source))

        self.assertTrue(np.array_equal(source, original))

    def test_transforms_support_grayscale_images(self):
        source = make_test_page(channels=1)

        for name in TRANSFORMS:
            with self.subTest(name=name):
                transformed = apply_transform(source, name)
                self.assertEqual(transformed.shape, source.shape)
                self.assertEqual(transformed.dtype, np.uint8)

    def test_unknown_transform_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown robustness transform"):
            apply_transform(make_test_page(), "unknown", seed=1)

    def test_non_uint8_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "uint8"):
            apply_transform(make_test_page().astype(np.float32), "mild_blur")


if __name__ == "__main__":
    unittest.main()
