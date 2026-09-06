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
import re
from pathlib import Path

FIELDNAMES = [
    "submission_id", "image_path", "verified_text", "extracted_text",
    "verified_at", "topic", "student_name",
    "literal_verified", "literal_verified_by", "literal_verified_at",
    "correction_edit_distance",
]

_WRITER_BATCH_ID = re.compile(r"^(bond|green|yellow)_writer\d+")


def is_writer_batch_id(submission_id: str) -> bool:
    return bool(_WRITER_BATCH_ID.match(submission_id))


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
