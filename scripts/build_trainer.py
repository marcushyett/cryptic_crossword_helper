#!/usr/bin/env python3
"""Build the drill trainer artifact from generated drills.

Usage: build_trainer.py <drills.json> <src/trainer_template.html> <out.html>
       [--max-drills N]

The trainer is a study tool: it shows real clues from recent puzzles, one
question at a time, alongside the substitution and indicator frequencies
derived from analysing them. Clue text stays attributed to the paper that
published it.
"""
import argparse
import json


CREDIT = ('Clues &copy; The Times / News UK, from the daily cryptic. Drills and '
          'wordplay analysis generated for personal study; frequencies are counted '
          'over the clues analysed, not over the whole history of the puzzle.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('drills')
    ap.add_argument('template')
    ap.add_argument('out')
    ap.add_argument('--max-drills', type=int, default=1600)
    args = ap.parse_args()

    data = json.load(open(args.drills))

    # Keep the payload a sensible size for a phone: take a spread across drill
    # kinds rather than the first N, so every track stays playable.
    by_kind = {}
    for d in data['drills']:
        by_kind.setdefault(d['kind'], []).append(d)
    kept, i = [], 0
    while len(kept) < args.max_drills and any(by_kind.values()):
        for kind in list(by_kind):
            if by_kind[kind]:
                kept.append(by_kind[kind].pop())
            if len(kept) >= args.max_drills:
                break
        i += 1
    data['drills'] = kept

    corpus = '%d clues analysed' % data.get('clues', 0)
    html = open(args.template).read()
    html = html.replace('__DATA__', json.dumps(data, ensure_ascii=False))
    html = html.replace('__CORPUS__', json.dumps(corpus))
    html = html.replace('__CREDIT__', json.dumps(CREDIT))
    open(args.out, 'w').write(html)
    counts = {}
    for d in kept:
        counts[d['kind']] = counts.get(d['kind'], 0) + 1
    print('wrote %s — %d drills (%s)' % (args.out, len(kept),
          ', '.join('%s %d' % kv for kv in sorted(counts.items()))))


if __name__ == '__main__':
    main()
