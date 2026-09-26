# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_main
import importlib
import asyncio
import os
import sys
import tempfile
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


class FakeDownload:
    """A requests.get response for download_image: status and body only."""

    def __init__(self, status_code=200, body=b"img"):
        self.status_code = status_code
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def iter_content(self, chunk_size):
        yield self.body


class WhoMayCallTests(unittest.TestCase):
    # Review 2026-09-26 #8: other websites and internal addresses.

    def load(self, **env):
        with patch.dict(os.environ, {"OCR_ALLOWED_ORIGINS": "", **env}):
            return load_main(lambda *_args, **_kwargs: {})

    def preflight(self, client, origin):
        return client.options("/api/ocr/extract-from-url", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })

    def test_only_the_web_app_passes_the_browser_preflight(self):
        from fastapi.testclient import TestClient
        client = TestClient(self.load().app)

        allowed = self.preflight(client, "http://localhost:4200")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.headers["access-control-allow-origin"], "http://localhost:4200")

        refused = self.preflight(client, "https://some-other-site.example")
        self.assertEqual(refused.status_code, 400)
        self.assertNotIn("access-control-allow-origin", refused.headers)

    def test_origins_can_be_replaced_in_env(self):
        main = self.load()
        self.assertEqual(
            main.allowed_origins({"OCR_ALLOWED_ORIGINS": "http://localhost:4300/, http://10.0.0.5:4200"}),
            ["http://localhost:4300", "http://10.0.0.5:4200"],
        )
        self.assertIn("http://localhost:4200", main.allowed_origins({}))

    def test_json_sent_without_a_preflight_is_not_read(self):
        # A site can skip the preflight only with a "simple" content type;
        # the endpoint must then refuse the body instead of fetching the URL.
        from fastapi.testclient import TestClient
        main = self.load()
        with patch.object(main, "download_image", side_effect=AssertionError("fetched")):
            response = TestClient(main.app).post(
                "/api/ocr/extract-from-url",
                content='{"submission_id": "s1", "image_url": "http://169.254.169.254/"}',
                headers={"Content-Type": "text/plain", "Origin": "https://some-other-site.example"},
            )
        self.assertEqual(response.status_code, 422)

    def test_image_hosts_come_from_supabase_url_unless_listed(self):
        main = self.load()
        self.assertEqual(
            main.allowed_image_hosts({"SUPABASE_URL": "https://abc.supabase.co/"}),
            {"abc.supabase.co"},
        )
        self.assertEqual(
            main.allowed_image_hosts({
                "SUPABASE_URL": "https://abc.supabase.co",
                "OCR_ALLOWED_IMAGE_HOSTS": "127.0.0.1:54321, ABC.supabase.co",
            }),
            {"127.0.0.1:54321", "abc.supabase.co"},
        )
        self.assertEqual(main.allowed_image_hosts({}), set())

    def test_other_hosts_are_refused_before_any_download(self):
        main = self.load()
        env = {"SUPABASE_URL": "https://abc.supabase.co", "OCR_ALLOWED_IMAGE_HOSTS": ""}
        with patch.dict(os.environ, env), \
                patch.object(main.requests, "get", side_effect=AssertionError("fetched")), \
                self.assertRaises(main.HTTPException) as refused:
            main.download_image("http://169.254.169.254/latest/meta-data", Path("unused.jpg"))
        self.assertEqual(refused.exception.status_code, 400)
        self.assertIn("Supabase storage", refused.exception.detail)

    def test_storage_photos_download_without_following_redirects(self):
        main = self.load()
        calls = []

        def fake_get(url, **kwargs):
            calls.append(kwargs)
            return FakeDownload()

        env = {"SUPABASE_URL": "https://abc.supabase.co", "OCR_ALLOWED_IMAGE_HOSTS": ""}
        with patch.dict(os.environ, env), patch.object(main.requests, "get", fake_get), \
                tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "photo.jpg"
            main.download_image("https://abc.supabase.co/storage/v1/object/public/submissions/1.jpg", dest)
            self.assertEqual(dest.read_bytes(), b"img")
        self.assertIs(calls[0]["allow_redirects"], False)

        # A redirect is a failed download, not a second request elsewhere.
        with patch.dict(os.environ, env), \
                patch.object(main.requests, "get", lambda url, **kwargs: FakeDownload(302)), \
                self.assertRaises(main.HTTPException):
            main.download_image("https://abc.supabase.co/storage/v1/object/public/submissions/1.jpg",
                                Path("unused.jpg"))


if __name__ == "__main__":
    unittest.main()
