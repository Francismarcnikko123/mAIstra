"""
Export teacher-verified submissions from Supabase as an OCR dataset --
(image, verified_text) pairs are exactly the training/evaluation examples
fine-tuning will need, produced as a byproduct of normal grading use.

Dev tool, not used by the live backend. Reads SUPABASE_URL and
SUPABASE_ANON_KEY from .env (same values the backend uses). Run from the
ocr_feature/ directory (module path, not the file path -- this file does
`from evaluators.evaluation import ...`, which only resolves as a package
import):

    .venv/bin/python -m evaluators.export_dataset

Writes to datasets/verified/:
    labels.csv   one row per verified submission
    images/      the submission images, named <submission_id>.jpg

Re-running is safe: already-downloaded images are kept, and the CSV write
merges rather than overwrites -- rows from import_verified_batch.py's
writer-batch namespace (see evaluators/labels_schema.py) are preserved
untouched; only this script's own Supabase-sourced rows are rebuilt from
current database state. Rows whose image can't be downloaded are skipped
with a warning rather than failing the export. Rows whose verified text
matches the stored OCR text after whitespace normalization are quarantined
and listed in a warning.
"""
import csv
import os
import sys
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

# The contamination guard compares texts with whitespace collapsed, which is
# exactly the normalization the CER evaluator uses. Import the one canonical
# implementation from evaluation.py rather than keeping a second copy here.
from evaluators.evaluation import edit_distance, normalize_ws as normalize_whitespace
from evaluators.labels_schema import is_writer_batch_id, load_existing_rows, write_labels_csv

EXPORT_DIR = Path("datasets/verified")
IMAGES_DIR = EXPORT_DIR / "images"
LABELS_CSV = EXPORT_DIR / "labels.csv"

PAGE_SIZE = 100


def is_suspected_unedited(row: dict) -> bool:
    """Return whether verified text appears to be saved OCR output."""
    verified = normalize_whitespace(row.get("verified_text") or "")
    extracted = normalize_whitespace(row.get("extracted_text") or "")
    if not verified or not extracted:
        return False

    # This heuristic cannot catch every contamination case (for example, a
    # wrong-program label). It only catches the "saved without editing" pattern,
    # which accounted for the majority of the known contaminated rows.
    return verified == extracted


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
    suspected_unedited_ids = []
    for row in rows:
        text = (row.get("verified_text") or "").strip()
        image_url = row.get("image_url") or ""
        if not text or not image_url:
            print(f"  skip {row.get('id')}: missing verified_text or image_url")
            skipped += 1
            continue
        if is_suspected_unedited(row):
            suspected_unedited_ids.append(str(row.get("id")))
            skipped += 1
            continue
        dest = IMAGES_DIR / f"{row['id']}.jpg"
        if not download_image(image_url, dest):
            print(f"  skip {row.get('id')}: image download failed")
            skipped += 1
            continue
        exported.append(row)

    existing = load_existing_rows(LABELS_CSV)
    preserved = {
        sid: row for sid, row in existing.items() if is_writer_batch_id(sid)
    }
    own_new = {}
    for row in exported:
        extracted = row.get("extracted_text") or ""
        verified = row["verified_text"]
        distance = edit_distance(
            normalize_whitespace(extracted), normalize_whitespace(verified)
        )
        own_new[row["id"]] = {
            "submission_id": row["id"],
            "image_path": f"images/{row['id']}.jpg",
            "verified_text": verified,
            "extracted_text": extracted,
            "verified_at": row.get("verified_at") or "",
            "topic": row.get("topic") or "",
            "student_name": row.get("student_name") or "",
            "literal_verified": "",
            "literal_verified_by": "",
            "literal_verified_at": "",
            "correction_edit_distance": str(distance),
        }
    merged = {**preserved, **own_new}
    write_labels_csv(LABELS_CSV, merged)

    # Re-captures of the same page produce identical verified text; they must
    # not straddle a future train/test split, so flag them at export time.
    duplicates = Counter(
        normalize_whitespace(row["verified_text"]) for row in exported)
    duplicate_groups = {t: n for t, n in duplicates.items() if n > 1}

    fully_verified = sum(
        1 for row in merged.values()
        if str(row.get("literal_verified", "")).strip().lower() == "true"
        and row.get("literal_verified_by")
        and row.get("literal_verified_at")
    )
    distances = [
        int(row["correction_edit_distance"])
        for row in merged.values()
        if str(row.get("correction_edit_distance", "")).strip().isdigit()
    ]

    print(f"Exported {len(exported)} pair(s) to {LABELS_CSV} "
          f"({skipped} skipped).")
    print(f"labels.csv now contains {len(merged)} total row(s) "
          f"({len(preserved)} preserved, {len(own_new)} from this run).")
    print(f"Provenance: {fully_verified}/{len(merged)} fully verified "
          f"(literal_verified=true with verifier and date recorded).")
    if distances:
        distances.sort()
        mid = len(distances) // 2
        median = (
            distances[mid] if len(distances) % 2
            else (distances[mid - 1] + distances[mid]) / 2
        )
        print(f"Correction edit-distance (OCR-sourced rows only, n={len(distances)}): "
              f"mean {sum(distances) / len(distances):.1f}, median {median}, "
              f"min {min(distances)}, max {max(distances)}.")
    if suspected_unedited_ids:
        print(
            "WARNING: skipped submission(s) whose verified_text matches "
            "extracted_text after whitespace normalization: "
            + ", ".join(suspected_unedited_ids)
        )
    if duplicate_groups:
        print(f"WARNING: {len(duplicate_groups)} verified text(s) appear on "
              f"multiple submissions (likely re-captures of the same page). "
              f"Keep such groups on the same side of any train/test split.")


if __name__ == "__main__":
    main()
