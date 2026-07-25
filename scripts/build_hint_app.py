#!/usr/bin/env python3
"""Build the clue-by-clue hint app from a solved-clue file.

Usage: build_hint_app.py <solved.json> <src/hint_app_template.html> <out.html>

solved.json is a list of objects:
  {id, number, direction, clue, format, length,
   definition_hint, indicators, fodder, explanation, answer}

Answers never appear in the output as plain text: each is stored base64-encoded
for the reveal and SHA-256-hashed for answer checking.
"""
import base64
import hashlib
import html
import json
import re
import sys


def bare(s):
    return re.sub(r'[^A-Z]', '', s.upper())


def redact(text, answer):
    """Blank the answer wherever it appears in hint text.

    A full parsing inevitably ends in the answer, which would spoil the rungs
    below it — and would sit in the page source in plain sight. Match the
    letters with any separators between them (ABSENT-MINDED, A,B,S,E,N,T...)
    and swap in a marker instead.
    """
    letters = bare(answer)
    if not letters:
        return text
    pattern = r'[\s,.\-’\']*'.join(re.escape(ch) for ch in letters)
    return re.sub(pattern, '<span class="redact">the answer</span>', text, flags=re.I)


def build(solved, template, title, dateline, credit, puzzle_id):
    clues = []
    for c in solved:
        answer = c['answer'].upper()
        clues.append({
            'id': c['id'],
            'num': c['number'],
            'dir': c['direction'],
            'clue': c['clue'],
            'fmt': c['format'],
            'len': c['length'],
            'a': base64.b64encode(answer.encode()).decode(),
            'k': hashlib.sha256(bare(answer).encode()).hexdigest(),
            'h': {
                k: redact(html.escape(c[src]), answer)
                for k, src in (('definition', 'definition_hint'),
                               ('indicators', 'indicators'),
                               ('fodder', 'fodder'),
                               ('explanation', 'explanation'))
            },
        })
    out = template
    out = out.replace('__DATA__', json.dumps(clues, ensure_ascii=False))
    out = out.replace('__TITLE__', html.escape(title))
    out = out.replace('__DATELINE__', html.escape(dateline))
    out = out.replace('__CREDIT__', credit)
    out = out.replace('__PUZZLEID__', puzzle_id)
    return out


def main():
    solved_path, template_path, out_path = sys.argv[1:4]
    solved = json.load(open(solved_path))
    meta = solved.pop(0) if isinstance(solved[0], dict) and 'meta' in solved[0] else None
    template = open(template_path).read()
    m = meta['meta'] if meta else {}
    out = build(
        solved,
        template,
        m.get('title', 'Cryptic Crossword'),
        m.get('dateline', ''),
        m.get('credit', ''),
        m.get('puzzle_id', 'puzzle'),
    )
    open(out_path, 'w').write(out)
    print('wrote %s (%d clues)' % (out_path, len(solved)))


if __name__ == '__main__':
    main()
