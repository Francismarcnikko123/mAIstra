"""Conservative association of spatially separated code continuations.

This module decides only the order of existing OCR detections. It does not
recognize, repair, split, merge, insert, or remove characters. Ambiguous or
unsafe evidence preserves the supplied baseline order.
"""

import math
import re
from statistics import median


GUTTER_HEIGHTS = 2.0
BAND_GAP_HEIGHTS = 1.2
QUESTION = re.compile(r"^\s*q[a-z]{3,10}\s*(\d+)\s*[:;.]?\s*$", re.I)


def _code_only(text):
    """Mask C literals and comments used as structural evidence."""
    output = []
    index = 0
    while index < len(text):
        if text.startswith("//", index):
            newline = text.find("\n", index)
            if newline < 0:
                break
            output.append("\n")
            index = newline + 1
        elif text.startswith("/*", index):
            close = text.find("*/", index + 2)
            if close < 0:
                return "", False
            output.append(" ")
            index = close + 2
        elif text[index] in ('"', "'"):
            quote = text[index]
            index += 1
            while index < len(text) and text[index] != quote:
                if text[index] == "\n":
                    return "", False
                index += 2 if text[index] == "\\" else 1
            if index >= len(text):
                return "", False
            output.append(" ")
            index += 1
        else:
            output.append(text[index])
            index += 1
    return "".join(output), True


def _scope(code):
    depth = 0
    lowest = 0
    for character in code:
        depth += (character == "{") - (character == "}")
        lowest = min(lowest, depth)
    return depth, lowest


def _code_rows(text_rows):
    """Return safe row evidence plus whether every row was lexically safe."""
    output = []
    fully_safe = True
    for text in text_rows:
        code, safe = _code_only(text)
        if safe:
            output.append(code)
        else:
            fully_safe = False
            output.append(" ")
    return "\n".join(output), fully_safe


def _blocks(identifiers, records, height, side):
    ordered = sorted(
        identifiers,
        key=lambda identifier: (
            sum(records[identifier]["box"][1::2]) / 2,
            records[identifier]["box"][0],
            identifier,
        ),
    )
    rows = []
    for identifier in ordered:
        box = records[identifier]["box"]
        center = (box[1] + box[3]) / 2
        if rows and abs(center - rows[-1]["center"]) <= .55 * height:
            rows[-1]["ids"].append(identifier)
            rows[-1]["bottom"] = max(rows[-1]["bottom"], box[3])
        else:
            rows.append({
                "ids": [identifier],
                "center": center,
                "top": box[1],
                "bottom": box[3],
            })

    bands = []
    for row in rows:
        row["ids"].sort(key=lambda identifier: (
            records[identifier]["box"][0], identifier
        ))
        text = " ".join(records[identifier]["text"] for identifier in row["ids"])
        if (not bands
                or row["top"] - bands[-1]["bottom"] > BAND_GAP_HEIGHTS * height
                or QUESTION.fullmatch(text)):
            bands.append({
                "id": f"{side}{len(bands)}",
                "side": side,
                "detection_ids": [],
                "top": row["top"],
                "bottom": row["bottom"],
                "text_rows": [],
            })
        bands[-1]["detection_ids"].extend(row["ids"])
        bands[-1]["text_rows"].append(text)
        bands[-1]["bottom"] = max(bands[-1]["bottom"], row["bottom"])
    return bands


def _fallback_result(baseline_ids, reason):
    return {
        "baseline_ids": list(baseline_ids),
        "ordered_ids": list(baseline_ids),
        "blocks": [],
        "relations": [],
        "changed_order": False,
        "status": "ambiguous",
        "reasons": [reason],
    }


def associate_continuation(records, baseline_ids):
    """Return supported detection order and inspectable evidence.

    ``records`` are treated as immutable and identified by their list index.
    ``baseline_ids`` must be a complete permutation of those indices.
    """
    natural = list(range(len(records)))
    try:
        baseline = list(baseline_ids)
    except TypeError:
        baseline = natural
    if len(baseline) != len(records) or sorted(baseline) != natural:
        return _fallback_result(natural, "invalid_baseline_order")

    try:
        for record in records:
            box = record["box"]
            score = float(record["score"])
            if (len(box) != 4
                    or not all(math.isfinite(float(value)) for value in box)
                    or float(box[2]) <= float(box[0])
                    or float(box[3]) <= float(box[1])
                    or not isinstance(record["text"], str)
                    or not math.isfinite(score)):
                raise ValueError("unsafe detection")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _fallback_result(
            baseline, "invalid_detection_geometry_or_payload"
        )
    if not records:
        return _fallback_result(baseline, "empty_input")

    result = _fallback_result(baseline, "heuristic_evidence_not_semantic_proof")
    height = median(
        float(record["box"][3]) - float(record["box"][1])
        for record in records
    )
    identifiers = sorted(
        natural,
        key=lambda identifier: float(records[identifier]["box"][0]),
    )
    edge = float(records[identifiers[0]]["box"][2])
    gaps = []
    for position, identifier in enumerate(identifiers[1:], 1):
        box = records[identifier]["box"]
        left = float(box[0])
        if left > edge and position >= 2 and len(identifiers) - position >= 2:
            gaps.append((left - edge, position))
        edge = max(edge, float(box[2]))
    gaps.sort(reverse=True)
    if not gaps or (
        len(gaps) > 1 and math.isclose(gaps[0][0], gaps[1][0])
    ):
        result["reasons"] = ["no_unique_supported_global_gutter"]
        return result

    _gap, cut = gaps[0]
    left_blocks = _blocks(identifiers[:cut], records, height, "L")
    right_blocks = _blocks(identifiers[cut:], records, height, "R")
    result["blocks"] = left_blocks + right_blocks
    moves = []

    for right_block in right_blocks:
        candidates = [
            left_block for left_block in left_blocks
            if (left_block["bottom"] >= right_block["top"] - .5 * height
                and right_block["bottom"] >= left_block["top"] - .5 * height)
        ]
        relation = {
            "source_block": right_block["id"],
            "source_detection_ids": right_block["detection_ids"],
            "target_block": None,
            "target_detection_ids": [],
            "candidate_targets": [candidate["id"] for candidate in candidates],
            "decision": "ambiguous",
            "reasons": [],
        }
        result["relations"].append(relation)
        if len(candidates) != 1:
            relation["reasons"] = ["no_unique_local_vertical_match"]
            continue

        left_block = candidates[0]
        relation.update(
            target_block=left_block["id"],
            target_detection_ids=left_block["detection_ids"],
        )
        local_gap = (
            min(float(records[i]["box"][0])
                for i in right_block["detection_ids"])
            - max(float(records[i]["box"][2])
                  for i in left_block["detection_ids"])
        )
        relation["local_gap_heights"] = local_gap / height
        if local_gap < GUTTER_HEIGHTS * height:
            relation["reasons"] = ["insufficient_local_gutter"]
            continue

        left_questions = [
            match.group(1)
            for text in left_block["text_rows"]
            for match in [QUESTION.fullmatch(text)]
            if match
        ]
        right_questions = [
            match.group(1)
            for text in right_block["text_rows"]
            for match in [QUESTION.fullmatch(text)]
            if match
        ]
        left_code, left_safe = _code_rows(left_block["text_rows"])
        right_code, right_safe = _code_rows(right_block["text_rows"])

        if (left_questions and right_questions
                and set(left_questions).isdisjoint(right_questions)):
            relation.update(
                decision="independent",
                reasons=["distinct_numbered_headings", "clean_gutter"],
            )
            continue
        if (left_safe and right_safe
                and re.search(r"\bmain\s*\(", left_code)
                and re.search(r"\bmain\s*\(", right_code)):
            relation.update(
                decision="independent",
                reasons=["separate_main_entries", "clean_gutter"],
            )
            continue
        later_numbered_question = any(
            QUESTION.fullmatch(text)
            for candidate in left_blocks
            if candidate["top"] > left_block["bottom"]
            for text in candidate["text_rows"]
        )
        if (right_safe
                and later_numbered_question
                and re.search(r"\bif\b", left_code)
                and re.search(r"\belse\b", right_code)):
            relation.update(
                decision="continuation",
                reasons=[
                    "clean_gutter",
                    "unique_local_vertical_match",
                    "if_else_link_before_next_numbered_question",
                ],
            )
            moves.append((left_block, right_block, relation))
            continue
        if not left_safe or not right_safe:
            relation["reasons"] = ["uncertain_literal_or_comment_boundary"]
            continue

        left_depth, left_minimum = _scope(left_code)
        right_delta, right_minimum = _scope(right_code)
        relation["scope_evidence"] = {
            "left_depth": left_depth,
            "right_delta": right_delta,
            "right_minimum": right_minimum,
        }
        if (left_depth <= 0
                or left_minimum < 0
                or right_delta >= 0
                or left_depth + right_minimum < 0
                or (re.search(r"\belse\b", right_code)
                    and not re.search(r"\bif\b", left_code))):
            relation["reasons"] = [
                "insufficient_or_conflicting_scope_evidence"
            ]
            continue

        relation.update(
            decision="continuation",
            reasons=[
                "clean_gutter",
                "unique_local_vertical_match",
                "recognized_open_scope_and_closing_block",
            ],
        )
        moves.append((left_block, right_block, relation))

    for left_block, right_block, relation in moves:
        if sum(
            other_left["id"] == left_block["id"]
            for other_left, _other_right, _other_relation in moves
        ) != 1:
            relation.update(
                decision="ambiguous",
                reasons=["competing_blocks_for_insertion_point"],
            )
            continue
        moving = set(right_block["detection_ids"])
        remaining = [
            identifier for identifier in result["ordered_ids"]
            if identifier not in moving
        ]
        anchor = max(
            remaining.index(identifier)
            for identifier in left_block["detection_ids"]
        ) + 1
        result["ordered_ids"] = (
            remaining[:anchor]
            + right_block["detection_ids"]
            + remaining[anchor:]
        )

    if sorted(result["ordered_ids"]) != natural:
        return _fallback_result(baseline, "invalid_proposed_order")
    result["changed_order"] = result["ordered_ids"] != baseline
    result["status"] = (
        "ambiguous"
        if any(relation["decision"] == "ambiguous"
               for relation in result["relations"])
        else "supported"
    )
    return result
