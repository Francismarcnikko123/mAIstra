"""Manually test a real handwriting photo with the offline association prototype.

From the repository root:
    cd ocr_feature
    PYTHONPATH=. .venv/bin/python -m tests.manual_continuation --help
    PYTHONPATH=. .venv/bin/python -m tests.manual_continuation "/path/to/photo.jpg"

Example using the existing two-question development paper:
    PYTHONPATH=. .venv/bin/python -m tests.manual_continuation \
        outputs/continuation_association_intake/development/writerX_page05.jpg

Optional output root (each invocation creates a unique run directory):
    PYTHONPATH=. .venv/bin/python -m tests.manual_continuation "/path/to/photo.jpg" \
        --output-dir outputs/my_continuation_checks

Requires the normal OCR environment and downloaded fine-tuned model. This runs
fresh OCR, prints production raw text versus proposed detection order, then prints
continuation/independent/ambiguous decisions and reasons. Debug data and a complete
comparison.json are saved under outputs/manual_continuation/run-* by default.
Prototype text is one retained detection per line: diagnostic display, not the
pipeline's final indentation/blank-line formatting. No recognition errors are fixed.
Ambiguous means abstention, not proof that the fallback order is correct. This is
an exploratory check with no ground-truth accuracy score. Use the frozen evaluators
for reproducible development/reserved scores. This script never overwrites their
fixtures or labels, never enables the feature in the web app, and is not run by
unittest discovery. Model loading occurs only when main() runs on a valid file.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from evaluators import continuation_prototype

ROOT = Path(__file__).resolve().parents[1]


def compare_photo(photo, run_dir, extract):
    """Extract and compare in an isolated run directory; extractor is injectable."""
    ocr = extract(str(photo), output_dir=str(run_dir))
    stem = Path(ocr['preprocessed_image']).stem
    debug_path = run_dir / 'debug' / f'{stem}.json'
    if not debug_path.is_file():
        raise FileNotFoundError(f'OCR debug detections were not written: {debug_path}')
    debug = json.loads(debug_path.read_text())
    records = debug['detections']
    original = copy.deepcopy(records)
    prediction = continuation_prototype.associate(records)
    if records != original or sorted(prediction['ordered_ids']) != list(range(len(records))):
        raise ValueError('Prototype changed or lost retained OCR records')
    report = dict(
        scope='Manual exploratory photo test; not a ground-truth evaluation',
        source_image=str(photo), source_sha256=hashlib.sha256(photo.read_bytes()).hexdigest(),
        prototype_sha256=hashlib.sha256(Path(continuation_prototype.__file__).read_bytes()).hexdigest(),
        ocr=ocr, detections=records, dropped_low_confidence=debug.get('dropped_low_confidence', []),
        prediction=prediction, prototype_detection_text=[records[i]['text'] for i in prediction['ordered_ids']],
        all_retained_records_preserved=True)
    (run_dir / 'comparison.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('photo', type=Path, help='Local handwriting photo')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/manual_continuation',
                        help='Parent directory for unique run folders')
    args = parser.parse_args(argv)
    photo = args.photo.expanduser().resolve()
    if not photo.is_file():
        parser.error(f'Photo does not exist: {photo}')
    # Keep --help, invalid-path checks and test discovery independent of PaddleOCR.
    from core.ocr_pipeline import extract_text_from_image
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix='run-', dir=output))
    report = compare_photo(photo, run_dir, extract_text_from_image)
    print('\n=== CURRENT PIPELINE RAW TEXT ===')
    print(report['ocr']['raw_text'])
    print('\n=== PROTOTYPE ORDER (one retained detection per line) ===')
    print('\n'.join(report['prototype_detection_text']))
    prediction = report['prediction']
    print('\n=== ASSOCIATION DECISIONS ===')
    for relation in prediction['relations']:
        print(f"Right block {relation['source_block']}: {relation['decision']}; "
              f"compared with left block {relation['target_block']} "
              f"({', '.join(relation['reasons'])})")
    if not prediction['relations']:
        print('No association candidates:', ', '.join(prediction['reasons']))
    print('Order changed:', prediction['changed_order'])
    print('Overall status:', prediction['status'])
    print('All retained records preserved:', report['all_retained_records_preserved'])
    print('Dropped upstream:', len(report['dropped_low_confidence']))
    print('Saved comparison:', run_dir / 'comparison.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
