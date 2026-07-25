#!/usr/bin/env python3
"""Render the solved-clue file as a markdown table with spoiler-hidden answers.

Usage: build_hint_table.py <solved.json> <out.md>
"""
import json
import sys


def cell(s):
    return s.replace('|', '\\|').replace('\n', ' ')


def main():
    solved = json.load(open(sys.argv[1]))
    meta = solved.pop(0)['meta'] if 'meta' in solved[0] else {}
    lines = []
    lines.append('# %s' % meta.get('title', 'Cryptic crossword'))
    lines.append('')
    lines.append('%s' % meta.get('dateline', ''))
    lines.append('')
    lines.append('Solutions are collapsed — click **Reveal** to spoil one.')
    lines.append('')
    lines.append('| Clue | Enum | Indicator hint | Fodder hint | Definition hint | Solution |')
    lines.append('|---|---|---|---|---|---|')
    for c in solved:
        sol = '<details><summary>Reveal</summary>%s</details>' % c['answer']
        lines.append('| **%s** %s | (%s) = %d | %s | %s | %s | %s |' % (
            c['id'], cell(c['clue']), c['format'], c['length'],
            cell(c['indicators']), cell(c['fodder']), cell(c['definition_hint']), sol))
    lines.append('')
    lines.append('## Full parsings')
    lines.append('')
    for c in solved:
        lines.append('<details><summary><strong>%s</strong> %s (%s)</summary>' % (
            c['id'], c['clue'], c['format']))
        lines.append('')
        lines.append('**%s** — %s' % (c['answer'], c['explanation']))
        lines.append('')
        lines.append('</details>')
        lines.append('')
    open(sys.argv[2], 'w').write('\n'.join(lines))
    print('wrote %s' % sys.argv[2])


if __name__ == '__main__':
    main()
