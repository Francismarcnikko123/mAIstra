import httpx
from fastapi.testclient import TestClient

import main


class UnreachableJudge0Client:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        raise httpx.ConnectError("All connection attempts failed")


def test_run_code_reports_unreachable_judge0(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", UnreachableJudge0Client)
    monkeypatch.setattr(main, "JUDGE0_BASE_URL", "http://127.0.0.1:2358")

    client = TestClient(main.app, raise_server_exceptions=False)

    response = client.post(
        "/api/judge0/run",
        json={
            "source_code": "int main(void) { return 0; }",
            "language_id": 50,
            "stdin": "",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Judge0 is unreachable at http://127.0.0.1:2358. "
        "Start Judge0 or update JUDGE0_BASE_URL."
    )
