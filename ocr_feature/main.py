import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

from ocr_pipeline import extract_text_from_image, warmup


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the OCR models on startup so the first real request is fast.
    warmup()
    yield


app = FastAPI(title="MaestrAI OCR Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ImageUrlRequest(BaseModel):
    submission_id: str
    image_url: str


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Optional[Client] = None

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


@app.get("/")
def health_check():
    return {"status": "MaestrAI OCR Backend is running"}


@app.post("/api/ocr/extract-upload")
async def extract_from_upload(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    file_path = UPLOAD_DIR / file.filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = extract_text_from_image(str(file_path))

    return {
        "raw_text": result["raw_text"],
        "cleaned_text": result["cleaned_text"],
        "average_confidence": result["average_confidence"],
    }


@app.post("/api/ocr/extract-from-url")
def extract_from_url(request: ImageUrlRequest):
   
    image_path = UPLOAD_DIR / f"{request.submission_id}.jpg"

    response = requests.get(request.image_url, timeout=30)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to download image URL.")

    image_path.write_bytes(response.content)

    result = extract_text_from_image(str(image_path))

    return {
        "submission_id": request.submission_id,
        "raw_text": result["raw_text"],
        "cleaned_text": result["cleaned_text"],
        "average_confidence": result["average_confidence"],
        "saved_to_db": False,
    }


@app.post("/api/submissions/save-verified-text")
def save_verified_text(
    submission_id: str = Form(...),
    verified_text: str = Form(...),
    teacher_id: Optional[str] = Form(None),
):
    if not supabase:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured. Check .env file.",
        )

    update_data = {
        "verified_text": verified_text,
        "status": "verified",
    }

    if teacher_id:
        update_data["verified_by"] = teacher_id

    response = supabase.table("submissions").update(update_data).eq(
        "id", submission_id
    ).execute()

    return {
        "message": "Verified text saved successfully.",
        "submission_id": submission_id,
        "data": response.data,
    }