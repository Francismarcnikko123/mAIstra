from pathlib import Path

import cv2


def preprocess_image(image_path: str, output_dir: str = "outputs") -> str:
    """Preprocess an image for OCR, writing the result to output_dir and
    returning its path."""

    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image file: {image_path}")

    # Cap resolution -- beyond this the OCR model downsamples internally
    # anyway, so paying denoise/detect cost for it is wasted.
    max_side = 1600
    height, width = img.shape[:2]
    longest_side = max(height, width)

    if longest_side > max_side:
        scale = max_side / longest_side
        img = cv2.resize(
            img,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    processed = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        15,
    )

    output_path = output_dir / f"{image_path.stem}_preprocessed.jpg"

    cv2.imwrite(str(output_path), processed)

    return str(output_path)