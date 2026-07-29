"""
Export teacher-verified submissions from Supabase as an OCR dataset --
(image, verified_text) pairs are exactly the training/evaluation examples
fine-tuning will need, produced as a byproduct of normal grading use.

Dev tool, not used by the live backend. Reads SUPABASE_URL and
SUPABASE_ANON_KEY from .env (same values the backend uses):

    python export_dataset.py

Writes to datasets/verified/:
    labels.csv   one row per verified submission
    images/      the submission images, named <submission_id>.jpg

Re-running is safe: already-downloaded images are kept, the CSV is
rewritten from the current database state. Rows whose image can't be
downloaded are skipped with a warning rather than failing the export.
"""
import csv
import os
import sys
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

EXPORT_DIR = Path("datasets/verified")
IMAGES_DIR = EXPORT_DIR / "images"
LABELS_CSV = EXPORT_DIR / "labels.csv"

PAGE_SIZE = 100


def fetch_verified_submissions(base_url: str, anon_key: str) -> list[dict]:
    """Fetch all status='verified' rows, paging until exhausted."""
    rows = []
    headers = {"apikey": anon_key, "Authorization": f"Bearer {anon_key}"}
    offset = 0
    while True:
        response = requests.get(
            f"{base_url}/rest/v1/submissions",
            headers=headers,
            params={
                "status": "eq.verified",
                "select": "id,image_url,extracted_text,verified_text,"
                          "verified_at,topic,student_name",
                "order": "verified_at.asc",
                "limit": str(PAGE_SIZE),
                "offset": str(offset),
            },
            timeout=30,
        )
        response.raise_for_status()
        page = response.json()
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def download_image(url: str, dest: Path) -> bool:
    """Download url to dest unless it already exists. Returns success."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        with requests.get(url, timeout=(15, 120), stream=True) as response:
            if response.status_code != 200:
                return False
            with dest.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except requests.RequestException:
        dest.unlink(missing_ok=True)
        return False


def main() -> None:
    load_dotenv()
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "")
    if not base_url or not anon_key:
        sys.exit("SUPABASE_URL and SUPABASE_ANON_KEY must be set (see .env).")

    rows = fetch_verified_submissions(base_url, anon_key)
    print(f"Found {len(rows)} verified submission(s).")
    if not rows:
        return

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    exported = []
    skipped = 0
    for row in rows:
        text = (row.get("verified_text") or "").strip()
        image_url = row.get("image_url") or ""
        if not text or not image_url:
            print(f"  skip {row.get('id')}: missing verified_text or image_url")
            skipped += 1
            continue
        dest = IMAGES_DIR / f"{row['id']}.jpg"
        if not download_image(image_url, dest):
            print(f"  skip {row.get('id')}: image download failed")
            skipped += 1
            continue
        exported.append(row)

    with LABELS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "submission_id", "image_path", "verified_text",
            "extracted_text", "verified_at", "topic", "student_name",
        ])
        for row in exported:
            writer.writerow([
                row["id"],
                f"images/{row['id']}.jpg",
                row["verified_text"],
                row.get("extracted_text") or "",
                row.get("verified_at") or "",
                row.get("topic") or "",
                row.get("student_name") or "",
            ])

    # Re-captures of the same page produce identical verified text; they must
    # not straddle a future train/test split, so flag them at export time.
    duplicates = Counter(
        " ".join(row["verified_text"].split()) for row in exported)
    duplicate_groups = {t: n for t, n in duplicates.items() if n > 1}

    print(f"Exported {len(exported)} pair(s) to {LABELS_CSV} "
          f"({skipped} skipped).")
    if duplicate_groups:
        print(f"WARNING: {len(duplicate_groups)} verified text(s) appear on "
              f"multiple submissions (likely re-captures of the same page). "
              f"Keep such groups on the same side of any train/test split.")


if __name__ == "__main__":
    main()
