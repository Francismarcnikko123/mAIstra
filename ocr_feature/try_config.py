"""
Scratch script for eyeballing a single image under a given preprocessing
config. Not part of the pipeline and not imported by anything -- edit it
freely, or delete it.

    python try_config.py                                  # default IMAGE, default config
    python try_config.py path/to/photo.jpg                # any image, default config
    python try_config.py path/to/photo.jpg --adaptive-denoise

The image path is optional -- omit it to fall back to IMAGE below.
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
print(f"avg confidence   : {result['average_confidence']:.3f}")
print("-" * 60)
print(result["cleaned_text"])
