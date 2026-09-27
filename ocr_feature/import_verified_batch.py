"""Import a physically-verified writer-named batch (bond/greenbook/yellow_pad,
from ~/Downloads/image_to_transcribe_verified/) into
datasets/verified/images/<paper_type>/ and add its .txt content to
datasets/verified/labels.csv.

Safe to re-run for each new batch (2026-09-27): pages already imported keep
their row, their place in labels.csv and who verified them, even when they're
not in the source folder; test pages in samples/ and new pages from greenbook
test writers are never imported; a paper type the batch doesn't have is
skipped. Run with --dry-run first: it prints everything and writes nothing.

Named "_verified" specifically to not be confused with the *other*,
separate, still-unverified `submission_*`-named batch that lives in
~/Desktop/image_to_transcribe/ -- that one hasn't been checked against
physical paper yet and must never be imported by this script.

Writer identity is stored as a bare "writer<N>" pseudonym per
writer-pseudonyms-no-real-names -- never a real name -- scoped per
paper_type (the same number in different paper types is not the same
student).

Run from ocr_feature/:
    python import_verified_batch.py --verified-by "Name of verifier" --dry-run
    python import_verified_batch.py --verified-by "Name of verifier"
"""
import argparse
import csv
import re
import shutil
from datetime import date
from pathlib import Path

from evaluators.labels_schema import FIELDNAMES, is_writer_batch_id, load_existing_rows, write_labels_csv
from select_holdout import group_key

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
    before this guard existed; see the 2026-08-30 fix.

    select_holdout.py keeps each paper type in its own folder
    (samples/bond/, ...), so images are found at any depth, and every
    filename in samples/labels.csv counts too. Until 2026-09-27 only
    top-level samples/*.jpg was checked, which matched none of the 20 test
    pages."""
    if not SAMPLES_DIR.exists():
        return set()
    stems = {p.stem for p in SAMPLES_DIR.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg")}
    labels = SAMPLES_DIR / "labels.csv"
    if labels.exists():
        with labels.open(encoding="utf-8", newline="") as f:
            stems |= {Path(row["filename"]).stem for row in csv.DictReader(f) if row.get("filename")}
    return stems


def find_txt_dir(paper_dir: Path) -> Path:
    candidates = [p for p in paper_dir.iterdir() if p.is_dir() and "txt" in p.name.lower()]
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one *_txt dir in {paper_dir}, found {candidates}")
    return candidates[0]


def main(verified_by: str, dry_run: bool = False) -> int:
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
    # Greenbook's test set holds out whole writers (green_writerN_Bk, the
    # select_holdout.py group), so a NEW page from one of them is a
    # test-writer page too. Bond/yellow are held out per page.
    test_groups = {group_key("greenbook", stem) for stem in holdout}

    def is_test(stem: str) -> bool:
        return stem in holdout or group_key("greenbook", stem) in test_groups

    today = date.today().isoformat()
    rows = []
    skipped = []

    for paper_type in PAPER_TYPES:
        paper_dir = SOURCE_ROOT / paper_type
        if not paper_dir.is_dir():
            # A batch may bring only some paper types.
            skipped.append((f"{paper_type}/", "no such folder in this batch"))
            continue
        txt_dir = find_txt_dir(paper_dir)
        dest_dir = DEST_IMAGES_ROOT / paper_type
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)

        images = sorted(paper_dir.glob("*.jpg")) + sorted(paper_dir.glob("*.jpeg"))
        for image_path in images:
            stem = image_path.stem
            if stem in holdout:
                skipped.append((stem, "held out as test set in samples/ -- never train on this"))
                continue
            if is_test(stem):
                skipped.append((stem, f"new page from test writer {group_key('greenbook', stem)} "
                                      "in samples/ -- never train on this"))
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
            verified_text = txt_path.read_text(encoding="utf-8").rstrip("\n")

            previous = existing_full.get(stem)
            if previous is not None and previous["verified_text"] == verified_text:
                # Already imported with this exact text: keep its row, so who
                # verified it and when stay as recorded. Only new pages and
                # changed text (a re-verification) get this run's verifier.
                if not dry_run and not dest_image_path.exists():
                    shutil.copy2(image_path, dest_image_path)
                rows.append(previous)
                continue

            if not dry_run:
                shutil.copy2(image_path, dest_image_path)

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

    # Rows keep their place in labels.csv, so its diff shows only real
    # changes; new pages go at the end. Supabase-exported rows are untouched.
    # Pages imported earlier stay even if this source folder doesn't have
    # them (it may hold only the new batch). A test page never stays in train.
    own_new = {row["submission_id"]: row for row in rows}
    merged = {}
    preserved = kept = 0
    dropped_test = []
    for sid, row in existing_full.items():
        if not is_writer_batch_id(sid):
            merged[sid] = row
            preserved += 1
        elif sid in own_new:
            merged[sid] = own_new[sid]
        elif is_test(sid):
            dropped_test.append(sid)
        else:
            merged[sid] = row
            kept += 1
    for sid, row in own_new.items():
        merged.setdefault(sid, row)

    if dry_run:
        print("DRY RUN: nothing copied or written. labels.csv would contain "
              f"{len(merged)} row(s).")
    else:
        write_labels_csv(LABELS_CSV, merged)
        print(f"labels.csv now contains {len(merged)} total row(s).")
    print(f"  {preserved} preserved from Supabase export, {len(own_new)} from "
          f"this source folder, {kept} imported earlier and kept.")
    if skipped:
        print(f"Skipped {len(skipped)}:")
        for name, reason in skipped:
            print(f"  {name}: {reason}")

    # Sanity check: does this source actually align with what's already in
    # labels.csv, or did it just silently change/lose data underneath us?
    new_ids = {row["submission_id"] for row in rows}
    old_ids = set(existing)
    added = sorted(new_ids - old_ids)
    changed = sorted(
        sid for sid in (new_ids & old_ids)
        if existing[sid] != next(r["verified_text"] for r in rows if r["submission_id"] == sid)
    )

    print("\n--- Sanity check vs. previous labels.csv ---")
    if not existing:
        print("No previous labels.csv to compare against (first import).")
    elif not added and not changed and not dropped_test:
        print(f"NO NEW OR CHANGED PAGES ({len(rows)} in this folder, all already imported).")
    else:
        if added:
            print(f"ADDED ({len(added)}): {added}")
        if dropped_test:
            print(f"REMOVED FROM TRAIN ({len(dropped_test)}) -- test pages in samples/: {dropped_test}")
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported, kept, skipped or changed; copy "
             "and write nothing.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(main(args.verified_by, dry_run=args.dry_run))
