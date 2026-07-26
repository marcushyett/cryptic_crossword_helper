#!/usr/bin/env python3
"""Aggregate clue annotations into the CSV database.

Usage: build_database.py <annotations.jsonl> <out_dir>

Writes:
  clues.csv          one row per clue: definition, device, indicators, fodder
  substitutions.csv  surface word -> letters, ranked by how often the setter uses it
  indicators.csv     indicator word -> device it signals, ranked by frequency
  devices.csv        how often each wordplay device appears

The substitution table is the point of the exercise: which words this paper's
setters reach for when they mean a letter or two, and how often — knowledge you
only get by reading a lot of their clues.
"""
import collections
import csv
import json
import os
import re
import sys


def norm(s):
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


# "close to free" yields E, but only in that clue. Instructions like these are
# letter-selection wordplay, not conventions worth memorising, so they are kept
# in the clue-level table and flagged out of the frequency tables.
ONE_OFF = re.compile(
    r'\b(first|last|initial|initially|opening|opens|start|starts|starter|'
    r'beginning|begins|end|ends|ending|final|finally|close to|closing|middle|'
    r'centre|center|heart|edges|sides|outside|ultimately|leader|leading|'
    r'head of|tail of|top of|bottom of|periodically|alternately|regularly)\b')


def reusable(surface, kind):
    """Is this a convention that will turn up again, or a one-off instruction?"""
    s = norm(surface)
    if not s or ONE_OFF.search(s):
        return False
    if kind in ('selection',):
        return False
    return len(s.split()) <= 3


def load(path):
    rows = []
    for line in open(path):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_csv(path, header, rows):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print('%-22s %5d rows' % (os.path.basename(path), len(rows)))


def main():
    ann_path, out_dir = sys.argv[1:3]
    os.makedirs(out_dir, exist_ok=True)
    clues = load(ann_path)

    # ---- clues.csv -------------------------------------------------------
    clue_rows = []
    for c in clues:
        inds = '|'.join('%s:%s' % (i.get('text', ''), i.get('type', ''))
                        for i in c.get('indicators', []))
        subs = '|'.join('%s=%s' % (s.get('surface', ''), s.get('letters', ''))
                        for s in c.get('substitutions', []))
        clue_rows.append([
            c['id'], c.get('date', ''), c.get('puzzle', ''), c.get('number', ''),
            c.get('direction', ''), c['clue'], c.get('enumeration', ''),
            c.get('length', ''), c['answer'], c.get('definition', ''),
            '|'.join(c.get('devices', [])), inds, c.get('fodder', ''), subs,
            c.get('explanation', ''),
        ])
    write_csv(os.path.join(out_dir, 'clues.csv'),
              ['id', 'date', 'puzzle', 'number', 'direction', 'clue', 'enumeration',
               'length', 'answer', 'definition', 'devices', 'indicators', 'fodder',
               'substitutions', 'explanation'],
              clue_rows)

    # ---- substitutions.csv ----------------------------------------------
    subs = collections.defaultdict(lambda: {'kinds': collections.Counter(), 'ex': []})
    for c in clues:
        for s in c.get('substitutions', []):
            surface, letters = norm(s.get('surface')), (s.get('letters') or '').upper().strip()
            if not surface or not letters:
                continue
            rec = subs[(surface, letters)]
            rec['kinds'][s.get('kind', 'other')] += 1
            rec['ex'].append((c['id'], c['clue'], c['answer']))
    sub_rows = []
    for (surface, letters), rec in subs.items():
        ex = rec['ex'][0]
        kind = rec['kinds'].most_common(1)[0][0]
        sub_rows.append([surface, letters, len(rec['ex']), kind,
                         'yes' if reusable(surface, kind) else 'no',
                         '; '.join(sorted({e[0] for e in rec['ex']})[:5]),
                         ex[1], ex[2]])
    sub_rows.sort(key=lambda r: (-r[2], r[0]))
    write_csv(os.path.join(out_dir, 'substitutions.csv'),
              ['surface', 'letters', 'count', 'kind', 'reusable', 'seen_in',
               'example_clue', 'example_answer'], sub_rows)

    # ---- letter_index.csv ------------------------------------------------
    # The reverse lookup: sitting at the puzzle you rarely ask "what is 'wife'
    # worth" — you ask "I need an L here, what might be giving it".
    by_letters = collections.defaultdict(collections.Counter)
    for c in clues:
        for s in c.get('substitutions', []):
            letters = (s.get('letters') or '').upper().strip()
            surface = norm(s.get('surface'))
            if letters and surface and reusable(surface, s.get('kind')):
                by_letters[letters][surface] += 1
    letter_rows = []
    for letters, surfaces in by_letters.items():
        letter_rows.append([
            letters, sum(surfaces.values()), len(surfaces),
            ', '.join('%s (%d)' % (w, n) for w, n in surfaces.most_common(12)),
        ])
    letter_rows.sort(key=lambda r: (-r[1], r[0]))
    write_csv(os.path.join(out_dir, 'letter_index.csv'),
              ['letters', 'times_seen', 'distinct_words', 'words_that_give_it'],
              letter_rows)

    # ---- indicators.csv --------------------------------------------------
    inds = collections.defaultdict(lambda: {'ex': [], 'n': 0})
    for c in clues:
        for i in c.get('indicators', []):
            text, kind = norm(i.get('text')), norm(i.get('type'))
            if not text or not kind:
                continue
            rec = inds[(text, kind)]
            rec['n'] += 1
            rec['ex'].append((c['id'], c['clue']))
    ind_rows = [[t, k, r['n'], '; '.join(sorted({e[0] for e in r['ex']})[:5]), r['ex'][0][1]]
                for (t, k), r in inds.items()]
    ind_rows.sort(key=lambda r: (-r[2], r[0]))
    write_csv(os.path.join(out_dir, 'indicators.csv'),
              ['indicator', 'signals', 'count', 'seen_in', 'example_clue'], ind_rows)

    # ---- devices.csv -----------------------------------------------------
    dev = collections.Counter()
    for c in clues:
        for d in c.get('devices', []):
            dev[norm(d)] += 1
    total = sum(dev.values()) or 1
    write_csv(os.path.join(out_dir, 'devices.csv'), ['device', 'count', 'share'],
              [[d, n, '%.1f%%' % (100.0 * n / total)] for d, n in dev.most_common()])

    print('\n%d clues · %d distinct substitutions · %d distinct indicators'
          % (len(clues), len(sub_rows), len(ind_rows)))


if __name__ == '__main__':
    main()
