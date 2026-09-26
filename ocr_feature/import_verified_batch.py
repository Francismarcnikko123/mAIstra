"""One-off import: copy the teammate's physically-verified writer-named
batch (bond/greenbook/yellow_pad, from ~/Downloads/image_to_transcribe_verified/)
into datasets/verified/images/<paper_type>/ and rebuild
datasets/verified/labels.csv from their .txt content.

Named "_verified" specifically to not be confused with the *other*,
separate, still-unverified `submission_*`-named batch that lives in
~/Desktop/image_to_transcribe/ -- that one hasn't been checked against
physical paper yet and must never be imported by this script.

Writer identity is stored as a bare "writer<N>" pseudonym per
writer-pseudonyms-no-real-names -- never a real name -- scoped per
paper_type (the same number in different paper types is not the same
student).

Run once from ocr_feature/:
    python import_verified_batch.py --verified-by "Name of verifier"
"""
import argparse
import csv
import re
import shutil
from datetime import date
from pathlib import Path

from evaluators.labels_schema import FIELDNAMES, is_writer_batch_id, load_existing_rows, write_labels_csv

SOURCE_ROOT = Path.home() / "Downloads" / "image_to_transcribe_verified"
DEST_IMAGES_ROOT = Path("datasets/verified/images")
LABELS_CSV = Path("datasets/verified/labels.csv")
SAMPLES_DIR = Path("samples")

PAPER_TYPES = ["bond", "greenbook", "yellow_pad"]
WRITER_RE = re.compile(r"writer(\d+)")


def _holdout_stems() -> set:
    """Filename stems already held out as the test set in samples/ -- these
    must NEVER be copied into datasets/verified/ (train). samples/ = test,
    datasets/verified/ = train, never overlap -- a hard project rule. A prior
    run of this script violated it by copying 20 held-out images into train
    before this guard existed; see the 2026-08-30 fix."""
    if not SAMPLES_DIR.exists():
        return set()
    return {p.stem for p in SAMPLES_DIR.glob("*.jpg")} | {p.stem for p in SAMPLES_DIR.glob("*.jpeg")}


def find_txt_dir(paper_dir: Path) -> Path:
    candidates = [p for p in paper_dir.iterdir() if p.is_dir() and "txt" in p.name.lower()]
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one *_txt dir in {paper_dir}, found {candidates}")
    return candidates[0]


def main(verified_by: str) -> int:
    if not SOURCE_ROOT.exists():
        raise RuntimeError(
            f"Source not found: {SOURCE_ROOT}\n"
            "Expected the physically-verified batch here (bond/greenbook/"
            "yellow_pad, writerN-named files). If it's still named "
            "'image_to_transcribe' without '_verified', rename it first -- "
            "that name is reserved for the OTHER, unverified submission_* batch."
        )

    existing_full = load_existing_rows(LABELS_CSV)
    existing = {
        sid: row["verified_text"] for sid, row in existing_full.items()
        if is_writer_batch_id(sid)
    }
    holdout = _holdout_stems()
    today = date.today().isoformat()
    rows = []
    skipped = []

    for paper_type in PAPER_TYPES:
        paper_dir = SOURCE_ROOT / paper_type
        txt_dir = find_txt_dir(paper_dir)
        dest_dir = DEST_IMAGES_ROOT / paper_type
        dest_dir.mkdir(parents=True, exist_ok=True)

        images = sorted(paper_dir.glob("*.jpg")) + sorted(paper_dir.glob("*.jpeg"))
        for image_path in images:
            stem = image_path.stem
            if stem in holdout:
                skipped.append((stem, "held out as test set in samples/ -- never train on this"))
                continue

            txt_path = txt_dir / f"{stem}.txt"
            if not txt_path.exists():
                skipped.append((stem, "no matching .txt"))
                continue

            match = WRITER_RE.search(stem)
            if not match:
                skipped.append((stem, "no writerN in filename"))
                continue
            writer = f"writer{match.group(1)}"

            dest_image_path = dest_dir / image_path.name
            shutil.copy2(image_path, dest_image_path)

            verified_text = txt_path.read_text(encoding="utf-8").rstrip("\n")

            rows.append({
                "submission_id": stem,
                "image_path": f"images/{paper_type}/{image_path.name}",
                "verified_text": verified_text,
                "extracted_text": "",
                "verified_at": today,
                "topic": "",
                "student_name": writer,
                "literal_verified": "true",
                "literal_verified_by": verified_by,
                "literal_verified_at": today,
                "correction_edit_distance": "",
            })

    preserved = {
        sid: row for sid, row in existing_full.items()
        if not is_writer_batch_id(sid)
    }
    own_new = {row["submission_id"]: row for row in rows}
    merged = {**preserved, **own_new}
    write_labels_csv(LABELS_CSV, merged)
    print(f"labels.csv now contains {len(merged)} total row(s) "
          f"({len(preserved)} preserved from Supabase export, "
          f"{len(own_new)} from this batch).")
    if skipped:
        print(f"Skipped {len(skipped)}:")
        for name, reason in skipped:
            print(f"  {name}: {reason}")

    # Sanity check: does this source actually align with what's already in
    # labels.csv, or did it just silently change/lose data underneath us?
    new_ids = {row["submission_id"] for row in rows}
    old_ids = set(existing)
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    changed = sorted(
        sid for sid in (new_ids & old_ids)
        if existing[sid] != next(r["verified_text"] for r in rows if r["submission_id"] == sid)
    )

    print("\n--- Sanity check vs. previous labels.csv ---")
    if not existing:
        print("No previous labels.csv to compare against (first import).")
    elif not added and not removed and not changed:
        print(f"IDENTICAL to what was already imported ({len(rows)} rows unchanged).")
    else:
        if added:
            print(f"ADDED ({len(added)}): {added}")
        if removed:
            print(f"REMOVED ({len(removed)}) -- was this batch supposed to drop these?: {removed}")
        if changed:
            print(f"TEXT CHANGED ({len(changed)}) -- re-verification updates?: {changed}")

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verified-by",
        required=True,
        help="Name of the person who physically verified this batch against "
             "the source paper (recorded in literal_verified_by).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main(_parse_args().verified_by))
