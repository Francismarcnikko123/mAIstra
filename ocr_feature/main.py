import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from core.ocr_pipeline import extract_text_from_image, warmup


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
    # No cookies or auth headers are used, so never let other sites send them.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ImageUrlRequest(BaseModel):
    submission_id: str
    image_url: str


@app.get("/")
def health_check():
    return {"status": "MaestrAI OCR Backend is running"}


# Each request works in its own temporary folder, deleted afterwards: student
# photos, preprocessed copies and debug dumps are never kept on this machine,
# and no client-supplied name ever becomes part of a file path.
# Plain `def` (not async): extraction is seconds of blocking CPU work, so
# FastAPI must run it in its threadpool instead of on the event loop.
@app.post("/api/ocr/extract-upload")
def extract_from_upload(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    with tempfile.TemporaryDirectory(prefix="maistra-ocr-") as work_dir:
        file_path = Path(work_dir) / "upload.jpg"
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = extract_text_from_image(str(file_path), output_dir=work_dir)

    return {
        "raw_text": result["raw_text"],
        "cleaned_text": result["cleaned_text"],
        "average_confidence": result["average_confidence"],
    }


# Mobile captures run 3-5MB; a slow connection plus TLS handshake can blow
# past a short timeout, so give the read phase real room and retry transient
# failures instead of failing the whole extraction on one bad attempt.
DOWNLOAD_CONNECT_TIMEOUT = 15   # seconds to establish the connection
DOWNLOAD_READ_TIMEOUT = 120     # seconds to finish reading the body
DOWNLOAD_RETRIES = 3
# Well above a 3-5MB phone capture; stops a huge or endless response from
# filling the disk.
DOWNLOAD_MAX_BYTES = 25 * 1024 * 1024


def download_image(url: str, dest: Path) -> None:
    """Download an image to `dest`, retrying on network errors. Raises
    HTTPException(400) if all attempts fail."""
    if urlparse(url).scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Image URL must be http or https.")
    last_error = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            with requests.get(
                url,
                timeout=(DOWNLOAD_CONNECT_TIMEOUT, DOWNLOAD_READ_TIMEOUT),
                stream=True,
            ) as response:
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to download image URL (HTTP {response.status_code}).",
                    )
                written = 0
                with dest.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            written += len(chunk)
                            if written > DOWNLOAD_MAX_BYTES:
                                raise HTTPException(
                                    status_code=400,
                                    detail="Image is larger than the 25 MB limit.",
                                )
                            f.write(chunk)
            return
        except HTTPException:
            # A non-200 status is not a transient error; don't retry it.
            raise
        except requests.RequestException as exc:
            # Network/timeout error: worth retrying.
            last_error = exc

    raise HTTPException(
        status_code=400,
        detail=f"Failed to download image after {DOWNLOAD_RETRIES} attempts: {last_error}",
    )


@app.post("/api/ocr/extract-from-url")
def extract_from_url(request: ImageUrlRequest):
    with tempfile.TemporaryDirectory(prefix="maistra-ocr-") as work_dir:
        image_path = Path(work_dir) / "submission.jpg"
        download_image(request.image_url, image_path)
        result = extract_text_from_image(str(image_path), output_dir=work_dir)

    return {
        "submission_id": request.submission_id,
        "raw_text": result["raw_text"],
        "cleaned_text": result["cleaned_text"],
        "average_confidence": result["average_confidence"],
        "saved_to_db": False,
    }
