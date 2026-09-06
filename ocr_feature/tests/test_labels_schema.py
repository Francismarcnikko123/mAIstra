# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_labels_schema
import csv
import tempfile
import unittest
from pathlib import Path

from evaluators.labels_schema import (
    FIELDNAMES,
    is_writer_batch_id,
    load_existing_rows,
    write_labels_csv,
)


class IsWriterBatchIdTests(unittest.TestCase):
    def test_matches_known_paper_type_writer_ids(self):
        self.assertTrue(is_writer_batch_id("bond_writer1_2"))
        self.assertTrue(is_writer_batch_id("green_writer1"))
        self.assertTrue(is_writer_batch_id("green_writer13_B2_1"))
        self.assertTrue(is_writer_batch_id("yellow_writer4_1"))
        self.assertTrue(is_writer_batch_id("yellow_writer4_B2_1"))

    def test_rejects_supabase_uuid(self):
        self.assertFalse(
            is_writer_batch_id("6384b35e-bcf3-4a00-9ecf-4387968b6830")
        )

    def test_rejects_unrelated_string(self):
        self.assertFalse(is_writer_batch_id("submission_42"))


class LoadExistingRowsTests(unittest.TestCase):
    def test_returns_empty_dict_when_file_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "labels.csv"
            self.assertEqual(load_existing_rows(missing), {})

    def test_loads_rows_keyed_by_submission_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labels.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerow({
                    "submission_id": "bond_writer1_2",
                    "image_path": "images/bond/bond_writer1_2.jpg",
                    "verified_text": "int main() {}",
                    "extracted_text": "",
                    "verified_at": "2026-09-01",
                    "topic": "",
                    "student_name": "writer1",
                    "literal_verified": "true",
                    "literal_verified_by": "Jayrald",
                    "literal_verified_at": "2026-09-01",
                    "correction_edit_distance": "",
                })

            result = load_existing_rows(path)

        self.assertEqual(set(result), {"bond_writer1_2"})
        self.assertEqual(result["bond_writer1_2"]["verified_text"], "int main() {}")
        self.assertEqual(result["bond_writer1_2"]["literal_verified_by"], "Jayrald")


class WriteLabelsCsvTests(unittest.TestCase):
    def test_preserves_insertion_order_not_sorted(self):
        rows_by_id = {
            "d8cb2ec1-uuid": {"submission_id": "d8cb2ec1-uuid", "verified_text": "b"},
            "bond_writer1_2": {"submission_id": "bond_writer1_2", "verified_text": "a"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labels.csv"
            write_labels_csv(path, rows_by_id)
            with path.open(newline="", encoding="utf-8") as f:
                ids = [row["submission_id"] for row in csv.DictReader(f)]

        self.assertEqual(ids, ["d8cb2ec1-uuid", "bond_writer1_2"])

    def test_missing_fields_default_to_empty_string(self):
        rows_by_id = {"x": {"submission_id": "x", "verified_text": "hi"}}
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labels.csv"
            write_labels_csv(path, rows_by_id)
            with path.open(newline="", encoding="utf-8") as f:
                row = next(csv.DictReader(f))

        self.assertEqual(row["correction_edit_distance"], "")
        self.assertEqual(row["literal_verified"], "")

    def test_writes_header_with_all_fieldnames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labels.csv"
            write_labels_csv(path, {})
            with path.open(newline="", encoding="utf-8") as f:
                header = next(csv.reader(f))

        self.assertEqual(header, FIELDNAMES)


if __name__ == "__main__":
    unittest.main()
