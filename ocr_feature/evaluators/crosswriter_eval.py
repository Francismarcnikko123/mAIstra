"""Cross-writer (writer-disjoint) evaluation for the mAIstra OCR fine-tune.

Runs the CURRENTLY-CONFIGURED recognizer on the held-out greenbook pages
(writers 7, 8, 20, 27 -- fully excluded from the cross-writer retrain's
training data) and reports page-level CER + WER, comparable to the same-writer
0.126 CER on samples/. This measures generalization to writers NEVER seen in
training. Build the dataset + manifest first with
evaluators.build_crosswriter_dataset.

Select which recognizer to evaluate via the MAISTRA_REC_MODEL_DIR env var
(read by core/ocr_pipeline.py) -- no source editing needed:

  # the cross-writer fine-tuned model (the retrained one):
  MAISTRA_REC_MODEL_DIR=models/fine_tuned_rec_crosswriter/inference \
      .venv/bin/python -m evaluators.crosswriter_eval

  # stock baseline on the same pages: leave the model dir at a valid path but
  # the stock recognizer is a NAME not a dir, so for the stock number use the
  # documented temporary swap in ocr_pipeline (text_recognition_model_name=
  # "PP-OCRv6_medium_rec"), run this, then revert.

Result on 2026-09-01 (cross-writer fine-tuned model): CER 0.123 / WER 0.397 on
15 never-seen-writer pages; stock on the same pages CER 0.296 / WER 0.792
(fine-tuning improved new-writer CER by -58%). See docs/ocr/EVALUATION.md.
"""
import json
from pathlib import Path

from core.ocr_pipeline import extract_text_from_image, _FINE_TUNED_REC_DIR
from evaluators.evaluation import evaluate_text_pair, evaluate_word_token_pair

MANIFEST = Path("evaluators/crosswriter_test_manifest.json")


def main() -> int:
    print(f"[crosswriter_eval] recognizer dir: {_FINE_TUNED_REC_DIR}\n")
    rows = json.loads(MANIFEST.read_text())
    cer, wer, tok = [], [], []
    by_writer: dict[str, list] = {}
    print(f"{'page':34s} {'CER(cln_ws)':>11s} {'WER(clean)':>11s}")
    print("-" * 60)
    for r in rows:
        img = Path(r["image_path"])
        if not img.exists():
            img = Path("datasets/verified/images/greenbook") / r["filename"]
        res = extract_text_from_image(str(img))
        raw, clean = res["raw_text"], res["cleaned_text"]
        m = evaluate_text_pair(raw, clean, r["ground_truth_text"])
        w = evaluate_word_token_pair(raw, clean, r["ground_truth_text"])
        cer.append(m["clean_ws"]); wer.append(w["clean_wer"]); tok.append(w["clean_token_accuracy"])
        by_writer.setdefault(r["writer"], []).append(m["clean_ws"])
        print(f"{r['filename'][:34]:34s} {m['clean_ws']:11.3f} {w['clean_wer']:11.3f}")

    n = len(cer)
    print("-" * 60)
    print(f"\nCROSS-WRITER (new-writer) averages over {n} pages:")
    print(f"  CER (clean_ws):        {sum(cer)/n:.3f}")
    print(f"  WER (clean):           {sum(wer)/n:.3f}")
    print(f"  token accuracy (clean):{sum(tok)/n:.3f}")
    print("\n  per writer (CER clean_ws):")
    for wtr, v in sorted(by_writer.items()):
        print(f"    {wtr}: {sum(v)/len(v):.3f}  (n={len(v)})")
    print("\nCompare to same-writer held-out: CER 0.126 / WER 0.359.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
