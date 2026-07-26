#!/usr/bin/env python3
"""Turn annotated clues into single-action training drills.

Usage: build_drills.py <annotations.jsonl> <out.json> [--max-clues N]

Every drill asks for exactly one thing about one real clue — spot the
definition, name the device, say what letters a word yields — so a session is a
run of small decisions rather than a run of whole solves. The same clue turns up
under several drill types, which is the point: you meet it once for its
definition, again for its anagram indicator, again for the abbreviation buried
in it.

Drill types
  definition     tap the words that define the answer
  indicator      tap the word doing the signalling
  device         name the wordplay device
  indicator_type say which device an indicator signals
  substitution   what letters does this word yield here
  reverse_sub    which word in the clue yields these letters
  fodder         tap the words the wordplay operates on
"""
import argparse
import collections
import json
import random
import re

DEVICE_LABELS = {
    'anagram': 'Anagram',
    'charade': 'Charade',
    'container': 'Container',
    'hidden': 'Hidden word',
    'reversal': 'Reversal',
    'deletion': 'Deletion',
    'homophone': 'Homophone',
    'substitution': 'Substitution',
    'selection': 'Letter selection',
    'double-definition': 'Double definition',
    'cryptic-definition': 'Cryptic definition',
    '&lit': '&lit',
    'spoonerism': 'Spoonerism',
}

INDICATOR_TYPES = ['anagram', 'container', 'insertion', 'reversal', 'hidden',
                   'deletion', 'homophone', 'selection']


def words_of(clue):
    """Split a clue into tappable tokens, keeping punctuation attached."""
    return [w for w in re.findall(r"[^\s]+", clue) if w]


def token_indices(clue, phrase):
    """Which token positions of the clue does this phrase cover?"""
    toks = [re.sub(r"[^a-z0-9']", '', w.lower()) for w in words_of(clue)]
    want = [re.sub(r"[^a-z0-9']", '', w.lower()) for w in re.findall(r"[^\s]+", phrase)]
    want = [w for w in want if w]
    if not want:
        return []
    for start in range(len(toks) - len(want) + 1):
        if toks[start:start + len(want)] == want:
            return list(range(start, start + len(want)))
    # fall back to a single distinctive token
    for i, t in enumerate(toks):
        if t and t == want[0]:
            return [i]
    return []


def choices(correct, pool, n=4, rng=random):
    others = [p for p in dict.fromkeys(pool) if p != correct]
    rng.shuffle(others)
    opts = [correct] + others[:n - 1]
    rng.shuffle(opts)
    return opts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('annotations')
    ap.add_argument('out')
    ap.add_argument('--max-clues', type=int, default=0)
    ap.add_argument('--seed', type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    clues = [json.loads(l) for l in open(args.annotations) if l.strip()]
    if args.max_clues:
        clues = clues[:args.max_clues]

    # frequency tables drive both the distractors and the "worth drilling" test
    sub_freq = collections.Counter()
    sub_letters = collections.defaultdict(collections.Counter)
    ind_freq = collections.Counter()
    for c in clues:
        for s in c.get('substitutions', []):
            key = (s.get('surface') or '').strip().lower()
            letters = (s.get('letters') or '').strip().upper()
            if key and letters:
                sub_freq[key] += 1
                sub_letters[key][letters] += 1
        for i in c.get('indicators', []):
            if i.get('text'):
                ind_freq[i['text'].strip().lower()] += 1
    all_letters = [l for k in sub_letters for l in sub_letters[k]]

    drills = []

    def add(kind, clue, prompt, **kw):
        drills.append(dict(
            kind=kind, clue_id=clue['id'], clue=clue['clue'],
            enumeration=clue.get('enumeration', ''), answer_word=clue['answer'],
            puzzle=clue.get('puzzle', ''), date=clue.get('date', ''),
            prompt=prompt, explanation=clue.get('explanation', ''), **kw))

    for c in clues:
        toks = words_of(c['clue'])

        # 1. spot the definition
        idx = token_indices(c['clue'], c.get('definition', ''))
        if idx:
            add('definition', c, 'Tap the definition', targets=idx, tokens=toks)

        # 2. spot an indicator, and 3. say what it signals
        for ind in c.get('indicators', []):
            text, kind = (ind.get('text') or '').strip(), (ind.get('type') or '').strip()
            if not text or not kind:
                continue
            idx = token_indices(c['clue'], text)
            if idx:
                add('indicator', c, 'Tap the %s indicator' % kind,
                    targets=idx, tokens=toks, tag=kind)
            add('indicator_type', c, 'What does “%s” signal here?' % text,
                options=choices(kind, INDICATOR_TYPES, 4, rng), correct=kind, tag=kind)

        # 4. the wordplay device
        devs = [d for d in c.get('devices', []) if d in DEVICE_LABELS]
        if devs:
            correct = DEVICE_LABELS[devs[0]]
            add('device', c, 'Which device is doing the work?',
                options=choices(correct, list(DEVICE_LABELS.values()), 4, rng),
                correct=correct, tag=devs[0])

        # 5/6. substitutions, both directions
        for s in c.get('substitutions', []):
            surface = (s.get('surface') or '').strip()
            letters = (s.get('letters') or '').strip().upper()
            if not surface or not letters:
                continue
            add('substitution', c, 'In this clue, “%s” gives which letters?' % surface,
                options=choices(letters, all_letters, 4, rng), correct=letters,
                tag=surface.lower(), kind_of_sub=s.get('kind', 'other'))
            idx = token_indices(c['clue'], surface)
            if idx:
                add('reverse_sub', c, 'Which word here gives %s?' % letters,
                    targets=idx, tokens=toks, tag=surface.lower())

        # 7. anagram fodder
        if 'anagram' in c.get('devices', []) and c.get('fodder'):
            fodder = re.sub(r'\(.*?\)', ' ', c['fodder'])
            fodder = re.sub(r'[^A-Za-z\s]', ' ', fodder)
            idx = token_indices(c['clue'], fodder)
            if idx:
                add('fodder', c, 'Tap the anagram fodder', targets=idx, tokens=toks)

    rng.shuffle(drills)
    stats = collections.Counter(d['kind'] for d in drills)
    payload = {
        'drills': drills,
        'subs': [{'surface': k, 'letters': sub_letters[k].most_common(1)[0][0],
                  'count': v} for k, v in sub_freq.most_common(120)],
        'indicators': [{'text': k, 'count': v} for k, v in ind_freq.most_common(120)],
        'clues': len(clues),
    }
    with open(args.out, 'w') as f:
        json.dump(payload, f, ensure_ascii=False)
    print('%d drills from %d clues' % (len(drills), len(clues)))
    for k, n in stats.most_common():
        print('  %-15s %5d' % (k, n))


if __name__ == '__main__':
    main()
