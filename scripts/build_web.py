#!/usr/bin/env python3
"""Build the deployable drill app.

Usage: build_web.py <merged.jsonl> <web_dir> [--examples N]

Two kinds of card, deliberately:

* Convention cards carry no clue text at all. "What is 'artist' worth?" and
  "what does 'about' signal?" are questions about the conventions counted out of
  the corpus — derived facts, and the ones worth drilling hardest anyway.
  Deduplicating them also means you meet each convention once rather than once
  per clue that happens to use it.

* Example cards do need the clue in front of you — you cannot tap the definition
  without it. Those are capped at a small illustrative sample, credited, rather
  than shipping the corpus.
"""
import argparse
import collections
import json
import os
import random
import re

CREDIT = ('Wordplay conventions counted from recent Times daily cryptics. The '
          'worked examples quote individual clues, &copy; The Times / News UK, '
          'for teaching. Crux is a personal training tool, not affiliated with '
          'The Times.')

INDICATOR_TYPES = ['anagram', 'container', 'insertion', 'reversal', 'hidden',
                   'deletion', 'homophone', 'selection']

ONE_OFF = re.compile(
    r'\b(first|last|initial|initially|opening|opens|start|starts|starter|'
    r'beginning|begins|end|ends|ending|final|finally|close to|closing|middle|'
    r'centre|center|heart|edges|sides|outside|ultimately|leader|leading|'
    r'head of|tail of|top of|bottom of|periodically|alternately|regularly)\b')


def reusable(surface, kind):
    s = (surface or '').strip().lower()
    return bool(s) and not ONE_OFF.search(s) and kind != 'selection' and len(s.split()) <= 3


def options(correct, pool, rng, n=4):
    others = [p for p in dict.fromkeys(pool) if p != correct]
    rng.shuffle(others)
    opts = [correct] + others[:n - 1]
    rng.shuffle(opts)
    return opts


def words_of(clue):
    return [w for w in re.findall(r'[^\s]+', clue) if w]


def token_indices(clue, phrase):
    toks = [re.sub(r"[^a-z0-9']", '', w.lower()) for w in words_of(clue)]
    want = [re.sub(r"[^a-z0-9']", '', w.lower()) for w in re.findall(r'[^\s]+', phrase or '')]
    want = [w for w in want if w]
    if not want:
        return []
    for i in range(len(toks) - len(want) + 1):
        if toks[i:i + len(want)] == want:
            return list(range(i, i + len(want)))
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('merged')
    ap.add_argument('web_dir')
    ap.add_argument('--examples', type=int, default=60)
    ap.add_argument('--seed', type=int, default=11)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    clues = [json.loads(l) for l in open(args.merged) if l.strip()]

    # ---------- convention cards, from the derived tables ----------
    subs = collections.Counter()
    sub_kind = {}
    inds = collections.Counter()
    for c in clues:
        for s in c.get('substitutions', []):
            surface = (s.get('surface') or '').strip()
            letters = (s.get('letters') or '').strip().upper()
            if surface and letters and reusable(surface, s.get('kind')):
                subs[(surface.lower(), letters)] += 1
                sub_kind[(surface.lower(), letters)] = s.get('kind', 'other')
        for i in c.get('indicators', []):
            text = (i.get('text') or '').strip().lower()
            typ = (i.get('type') or '').strip().lower()
            if text and typ in INDICATOR_TYPES and len(text.split()) <= 3:
                inds[(text, typ)] += 1

    all_letters = [l for (_, l) in subs]
    cards = []

    for (surface, letters), n in subs.most_common():
        cards.append({
            'kind': 'substitution',
            'prompt': 'What is “%s” worth?' % surface,
            'options': options(letters, all_letters, rng),
            'correct': letters,
            'tag': surface,
            'note': '%s → %s. Seen %d time%s in the clues analysed%s.' % (
                surface, letters, n, '' if n == 1 else 's',
                ' (%s)' % sub_kind[(surface, letters)] if sub_kind.get((surface, letters)) not in (None, 'other') else ''),
        })

    for (text, typ), n in inds.most_common():
        cards.append({
            'kind': 'indicator_type',
            'prompt': 'What does “%s” signal?' % text,
            'options': options(typ, INDICATOR_TYPES, rng),
            'correct': typ,
            'tag': text,
            'note': '“%s” signals %s. Seen %d time%s.' % (text, typ, n, '' if n == 1 else 's'),
        })

    # ---------- worked examples, capped ----------
    with_def = [c for c in clues if token_indices(c['clue'], c.get('definition', ''))]
    rng.shuffle(with_def)
    examples = with_def[:args.examples]
    for c in examples:
        toks = words_of(c['clue'])
        cards.append({
            'kind': 'definition', 'prompt': 'Tap the definition',
            'clue': c['clue'], 'enumeration': c.get('enumeration', ''),
            'tokens': toks, 'targets': token_indices(c['clue'], c['definition']),
            'answer_word': c['answer'], 'puzzle': c.get('puzzle', ''),
            'tag': c['id'], 'note': c.get('explanation', ''),
        })
        for ind in c.get('indicators', []):
            idx = token_indices(c['clue'], ind.get('text', ''))
            if idx and (ind.get('type') or '') in INDICATOR_TYPES:
                cards.append({
                    'kind': 'indicator',
                    'prompt': 'Tap the %s indicator' % ind['type'],
                    'clue': c['clue'], 'enumeration': c.get('enumeration', ''),
                    'tokens': toks, 'targets': idx,
                    'answer_word': c['answer'], 'puzzle': c.get('puzzle', ''),
                    'tag': c['id'] + ':' + ind['text'], 'note': c.get('explanation', ''),
                })
                break

    rng.shuffle(cards)
    os.makedirs(args.web_dir, exist_ok=True)
    with open(os.path.join(args.web_dir, 'data.js'), 'w') as f:
        f.write('const DRILLS = %s;\n' % json.dumps(cards, ensure_ascii=False,
                                                    separators=(',', ':')))
        f.write('const CREDIT = %s;\n' % json.dumps(CREDIT))

    counts = collections.Counter(c['kind'] for c in cards)
    size = os.path.getsize(os.path.join(args.web_dir, 'data.js'))
    print('data.js: %d cards, %.0f KB' % (len(cards), size / 1024))
    for k, n in counts.most_common():
        print('  %-15s %4d' % (k, n))
    print('clues quoted: %d' % len({c['tag'].split(':')[0] for c in cards if c.get('clue')}))


if __name__ == '__main__':
    main()
