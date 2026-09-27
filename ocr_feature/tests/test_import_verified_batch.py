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



def _row(submission_id, text, verified_by=""):
    """A writer-batch row as an earlier import left it in labels.csv."""
    paper_type = submission_id.split("_")[0]
    return {
        **{field: "" for field in FIELDNAMES},
        "submission_id": submission_id,
        "image_path": f"images/{paper_type}/{submission_id}.jpg",
        "verified_text": text,
        "extracted_text": "",
        "verified_at": "2026-08-30",
        "topic": "",
        "student_name": "writer1",
        "literal_verified": "true" if verified_by else "",
        "literal_verified_by": verified_by,
        "literal_verified_at": "2026-08-30" if verified_by else "",
        "correction_edit_distance": "",
    }


class ReimportForANewBatchTests(unittest.TestCase):
    """Importing a new batch: test pages stay out of train, and earlier pages
    keep their rows."""

    PAPER_FOLDERS = {"bond": "bond", "green": "greenbook", "yellow": "yellow_pad"}

    def run_import(self, source, existing=(), sample_images=(), sample_labels=(),
                   paper_types=("bond",), already_copied=(), dry_run=False):
        """Run the import in a temporary folder.

        source: {stem: text}; each page goes to its paper type's folder.
        existing: labels.csv rows. sample_images: paths under samples/.
        sample_labels: filenames listed in samples/labels.csv.
        already_copied: stems whose image is already in the train folder.
        Returns (rows by id, stems copied by this run, printed output,
        labels.csv bytes before, labels.csv bytes after)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for stem, text in source.items():
                folder = root / "source" / self.PAPER_FOLDERS[stem.split("_")[0]]
                (folder / "txt").mkdir(parents=True, exist_ok=True)
                (folder / f"{stem}.jpg").write_bytes(b"img")
                (folder / "txt" / f"{stem}.txt").write_text(text + "\n", encoding="utf-8")
            (root / "source").mkdir(exist_ok=True)
            dest_images = root / "dest_images"
            for stem in already_copied:
                folder = dest_images / self.PAPER_FOLDERS[stem.split("_")[0]]
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{stem}.jpg").write_bytes(b"img")
            labels_csv = root / "labels.csv"
            with labels_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                for row in existing:
                    writer.writerow(row)
            before = labels_csv.read_bytes()
            samples_dir = root / "samples"
            for relative in sample_images:
                (samples_dir / relative).parent.mkdir(parents=True, exist_ok=True)
                (samples_dir / relative).write_bytes(b"img")
            if sample_labels:
                samples_dir.mkdir(exist_ok=True)
                with (samples_dir / "labels.csv").open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["filename", "ground_truth_text"])
                    writer.writeheader()
                    for filename in sample_labels:
                        writer.writerow({"filename": filename, "ground_truth_text": "x"})

            copies = []
            real_copy = batch.shutil.copy2

            def copy2(src, dst):
                copies.append(Path(src).stem)
                return real_copy(src, dst)

            output = io.StringIO()
            with (
                patch.object(batch, "SOURCE_ROOT", root / "source"),
                patch.object(batch, "PAPER_TYPES", list(paper_types)),
                patch.object(batch, "DEST_IMAGES_ROOT", dest_images),
                patch.object(batch, "LABELS_CSV", labels_csv),
                patch.object(batch, "SAMPLES_DIR", samples_dir),
                patch.object(batch.shutil, "copy2", copy2),
                redirect_stdout(output),
            ):
                batch.main("Nikko", dry_run=dry_run)

            with labels_csv.open(newline="", encoding="utf-8") as f:
                rows = {row["submission_id"]: row for row in csv.DictReader(f)}
            after = labels_csv.read_bytes()
        return rows, copies, output.getvalue(), before, after

    def test_a_test_page_in_its_paper_type_folder_is_never_imported(self):
        # select_holdout.py keeps test images in samples/<paper_type>/.
        rows, copied, _, _, _ = self.run_import(
            {"bond_writer1_1": "int a;", "bond_writer5_1": "int b;"},
            sample_images=["bond/bond_writer1_1.jpg"],
        )
        self.assertNotIn("bond_writer1_1", rows)
        self.assertNotIn("bond_writer1_1", copied)
        self.assertIn("bond_writer5_1", rows)

    def test_a_test_page_listed_in_samples_labels_is_never_imported(self):
        rows, _, _, _, _ = self.run_import(
            {"bond_writer1_1": "int a;"}, sample_labels=["bond/bond_writer1_1.jpg"],
        )
        self.assertNotIn("bond_writer1_1", rows)

    def test_a_test_page_already_in_train_is_removed_and_reported(self):
        rows, _, output, _, _ = self.run_import(
            {"bond_writer5_1": "int b;"},
            existing=[_row("bond_writer1_1", "int a;")],
            sample_images=["bond/bond_writer1_1.jpg"],
        )
        self.assertNotIn("bond_writer1_1", rows)
        self.assertIn("REMOVED FROM TRAIN (1)", output)

    def test_a_folder_with_only_the_new_batch_keeps_earlier_pages(self):
        earlier = _row("bond_writer1_2", "int a;", verified_by="Jayrald")
        rows, _, _, _, _ = self.run_import({"bond_writer5_1": "int b;"}, existing=[earlier])
        self.assertEqual(rows["bond_writer1_2"], earlier)
        self.assertIn("bond_writer5_1", rows)

    def test_rerun_keeps_who_verified_earlier_pages(self):
        unrecorded = _row("bond_writer1_2", "int a;")             # before provenance existed
        recorded = _row("bond_writer2_1", "int c;", verified_by="Jayrald")
        rows, _, _, _, _ = self.run_import(
            {"bond_writer1_2": "int a;", "bond_writer2_1": "int c;", "bond_writer5_1": "int b;"},
            existing=[unrecorded, recorded],
        )
        self.assertEqual(rows["bond_writer1_2"], unrecorded)       # still unknown, not "Nikko"
        self.assertEqual(rows["bond_writer2_1"]["literal_verified_by"], "Jayrald")
        self.assertEqual(rows["bond_writer5_1"]["literal_verified_by"], "Nikko")

    def test_changed_text_counts_as_a_new_verification(self):
        rows, _, output, _, _ = self.run_import(
            {"bond_writer1_2": "int a = 1;"},
            existing=[_row("bond_writer1_2", "int a;", verified_by="Jayrald")],
        )
        self.assertEqual(rows["bond_writer1_2"]["verified_text"], "int a = 1;")
        self.assertEqual(rows["bond_writer1_2"]["literal_verified_by"], "Nikko")
        self.assertIn("TEXT CHANGED (1)", output)

    def test_a_new_page_from_a_greenbook_test_writer_is_never_imported(self):
        # Greenbook holds out whole writers (number + batch); a returning
        # student keeps both, so their new page must stay out of train too.
        rows, copied, output, _, _ = self.run_import(
            {"green_writer13_B2_3": "int a;", "green_writer5_B4_1": "int b;"},
            sample_images=["greenbook/green_writer13_B2_1.jpg"],
            paper_types=("greenbook",),
        )
        self.assertNotIn("green_writer13_B2_3", rows)
        self.assertNotIn("green_writer13_B2_3", copied)
        self.assertIn("test writer green_writer13_B2", output)
        self.assertIn("green_writer5_B4_1", rows)

    def test_a_batch_without_some_paper_types_still_imports(self):
        rows, _, output, _, _ = self.run_import(
            {"bond_writer5_1": "int b;"}, paper_types=("bond", "yellow_pad"),
        )
        self.assertIn("bond_writer5_1", rows)
        self.assertIn("yellow_pad/: no such folder in this batch", output)

    def test_rows_keep_their_place_and_new_pages_go_last(self):
        earlier = [_row("bond_writer1_1", "int a;"), _row("bond_writer1_2", "int c;")]
        rows, _, _, _, _ = self.run_import({"bond_writer5_1": "int b;"}, existing=earlier)
        self.assertEqual(list(rows), ["bond_writer1_1", "bond_writer1_2", "bond_writer5_1"])

    def test_pages_already_imported_are_not_copied_again(self):
        _, copied, _, _, _ = self.run_import(
            {"bond_writer1_2": "int a;", "bond_writer5_1": "int b;"},
            existing=[_row("bond_writer1_2", "int a;")],
            already_copied=["bond_writer1_2"],
        )
        self.assertEqual(copied, ["bond_writer5_1"])

    def test_dry_run_reports_everything_and_writes_nothing(self):
        rows, copied, output, before, after = self.run_import(
            {"bond_writer1_2": "int a = 1;", "bond_writer5_1": "int b;"},
            existing=[_row("bond_writer1_2", "int a;", verified_by="Jayrald")],
            dry_run=True,
        )
        self.assertEqual(after, before)
        self.assertEqual(copied, [])
        self.assertIn("DRY RUN", output)
        self.assertIn("ADDED (1): ['bond_writer5_1']", output)
        self.assertIn("TEXT CHANGED (1)", output)

if __name__ == "__main__":
    unittest.main()
