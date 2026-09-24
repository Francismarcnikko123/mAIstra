import os
import asyncio
import math
from typing import Optional
import base64
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JUDGE0_BASE_URL = os.getenv("JUDGE0_BASE_URL")
JUDGE0_API_KEY = os.getenv("JUDGE0_API_KEY")


def positive_integer_setting(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


JUDGE0_C_LANGUAGE_ID = positive_integer_setting("JUDGE0_C_LANGUAGE_ID", 50)
# Sandbox limits the wrapper owns, so runaway code (e.g. an infinite loop) is
# killed on a deadline this service controls rather than whatever the Judge0 box
# happens to be configured with.
JUDGE0_CPU_TIME_LIMIT_SECONDS = positive_integer_setting(
    "JUDGE0_CPU_TIME_LIMIT_SECONDS", 5
)
JUDGE0_WALL_TIME_LIMIT_SECONDS = positive_integer_setting(
    "JUDGE0_WALL_TIME_LIMIT_SECONDS", 10
)
# How long a run may wait in Judge0's queue before it starts. Queue time depends
# on how busy the Judge0 box is, not on the submitted code, so it gets its own
# budget instead of eating into the run deadline below.
JUDGE0_MAX_QUEUE_WAIT_SECONDS = positive_integer_setting(
    "JUDGE0_MAX_QUEUE_WAIT_SECONDS", 60
)
MAX_BATCH_RUNS = 30
BATCH_CONCURRENCY = 3

# How long the wrapper waits for a started run to finish before giving up. Must
# comfortably exceed the wall-time limit so a timed-out run reports its own TLE
# status instead of tripping this poll budget.
_POLL_INTERVAL_SECONDS = 0.5
_MAX_POLL_ATTEMPTS = max(
    1,
    math.ceil((JUDGE0_WALL_TIME_LIMIT_SECONDS + 5) / _POLL_INTERVAL_SECONDS),
)
_MAX_QUEUE_POLL_ATTEMPTS = max(
    1,
    math.ceil(JUDGE0_MAX_QUEUE_WAIT_SECONDS / _POLL_INTERVAL_SECONDS),
)
_JUDGE0_IN_QUEUE = 1
_JUDGE0_PROCESSING = 2


if not JUDGE0_BASE_URL:
    raise RuntimeError(
        "JUDGE0_BASE_URL is not set. Create a .env file with JUDGE0_BASE_URL=http://<host>:<port>"
    )


class RunCodeRequest(BaseModel):
    source_code: str
    stdin: Optional[str] = ""


class RunCodeBatchRequest(BaseModel):
    runs: list[RunCodeRequest] = Field(min_length=1, max_length=MAX_BATCH_RUNS)


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/api/judge0/run")
async def run_code(payload: RunCodeRequest):

    headers = {
        "Content-Type": "application/json",
    }

    if JUDGE0_API_KEY:
        headers["X-Auth-Token"] = JUDGE0_API_KEY

    submission_payload = {
    "source_code": encode_base64(payload.source_code),
    "language_id": JUDGE0_C_LANGUAGE_ID,
    "stdin": encode_base64(payload.stdin or ""),
    "cpu_time_limit": JUDGE0_CPU_TIME_LIMIT_SECONDS,
    "wall_time_limit": JUDGE0_WALL_TIME_LIMIT_SECONDS,
    }

    try:  # catches httpx.RequestError for both POST and polling GETs
        async with httpx.AsyncClient(timeout=20) as client:
            create_response = await client.post(
                f"{JUDGE0_BASE_URL}/submissions",
                params={
                    "base64_encoded": "true",
                    "wait": "false",
                },
                json=submission_payload,
                headers=headers,
            )

            if create_response.status_code >= 400:
                raise HTTPException(
                    status_code=create_response.status_code,
                    detail=create_response.text,
                )

            token = create_response.json().get("token")

            if not token:
                raise HTTPException(status_code=500, detail="Judge0 did not return a token")

            queued_polls = 0
            processing_polls = 0
            while True:
                result_response = await client.get(
                    f"{JUDGE0_BASE_URL}/submissions/{token}",
                    params={
                        "base64_encoded": "true",
                        "fields": "stdout,stderr,compile_output,message,status,time,memory",
                    },
                    headers=headers,
                )

                if result_response.status_code >= 400:
                    raise HTTPException(
                        status_code=result_response.status_code,
                        detail=result_response.text,
                    )

                result = result_response.json()

                status_id = result.get("status", {}).get("id")
                for field in ["stdout", "stderr", "compile_output", "message"]:
                    result[field] = decode_base64(result.get(field))

                if status_id not in [_JUDGE0_IN_QUEUE, _JUDGE0_PROCESSING]:
                    return result

                # Waiting in the queue and running have separate budgets, so a
                # busy Judge0 box cannot make correct code look like it hung.
                if status_id == _JUDGE0_IN_QUEUE:
                    queued_polls += 1
                    if queued_polls >= _MAX_QUEUE_POLL_ATTEMPTS:
                        raise HTTPException(
                            status_code=504,
                            detail=(
                                "Judge0 is busy and did not start the run in "
                                "time. Try again."
                            ),
                        )
                else:
                    processing_polls += 1
                    if processing_polls >= _MAX_POLL_ATTEMPTS:
                        raise HTTPException(
                            status_code=504,
                            detail="Judge0 did not return a result in time. Try again.",
                        )

                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Judge0 is unreachable at {JUDGE0_BASE_URL}. "
                "Start Judge0 or update JUDGE0_BASE_URL."
            ),
        ) from exc


@app.post("/api/judge0/run-batch")
async def run_code_batch(payload: RunCodeBatchRequest):
    semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def run_bounded(run: RunCodeRequest):
        async with semaphore:
            return await run_code(run)

    tasks = [asyncio.create_task(run_bounded(run)) for run in payload.runs]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        # A grade needs every test case, so the first failure fails the batch.
        # gather() does not cancel the other runs on its own; stop them (and any
        # still queued on the semaphore) instead of leaving them polling Judge0.
        # BaseException also covers the request itself being cancelled.
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def encode_base64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def decode_base64(value):
    if value is None:
        return None

    return base64.b64decode(value).decode("utf-8", errors="replace")
