import asyncio
import httpx
from types import SimpleNamespace
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


class SuccessfulJudge0Client:
    submitted_payload = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        type(self).submitted_payload = kwargs["json"]
        return SimpleNamespace(
            status_code=201,
            text="",
            json=lambda: {"token": "submission-token"},
        )

    async def get(self, *args, **kwargs):
        return SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {
                "stdout": None,
                "stderr": None,
                "compile_output": None,
                "message": None,
                "status": {"id": 3, "description": "Accepted"},
            },
        )


def test_cors_allows_configured_angular_development_origins():
    client = TestClient(main.app)

    for origin in (
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ):
        response = client.options(
            "/api/judge0/run",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


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


def test_logic_analysis_endpoint_is_not_available_on_execution_branch():
    client = TestClient(main.app)

    response = client.post(
        "/api/judge0/analyze-logic",
        json={
            "model_code": "int add(int a, int b) { return a + b; }",
            "student_code": "int add(int x, int y) { return x + y; }",
        },
    )

    assert response.status_code == 404


def test_run_code_uses_server_configured_c_language_id(monkeypatch):
    SuccessfulJudge0Client.submitted_payload = None
    monkeypatch.setattr(main.httpx, "AsyncClient", SuccessfulJudge0Client)
    monkeypatch.setattr(main, "JUDGE0_C_LANGUAGE_ID", 50, raising=False)

    client = TestClient(main.app)
    response = client.post(
        "/api/judge0/run",
        json={
            "source_code": "int main(void) { return 0; }",
            "language_id": 71,
            "stdin": "",
        },
    )

    assert response.status_code == 200
    assert SuccessfulJudge0Client.submitted_payload["language_id"] == 50


def test_run_code_sends_wrapper_owned_time_limits(monkeypatch):
    SuccessfulJudge0Client.submitted_payload = None
    monkeypatch.setattr(main.httpx, "AsyncClient", SuccessfulJudge0Client)
    monkeypatch.setattr(main, "JUDGE0_CPU_TIME_LIMIT_SECONDS", 5, raising=False)
    monkeypatch.setattr(main, "JUDGE0_WALL_TIME_LIMIT_SECONDS", 10, raising=False)

    client = TestClient(main.app)
    response = client.post(
        "/api/judge0/run",
        json={"source_code": "int main(void) { return 0; }", "stdin": ""},
    )

    assert response.status_code == 200
    assert SuccessfulJudge0Client.submitted_payload["cpu_time_limit"] == 5
    assert SuccessfulJudge0Client.submitted_payload["wall_time_limit"] == 10


def test_batch_run_rejects_more_than_thirty_cases():
    client = TestClient(main.app)
    response = client.post(
        "/api/judge0/run-batch",
        json={
            "runs": [
                {"source_code": f"int main(void) {{ return {index}; }}", "stdin": ""}
                for index in range(31)
            ]
        },
    )

    assert response.status_code == 422


def test_batch_run_executes_at_most_three_cases_concurrently(monkeypatch):
    active_runs = 0
    highest_active_runs = 0

    async def tracked_run(_payload):
        nonlocal active_runs, highest_active_runs
        active_runs += 1
        highest_active_runs = max(highest_active_runs, active_runs)
        await asyncio.sleep(0.01)
        active_runs -= 1
        return {"status": {"id": 3, "description": "Accepted"}}

    monkeypatch.setattr(main, "run_code", tracked_run)

    client = TestClient(main.app)
    response = client.post(
        "/api/judge0/run-batch",
        json={
            "runs": [
                {"source_code": f"int main(void) {{ return {index}; }}", "stdin": ""}
                for index in range(14)
            ]
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 14
    assert highest_active_runs == 3


class StillProcessingJudge0Client:
    """Always reports the submission as still processing (status id 2)."""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        return SimpleNamespace(
            status_code=201,
            text="",
            json=lambda: {"token": "submission-token"},
        )

    async def get(self, *args, **kwargs):
        return SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {
                "stdout": None,
                "stderr": None,
                "compile_output": None,
                "message": None,
                "status": {"id": 2, "description": "Processing"},
            },
        )


def test_run_code_returns_504_when_result_never_ready(monkeypatch):
    async def instant_sleep(_seconds):
        return None

    monkeypatch.setattr(main.httpx, "AsyncClient", StillProcessingJudge0Client)
    monkeypatch.setattr(main.asyncio, "sleep", instant_sleep)
    monkeypatch.setattr(main, "_MAX_POLL_ATTEMPTS", 3, raising=False)

    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.post(
        "/api/judge0/run",
        json={"source_code": "int main(void) { while (1) {} }", "stdin": ""},
    )

    assert response.status_code == 504
    assert response.json()["detail"] == (
        "Judge0 did not return a result in time. Try again."
    )
