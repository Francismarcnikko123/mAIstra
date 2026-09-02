import os
import asyncio
from typing import Optional
import base64
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
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
class GradeSubmissionRequest(BaseModel):
    model_code: str
    student_code: str
    expected_output: str
    actual_output: str
    compilation_passed: bool

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
def normalize_output(output: str) -> str:
    if output is None:
        return ""

    output = output.strip().lower()
    output = re.sub(r"\s*:\s*", ":", output)
    output = re.sub(r"\s+", " ", output)

    return output


def remove_comments(code: str) -> str:
    code = re.sub(r"//.*", "", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return code


def normalize_code(code: str) -> str:
    code = remove_comments(code or "")
    code = code.lower()
    code = re.sub(r"\s+", " ", code)
    return code.strip()


def extract_logic_features(code: str) -> dict:
    normalized = normalize_code(code)
    numbers = re.findall(r"\b\d+\b", normalized)

    return {
        "has_main": "main" in normalized,
        "has_printf": "printf" in normalized,
        "has_scanf": "scanf" in normalized,
        "has_assignment": "=" in normalized,
        "uses_addition": "+" in normalized,
        "uses_subtraction": "-" in normalized,
        "uses_multiplication": "*" in normalized,
        "uses_division": "/" in normalized,
        "has_return": "return" in normalized,
        "numbers": set(numbers),
    }


def compare_logic(model_code: str, student_code: str) -> dict:
    model = extract_logic_features(model_code)
    student = extract_logic_features(student_code)

    checks = []

    def add_check(name: str, passed: bool, weight: int):
        checks.append({
            "name": name,
            "passed": passed,
            "weight": weight,
            "score": weight if passed else 0,
        })

    add_check("Has main function", student["has_main"], 10)
    add_check("Has output statement", student["has_printf"], 10)
    add_check("Uses assignment", student["has_assignment"], 15)

    if model["uses_addition"]:
        add_check("Uses addition operator", student["uses_addition"], 25)

    if model["uses_subtraction"]:
        add_check("Uses subtraction operator", student["uses_subtraction"], 25)

    if model["uses_multiplication"]:
        add_check("Uses multiplication operator", student["uses_multiplication"], 25)

    if model["uses_division"]:
        add_check("Uses division operator", student["uses_division"], 25)

    if model["numbers"]:
        add_check(
            "Uses required numeric values",
            model["numbers"].issubset(student["numbers"]),
            25,
        )

    total_weight = sum(check["weight"] for check in checks)
    earned_score = sum(check["score"] for check in checks)
    score = round((earned_score / total_weight) * 100, 2) if total_weight else 0

    return {
        "score": score,
        "checks": checks,
    }

@app.post("/api/judge0/grade-submission")
async def grade_submission(payload: GradeSubmissionRequest):
    compilation_score = 100 if payload.compilation_passed else 0

    logic_result = compare_logic(
        payload.model_code,
        payload.student_code,
    )

    expected = normalize_output(payload.expected_output)
    actual = normalize_output(payload.actual_output)

    output_passed = expected == actual
    output_score = 100 if output_passed else 0

    final_score = (
        logic_result["score"] * 0.50
        + output_score * 0.40
        + compilation_score * 0.10
    )

    return {
        "final_score": round(final_score, 2),
        "compilation_score": compilation_score,
        "logic_score": logic_result["score"],
        "output_score": output_score,
        "logic_details": logic_result["checks"],
        "output_details": {
            "passed": output_passed,
            "score": output_score,
            "expected_normalized": expected,
            "actual_normalized": actual,
        },
    }

def encode_base64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def decode_base64(value):
    if value is None:
        return None

    return base64.b64decode(value).decode("utf-8", errors="replace")