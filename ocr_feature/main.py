import os
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

from core.auto_extract import start_auto_extract
from core.ocr_pipeline import extract_text_from_image, warmup


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the OCR models on startup so the first real request is fast.
    warmup()
    # Pre-extraction on arrival: off unless AUTO_EXTRACT=true in .env
    # (see core/auto_extract.py). Uses the same extraction as the endpoint.
    worker = start_auto_extract(os.environ, extract_image_url)
    app.state.auto_extract = worker
    yield
    if worker is not None:
        worker.stop()
    app.state.auto_extract = None


app = FastAPI(title="MaestrAI OCR Backend", lifespan=lifespan)

# Only the web app may call this server from a browser. With "*", any website
# the teacher had open could make it download URLs of that site's choosing
# (review 2026-09-26 #8). The ng serve ports by default; OCR_ALLOWED_ORIGINS
# in .env (comma-separated) replaces the list, e.g. for another port.
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:4200,http://127.0.0.1:4200,"
    "http://localhost:4201,http://127.0.0.1:4201"
)


def allowed_origins(env=os.environ) -> list[str]:
    raw = env.get("OCR_ALLOWED_ORIGINS") or DEFAULT_ALLOWED_ORIGINS
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    # No cookies or auth headers are used, so never let other sites send them.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class ImageUrlRequest(BaseModel):
    submission_id: str
    image_url: str


@app.get("/")
def health_check():
    worker = getattr(app.state, "auto_extract", None)
    auto_extract = {"enabled": worker is not None, "since": None, "failed": []}
    if worker is not None:
        auto_extract["since"] = worker.config.since.isoformat() if worker.config.since else None
        auto_extract["failed"] = [
            submission_id for submission_id, count in worker.failures.copy().items()
            if count >= worker.config.max_failures
        ]
    return {"status": "MaestrAI OCR Backend is running", "auto_extract": auto_extract}


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


def allowed_image_hosts(env=os.environ) -> set[str]:
    """Hosts an image URL may point to: OCR_ALLOWED_IMAGE_HOSTS if set
    (comma-separated host[:port]), else the host of SUPABASE_URL, where every
    paper's photo is stored. Empty (no .env yet) accepts any host."""
    raw = env.get("OCR_ALLOWED_IMAGE_HOSTS", "")
    hosts = {host.strip().lower() for host in raw.split(",") if host.strip()}
    if not hosts and env.get("SUPABASE_URL"):
        hosts.add(urlparse(env["SUPABASE_URL"]).netloc.lower())
    return hosts


def download_image(url: str, dest: Path) -> None:
    """Download an image to `dest`, retrying on network errors. Raises
    HTTPException(400) if all attempts fail."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Image URL must be http or https.")
    # Other devices on the network may reach this server, so it must not
    # download internal addresses for whoever asks.
    hosts = allowed_image_hosts()
    if hosts and parsed.netloc.lower() not in hosts:
        raise HTTPException(
            status_code=400,
            detail="Image URL must point to this project's Supabase storage "
                   "(SUPABASE_URL or OCR_ALLOWED_IMAGE_HOSTS in ocr_feature/.env).",
        )
    last_error = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            with requests.get(
                url,
                timeout=(DOWNLOAD_CONNECT_TIMEOUT, DOWNLOAD_READ_TIMEOUT),
                stream=True,
                # Supabase storage serves photos directly; a redirect could
                # lead past the host check above.
                allow_redirects=False,
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


def extract_image_url(image_url: str) -> dict:
    """Download one image and run the OCR pipeline on it, in a temporary
    folder that is deleted afterwards. Shared by the endpoint and the
    auto-extract worker, so both always produce the same text."""
    with tempfile.TemporaryDirectory(prefix="maistra-ocr-") as work_dir:
        image_path = Path(work_dir) / "submission.jpg"
        download_image(image_url, image_path)
        result = extract_text_from_image(str(image_path), output_dir=work_dir)
    return {
        "raw_text": result["raw_text"],
        "cleaned_text": result["cleaned_text"],
        "average_confidence": result["average_confidence"],
    }


@app.post("/api/ocr/extract-from-url")
def extract_from_url(request: ImageUrlRequest):
    result = extract_image_url(request.image_url)
    return {
        "submission_id": request.submission_id,
        **result,
        "saved_to_db": False,
    }
