"""Export teacher-verified papers from Supabase as OCR training data.

Writes datasets/verified/labels.csv (one row per paper) and the photos as
datasets/verified/images/<submission_id>.jpg. Reads SUPABASE_URL and
SUPABASE_KEY from .env. A development tool; the server doesn't use it.

- Exports papers with status 'verified' or 'graded'.
- The text comes from submission_programs (or the paper's own
  verified_text if it has no programs). A paper split into several programs
  stores each one in program_blocks and is never used as whole-page ground
  truth.
- Safe to re-run: photos already downloaded are kept, rows added by
  import_verified_batch.py are kept, and only this script's rows are rebuilt.
- Skipped and listed: a paper whose verified text equals its OCR text (saved
  without editing), and a paper whose photo can't be downloaded.

Run from ocr_feature/:
    .venv/bin/python -m evaluators.export_dataset
"""
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

# Same whitespace handling as the CER evaluator.
from evaluators.evaluation import edit_distance, normalize_ws as normalize_whitespace
from evaluators.labels_schema import is_writer_batch_id, load_existing_rows, write_labels_csv

EXPORT_DIR = Path("datasets/verified")
IMAGES_DIR = EXPORT_DIR / "images"
LABELS_CSV = EXPORT_DIR / "labels.csv"

PAGE_SIZE = 100


def is_suspected_unedited(row: dict) -> bool:
    """True if the verified text equals the OCR text (ignoring whitespace):
    the teacher probably saved without checking it."""
    verified = normalize_whitespace(row.get("verified_text") or "")
    extracted = normalize_whitespace(row.get("extracted_text") or "")
    if not verified or not extracted:
        return False

    # Catches this common case only, not every bad label (e.g. the wrong
    # program).
    return verified == extracted


SUBMISSION_COLUMNS = (
    "id,image_url,extracted_text,verified_text,verified_at,topic,student_name"
)
# Each paper's programs, fetched in the same request.
PROGRAMS_EMBED = "submission_programs(position,verified_text)"


def fetch_verified_submissions(base_url: str, api_key: str) -> list[dict]:
    """Fetch every verified or graded paper with its programs, 100 at a time.
    On a database without submission_programs, every paper is exported as
    one text."""
    rows = []
    headers = {"apikey": api_key, "Authorization": f"Bearer {api_key}"}
    select = f"{SUBMISSION_COLUMNS},{PROGRAMS_EMBED}"
    offset = 0
    while True:
        response = requests.get(
            f"{base_url}/rest/v1/submissions",
            headers=headers,
            params={
                "status": "in.(verified,graded)",
                "select": select,
                "order": "verified_at.asc",
                "limit": str(PAGE_SIZE),
                "offset": str(offset),
            },
            timeout=30,
        )
        if (
            response.status_code == 400
            and select != SUBMISSION_COLUMNS
            and "submission_programs" in response.text
        ):
            print("  note: this database has no submission_programs table; "
                  "exporting every page as one text.")
            select = SUBMISSION_COLUMNS
            rows, offset = [], 0
            continue
        response.raise_for_status()
        page = response.json()
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def page_programs(row: dict) -> list[str]:
    """The page's verified programs in tab order (Program 1 first)."""
    programs = row.get("submission_programs") or []
    ordered = sorted(programs, key=lambda program: program.get("position") or 0)
    return [program.get("verified_text") or "" for program in ordered]


def label_for(row: dict) -> tuple[str, list[str]]:
    """(verified_text, program_blocks) for one paper. One program: its text
    and no blocks. Several: the programs joined by a blank line (for reading
    only) and the programs. None: the paper's own verified_text."""
    programs = page_programs(row)
    if len(programs) > 1:
        return "\n\n".join(programs), programs
    if len(programs) == 1:
        return programs[0], []
    return row.get("verified_text") or "", []


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
    # SUPABASE_ANON_KEY is still accepted from old .env files.
    api_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not base_url or not api_key:
        sys.exit("SUPABASE_URL and SUPABASE_KEY must be set (see .env).")

    rows = fetch_verified_submissions(base_url, api_key)
    print(f"Found {len(rows)} verified submission(s).")
    if not rows:
        return

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    exported = []
    skipped = 0
    suspected_unedited_ids = []
    mirror_mismatch_ids = []
    for row in rows:
        label_text, blocks = label_for(row)
        programs = page_programs(row)
        # Program 1 should equal submissions.verified_text. If it doesn't,
        # the programs table wins and the paper is reported.
        if programs and (row.get("verified_text") or "") != programs[0]:
            mirror_mismatch_ids.append(str(row.get("id")))
        row = {**row, "verified_text": label_text}
        text = label_text.strip()
        image_url = row.get("image_url") or ""
        if not text or not image_url or any(not block.strip() for block in blocks):
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
        exported.append({**row, "_blocks": blocks})

    existing = load_existing_rows(LABELS_CSV)
    preserved = {
        sid: row for sid, row in existing.items() if is_writer_batch_id(sid)
    }
    own_new = {}
    for row in exported:
        extracted = row.get("extracted_text") or ""
        verified = row["verified_text"]
        blocks = row["_blocks"]
        # Blank for split papers: the programs are in tab order, not page
        # order, so the distance would count reordering, not corrections.
        distance = "" if blocks else str(edit_distance(
            normalize_whitespace(extracted), normalize_whitespace(verified)
        ))
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
            "correction_edit_distance": distance,
            "program_blocks": json.dumps(blocks, ensure_ascii=False) if blocks else "",
        }
    merged = {**preserved, **own_new}
    write_labels_csv(LABELS_CSV, merged)

    # The same page photographed twice has the same text; flag it so both
    # copies stay on the same side of a train/test split.
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

    split_pages = sum(1 for row in exported if row["_blocks"])
    print(f"Exported {len(exported)} pair(s) to {LABELS_CSV} "
          f"({skipped} skipped).")
    if split_pages:
        print(f"{split_pages} of them hold several programs: stored per program "
              f"in program_blocks; the crop builder aligns each program on its "
              f"own, and CER/holdout readers skip them.")
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
    if mirror_mismatch_ids:
        print(
            "WARNING: Program 1 in submission_programs differs from "
            "submissions.verified_text for: " + ", ".join(mirror_mismatch_ids)
            + ". The programs table was used. A save probably bypassed "
            "save_submission_programs(); tell Jayrald."
        )
    if duplicate_groups:
        print(f"WARNING: {len(duplicate_groups)} verified text(s) appear on "
              f"multiple submissions (likely re-captures of the same page). "
              f"Keep such groups on the same side of any train/test split.")


if __name__ == "__main__":
    main()
