#!/usr/bin/env python3
"""Turn cached puzzle JSON into clue/answer rows.

Usage: extract_corpus.py <archive_dir> <out.jsonl>

Every puzzle past its solution date carries settings.solution — the finished
grid, row-major, one space per black square. Laying that back over the grid and
slicing it with the word coordinates gives the answer to every clue, so the
corpus needs no solving at all. Puzzles without a published solution are
skipped rather than guessed at.
"""
import glob
import html
import json
import os
import re
import sys


def cells(word):
    x, y = str(word['x']), str(word['y'])
    if '-' in x:
        a, b = map(int, x.split('-'))
        return [(int(y), c) for c in range(a, b + 1)]
    a, b = map(int, y.split('-'))
    return [(r, int(x)) for r in range(a, b + 1)]


def puzzle_rows(path):
    data = json.load(open(path))['data']
    copy = data['copy']
    solution = copy.get('settings', {}).get('solution')
    if not solution:
        return []

    grid = data['grid']
    rows, cols = len(grid), len(grid[0])
    if len(solution) != rows * cols:
        return []
    letters = [[solution[r * cols + c] for c in range(cols)] for r in range(rows)]

    words = {w['id']: w for w in copy['words']}
    date = re.sub(r'\D', '', copy.get('date-publish-analytics', ''))[:8]
    out = []
    for group in copy['clues']:
        direction = group['title'].lower()
        for clue in group['clues']:
            answer = ''.join(letters[r - 1][c - 1] for r, c in cells(words[clue['word']]))
            if len(answer) != clue['length'] or ' ' in answer:
                continue
            out.append({
                'puzzle': copy['title'],
                'date': date,
                'id': '%s-%d%s' % (date, clue['number'], direction[0].upper()),
                'number': clue['number'],
                'direction': direction,
                'clue': html.unescape(clue['clue']),
                'enumeration': clue['format'],
                'length': clue['length'],
                'answer': answer,
            })
    return out


def main():
    archive, out_path = sys.argv[1:3]
    rows, skipped = [], 0
    for path in sorted(glob.glob(os.path.join(archive, 'raw', '*.json'))):
        got = puzzle_rows(path)
        if got:
            rows.extend(got)
        else:
            skipped += 1
    with open(out_path, 'w') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    puzzles = len({r['date'] for r in rows})
    print('%d clues from %d puzzles (%d skipped, no published solution) -> %s'
          % (len(rows), puzzles, skipped, out_path))


if __name__ == '__main__':
    main()
