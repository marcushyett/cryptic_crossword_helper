#!/usr/bin/env python3
"""Prove a set of answers is the real solution, using the feed's own hash.

The Times feed omits the solution letters but ships settings.solution_hashed:
the MD5 of the completed grid, read row-major, with a single space for every
black square. Fill the grid from the answers, hash it, compare.

Usage: verify_solution.py <crossword.json> <solved_clues.json>
Exit status 0 on a match.
"""
import hashlib
import json
import re
import sys


def cells(word):
    x, y = str(word['x']), str(word['y'])
    if '-' in x:
        a, b = map(int, x.split('-'))
        return [(int(y), c) for c in range(a, b + 1)]
    a, b = map(int, y.split('-'))
    return [(r, int(x)) for r in range(a, b + 1)]


def main():
    feed = json.load(open(sys.argv[1]))['data']
    solved = json.load(open(sys.argv[2]))
    grid = feed['grid']
    words = {w['id']: w for w in feed['copy']['words']}
    target = feed['copy']['settings']['solution_hashed']

    answers = {c['id']: re.sub(r'[^A-Z]', '', c['answer'].upper()) for c in solved}
    rows, cols = len(grid), len(grid[0])
    filled = [[None] * cols for _ in range(rows)]
    problems = []

    for group in feed['copy']['clues']:
        d = group['title'][0].upper()
        for clue in group['clues']:
            key = '%d%s' % (clue['number'], d)
            answer = answers.get(key)
            if not answer:
                problems.append('%s: no answer supplied' % key)
                continue
            if len(answer) != clue['length']:
                problems.append('%s: %d letters, expected %d' % (key, len(answer), clue['length']))
                continue
            for (r, c), ch in zip(cells(words[clue['word']]), answer):
                if filled[r - 1][c - 1] not in (None, ch):
                    problems.append('%s: clashes at row %d col %d (%s vs %s)'
                                    % (key, r, c, filled[r - 1][c - 1], ch))
                filled[r - 1][c - 1] = ch

    flat = ''.join(
        ' ' if grid[r][c]['Blank'] else (filled[r][c] or '?')
        for r in range(rows) for c in range(cols)
    )
    digest = hashlib.md5(flat.encode()).hexdigest()

    for r in range(rows):
        print(flat[r * cols:(r + 1) * cols].replace(' ', '#'))
    for p in problems:
        print('!', p)
    print('md5 %s / target %s' % (digest, target))
    if digest == target:
        print('MATCH — this is the published solution.')
        return 0
    print('NO MATCH')
    return 1


if __name__ == '__main__':
    sys.exit(main())
