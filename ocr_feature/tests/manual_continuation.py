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

# Plain-English translations for the decision labels and reason codes the
# prototype emits. Display only -- the codes in comparison.json are unchanged.
DECISION_PLAIN = {
    'continuation': 'CONTINUATION -> moved into place after the left block',
    'independent': 'SEPARATE ANSWER -> left where it is',
    'ambiguous': 'NOT SURE -> left in original order (safe default)',
}
REASON_PLAIN = {
    'no_unique_supported_global_gutter':
        'no single clear left/right split on the page, so nothing to compare',
    'no_unique_local_vertical_match':
        'the side block does not line up with exactly one block on the left',
    'insufficient_local_gutter':
        'the gap between the two blocks is too small to trust as a margin note',
    'distinct_numbered_headings':
        'the two sides have different question numbers',
    'clean_gutter': 'there is a clear gap between the two sides',
    'separate_main_entries':
        'both sides have their own main(), so two separate programs',
    'if_else_link_before_next_numbered_question':
        'left has an if, right has the matching else, before the next question',
    'unique_local_vertical_match':
        'the side block lines up with exactly one block on the left',
    'recognized_open_scope_and_closing_block':
        'the braces show the left block is still open and the right block closes it',
    'uncertain_literal_or_comment_boundary':
        'a string or comment could not be read safely, so no move was made',
    'insufficient_or_conflicting_scope_evidence':
        'the brace math does not clearly support a continuation',
    'competing_blocks_for_insertion_point':
        'more than one side block wanted the same spot, so nothing was moved',
    'heuristic_evidence_not_semantic_proof':
        'decisions use layout evidence, not proof the code is correct',
    'empty_input': 'no detections were found on the page',
    'invalid_detection_geometry_or_payload':
        'a detection had unusable coordinates, so the original order was kept',
}


def _plain_reasons(reasons):
    """Human-readable reason list; unknown codes pass through unchanged."""
    return '; '.join(REASON_PLAIN.get(reason, reason) for reason in reasons)


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
    prediction = report['prediction']
    changed = prediction['changed_order']
    bar = '=' * 64

    print('\n' + bar)
    print(f' CONTINUATION CHECK: {photo.name}')
    print(bar)
    print('Re-runs OCR on the photo, then checks whether any code written off')
    print('to the side belongs earlier in the program. It only REORDERS whole')
    print('lines -- it never edits, adds, or removes a single character.')

    print('\n--- 1. WHAT THE OCR READ (original top-to-bottom order) ---')
    print(report['ocr']['raw_text'])

    print('\n--- 2. ORDER AFTER THE CONTINUATION CHECK ---')
    print('\n'.join(report['prototype_detection_text']))
    if changed:
        print('\n>> Lines WERE reordered: a side block was moved into place.')
    else:
        print('\n>> No lines moved: the original order was already correct,')
        print('   or there was not enough evidence to safely move anything.')

    print('\n--- 3. DECISIONS (one per side block the check considered) ---')
    if not prediction['relations']:
        print('No side blocks to compare.')
        print(f"Reason: {_plain_reasons(prediction['reasons'])}")
    for relation in prediction['relations']:
        target = relation['target_block']
        against = f"left block {target}" if target else "the left side"
        print(f"\nRight-side block {relation['source_block']} vs {against}:")
        print(f"   -> {DECISION_PLAIN.get(relation['decision'], relation['decision'])}")
        if relation['reasons']:
            print(f"      Why: {_plain_reasons(relation['reasons'])}")

    print('\n--- SUMMARY ---')
    print(f"Lines reordered : {'Yes' if changed else 'No'}")
    if prediction['status'] == 'supported':
        print("Overall         : SUPPORTED -- every decision had clear evidence")
    else:
        print("Overall         : NOT SURE -- at least one block lacked clear")
        print("                  evidence, so it was left in its original place")
    print(f"All text kept    : {'Yes' if report['all_retained_records_preserved'] else 'NO'}"
          " (no characters added, edited, or dropped)")
    print(f"Low-conf dropped : {len(report['dropped_low_confidence'])}"
          " (removed before this step as OCR noise)")
    print(f"Full details     : {run_dir / 'comparison.json'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
