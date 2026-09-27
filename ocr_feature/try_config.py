"""Run OCR on one photo, with or without adaptive denoising, and print the
text. A quick manual check; nothing imports it.

    python try_config.py                                  # default photo
    python try_config.py path/to/photo.jpg --adaptive-denoise
"""
import sys
from pathlib import Path

from core.preprocess import PreprocessConfig
from core.ocr_pipeline import extract_text_from_image

IMAGE = str(Path(__file__).resolve().parent
            / "samples/greenbook/green_writer10_B2_1.jpg")

image_args = [a for a in sys.argv[1:] if not a.startswith("--")]
IMAGE = image_args[0] if image_args else IMAGE

config = PreprocessConfig(
    adaptive_denoise="--adaptive-denoise" in sys.argv,
)

result = extract_text_from_image(IMAGE, preprocess_config=config)

print(f"image            : {IMAGE}")
print(f"adaptive_denoise : {config.adaptive_denoise}")
# None when nothing was detected.
_conf = result["average_confidence"]
print(f"avg confidence   : {_conf:.3f}" if _conf is not None
      else "avg confidence   : n/a")
print("-" * 60)
print(result["cleaned_text"])
