import builtins
import importlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


_real_import = builtins.__import__


def _reject_ocr_import(name, *args, **kwargs):
    if name in {"ocr_pipeline", "paddleocr"}:
        raise AssertionError(f"CER evaluator imported OCR runtime eagerly: {name}")
    return _real_import(name, *args, **kwargs)


class EvaluateCerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.modules.pop("evaluate_cer", None)
        with patch("builtins.__import__", side_effect=_reject_ocr_import):
            cls.evaluator = importlib.import_module("evaluate_cer")

    def _row(self):
        return {
            "filename": "page.png",
            "ground_truth_text": "abcd",
            "paper_type": "bond",
            "writer": "nikko",
            "literal_verified": "true",
            "literal_verified_by": "human-reviewer",
            "literal_verified_at": "2026-08-02",
        }

    def _write_fixture(self, root, row, include_verification=True):
        samples = root / "samples"
        samples.mkdir()
        (samples / row["filename"]).write_bytes(b"image")
        columns = ["filename", "ground_truth_text", "paper_type", "writer"]
        if include_verification:
            columns.extend((
                "literal_verified",
                "literal_verified_by",
                "literal_verified_at",
            ))
        values = [str(row.get(column, "")) for column in columns]
        (samples / "labels.csv").write_text(
            ",".join(columns) + "\n" + ",".join(values) + "\n",
            encoding="utf-8",
        )
        return samples

    def _run_invalid(self, row, include_verification=True):
        attempted_imports = []
        output = io.StringIO()

        def track_import(name, *args, **kwargs):
            if name in {"ocr_pipeline", "paddleocr"}:
                attempted_imports.append(name)
            return _real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            samples = self._write_fixture(
                Path(temp_dir),
                row,
                include_verification=include_verification,
            )
            with (
                patch.object(self.evaluator, "SAMPLES_DIR", samples),
                patch.object(
                    self.evaluator,
                    "LABELS_CSV",
                    samples / "labels.csv",
                ),
                patch("builtins.__import__", side_effect=track_import),
                redirect_stdout(output),
            ):
                exit_code = self.evaluator.main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(attempted_imports, [])
        return output.getvalue()

    def test_missing_literal_verification_rejects_before_ocr_import(self):
        rendered = self._run_invalid(
            self._row(),
            include_verification=False,
        )

        self.assertIn("literal_verified must be true", rendered)
        self.assertIn("human transcription from the source paper", rendered)

    def test_blank_literal_verification_rejects_before_ocr_import(self):
        row = self._row()
        row["literal_verified"] = ""

        rendered = self._run_invalid(row)

        self.assertIn("page.png: literal_verified must be true", rendered)

    def test_false_literal_verification_rejects_before_ocr_import(self):
        row = self._row()
        row["literal_verified"] = "false"

        rendered = self._run_invalid(row)

        self.assertIn("page.png: literal_verified must be true", rendered)

    def test_missing_audit_metadata_rejects_before_ocr_import(self):
        row = self._row()
        row["literal_verified_by"] = ""
        row["literal_verified_at"] = ""

        rendered = self._run_invalid(row)

        self.assertIn("page.png: literal_verified_by is required", rendered)
        self.assertIn("page.png: literal_verified_at is required", rendered)

    def test_valid_synthetic_row_preserves_cer_report(self):
        calls = []

        def fake_extract(image_path):
            calls.append(image_path)
            return {
                "raw_text": "abxd",
                "cleaned_text": "abcd",
                "review_suggestions": [],
            }

        output = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            samples = self._write_fixture(Path(temp_dir), self._row())
            with (
                patch.object(self.evaluator, "SAMPLES_DIR", samples),
                patch.object(
                    self.evaluator,
                    "LABELS_CSV",
                    samples / "labels.csv",
                ),
                patch.object(
                    self.evaluator,
                    "_load_extractor",
                    return_value=fake_extract,
                ) as load_extractor,
                redirect_stdout(output),
            ):
                exit_code = self.evaluator.main()

        rendered = output.getvalue()
        self.assertEqual(exit_code, 0)
        load_extractor.assert_called_once_with()
        self.assertEqual(calls, [str(samples / "page.png")])
        self.assertIn("Evaluating 1 sample(s)...", rendered)
        self.assertIn("page.png", rendered)
        self.assertIn("AVERAGE CER", rendered)
        self.assertIn("sample coverage: 0/1", rendered)


if __name__ == "__main__":
    unittest.main()
