# Library module, not runnable on its own (no __main__) -- imported by
# evaluate_robustness.py. Run that instead.
"""Deterministic image transforms for OCR robustness diagnostics."""

import cv2
import numpy as np


TRANSFORMS = (
    "mild_blur",
    "shadow",
    "texture",
    "show_through",
    "mild_rotation",
)


def _shadow(image: np.ndarray) -> np.ndarray:
    width = image.shape[1]
    shape = (1, width) if image.ndim == 2 else (1, width, 1)
    shade = np.linspace(0.72, 1.0, width, dtype=np.float32).reshape(shape)
    return np.clip(image.astype(np.float32) * shade, 0, 255).astype(np.uint8)


def _texture(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 4.0, image.shape).astype(np.float32)
    return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def _show_through(image: np.ndarray) -> np.ndarray:
    mirrored = cv2.flip(image, 1)
    blurred = cv2.GaussianBlur(mirrored, (9, 9), 0).astype(np.float32)
    ghost = 255.0 - (255.0 - blurred) * 0.12
    return np.minimum(image.astype(np.float32), ghost).astype(np.uint8)


def _mild_rotation(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), 1.5, 1.0)
    border = 255 if image.ndim == 2 else (255, 255, 255)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border,
    )


def apply_transform(
    image: np.ndarray,
    name: str,
    seed: int = 20260802,
) -> np.ndarray:
    """Return a deterministic transformed copy of a uint8 page image."""
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError("image must be a uint8 array")
    if image.ndim not in (2, 3):
        raise ValueError("image must be grayscale or color")

    source = image.copy()
    rng = np.random.default_rng(seed)

    if name == "mild_blur":
        return cv2.GaussianBlur(source, (3, 3), 0)
    if name == "shadow":
        return _shadow(source)
    if name == "texture":
        return _texture(source, rng)
    if name == "show_through":
        return _show_through(source)
    if name == "mild_rotation":
        return _mild_rotation(source)
    raise ValueError(f"unknown robustness transform: {name}")
