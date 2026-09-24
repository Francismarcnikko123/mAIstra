# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_main
import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def load_main(extract):
    """Import main.py with the heavy OCR pipeline replaced by `extract`."""
    fake_pipeline = types.ModuleType("core.ocr_pipeline")
    fake_pipeline.extract_text_from_image = extract
    fake_pipeline.warmup = lambda: None
    with patch.dict(sys.modules, {"core.ocr_pipeline": fake_pipeline}):
        sys.modules.pop("main", None)
        return importlib.import_module("main")


class ExtractImageUrlTests(unittest.TestCase):
    def test_downloads_extracts_and_removes_the_temporary_folder(self):
        seen = {}

        def extract(image_path, output_dir):
            seen["image"] = image_path
            seen["folder"] = output_dir
            return {"raw_text": "raw", "cleaned_text": "clean", "average_confidence": 0.9}

        main = load_main(extract)
        with patch.object(main, "download_image", lambda url, dest: Path(dest).write_bytes(b"img")):
            result = main.extract_image_url("https://x/1.jpg")

        self.assertEqual(result, {"raw_text": "raw", "cleaned_text": "clean", "average_confidence": 0.9})
        self.assertTrue(seen["image"].startswith(seen["folder"]))
        self.assertFalse(os.path.exists(seen["folder"]))

    def test_endpoint_keeps_its_response_shape(self):
        main = load_main(lambda image_path, output_dir: {
            "raw_text": "raw", "cleaned_text": "clean", "average_confidence": 0.5})
        with patch.object(main, "download_image", lambda url, dest: Path(dest).write_bytes(b"img")):
            response = main.extract_from_url(main.ImageUrlRequest(submission_id="s1", image_url="https://x/1.jpg"))

        self.assertEqual(response, {
            "submission_id": "s1", "raw_text": "raw", "cleaned_text": "clean",
            "average_confidence": 0.5, "saved_to_db": False,
        })


if __name__ == "__main__":
    unittest.main()
