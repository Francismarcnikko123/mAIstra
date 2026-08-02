import builtins
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


_real_import = builtins.__import__


def _reject_ocr_import(name, *args, **kwargs):
    if name in {"ocr_pipeline", "recognition_consensus", "paddleocr"}:
        raise AssertionError(f"evaluator imported OCR runtime eagerly: {name}")
    return _real_import(name, *args, **kwargs)


# Importing this test module must prove that importing the evaluator itself
# cannot import Paddle or either OCR runtime module.
with patch("builtins.__import__", side_effect=_reject_ocr_import):
    import evaluate_raw_consensus as evaluator


BASELINE_CONFIG = object()
CONSENSUS_CONFIG = object()
REQUIRED_DELTAS = {
    "paper:bond": 0.0,
    "paper:greenbook": 0.0,
    "writer:nikko": 0.0,
    "writer:nombrado": 0.0,
}


class PromotionGateTests(unittest.TestCase):
    def test_constants_are_pinned(self):
        self.assertEqual(evaluator.RAW_WS_TARGET, 0.181)
        self.assertEqual(evaluator.RAW_STRICT_BASELINE, 0.227)
        self.assertEqual(evaluator.SUBGROUP_REGRESSION_LIMIT, 0.005)
        self.assertEqual(evaluator.EXPECTED_SAMPLE_COUNT, 13)
        self.assertEqual(evaluator.REQUIRED_SUBGROUP_KEYS, set(REQUIRED_DELTAS))

    def test_passes_at_numeric_boundaries_with_complete_cohort(self):
        gate = evaluator.promotion_gate(
            {"raw": 0.190},
            {"raw": 0.190, "raw_ws": 0.181},
            {key: 0.005 for key in REQUIRED_DELTAS},
            cohort_complete=True,
        )

        self.assertTrue(gate["passed"])
        self.assertEqual(gate["checks"], {
            "raw_ws_target": True,
            "strict_raw_non_regression": True,
            "subgroup_non_regression": True,
            "cohort_complete": True,
        })

    def test_missing_subgroups_do_not_vacuously_pass(self):
        gate = evaluator.promotion_gate(
            {"raw": 0.227},
            {"raw": 0.227, "raw_ws": 0.181},
            {},
            cohort_complete=True,
        )

        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["subgroup_non_regression"])
        self.assertFalse(gate["checks"]["cohort_complete"])

    def test_incomplete_cohort_fails_even_with_all_numeric_checks(self):
        gate = evaluator.promotion_gate(
            {"raw": 0.227},
            {"raw": 0.200, "raw_ws": 0.181},
            REQUIRED_DELTAS,
            cohort_complete=False,
        )

        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["cohort_complete"])

    def test_fails_raw_ws_above_target(self):
        gate = evaluator.promotion_gate(
            {"raw": 0.227},
            {"raw": 0.200, "raw_ws": 0.182},
            REQUIRED_DELTAS,
            cohort_complete=True,
        )

        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["raw_ws_target"])

    def test_fails_subgroup_regression_above_limit(self):
        deltas = {**REQUIRED_DELTAS, "paper:bond": 0.006}
        gate = evaluator.promotion_gate(
            {"raw": 0.227},
            {"raw": 0.200, "raw_ws": 0.181},
            deltas,
            cohort_complete=True,
        )

        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["subgroup_non_regression"])

    def test_fails_strict_raw_regression_using_fallback_baseline(self):
        gate = evaluator.promotion_gate(
            {},
            {"raw": 0.228, "raw_ws": 0.181},
            REQUIRED_DELTAS,
            cohort_complete=True,
        )

        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["strict_raw_non_regression"])


class AggregationTests(unittest.TestCase):
    def test_macro_average_and_category_qualified_subgroup_deltas(self):
        rows = [
            {
                "paper_type": "bond",
                "writer": "nikko",
                "baseline": {"metrics": {"raw": 0.4, "raw_ws": 0.2}},
                "consensus": {"metrics": {"raw": 0.2, "raw_ws": 0.1}},
            },
            {
                "paper_type": "bond",
                "writer": "sam",
                "baseline": {"metrics": {"raw": 0.2, "raw_ws": 0.4}},
                "consensus": {"metrics": {"raw": 0.1, "raw_ws": 0.3}},
            },
            {
                "paper_type": "grid",
                "writer": "nikko",
                "baseline": {"metrics": {"raw": 0.6, "raw_ws": 0.6}},
                "consensus": {"metrics": {"raw": 0.3, "raw_ws": 0.6}},
            },
        ]

        overall = evaluator.aggregate_metrics(rows)
        subgroups = evaluator.subgroup_summaries(rows)
        deltas = evaluator.subgroup_deltas(subgroups)

        self.assertAlmostEqual(overall["baseline"]["raw_ws"], 0.4)
        self.assertAlmostEqual(overall["consensus"]["raw"], 0.2)
        self.assertAlmostEqual(
            subgroups["paper_type"]["bond"]["baseline"]["raw_ws"],
            0.3,
        )
        self.assertAlmostEqual(deltas["paper:bond"], -0.1)
        self.assertAlmostEqual(deltas["paper:grid"], 0.0)
        self.assertAlmostEqual(deltas["writer:nikko"], -0.05)
        self.assertAlmostEqual(deltas["writer:sam"], -0.1)


class EvaluatorCLITests(unittest.TestCase):
    def _complete_rows(self):
        rows = []
        for index in range(evaluator.EXPECTED_SAMPLE_COUNT):
            rows.append({
                "filename": f"page-{index:02d}.png",
                "ground_truth_text": "abcd",
                "paper_type": "bond" if index < 7 else "greenbook",
                "writer": "nikko" if index % 2 == 0 else "nombrado",
                "literal_verified": "true",
                "literal_verified_by": "human-reviewer",
                "literal_verified_at": "2026-08-02",
            })
        return rows

    def _write_fixture(
        self,
        root,
        rows,
        missing_images=(),
        include_literal_verified=True,
    ):
        samples = root / "samples"
        samples.mkdir()
        missing_images = set(missing_images)
        for row in rows:
            filename = row["filename"]
            if filename and filename not in missing_images:
                (samples / filename).write_bytes(filename.encode("utf-8"))
        columns = ["filename", "ground_truth_text", "paper_type", "writer"]
        if include_literal_verified:
            columns.extend((
                "literal_verified",
                "literal_verified_by",
                "literal_verified_at",
            ))
        labels = [",".join(columns)]
        labels.extend(
            ",".join(str(row.get(column, "")) for column in columns)
            for row in rows
        )
        (samples / "labels.csv").write_text(
            "\n".join(labels) + "\n",
            encoding="utf-8",
        )
        return samples

    def _run_invalid_fixture(
        self,
        rows,
        missing_images=(),
        include_literal_verified=True,
    ):
        output = io.StringIO()
        attempted_imports = []

        def track_import(name, *args, **kwargs):
            if name in {"ocr_pipeline", "recognition_consensus", "paddleocr"}:
                attempted_imports.append(name)
            return _real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            samples = self._write_fixture(
                Path(temp_dir),
                rows,
                missing_images=missing_images,
                include_literal_verified=include_literal_verified,
            )
            with (
                patch.object(evaluator, "SAMPLES_DIR", samples),
                patch.object(evaluator, "LABELS_CSV", samples / "labels.csv"),
                patch("builtins.__import__", side_effect=track_import),
                redirect_stdout(output),
            ):
                exit_code = evaluator.main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(attempted_imports, [])
        self.assertIn("acceptance cohort complete: FAIL", output.getvalue())
        self.assertIn("numeric gate: FAIL", output.getvalue())
        return output.getvalue()

    def test_main_audits_complete_cohort_and_returns_zero_for_numeric_pass(self):
        rows = self._complete_rows()
        events = []
        calls = []

        def fake_clock():
            events.append("timer")
            return len(events) / 1000

        def fake_extract(image_path, *, output_dir, recognition_config):
            events.append("extract")
            calls.append((image_path, Path(output_dir), recognition_config))
            if recognition_config is BASELINE_CONFIG:
                return {
                    "raw_text": "abxd",
                    "review_diagnostics": ["baseline note"],
                }
            return {
                "raw_text": "abcd",
                "consensus_decisions": [{
                    "action": "replace",
                    "baseline": "abxd",
                    "selected": "abcd",
                    "reason": "two-variant-support",
                }] if image_path.endswith("page-00.png") else [],
                "recognition_diagnostics": ["consensus note"],
                "review_diagnostics": [],
            }

        def fake_warmup():
            events.append("warmup")

        def runtime_loader():
            events.append("load")
            return evaluator.OCRRuntime(
                extractor=fake_extract,
                warmup=fake_warmup,
                baseline_config=BASELINE_CONFIG,
                consensus_config=CONSENSUS_CONFIG,
            )

        output = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            samples = self._write_fixture(Path(temp_dir), rows)
            with (
                patch.object(evaluator, "SAMPLES_DIR", samples),
                patch.object(evaluator, "LABELS_CSV", samples / "labels.csv"),
                redirect_stdout(output),
            ):
                exit_code = evaluator.main(
                    runtime_loader=runtime_loader,
                    clock=fake_clock,
                )

        rendered = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertEqual(events.count("warmup"), 1)
        self.assertEqual(events[:3], ["load", "warmup", "timer"])
        self.assertEqual(len(calls), evaluator.EXPECTED_SAMPLE_COUNT * 2)
        self.assertIs(calls[0][2], BASELINE_CONFIG)
        self.assertIs(calls[1][2], CONSENSUS_CONFIG)
        self.assertNotEqual(calls[0][1], calls[1][1])
        self.assertTrue(all(not output_dir.exists() for _, output_dir, _ in calls))
        self.assertIn("page-00.png", rendered)
        self.assertIn("'abxd' -> 'abcd'", rendered)
        self.assertIn("baseline note", rendered)
        self.assertIn("consensus note", rendered)
        self.assertIn("baseline     0.250000   0.250000", rendered)
        self.assertIn("observed consensus raw_ws: 0.000000", rendered)
        self.assertIn("observed consensus strict raw: 0.000000", rendered)
        self.assertIn("observed max subgroup delta: -0.250000", rendered)
        self.assertTrue(rendered.endswith(
            "PROMOTION GATE (offline OCR engineering only)\n"
            "raw_ws <= 0.181: PASS\n"
            "strict raw non-regression: PASS\n"
            "subgroup regression <= 0.005: PASS\n"
            "acceptance cohort complete: PASS\n"
            "decision audit: MANUAL REVIEW REQUIRED\n"
            "numeric gate: PASS\n"
        ))

    def test_duplicate_filename_rejects_cohort_before_ocr_import(self):
        rows = self._complete_rows()
        rows[-1]["filename"] = rows[0]["filename"]

        rendered = self._run_invalid_fixture(rows)

        self.assertIn("duplicate filename", rendered)

    def test_missing_image_rejects_cohort_before_ocr_import(self):
        rows = self._complete_rows()

        rendered = self._run_invalid_fixture(
            rows, missing_images={rows[-1]["filename"]}
        )

        self.assertIn("image file not found", rendered)

    def test_blank_truth_rejects_cohort_before_ocr_import(self):
        rows = self._complete_rows()
        rows[-1]["ground_truth_text"] = ""

        rendered = self._run_invalid_fixture(rows)

        self.assertIn("ground truth missing", rendered)

    def test_missing_required_subgroup_rejects_before_ocr_import(self):
        rows = self._complete_rows()
        for row in rows:
            row["paper_type"] = "bond"

        rendered = self._run_invalid_fixture(rows)

        self.assertIn("missing required subgroup: paper:greenbook", rendered)

    def test_wrong_sample_count_rejects_before_ocr_import(self):
        rendered = self._run_invalid_fixture(self._complete_rows()[:-1])

        self.assertIn("expected 13 label rows", rendered)

    def test_missing_literal_verification_rejects_before_ocr_import(self):
        rendered = self._run_invalid_fixture(
            self._complete_rows(),
            include_literal_verified=False,
        )

        self.assertIn("literal_verified must be true", rendered)
        self.assertIn("human transcription from the source paper", rendered)

    def test_blank_literal_verification_rejects_before_ocr_import(self):
        rows = self._complete_rows()
        rows[-1]["literal_verified"] = ""

        rendered = self._run_invalid_fixture(rows)

        self.assertIn("page-12.png: literal_verified must be true", rendered)
        self.assertIn("human transcription from the source paper", rendered)

    def test_false_literal_verification_rejects_before_ocr_import(self):
        rows = self._complete_rows()
        rows[-1]["literal_verified"] = "false"

        rendered = self._run_invalid_fixture(rows)

        self.assertIn("page-12.png: literal_verified must be true", rendered)
        self.assertIn("human transcription from the source paper", rendered)

    def test_missing_literal_verifier_rejects_before_ocr_import(self):
        rows = self._complete_rows()
        rows[-1]["literal_verified_by"] = ""

        rendered = self._run_invalid_fixture(rows)

        self.assertIn("page-12.png: literal_verified_by is required", rendered)

    def test_missing_literal_verification_date_rejects_before_import(self):
        rows = self._complete_rows()
        rows[-1]["literal_verified_at"] = ""

        rendered = self._run_invalid_fixture(rows)

        self.assertIn("page-12.png: literal_verified_at is required", rendered)

    def test_complete_cohort_numeric_regression_returns_one(self):
        rows = self._complete_rows()

        def regressing_extract(
            _image_path, *, output_dir, recognition_config
        ):
            del output_dir
            return {
                "raw_text": (
                    "abcd"
                    if recognition_config is BASELINE_CONFIG
                    else "zzzz"
                ),
                "consensus_decisions": [],
                "recognition_diagnostics": [],
                "review_diagnostics": [],
            }

        runtime = evaluator.OCRRuntime(
            extractor=regressing_extract,
            warmup=lambda: None,
            baseline_config=BASELINE_CONFIG,
            consensus_config=CONSENSUS_CONFIG,
        )
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            samples = self._write_fixture(Path(temp_dir), rows)
            with (
                patch.object(evaluator, "SAMPLES_DIR", samples),
                patch.object(evaluator, "LABELS_CSV", samples / "labels.csv"),
                redirect_stdout(output),
            ):
                exit_code = evaluator.main(runtime_loader=lambda: runtime)

        rendered = output.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("PER-PAGE REGRESSIONS", rendered)
        self.assertIn("0.000000 -> 1.000000", rendered)
        self.assertIn("acceptance cohort complete: PASS", rendered)
        self.assertIn("numeric gate: FAIL", rendered)

    def test_empty_labels_reject_before_ocr_import(self):
        output = io.StringIO()
        attempted_imports = []

        def track_import(name, *args, **kwargs):
            if name in {"ocr_pipeline", "recognition_consensus", "paddleocr"}:
                attempted_imports.append(name)
            return _real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            samples = Path(temp_dir) / "samples"
            samples.mkdir()
            labels_csv = samples / "labels.csv"
            labels_csv.write_text(
                "filename,ground_truth_text,paper_type,writer\n",
                encoding="utf-8",
            )
            with (
                patch.object(evaluator, "SAMPLES_DIR", samples),
                patch.object(evaluator, "LABELS_CSV", labels_csv),
                patch("builtins.__import__", side_effect=track_import),
                redirect_stdout(output),
            ):
                exit_code = evaluator.main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(attempted_imports, [])
        self.assertIn("labels.csv has no rows", output.getvalue())

    def test_missing_labels_returns_one_without_importing_ocr_runtime(self):
        output = io.StringIO()
        attempted_imports = []

        def track_import(name, *args, **kwargs):
            if name in {"ocr_pipeline", "recognition_consensus", "paddleocr"}:
                attempted_imports.append(name)
            return _real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "samples" / "labels.csv"
            with (
                patch.object(evaluator, "LABELS_CSV", missing),
                patch("builtins.__import__", side_effect=track_import),
                redirect_stdout(output),
            ):
                exit_code = evaluator.main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(attempted_imports, [])
        self.assertIn("No labels file", output.getvalue())
        self.assertIn("acceptance cohort complete: FAIL", output.getvalue())
        self.assertIn("numeric gate: FAIL", output.getvalue())


if __name__ == "__main__":
    unittest.main()
