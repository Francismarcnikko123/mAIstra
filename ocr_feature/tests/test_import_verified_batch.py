# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_import_verified_batch
import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import import_verified_batch as batch
from evaluators.labels_schema import FIELDNAMES


def _make_source_batch(root: Path):
    paper_dir = root / "bond"
    txt_dir = paper_dir / "bond_txt"
    txt_dir.mkdir(parents=True)
    (paper_dir / "bond_writer1_2.jpg").write_bytes(b"fake-image-bytes")
    (txt_dir / "bond_writer1_2.txt").write_text("int main() {}\n", encoding="utf-8")


class ImportVerifiedBatchProvenanceTests(unittest.TestCase):
    def test_populates_literal_verified_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            _make_source_batch(source_root)
            dest_images = root / "dest_images"
            labels_csv = root / "labels.csv"
            samples_dir = root / "samples"

            with (
                patch.object(batch, "SOURCE_ROOT", source_root),
                patch.object(batch, "PAPER_TYPES", ["bond"]),
                patch.object(batch, "DEST_IMAGES_ROOT", dest_images),
                patch.object(batch, "LABELS_CSV", labels_csv),
                patch.object(batch, "SAMPLES_DIR", samples_dir),
                redirect_stdout(io.StringIO()),
            ):
                batch.main("Jayrald")

            with labels_csv.open(newline="", encoding="utf-8") as f:
                row = next(csv.DictReader(f))

        self.assertEqual(row["literal_verified"], "true")
        self.assertEqual(row["literal_verified_by"], "Jayrald")
        self.assertTrue(row["literal_verified_at"])

    def test_preserves_supabase_sourced_rows_already_in_file(self):
        supabase_row = {
            "submission_id": "d8cb2ec1-31e1-48a0-86f8-8ba61543caa4",
            "image_path": "images/d8cb2ec1-31e1-48a0-86f8-8ba61543caa4.jpg",
            "verified_text": "printf(\"Result: %d\\n\", result);",
            "extracted_text": "printe(\"Result: %d\\n\", result);",
            "verified_at": "2026-08-01",
            "topic": "C programming",
            "student_name": "",
            "literal_verified": "",
            "literal_verified_by": "",
            "literal_verified_at": "",
            "correction_edit_distance": "1",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            _make_source_batch(source_root)
            dest_images = root / "dest_images"
            labels_csv = root / "labels.csv"
            samples_dir = root / "samples"

            with labels_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerow(supabase_row)

            with (
                patch.object(batch, "SOURCE_ROOT", source_root),
                patch.object(batch, "PAPER_TYPES", ["bond"]),
                patch.object(batch, "DEST_IMAGES_ROOT", dest_images),
                patch.object(batch, "LABELS_CSV", labels_csv),
                patch.object(batch, "SAMPLES_DIR", samples_dir),
                redirect_stdout(io.StringIO()),
            ):
                batch.main("Jayrald")

            with labels_csv.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

        ids = [r["submission_id"] for r in rows]
        self.assertIn("d8cb2ec1-31e1-48a0-86f8-8ba61543caa4", ids)
        self.assertIn("bond_writer1_2", ids)
        preserved = next(
            r for r in rows
            if r["submission_id"] == "d8cb2ec1-31e1-48a0-86f8-8ba61543caa4"
        )
        self.assertEqual(preserved["correction_edit_distance"], "1")


if __name__ == "__main__":
    unittest.main()
