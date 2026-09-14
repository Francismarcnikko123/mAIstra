"""Tests for the manual photo runner without loading recognition models.

Run from ocr_feature:
    PYTHONPATH=. .venv/bin/python -m unittest tests.test_manual_continuation -v
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests import manual_continuation as runner


class ManualContinuationTests(unittest.TestCase):
    def test_help_and_missing_photo_do_not_load_ocr(self):
        with patch.dict(sys.modules, {'core.ocr_pipeline': None}):
            for args, exit_code in [(['--help'], 0), (['/no/such/photo.jpg'], 2)]:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        runner.main(args)
                self.assertEqual(caught.exception.code, exit_code)

    def test_comparison_preserves_duplicate_records_and_reports_abstention(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'writerX.jpg'
            source.write_bytes(b'fake-photo-for-stub')
            run_dir = root / 'run'
            run_dir.mkdir()
            records = [dict(text='}', score=.9, box=[0, 0, 20, 20]) for _ in range(2)]
            def extract(image_path, output_dir):
                self.assertEqual(Path(image_path), source)
                debug = Path(output_dir) / 'debug'
                debug.mkdir()
                (debug / 'writerX_preprocessed.json').write_text(json.dumps(
                    dict(detections=records, dropped_low_confidence=[])))
                return dict(raw_text='} }', cleaned_text='} }', average_confidence=.9,
                            preprocessed_image=str(Path(output_dir) / 'writerX_preprocessed.jpg'))
            report = runner.compare_photo(source, run_dir, extract)
            self.assertEqual(report['detections'], records)
            self.assertEqual(sorted(report['prediction']['ordered_ids']), [0, 1])
            self.assertEqual(report['prototype_detection_text'], ['}', '}'])
            self.assertEqual(report['prediction']['status'], 'ambiguous')
            self.assertTrue(report['all_retained_records_preserved'])
            self.assertEqual(json.loads((run_dir / 'comparison.json').read_text()), report)


if __name__ == '__main__':
    unittest.main()
