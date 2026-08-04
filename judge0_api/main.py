import os
import asyncio
from typing import Optional
import base64
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JUDGE0_BASE_URL = os.getenv("JUDGE0_BASE_URL", "https://ce.judge0.com")
JUDGE0_API_KEY = os.getenv("JUDGE0_API_KEY")


class RunCodeRequest(BaseModel):
    source_code: str
    language_id: int
    stdin: Optional[str] = ""


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
    "language_id": payload.language_id,
    "stdin": encode_base64(payload.stdin or ""),
    }

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

        for _ in range(20):
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

            if status_id not in [1, 2]:
                return result

            await asyncio.sleep(0.5)

    raise HTTPException(status_code=504, detail="Judge0 execution timed out")

@app.get("/api/judge0/languages")
async def get_languages():
    headers = {}

    if JUDGE0_API_KEY:
        headers["X-Auth-Token"] = JUDGE0_API_KEY

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{JUDGE0_BASE_URL}/languages",
            headers=headers,
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text,
        )

    return response.json()
def encode_base64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def decode_base64(value):
    if value is None:
        return None

    return base64.b64decode(value).decode("utf-8", errors="replace")