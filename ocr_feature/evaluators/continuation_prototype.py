"""Experimental records-only association. Never imported by the OCR backend.

Rules v1: uncrossed global gutter and local gap >= 2 median box heights;
local bands separated by
an ink gap > 1.2 median heights or a numbered question heading. No label/model
access, character repair, confidence probability, or claim of semantic proof.
"""
from collections import defaultdict, deque
import math
import re
from statistics import median

from core import layout

RULE_VERSION = "local-gutter-scope-v1"
GUTTER_HEIGHTS = 2.0
BAND_GAP_HEIGHTS = 1.2
QUESTION = re.compile(r"^\s*q[a-z]{3,10}\s*(\d+)\s*[:;.]?\s*$", re.I)


def code_only(text):
    """Mask C literals/comments for evidence; never return this as OCR output."""
    out = []
    i = 0
    while i < len(text):
        if text.startswith('//', i):
            j = text.find('\n', i)
            if j < 0:
                break
            out.append('\n')
            i = j + 1
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            if j < 0:
                return '', False
            out.append(' ')
            i = j + 2
        elif text[i] in ('"', "'"):
            quote = text[i]
            i += 1
            while i < len(text) and text[i] != quote:
                if text[i] == '\n':
                    return '', False
                i += 2 if text[i] == '\\' else 1
            if i >= len(text):
                return '', False
            out.append(' ')
            i += 1
        else:
            out.append(text[i])
            i += 1
    return ''.join(out), True


def scope(code):
    depth = lowest = 0
    for c in code:
        depth += (c == '{') - (c == '}')
        lowest = min(lowest, depth)
    return depth, lowest


def _baseline(records):
    rows, safe = layout._group_detection_records(
        *[[d[k] for d in records] for k in ('text', 'score', 'box')])
    if not safe:
        return list(range(len(records)))
    available = defaultdict(deque)
    for i, d in enumerate(records):
        available[(d['text'], d['score'], tuple(d['box']))].append(i)
    order = []
    for row in rows:
        for m in row:
            key = (m['text'], m['score'], (m['x'], m['y_min'], m['x_max'], m['y_max']))
            order.append(available[key].popleft())
    if sorted(order) != list(range(len(records))):
        raise ValueError('Baseline did not preserve detection IDs')
    return order


def _blocks(ids, records, height, side):
    ordered = sorted(ids, key=lambda i: (sum(records[i]['box'][1::2])/2, records[i]['box'][0], i))
    rows = []
    for i in ordered:
        b = records[i]['box']
        center = (b[1] + b[3]) / 2
        if rows and abs(center - rows[-1]['center']) <= .55 * height:
            rows[-1]['ids'].append(i)
            rows[-1]['bottom'] = max(rows[-1]['bottom'], b[3])
        else:
            rows.append(dict(ids=[i], center=center, top=b[1], bottom=b[3]))
    bands = []
    for row in rows:
        row['ids'].sort(key=lambda i: (records[i]['box'][0], i))
        text = ' '.join(records[i]['text'] for i in row['ids'])
        if (not bands or row['top'] - bands[-1]['bottom'] > BAND_GAP_HEIGHTS * height
                or QUESTION.fullmatch(text)):
            bands.append(dict(id=f'{side}{len(bands)}', side=side, detection_ids=[],
                              top=row['top'], bottom=row['bottom'], text_rows=[]))
        bands[-1]['detection_ids'].extend(row['ids'])
        bands[-1]['text_rows'].append(text)
        bands[-1]['bottom'] = max(bands[-1]['bottom'], row['bottom'])
    return bands


def associate(records):
    """Return ID order, discovered blocks and justified/ambiguous relationships."""
    fallback = list(range(len(records)))
    result = dict(rule_version=RULE_VERSION, baseline_ids=fallback,
                  ordered_ids=fallback, blocks=[], relations=[], changed_order=False,
                  status='ambiguous', reasons=[])
    try:
        for d in records:
            b = d['box']
            if (len(b) != 4 or not all(math.isfinite(float(v)) for v in b)
                    or b[2] <= b[0] or b[3] <= b[1] or not isinstance(d['text'], str)
                    or not math.isfinite(float(d['score']))):
                raise ValueError('Unsafe detection')
    except (KeyError, TypeError, ValueError, OverflowError):
        result['reasons'] = ['invalid_detection_geometry_or_payload']
        return result
    if not records:
        result['reasons'] = ['empty_input']
        return result
    fallback = _baseline(records)
    result.update(baseline_ids=fallback, ordered_ids=fallback[:])
    height = median(d['box'][3] - d['box'][1] for d in records)
    ids = sorted(range(len(records)), key=lambda i: records[i]['box'][0])
    edge = records[ids[0]]['box'][2]
    gaps = []
    for j, i in enumerate(ids[1:], 1):
        b = records[i]['box']
        if b[0] > edge and j >= 2 and len(ids)-j >= 2:
            gaps.append((b[0] - edge, j))
        edge = max(edge, b[2])
    gaps.sort(reverse=True)
    if not gaps or (len(gaps) > 1 and math.isclose(gaps[0][0], gaps[1][0])):
        result['reasons'] = ['no_unique_supported_global_gutter']
        return result
    _, cut = gaps[0]
    left = _blocks(ids[:cut], records, height, 'L')
    right = _blocks(ids[cut:], records, height, 'R')
    result['blocks'] = left + right
    moves = []
    for r in right:
        candidates = [l for l in left if l['bottom'] >= r['top'] - .5*height
                      and r['bottom'] >= l['top'] - .5*height]
        relation = dict(source_block=r['id'], source_detection_ids=r['detection_ids'],
                        target_block=None, target_detection_ids=[],
                        candidate_targets=[l['id'] for l in candidates],
                        decision='ambiguous', reasons=[])
        result['relations'].append(relation)
        if len(candidates) != 1:
            relation['reasons'] = ['no_unique_local_vertical_match']
            continue
        l = candidates[0]
        relation.update(target_block=l['id'], target_detection_ids=l['detection_ids'])
        gap = (min(records[i]['box'][0] for i in r['detection_ids'])
               - max(records[i]['box'][2] for i in l['detection_ids']))
        relation['local_gap_heights'] = gap / height
        if gap < GUTTER_HEIGHTS * height:
            relation['reasons'] = ['insufficient_local_gutter']
            continue
        lq = [QUESTION.fullmatch(t).group(1) for t in l['text_rows'] if QUESTION.fullmatch(t)]
        rq = [QUESTION.fullmatch(t).group(1) for t in r['text_rows'] if QUESTION.fullmatch(t)]
        lc, lok = code_only('\n'.join(l['text_rows']))
        rc, rok = code_only('\n'.join(r['text_rows']))
        if lq and rq and set(lq).isdisjoint(rq):
            relation.update(decision='independent', reasons=['distinct_numbered_headings', 'clean_gutter'])
            continue
        if lok and rok and re.search(r'\bmain\s*\(', lc) and re.search(r'\bmain\s*\(', rc):
            relation.update(decision='independent', reasons=['separate_main_entries', 'clean_gutter'])
            continue
        if not lok or not rok:
            relation['reasons'] = ['uncertain_literal_or_comment_boundary']
            continue
        ld, lm = scope(lc)
        rd, rm = scope(rc)
        relation['scope_evidence'] = dict(left_depth=ld, right_delta=rd, right_minimum=rm)
        if (ld <= 0 or lm < 0 or rd >= 0 or ld + rm < 0
                or (re.search(r'\belse\b', rc) and not re.search(r'\bif\b', lc))):
            relation['reasons'] = ['insufficient_or_conflicting_scope_evidence']
            continue
        relation.update(decision='continuation', reasons=[
            'clean_gutter', 'unique_local_vertical_match', 'recognized_open_scope_and_closing_block'])
        moves.append((l, r, relation))
    # Multiple right blocks competing for one insertion point are not resolved by
    # choosing whichever happens to be visited first.
    for l, r, relation in moves:
        if sum(other[0]['id'] == l['id'] for other in moves) != 1:
            relation.update(decision='ambiguous', reasons=['competing_blocks_for_insertion_point'])
            continue
        moving = set(r['detection_ids'])
        remaining = [i for i in result['ordered_ids'] if i not in moving]
        anchor = max(remaining.index(i) for i in l['detection_ids']) + 1
        result['ordered_ids'] = remaining[:anchor] + r['detection_ids'] + remaining[anchor:]
    assert sorted(result['ordered_ids']) == list(range(len(records)))
    result['changed_order'] = result['ordered_ids'] != fallback
    result['status'] = ('ambiguous' if any(r['decision'] == 'ambiguous' for r in result['relations'])
                        else 'supported')
    result['reasons'] = ['heuristic_evidence_not_semantic_proof']
    return result
