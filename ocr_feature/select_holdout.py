"""Pick a stratified test-set holdout from datasets/verified/labels.csv,
move the chosen rows' images into samples/, and remove them from
datasets/verified/ (train) so the same page never appears in both.

Selection rules:
  - greenbook: multi-page "B<n>" groups (e.g. green_writer13_B2_1/_2) are
    moved as a whole unit, never split across train/test.
  - bond/yellow_pad: only 4 distinct writers each, so holding out a writer's
    entire set would remove a quarter of that paper type's train diversity.
    Individual pages are held out instead, leaving each writer represented
    in both train and test.
  - yellow_pad gets a higher fraction (currently zero real test coverage).

Run from ocr_feature/:
    python select_holdout.py            # dry run, prints the picks
    python select_holdout.py --apply    # actually moves files + rewrites CSVs
"""
import csv
import re
import shutil
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

VERIFIED_CSV = Path("datasets/verified/labels.csv")
SAMPLES_CSV = Path("samples/labels.csv")
VERIFIED_IMAGES = Path("datasets/verified/images")
SAMPLES_DIR = Path("samples")

TARGET_HOLDOUT = {"bond": 2, "greenbook": 14, "yellow_pad": 4}

SAMPLES_FIELDNAMES = [
    "filename", "ground_truth_text", "writer", "paper_type",
    "capture_condition", "literal_verified", "literal_verified_by",
    "literal_verified_at",
]


def group_key(paper_type: str, submission_id: str) -> str:
    if paper_type == "greenbook":
        m = re.match(r"(green_writer\d+_B\d+)_\d+$", submission_id)
        if m:
            return m.group(1)
    return submission_id


def main() -> int:
    apply = "--apply" in sys.argv

    rows = list(csv.DictReader(VERIFIED_CSV.open(encoding="utf-8")))
    by_type = defaultdict(list)
    for r in rows:
        pt = r["image_path"].split("/")[1]
        by_type[pt].append(r)

    holdout_rows = []
    for paper_type, target in TARGET_HOLDOUT.items():
        type_rows = by_type[paper_type]
        groups = defaultdict(list)
        for r in type_rows:
            groups[group_key(paper_type, r["submission_id"])].append(r)

        writer_total = defaultdict(int)
        writer_groups = defaultdict(list)
        for r in type_rows:
            writer_total[r["student_name"]] += 1
        for k, group in groups.items():
            writer_groups[group[0]["student_name"]].append(k)
        for writer, keys in writer_groups.items():
            keys.sort(key=lambda k: len(groups[k]))  # smallest groups first

        picked = []
        picked_count = 0
        writer_picked = defaultdict(int)
        # Round-robin: each round, the writer with the fewest pages picked so
        # far contributes their next-smallest still-eligible group. Spreads
        # the holdout across writers instead of draining one writer first.
        while picked_count < target:
            eligible_writers = [w for w, keys in writer_groups.items() if keys]
            if not eligible_writers:
                break
            eligible_writers.sort(key=lambda w: writer_picked[w])
            progressed = False
            for writer in eligible_writers:
                keys = writer_groups[writer]
                while keys:
                    k = keys[0]
                    group = groups[k]
                    if writer_total[writer] - len(group) >= 1:
                        picked.append(group)
                        picked_count += len(group)
                        writer_picked[writer] += len(group)
                        writer_total[writer] -= len(group)
                        keys.pop(0)
                        progressed = True
                        break
                    keys.pop(0)  # would empty this writer's train pages -- skip
                if progressed:
                    break
            if not progressed:
                break

        for group in picked:
            holdout_rows.extend(group)

    print(f"Selected {len(holdout_rows)} rows for holdout:")
    for r in holdout_rows:
        print(f"  {r['submission_id']} ({r['student_name']})")

    if not apply:
        print("\nDry run only -- pass --apply to actually move files and rewrite CSVs.")
        return 0

    holdout_ids = {r["submission_id"] for r in holdout_rows}
    remaining_verified = [r for r in rows if r["submission_id"] not in holdout_ids]

    existing_samples = []
    if SAMPLES_CSV.exists():
        existing_samples = list(csv.DictReader(SAMPLES_CSV.open(encoding="utf-8")))

    today = date.today().isoformat()
    new_sample_rows = []
    for r in holdout_rows:
        paper_type = r["image_path"].split("/")[1]
        src = VERIFIED_IMAGES / paper_type / Path(r["image_path"]).name
        dest = SAMPLES_DIR / Path(r["image_path"]).name
        shutil.move(str(src), str(dest))
        new_sample_rows.append({
            "filename": Path(r["image_path"]).name,
            "ground_truth_text": r["verified_text"],
            "writer": r["student_name"],
            "paper_type": paper_type,
            "capture_condition": "gate_raw",
            "literal_verified": "true",
            "literal_verified_by": "Nikko",
            "literal_verified_at": today,
        })

    with SAMPLES_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SAMPLES_FIELDNAMES)
        w.writeheader()
        w.writerows(existing_samples + new_sample_rows)

    with VERIFIED_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(remaining_verified)

    print(f"\nMoved {len(holdout_rows)} images to samples/, "
          f"{len(remaining_verified)} rows remain in datasets/verified/labels.csv, "
          f"{len(existing_samples) + len(new_sample_rows)} total rows in samples/labels.csv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
