import csv
import io
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


if __name__ == "__main__":
    unittest.main()
