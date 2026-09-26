"""Shared schema and read/merge/write helpers for datasets/verified/labels.csv.

Both export_dataset.py (Supabase-sourced rows) and import_verified_batch.py
(physically-verified batch rows, e.g. "bond_writer1_2") write into this same
file. Before this module existed, each script opened the file in truncating
write mode and wrote ONLY its own rows -- running one after the other
silently destroyed the other's data. is_writer_batch_id() lets each script
tell "my own rows" apart from "the other script's rows" by ID shape alone
(no extra column needed), so a merge-preserving write is possible without
either script needing to know about the other's data source.
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
    # Only for a page the teacher split into several programs (Supabase
    # submission_programs): a JSON list of each program's verified text in tab
    # order. Empty for every page stored as one text. Tab order is not the
    # page's reading order, so such a page's verified_text is NOT whole-page
    # ground truth; see is_split_page().
    "program_blocks",
]

_WRITER_BATCH_ID = re.compile(r"^(bond|green|yellow)_writer\d+")


def is_writer_batch_id(submission_id: str) -> bool:
    return bool(_WRITER_BATCH_ID.match(submission_id))


def program_blocks(row: dict) -> list[str]:
    """The verified programs of a split page, in tab order; [] otherwise.

    A malformed value raises instead of falling back to verified_text, so a
    damaged row can never quietly become a wrong training label."""
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
    """True when the page holds several programs stored as separate blocks.

    Readers that need the whole page in reading order (CER references, test
    holdouts) must skip these rows; the line-crop builder matches each block
    to the page's lines on its own instead."""
    return len(program_blocks(row)) > 1


def load_existing_rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["submission_id"]: row for row in csv.DictReader(f)}


def write_labels_csv(path: Path, rows_by_id: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows_by_id.values():
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})
