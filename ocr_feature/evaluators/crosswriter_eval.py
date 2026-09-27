"""Measure a recognizer on the 15 pages of the 4 held-out writers (see
build_crosswriter_dataset.py), i.e. on handwriting it has never seen.

Choose the model with MAISTRA_REC_MODEL_DIR:

    MAISTRA_REC_MODEL_DIR=models/fine_tuned_rec_crosswriter/inference \
        .venv/bin/python -m evaluators.crosswriter_eval

For the stock model, temporarily set text_recognition_model_name=
"PP-OCRv6_medium_rec" in core/ocr_pipeline.py instead.

Result: CER 0.123 / WER 0.397 with the cross-writer model, against
0.296 / 0.792 for the stock model on the same pages (CER -58%).
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
    print("\nSame-writer held-out samples/ references:")
    print("  Recognition-only fine-tune (before two-column split): "
          "CER 0.126 / WER 0.359.")
    print("  End-to-end after two-column split: "
          "CER (clean_ws) 0.099 / WER (clean) 0.328 / "
          "token accuracy (clean) 0.716.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
