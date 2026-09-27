"""The columns of datasets/verified/labels.csv, and helpers to read and
write it.

Two scripts write this file: export_dataset.py (rows from Supabase) and
import_verified_batch.py (rows such as "bond_writer1_2").
is_writer_batch_id() tells their rows apart, so each script keeps the
other's rows.
"""
import csv
import json
import re
from pathlib import Path

FIELDNAMES = [
    "submission_id", "image_path", "verified_text", "extracted_text",
    "verified_at", "topic", "student_name",
    "literal_verified", "literal_verified_by", "literal_verified_at",
    "correction_edit_distance",
    # Only for a page split into several programs: a JSON list of each
    # program's text, in tab order. Such a page isn't whole-page ground truth
    # (see is_split_page).
    "program_blocks",
]

_WRITER_BATCH_ID = re.compile(r"^(bond|green|yellow)_writer\d+")


def is_writer_batch_id(submission_id: str) -> bool:
    """True for rows from import_verified_batch.py (ids like "bond_writer1_2")."""
    return bool(_WRITER_BATCH_ID.match(submission_id))


def program_blocks(row: dict) -> list[str]:
    """The programs of a split page, in tab order; [] otherwise. A malformed
    value raises an error, so it can't become a wrong training label."""
    raw = (row.get("program_blocks") or "").strip()
    if not raw:
        return []
    try:
        blocks = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{row.get('submission_id')}: program_blocks is not valid JSON"
        ) from error
    if not isinstance(blocks, list) or not all(isinstance(b, str) for b in blocks):
        raise ValueError(
            f"{row.get('submission_id')}: program_blocks must be a list of strings"
        )
    return blocks


def is_split_page(row: dict) -> bool:
    """True if the page holds several programs. Anything that needs the
    whole page in reading order (CER, the test set) skips these rows."""
    return len(program_blocks(row)) > 1


def load_existing_rows(path: Path) -> dict[str, dict]:
    """labels.csv rows by submission_id; {} if the file doesn't exist."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["submission_id"]: row for row in csv.DictReader(f)}


def write_labels_csv(path: Path, rows_by_id: dict[str, dict]) -> None:
    """Write all rows with the standard columns, replacing the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows_by_id.values():
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})
