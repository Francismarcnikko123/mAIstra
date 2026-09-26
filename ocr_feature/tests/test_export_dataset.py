# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_export_dataset
import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from evaluators import export_dataset


def submission(submission_id, verified_text, extracted_text):
    return {
        "id": submission_id,
        "image_url": f"https://example.test/{submission_id}.jpg",
        "verified_text": verified_text,
        "extracted_text": extracted_text,
        "verified_at": "2026-07-30T00:00:00+00:00",
        "topic": "C programming",
        "student_name": "",
    }


class ExportDatasetContaminationGuardTests(unittest.TestCase):
    def test_skips_normalized_matches_and_lists_ids_in_warning(self):
        contaminated_ids = [
            "6384b35e-bcf3-4a00-9ecf-4387968b6830",
            "cd275d93-bd0a-417b-a34b-135aeaae076e",
            "36a42107-89dc-4ba2-82b3-23e42b15e5e4",
            "058c99f7-4952-4a7d-bd81-8ce66d11f9f2",
        ]
        rows = [
            submission(
                contaminated_ids[0],
                "int main() {\nreturn 0;\n}",
                "int main() { return 0; }",
            ),
            submission(
                contaminated_ids[1],
                "printf(\"x\");",
                "printf(\"x\");",
            ),
            submission(
                contaminated_ids[2],
                "int  total = 0;",
                "int total = 0;",
            ),
            submission(
                contaminated_ids[3],
                "for (i=0; i<3; i++)",
                "for (i=0;\ti<3;\ti++)",
            ),
            submission(
                "d8cb2ec1-31e1-48a0-86f8-8ba61543caa4",
                "printf(\"Result: %d\\n\", result);",
                "printe(\"Result: %d\\n\", result);",
            ),
            submission(
                "c11239b3-8286-40dd-888a-51780071e76d",
                "printf(\"Missing semicolon\");",
                "scanf(\"%d\", &number);",
            ),
            submission(
                "7b2f4eac-fe91-43f4-8e1f-16395424cd56",
                "int main() { return 0; }",
                "Int main() return 2e00;",
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = Path(temp_dir)
            labels_csv = export_dir / "labels.csv"
            output = io.StringIO()
            with (
                patch.object(export_dataset, "IMAGES_DIR", export_dir / "images"),
                patch.object(export_dataset, "LABELS_CSV", labels_csv),
                patch.object(export_dataset, "load_dotenv"),
                patch.object(
                    export_dataset.os,
                    "getenv",
                    side_effect=["https://db", "key"],
                ),
                patch.object(
                    export_dataset,
                    "fetch_verified_submissions",
                    return_value=rows,
                ),
                patch.object(
                    export_dataset,
                    "download_image",
                    return_value=True,
                ) as download,
                redirect_stdout(output),
            ):
                export_dataset.main()

            with labels_csv.open(newline="", encoding="utf-8") as file:
                exported_ids = [
                    row["submission_id"] for row in csv.DictReader(file)
                ]

        self.assertEqual(
            exported_ids,
            [
                "d8cb2ec1-31e1-48a0-86f8-8ba61543caa4",
                "c11239b3-8286-40dd-888a-51780071e76d",
                "7b2f4eac-fe91-43f4-8e1f-16395424cd56",
            ],
        )
        self.assertEqual(download.call_count, 3)
        warning = output.getvalue()
        self.assertIn("WARNING", warning)
        for submission_id in contaminated_ids:
            self.assertIn(submission_id, warning)
        self.assertNotIn("d8cb2ec1-31e1-48a0-86f8-8ba61543caa4", warning)


class ExportDatasetPreservesOtherSourceRowsTests(unittest.TestCase):
    def test_preserves_writer_batch_rows_already_in_file(self):
        existing_writer_batch_row = {
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
        }
        new_supabase_row = submission(
            "d8cb2ec1-31e1-48a0-86f8-8ba61543caa4",
            "printf(\"Result: %d\\n\", result);",
            "printe(\"Result: %d\\n\", result);",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = Path(temp_dir)
            labels_csv = export_dir / "labels.csv"
            with labels_csv.open("w", newline="", encoding="utf-8") as f:
                from evaluators.labels_schema import FIELDNAMES
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerow(existing_writer_batch_row)

            output = io.StringIO()
            with (
                patch.object(export_dataset, "IMAGES_DIR", export_dir / "images"),
                patch.object(export_dataset, "LABELS_CSV", labels_csv),
                patch.object(export_dataset, "load_dotenv"),
                patch.object(
                    export_dataset.os, "getenv", side_effect=["https://db", "key"],
                ),
                patch.object(
                    export_dataset, "fetch_verified_submissions",
                    return_value=[new_supabase_row],
                ),
                patch.object(export_dataset, "download_image", return_value=True),
                redirect_stdout(output),
            ):
                export_dataset.main()

            with labels_csv.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

        ids = [row["submission_id"] for row in rows]
        self.assertIn("bond_writer1_2", ids)
        self.assertIn("d8cb2ec1-31e1-48a0-86f8-8ba61543caa4", ids)
        preserved = next(r for r in rows if r["submission_id"] == "bond_writer1_2")
        self.assertEqual(preserved["literal_verified_by"], "Jayrald")


class ExportDatasetSummaryTests(unittest.TestCase):
    def test_summary_reports_provenance_and_correction_distance_over_full_file(self):
        pre_verified_row = {
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
        }
        new_row = submission(
            "d8cb2ec1-31e1-48a0-86f8-8ba61543caa4",
            "printf(\"Result: %d\\n\", result);",
            "printe(\"Result: %d\\n\", result);",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = Path(temp_dir)
            labels_csv = export_dir / "labels.csv"
            with labels_csv.open("w", newline="", encoding="utf-8") as f:
                from evaluators.labels_schema import FIELDNAMES
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerow(pre_verified_row)

            output = io.StringIO()
            with (
                patch.object(export_dataset, "IMAGES_DIR", export_dir / "images"),
                patch.object(export_dataset, "LABELS_CSV", labels_csv),
                patch.object(export_dataset, "load_dotenv"),
                patch.object(
                    export_dataset.os, "getenv", side_effect=["https://db", "key"],
                ),
                patch.object(
                    export_dataset, "fetch_verified_submissions",
                    return_value=[new_row],
                ),
                patch.object(export_dataset, "download_image", return_value=True),
                redirect_stdout(output),
            ):
                export_dataset.main()

        summary = output.getvalue()
        self.assertIn("Provenance: 1/2 fully verified", summary)
        self.assertIn("labels.csv now contains 2 total row(s)", summary)


def run_export(rows, getenv=("https://db", "key")):
    """Run main() on fake rows; return (labels.csv rows by id, printed output)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        export_dir = Path(temp_dir)
        labels_csv = export_dir / "labels.csv"
        output = io.StringIO()
        with (
            patch.object(export_dataset, "IMAGES_DIR", export_dir / "images"),
            patch.object(export_dataset, "LABELS_CSV", labels_csv),
            patch.object(export_dataset, "load_dotenv"),
            patch.object(export_dataset.os, "getenv", side_effect=list(getenv)),
            patch.object(export_dataset, "fetch_verified_submissions", return_value=rows),
            patch.object(export_dataset, "download_image", return_value=True),
            redirect_stdout(output),
        ):
            export_dataset.main()
        with labels_csv.open(newline="", encoding="utf-8") as file:
            written = {row["submission_id"]: row for row in csv.DictReader(file)}
    return written, output.getvalue()


class ExportDatasetProgramsTests(unittest.TestCase):
    def test_split_page_exports_every_program_as_its_own_block(self):
        row = submission("split-1", "int p1;", "int pl;\nint p2:\nint p3;")
        # Stored out of order on purpose: position decides, not list order.
        row["submission_programs"] = [
            {"position": 2, "verified_text": "int p2;"},
            {"position": 1, "verified_text": "int p1;"},
            {"position": 3, "verified_text": "int p3;"},
        ]
        written, output = run_export([row])

        exported = written["split-1"]
        self.assertEqual(json.loads(exported["program_blocks"]),
                         ["int p1;", "int p2;", "int p3;"])
        self.assertEqual(exported["verified_text"], "int p1;\n\nint p2;\n\nint p3;")
        # Tab order is not reading order: no misleading correction distance.
        self.assertEqual(exported["correction_edit_distance"], "")
        self.assertIn("1 of them hold several programs", output)

    def test_split_page_saved_without_edits_is_set_aside_like_any_other(self):
        row = submission("split-unedited", "int p1;", "int p1;\nint p2;")
        row["submission_programs"] = [
            {"position": 1, "verified_text": "int p1;"},
            {"position": 2, "verified_text": "int p2;"},
        ]
        written, output = run_export([row])
        self.assertNotIn("split-unedited", written)
        self.assertIn("split-unedited", output)

    def test_one_program_exports_exactly_as_before(self):
        row = submission("single-1", "int x = 1;", "int x = l;")
        row["submission_programs"] = [{"position": 1, "verified_text": "int x = 1;"}]
        written, _ = run_export([row])

        exported = written["single-1"]
        self.assertEqual(exported["verified_text"], "int x = 1;")
        self.assertEqual(exported["program_blocks"], "")
        self.assertEqual(exported["correction_edit_distance"], "1")

    def test_page_without_program_rows_falls_back_to_the_page_text(self):
        written, _ = run_export([submission("legacy-1", "int y;", "int v;")])
        self.assertEqual(written["legacy-1"]["verified_text"], "int y;")
        self.assertEqual(written["legacy-1"]["program_blocks"], "")

    def test_programs_table_wins_over_a_stale_program_1_copy_and_is_reported(self):
        row = submission("stale-1", "old program one", "int z = 0;")
        row["submission_programs"] = [{"position": 1, "verified_text": "int z = 0 ;"}]
        written, output = run_export([row])

        self.assertEqual(written["stale-1"]["verified_text"], "int z = 0 ;")
        self.assertIn("WARNING: Program 1 in submission_programs differs", output)
        self.assertIn("stale-1", output)

    def test_prefers_supabase_key_and_accepts_the_legacy_name(self):
        getenv_calls = []

        def getenv(name, default=None):
            getenv_calls.append(name)
            return {"SUPABASE_URL": "https://db", "SUPABASE_KEY": "publishable"}.get(name, default)

        with (
            patch.object(export_dataset, "load_dotenv"),
            patch.object(export_dataset.os, "getenv", side_effect=getenv),
            patch.object(export_dataset, "fetch_verified_submissions", return_value=[]) as fetch,
            redirect_stdout(io.StringIO()),
        ):
            export_dataset.main()
        fetch.assert_called_once_with("https://db", "publishable")
        self.assertNotIn("SUPABASE_ANON_KEY", getenv_calls)


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected HTTP {self.status_code}")


class FetchVerifiedSubmissionsTests(unittest.TestCase):
    def test_reads_verified_and_graded_pages_with_their_programs(self):
        with patch.object(export_dataset.requests, "get",
                          return_value=FakeResponse(200, [{"id": "a"}])) as get:
            rows = export_dataset.fetch_verified_submissions("https://db", "k")

        params = get.call_args.kwargs["params"]
        self.assertEqual(params["status"], "in.(verified,graded)")
        self.assertIn("submission_programs(position,verified_text)", params["select"])
        self.assertEqual(rows, [{"id": "a"}])

    def test_retries_without_programs_on_a_database_without_the_table(self):
        responses = [
            FakeResponse(400, text='Could not find a relationship between '
                                   '"submissions" and "submission_programs"'),
            FakeResponse(200, [{"id": "a"}]),
        ]
        with (
            patch.object(export_dataset.requests, "get", side_effect=responses) as get,
            redirect_stdout(io.StringIO()),
        ):
            rows = export_dataset.fetch_verified_submissions("https://db", "k")

        self.assertEqual(rows, [{"id": "a"}])
        self.assertNotIn("submission_programs", get.call_args.kwargs["params"]["select"])


if __name__ == "__main__":
    unittest.main()
