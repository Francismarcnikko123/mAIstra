from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.similarity import get_similarity_service, router
from similarity_service import MissingComparisonMetadataError


class FakeSimilarityService:
    def __init__(self):
        self.calls = []
        self.raise_missing = False
        self.raise_internal = False

    def scan_submission(self, submission_id):
        self.calls.append(("scan", submission_id))
        if self.raise_missing:
            raise MissingComparisonMetadataError("Missing comparison details")
        if self.raise_internal:
            raise RuntimeError("postgresql://teacher:secret@example.test/database")
        return {"status": "complete", "submission_id": submission_id}

    def get_submission_summary(self, submission_id):
        self.calls.append(("summary", submission_id))
        return {"status": "not_checked", "submission_id": submission_id}

    def get_match_detail(self, submission_id, peer_submission_id):
        self.calls.append(("detail", submission_id, peer_submission_id))
        return {
            "submission_id": submission_id,
            "peer_submission_id": peer_submission_id,
        }


def create_client(service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_similarity_service] = lambda: service
    return TestClient(app)


def test_scan_route_uses_only_the_submission_id():
    service = FakeSimilarityService()
    client = create_client(service)

    response = client.post("/api/similarity/submissions/submission-a/scan")

    assert response.status_code == 200
    assert service.calls == [("scan", "submission-a")]


def test_scan_route_returns_conflict_for_missing_metadata():
    service = FakeSimilarityService()
    service.raise_missing = True
    client = create_client(service)

    response = client.post("/api/similarity/submissions/submission-a/scan")

    assert response.status_code == 409
    assert response.json()["detail"] == "Missing comparison details"


def test_summary_and_match_detail_routes_delegate_scoped_ids():
    service = FakeSimilarityService()
    client = create_client(service)

    summary = client.get("/api/similarity/submissions/submission-a")
    detail = client.get(
        "/api/similarity/submissions/submission-a/matches/submission-b"
    )

    assert summary.status_code == 200
    assert detail.status_code == 200
    assert service.calls == [
        ("summary", "submission-a"),
        ("detail", "submission-a", "submission-b"),
    ]


def test_routes_report_missing_database_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/similarity/submissions/submission-a")

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]


def test_scan_route_does_not_expose_internal_failure_details():
    service = FakeSimilarityService()
    service.raise_internal = True
    response = create_client(service).post(
        "/api/similarity/submissions/submission-a/scan"
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Similarity check failed. Retry later."
    assert "secret" not in response.text
