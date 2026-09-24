# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_main
import importlib
import asyncio
import os
import sys
import types
import unittest
from datetime import datetime, timezone
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


class HealthCheckTests(unittest.TestCase):
    def test_worker_off_keeps_status_and_reports_disabled(self):
        main = load_main(lambda *_args, **_kwargs: {})
        self.assertEqual(main.health_check(), {
            "status": "MaestrAI OCR Backend is running",
            "auto_extract": {"enabled": False, "since": None, "failed": []},
        })

    def test_lifespan_exposes_worker_start_date_and_only_given_up_ids(self):
        main = load_main(lambda *_args, **_kwargs: {})
        since = datetime(2026, 9, 24, 10, 9, tzinfo=timezone.utc)
        worker = types.SimpleNamespace(
            config=types.SimpleNamespace(since=since, max_failures=3),
            failures={"retrying": 2, "given-up": 3, "also-given-up": 4},
            stop=lambda: None,
        )

        async def check_lifespan():
            with patch.object(main, "start_auto_extract", return_value=worker):
                async with main.lifespan(main.app):
                    self.assertIs(main.app.state.auto_extract, worker)
                    self.assertEqual(main.health_check(), {
                        "status": "MaestrAI OCR Backend is running",
                        "auto_extract": {
                            "enabled": True,
                            "since": "2026-09-24T10:09:00+00:00",
                            "failed": ["given-up", "also-given-up"],
                        },
                    })
            self.assertFalse(main.health_check()["auto_extract"]["enabled"])

        asyncio.run(check_lifespan())


if __name__ == "__main__":
    unittest.main()
