import sys
from types import ModuleType

from fastapi.testclient import TestClient

ocr_pipeline = ModuleType("core.ocr_pipeline")
ocr_pipeline.extract_text_from_image = lambda _path: {}
ocr_pipeline.warmup = lambda: None
sys.modules["core.ocr_pipeline"] = ocr_pipeline

import main


def test_cors_allows_configured_local_frontends():
    client = TestClient(main.app)

    for origin in (
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:4201",
        "http://127.0.0.1:4201",
    ):
        response = client.options(
            "/api/ocr/extract-from-url",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
