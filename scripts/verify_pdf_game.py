#!/usr/bin/env python3
"""Prove the PDF game's link graph by playing it.

Usage: verify_pdf_game.py <game.pdf> <solved_clues.json>

Reads the state->page map written alongside the PDF, then for every clue taps
out the correct answer letter by letter through the real link annotations and
checks it lands on that clue's solved page — and that every other key on every
keyboard leads to the right "not that letter" page.
"""
import json
import re
import sys

import fitz


def keyboard_keys(doc, pno):
    page = doc[pno]
    links = [(l['from'], int(l['page']) - 1) for l in page.get_links()]
    out = {}
    for w in page.get_text('words'):
        text = w[4]
        if len(text) != 1 or not text.isalpha():
            continue
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        for rect, target in links:
            if rect.x0 <= cx <= rect.x1 and rect.y0 <= cy <= rect.y1 and (rect.y1 - rect.y0) > 25:
                out[text] = target
    return out


def main():
    pdf_path, solved_path = sys.argv[1:3]
    doc = fitz.open(pdf_path)
    page_of = {k: v - 1 for k, v in json.load(open(pdf_path + '.map.json')).items()}
    solved = json.load(open(solved_path))
    if 'meta' in solved[0]:
        solved = solved[1:]

    problems = []
    for i, clue in enumerate(solved):
        answer = re.sub(r'[^A-Z]', '', clue['answer'].upper())
        pno = page_of['k%d_0' % i]
        for p, ch in enumerate(answer):
            keys = keyboard_keys(doc, pno)
            if len(keys) != 26:
                problems.append('%s pos %d: %d keys' % (clue['id'], p, len(keys)))
                break
            expect = page_of['ok%d' % i] if p + 1 == len(answer) else page_of['k%d_%d' % (i, p + 1)]
            if keys[ch] != expect:
                problems.append('%s pos %d: right letter goes to the wrong page' % (clue['id'], p))
                break
            if {keys[k] for k in keys if k != ch} != {page_of['x%d_%d' % (i, p)]}:
                problems.append('%s pos %d: wrong letters mis-routed' % (clue['id'], p))
                break
            pno = keys[ch]
        else:
            if pno != page_of['ok%d' % i]:
                problems.append('%s: did not land on its solved page' % clue['id'])

    # fitz reports link targets as 1-based page numbers
    out_of_range = sum(
        1 for n in range(doc.page_count) for l in doc[n].get_links()
        if not 1 <= int(l.get('page', 0)) <= doc.page_count)

    print('%d pages, %d links, %d clues played'
          % (doc.page_count,
             sum(len(doc[n].get_links()) for n in range(doc.page_count)),
             len(solved)))
    for p in problems:
        print('!', p)
    print('dangling links: %d' % out_of_range)
    if problems or out_of_range:
        return 1
    print('OK — every answer types through to its solved page.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
