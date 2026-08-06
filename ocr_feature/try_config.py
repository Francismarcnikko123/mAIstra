"""
Scratch script for eyeballing a single image under a given preprocessing
config. Not part of the pipeline and not imported by anything -- edit it
freely, or delete it.

    python try_config.py                      # default config
    python try_config.py --adaptive-denoise   # textured-paper denoising

Point IMAGE at whichever sample you want to inspect.
"""
import sys

from core.preprocess import PreprocessConfig
from core.ocr_pipeline import extract_text_from_image

IMAGE = "samples/nombrado_s06_struct_green_raw.jpeg"

config = PreprocessConfig(
    adaptive_denoise="--adaptive-denoise" in sys.argv,
)

result = extract_text_from_image(IMAGE, preprocess_config=config)

print(f"image            : {IMAGE}")
print(f"adaptive_denoise : {config.adaptive_denoise}")
print(f"avg confidence   : {result['average_confidence']:.3f}")
print("-" * 60)
print(result["cleaned_text"])
