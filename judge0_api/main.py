"""mAIstra's Judge0 wrapper: a small FastAPI service between the web app and Judge0.

The web app never talks to Judge0 directly. It calls this service, which:
- keeps Judge0's address and API key on the server, out of browser code;
- sets the same sandbox limits (CPU time, wall time) on every run;
- hides Judge0's two-step "submit, then ask for the result" protocol, so the
  browser sends one request and gets back one finished result.

How one run travels:

    Angular (Judge0Service)         this wrapper                  Judge0 CE
    POST /api/judge0/run  ───────▶  POST /submissions  ──────────▶ queues the run
                                    ◀─────────────────── { token }
                                    GET /submissions/{token} ────▶ repeated every
                                    ◀──────────── status + output  0.5 s until done
    ◀───────── finished result

Endpoints:
- GET  /                      health check.
- POST /api/judge0/run        runs one C program with one stdin.
- POST /api/judge0/run-batch  runs several (one per test case), 3 at a time.

This service only compiles and runs code. It never sees the expected output:
the web app compares stdout with each test case's expected output itself.

Settings come from judge0_api/.env; see docs/setup/JUDGE0_UBUNTU_DOCKER_SETUP.md.
"""

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

# Reads judge0_api/.env into environment variables before the settings below.
load_dotenv()

app = FastAPI()

# Browsers only let a page call another address when that address allows it.
# Only the Angular dev server (ng serve, port 4200) is allowed here.
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

# Where Judge0 CE listens, e.g. http://<vm-ip>:2358 (required, checked below).
JUDGE0_BASE_URL = os.getenv("JUDGE0_BASE_URL")
# Optional. Must match AUTHN_TOKEN in Judge0's judge0.conf when Judge0 is set
# up to require one; it is sent as the X-Auth-Token header.
JUDGE0_API_KEY = os.getenv("JUDGE0_API_KEY")


def positive_integer_setting(name: str, default: int) -> int:
    """Reads a whole-number setting from .env, or `default` when it is unset.

    A bad value (text, 0, negative) stops the service at start-up instead of
    breaking the first run.
    """
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


# Judge0's id for the compiler to use. 50 is "C (GCC 9.2.0)" on Judge0 CE.
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
# A batch holds one run per test case. At most 30 runs per batch, and only 3
# are sent to Judge0 at the same time so one grade can't flood the Judge0 box.
MAX_BATCH_RUNS = 30
BATCH_CONCURRENCY = 3

# How long the wrapper waits for a started run to finish before giving up. Must
# comfortably exceed the wall-time limit so a timed-out run reports its own TLE
# status instead of tripping this poll budget.
# Both budgets count polls: JUDGE0_MAX_QUEUE_WAIT_SECONDS of polling while
# queued, then the wall-time limit + 5 s while running. Each poll also waits
# for Judge0's answer, so the real wait can be longer.
_POLL_INTERVAL_SECONDS = 0.5
_MAX_POLL_ATTEMPTS = max(
    1,
    math.ceil((JUDGE0_WALL_TIME_LIMIT_SECONDS + 5) / _POLL_INTERVAL_SECONDS),
)
_MAX_QUEUE_POLL_ATTEMPTS = max(
    1,
    math.ceil(JUDGE0_MAX_QUEUE_WAIT_SECONDS / _POLL_INTERVAL_SECONDS),
)
# Judge0 status ids. These two mean "not finished yet, ask again". Every other
# id is final: 3 Accepted (compiled and ran normally), 5 Time Limit Exceeded,
# 6 Compilation Error, 7-12 Runtime Error (crash, non-zero exit, ...),
# 13 Internal Error, 14 Exec Format Error. We never send an expected output,
# so Judge0 never answers 4 Wrong Answer; the web app compares output itself.
_JUDGE0_IN_QUEUE = 1
_JUDGE0_PROCESSING = 2


if not JUDGE0_BASE_URL:
    raise RuntimeError(
        "JUDGE0_BASE_URL is not set. Create a .env file with JUDGE0_BASE_URL=http://<host>:<port>"
    )


class RunCodeRequest(BaseModel):
    """Body of POST /api/judge0/run: one program and what to type into it.

    `source_code` is the complete C file. The web app builds it before sending
    (buildCQuestionSource in maistra_web/src/app/utils/c-question.ts): it adds
    #include <stdio.h>, and for a function question also a generated main()
    that holds the test case's Test Code.
    """

    source_code: str
    # Text the program reads with scanf(). Empty for function questions.
    stdin: Optional[str] = ""


class RunCodeBatchRequest(BaseModel):
    """Body of POST /api/judge0/run-batch: several runs, one per test case."""

    runs: list[RunCodeRequest] = Field(min_length=1, max_length=MAX_BATCH_RUNS)
    # Grading needs every test case, so by default the first failed run fails
    # the whole batch. Model-answer validation sets this to False to get each
    # run's own outcome, with a failed run reported as {"error": {...}}.
    stop_on_error: bool = True


@app.get("/")
def health_check():
    """Answers {"status": "ok"} when this service is up. It does not contact Judge0."""
    return {"status": "ok"}


@app.post("/api/judge0/run")
async def run_code(payload: RunCodeRequest):
    """Compiles and runs one C program on Judge0 and returns the finished result.

    Used by "Run Sample" in Step 3, and once per test case by /run-batch.

    Returns Judge0's result with the text fields decoded, for example:
        {"stdout": "15\\n", "stderr": None, "compile_output": None,
         "message": None, "status": {"id": 3, "description": "Accepted"},
         "time": "0.001", "memory": 776}

    A compile error, a crash or a program that runs too long is still a normal
    result (status 6, 7-12, or 5 Time Limit Exceeded), not an HTTP error.
    HTTP errors mean the run itself could not be done:
    - 502: Judge0 cannot be reached at JUDGE0_BASE_URL, or its reply is not
      JSON or has no status.
    - 504: the run waited too long in Judge0's queue, or Judge0 itself did not
      finish it in time (a slow program gets status 5 before this).
    - 500: Judge0 accepted the code but did not return a token.
    - Judge0's own error code when Judge0 rejects the request.
    """

    headers = {
        "Content-Type": "application/json",
    }

    if JUDGE0_API_KEY:
        headers["X-Auth-Token"] = JUDGE0_API_KEY

    # Code, stdin and output travel base64-encoded, so quotes, newlines and
    # odd bytes printed by a broken program survive the JSON round trip.
    submission_payload = {
    "source_code": encode_base64(payload.source_code),
    "language_id": JUDGE0_C_LANGUAGE_ID,
    "stdin": encode_base64(payload.stdin or ""),
    "cpu_time_limit": JUDGE0_CPU_TIME_LIMIT_SECONDS,
    "wall_time_limit": JUDGE0_WALL_TIME_LIMIT_SECONDS,
    }

    try:  # catches httpx.RequestError for both POST and polling GETs
        async with httpx.AsyncClient(timeout=20) as client:
            # Step 1: hand the code to Judge0. wait=false makes Judge0 answer
            # at once with a token (a ticket for this run) instead of holding
            # the request open until the program finishes.
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

            token = judge0_json(create_response).get("token")

            if not token:
                raise HTTPException(status_code=500, detail="Judge0 did not return a token")

            # Step 2: ask Judge0 about the token every 0.5 s until the status
            # is final, or until a waiting budget runs out.
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

                result = judge0_json(result_response)

                status = result.get("status")
                status_id = status.get("id") if isinstance(status, dict) else None
                # Without a status there is no way to tell a pass from a crash,
                # so this run failed rather than scoring 0.
                if status_id is None:
                    raise HTTPException(
                        status_code=502,
                        detail="Judge0 sent a result without a status.",
                    )
                # Judge0 sends these fields base64-encoded; turn them back
                # into plain text for the web app.
                for field in ["stdout", "stderr", "compile_output", "message"]:
                    result[field] = decode_base64(result.get(field))

                # Step 3: a final status (Accepted, Compilation Error, ...)
                # ends the loop and goes back to the web app.
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
    """Runs several programs, usually one per test case, and returns their
    results in the same order as `runs`.

    Two modes, picked by `stop_on_error`:
    - True (grading, Step 3): all or nothing. If any run fails (Judge0 down,
      timeout), the whole request fails, so a grade is never saved with
      missing test cases.
    - False (Validate Test Cases in the question form): every run reports on
      its own; a failed run comes back as {"error": {"status_code", "detail"}}
      in its slot while the others still show their output.
    """
    # Lets only BATCH_CONCURRENCY runs talk to Judge0 at once; the rest wait.
    semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def run_bounded(run: RunCodeRequest):
        async with semaphore:
            return await run_code(run)

    tasks = [asyncio.create_task(run_bounded(run)) for run in payload.runs]
    if not payload.stop_on_error:
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for outcome in outcomes:
            # Only Judge0/HTTP failures belong to a single run; anything else
            # is a wrapper bug and should surface as a 500.
            if isinstance(outcome, BaseException) and not isinstance(
                outcome, HTTPException
            ):
                raise outcome
        return [
            {"error": {"status_code": outcome.status_code, "detail": outcome.detail}}
            if isinstance(outcome, HTTPException)
            else outcome
            for outcome in outcomes
        ]

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


def judge0_json(response) -> dict:
    """Judge0's reply as a dict, or a 502 for this run.

    An HTML error page from a proxy, or any body that isn't a JSON object,
    fails only this run. Left to crash, it would be a 500 that also takes down
    the other runs of a settled batch.
    """
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=502, detail="Judge0 sent a reply that is not JSON."
        )
    return body


def encode_base64(value: str) -> str:
    """Text -> base64 text, the form Judge0 expects with base64_encoded=true."""
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def decode_base64(value):
    """Base64 text from Judge0 -> plain text; None stays None (field was empty).

    Bytes that are not valid UTF-8 become a replacement mark instead of
    raising an error.
    """
    if value is None:
        return None

    return base64.b64decode(value).decode("utf-8", errors="replace")
