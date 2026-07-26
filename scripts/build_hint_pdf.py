#!/usr/bin/env python3
"""Build an interactive PDF of the clue-by-clue trainer.

Usage: build_hint_pdf.py <solved_clues.json> <crossword.json> <out.pdf>

Interactivity is link-driven rather than script-driven: every hint lives on its
own page, reached by tapping. That works in every PDF viewer — iOS Files and
Books, Chrome, Drive, Preview — whereas PDF JavaScript only runs in Adobe
Acrobat/Reader and is silently ignored everywhere else.

Layout per clue: a clue page, five hint pages (one rung each), an answer page.
Answers sit only on the answer pages, so nothing is spoiled by scrolling past.
"""
import json
import os
import re
import sys

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Paragraph

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_hint_app import bare  # noqa: E402

W, H = 360, 640                      # phone-shaped page
M = 24                               # margin
INK = HexColor('#14161A')
PAPER = HexColor('#FAFAF6')
PAPER2 = HexColor('#F0F0EA')
GRAPHITE = HexColor('#62666E')
RULE = HexColor('#D9D9D1')
MARK = HexColor('#E9B824')
MARK_SOFT = HexColor('#F7E7AE')
OK = HexColor('#2E7D4F')
WHITE = Color(1, 1, 1)

RUNGS = [
    ('definition_hint', 'Where the definition is'),
    ('indicators', 'What the setter is doing'),
    ('fodder', 'What the wordplay works on'),
    ('opening', 'The opening letters'),
    ('explanation', 'The full parsing'),
]


def redact_plain(text, answer, marker='[THE ANSWER]'):
    letters = bare(answer)
    pattern = r'[\s,.\-’\']*'.join(re.escape(ch) for ch in letters)
    return re.sub(pattern, marker, text, flags=re.I)


def para(text, size, leading, colour=INK, font='Times-Roman'):
    return Paragraph(text, ParagraphStyle('s', fontName=font, fontSize=size,
                                          leading=leading, textColor=colour))


def draw_para(c, text, x, y, width, size, leading, colour=INK, font='Times-Roman'):
    """Draw wrapped text with y as the TOP edge. Returns the new y (bottom)."""
    p = para(text, size, leading, colour, font)
    _, h = p.wrapOn(c, width, H)
    p.drawOn(c, x, y - h)
    return y - h


def button(c, label, x, y, w, h, dest, *, fill=PAPER2, stroke=RULE,
           text_colour=INK, font='Helvetica-Bold', size=9.5, step=None):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 2.5, stroke=1, fill=1)
    tx = x + 10
    if step is not None:
        c.setFillColor(MARK_SOFT if fill is PAPER2 else MARK)
        c.roundRect(x + 7, y + h / 2 - 6.5, 13, 13, 1.5, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont('Courier-Bold', 8)
        c.drawCentredString(x + 13.5, y + h / 2 - 3, str(step))
        tx = x + 26
    c.setFillColor(text_colour)
    c.setFont(font, size)
    c.drawString(tx, y + h / 2 - 3.2, label)
    c.setFillColor(GRAPHITE if text_colour is INK else text_colour)
    c.setFont('Helvetica', 9)
    c.drawRightString(x + w - 9, y + h / 2 - 3.2, '›')
    c.linkAbsolute('', dest, (x, y, x + w, y + h), Border='[0 0 0]')


def chrome(c, clue, i, total, page_label):
    """Masthead and footer navigation shared by every clue-related page."""
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica-Bold', 7)
    c.drawString(M, H - M - 6, 'TIMES CRYPTIC No 29604')
    c.setFont('Courier', 7)
    c.drawRightString(W - M, H - M - 6, '%d / %d' % (i + 1, total))
    c.setStrokeColor(RULE)
    c.setLineWidth(0.8)
    c.line(M, H - M - 14, W - M, H - M - 14)

    # clue number chip + what this page is
    y = H - M - 38
    label = '%d %s' % (clue['number'], clue['direction'].upper())
    w = pdfmetrics.stringWidth(label, 'Courier-Bold', 8) + 14
    c.setFillColor(INK)
    c.roundRect(M, y, w, 16, 2, stroke=0, fill=1)
    c.setFillColor(PAPER)
    c.setFont('Courier-Bold', 8)
    c.drawString(M + 7, y + 5, label)
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(M + w + 8, y + 5, page_label.upper())

    # footer nav
    c.setStrokeColor(RULE)
    c.line(M, 46, W - M, 46)
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(GRAPHITE)
    prev_dest = 'clue%d' % (i - 1) if i > 0 else 'index'
    next_dest = 'clue%d' % (i + 1) if i < total - 1 else 'index'
    c.drawString(M, 30, '‹ Prev' if i > 0 else '‹ Index')
    c.linkAbsolute('', prev_dest, (M, 24, M + 50, 40), Border='[0 0 0]')
    c.drawCentredString(W / 2, 30, 'All clues')
    c.linkAbsolute('', 'index', (W / 2 - 30, 24, W / 2 + 30, 40), Border='[0 0 0]')
    c.drawRightString(W - M, 30, 'Next ›' if i < total - 1 else 'Index ›')
    c.linkAbsolute('', next_dest, (W - M - 50, 24, W - M, 40), Border='[0 0 0]')
    return y - 16


def clue_page(c, clue, i, total):
    c.bookmarkPage('clue%d' % i)
    y = chrome(c, clue, i, total, 'the clue')

    y = draw_para(c, clue['clue'], M, y - 6, W - 2 * M, 15, 19.5)
    c.setFillColor(GRAPHITE)
    c.setFont('Courier-Bold', 10)
    c.drawString(M, y - 16, '(%s)' % clue['format'])

    # fillable answer box — viewers that support forms let you type here
    box_y = y - 52
    c.acroForm.textfield(
        name='ans_%s' % clue['id'], value='', x=M, y=box_y,
        width=W - 2 * M, height=26, maxlen=clue['length'] + 4,
        fontName='Courier', fontSize=13, textColor=INK,
        fillColor=WHITE, borderColor=INK, borderWidth=1,
        tooltip='Your answer to %s (%s letters)' % (clue['id'], clue['length']),
        forceBorder=True)

    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 7)
    c.drawString(M, box_y - 11, 'Type here if your viewer allows it, or keep it in your head.')

    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(M, box_y - 34, 'HINTS — TAKE THE LOWEST RUNG THAT UNSTICKS YOU')

    by = box_y - 70
    for n, (_, title) in enumerate(RUNGS):
        button(c, title, M, by, W - 2 * M, 24, 'hint%d_%d' % (i, n), step=n + 1)
        by -= 28
    button(c, 'Give up — show the answer', M, by - 6, W - 2 * M, 26,
           'ans%d' % i, fill=INK, stroke=INK, text_colour=PAPER)
    c.showPage()


def hint_page(c, clue, i, total, n):
    key, title = RUNGS[n]
    c.bookmarkPage('hint%d_%d' % (i, n))
    y = chrome(c, clue, i, total, 'hint %d of %d' % (n + 1, len(RUNGS)))

    y = draw_para(c, clue['clue'], M, y - 6, W - 2 * M, 11.5, 15, GRAPHITE)
    c.setFillColor(GRAPHITE)
    c.setFont('Courier-Bold', 9)
    c.drawString(M, y - 13, '(%s)' % clue['format'])

    y -= 30
    c.setFillColor(MARK)
    c.rect(M, y - 4, 3, 14, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont('Helvetica-Bold', 10.5)
    c.drawString(M + 10, y, title)

    if key == 'opening':
        letters = bare(clue['answer'])
        shown = 2 if clue['length'] > 5 else 1
        text = 'It begins <b>%s</b>, and runs to %d letters in all.' % (
            ' '.join(letters[:shown]), clue['length'])
    else:
        text = redact_plain(clue[key], clue['answer'])
    bottom = draw_para(c, text, M + 10, y - 12, W - 2 * M - 10, 10.5, 15)

    by = max(110, bottom - 34)
    if n + 1 < len(RUNGS):
        button(c, 'Next hint: %s' % RUNGS[n + 1][1], M, by, W - 2 * M, 24,
               'hint%d_%d' % (i, n + 1), step=n + 2)
        by -= 28
    button(c, 'Back to the clue', M, by, (W - 2 * M) / 2 - 4, 22, 'clue%d' % i)
    button(c, 'Show the answer', M + (W - 2 * M) / 2 + 4, by, (W - 2 * M) / 2 - 4, 22,
           'ans%d' % i, fill=INK, stroke=INK, text_colour=PAPER)
    c.showPage()


def answer_page(c, clue, i, total):
    c.bookmarkPage('ans%d' % i)
    y = chrome(c, clue, i, total, 'the answer')

    y = draw_para(c, clue['clue'], M, y - 6, W - 2 * M, 11.5, 15, GRAPHITE)

    y -= 24
    c.setFillColor(PAPER2)
    c.setStrokeColor(OK)
    c.setLineWidth(1.2)
    c.roundRect(M, y - 20, W - 2 * M, 40, 3, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont('Courier-Bold', 16)
    answer = clue['answer'].upper()
    size = 16
    while pdfmetrics.stringWidth(answer, 'Courier-Bold', size) > W - 2 * M - 20 and size > 8:
        size -= 0.5
        c.setFont('Courier-Bold', size)
    c.drawCentredString(W / 2, y - 5, answer)

    y -= 46
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(M, y, 'HOW IT WORKS')
    y = draw_para(c, clue['explanation'], M, y - 8, W - 2 * M, 10.5, 15)
    y = draw_para(c, '<b>Definition:</b> ' + clue['definition_hint'], M, y - 10,
                  W - 2 * M, 9.5, 13.5, GRAPHITE)

    by = 76
    nxt = 'clue%d' % (i + 1) if i < total - 1 else 'index'
    button(c, 'Next clue' if i < total - 1 else 'Back to all clues', M, by,
           W - 2 * M, 24, nxt, fill=INK, stroke=INK, text_colour=PAPER)
    c.showPage()


def cover(c, total):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont('Times-Bold', 20)
    c.drawString(M, H - 90, 'Times Cryptic')
    c.setFont('Times-Bold', 34)
    c.drawString(M, H - 124, 'No 29604')
    c.setFillColor(GRAPHITE)
    c.setFont('Courier', 9)
    c.drawString(M, H - 142, 'SATURDAY 25 JULY 2026  ·  %d CLUES' % total)

    c.setStrokeColor(RULE)
    c.line(M, H - 158, W - M, H - 158)

    y = draw_para(
        c,
        'One clue at a time. Work it out, and if you stick, climb the hints only as '
        'far as you need: where the definition is, what device the setter used, what '
        'the wordplay works on, the opening letters, the full parsing — and only '
        'then the answer.',
        M, H - 176, W - 2 * M, 11, 16, INK)

    y = draw_para(
        c,
        'Every hint is a tap away on its own page, so nothing is spoiled by reading '
        'ahead. Answers live only on the answer pages.',
        M, y - 12, W - 2 * M, 9.5, 14, GRAPHITE)

    button(c, 'Start with 1 across', M, y - 34, W - 2 * M, 28, 'clue0',
           fill=INK, stroke=INK, text_colour=PAPER, size=10.5)
    button(c, 'Jump to any clue', M, y - 68, W - 2 * M, 26, 'index')

    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 7)
    draw_para(c,
              'Clues © The Times / News UK, from the puzzle feed for 25 July 2026. '
              'Parsings written for practice; the full solution is verified against the '
              'feed’s own published grid hash.',
              M, 92, W - 2 * M, 7.5, 10.5, GRAPHITE, 'Helvetica')
    c.showPage()


def index_page(c, clues):
    c.bookmarkPage('index')
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont('Times-Bold', 15)
    c.drawString(M, H - 56, 'All clues')
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 8)
    c.drawString(M, H - 70, 'Tap any clue to go straight to it.')

    y = H - 90
    for i, clue in enumerate(clues):
        if i and clues[i - 1]['direction'] != clue['direction']:
            c.setFillColor(GRAPHITE)
            c.setFont('Helvetica-Bold', 7.5)
            y -= 6
            c.drawString(M, y, clue['direction'].upper())
            y -= 12
        elif i == 0:
            c.setFillColor(GRAPHITE)
            c.setFont('Helvetica-Bold', 7.5)
            c.drawString(M, y, clue['direction'].upper())
            y -= 12
        c.setFillColor(INK)
        c.setFont('Courier-Bold', 7.5)
        c.drawString(M, y, '%-4s' % clue['id'])
        text = clue['clue']
        while pdfmetrics.stringWidth(text, 'Times-Roman', 8) > W - 2 * M - 60:
            text = text[:-2]
        if text != clue['clue']:
            text += '…'
        c.setFont('Times-Roman', 8)
        c.drawString(M + 26, y, text)
        c.setFillColor(GRAPHITE)
        c.setFont('Courier', 7)
        c.drawRightString(W - M, y, '(%s)' % clue['format'])
        c.linkAbsolute('', 'clue%d' % i, (M, y - 3, W - M, y + 9), Border='[0 0 0]')
        y -= 14
    c.showPage()


def grid_page(c, feed):
    """A blank grid, so the deck doubles as the printable puzzle."""
    c.bookmarkPage('grid')
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont('Times-Bold', 15)
    c.drawString(M, H - 56, 'The grid')
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 8)
    c.drawString(M, H - 70, 'Blank, if you would rather solve it the usual way.')

    grid = feed['data']['grid']
    n = len(grid)
    size = (W - 2 * M) / n
    top = H - 96
    for r, row in enumerate(grid):
        for col, sq in enumerate(row):
            x = M + col * size
            y = top - (r + 1) * size
            c.setStrokeColor(INK)
            c.setLineWidth(0.4)
            c.setFillColor(INK if sq['Blank'] else WHITE)
            c.rect(x, y, size, size, stroke=1, fill=1)
            if sq['Number']:
                c.setFillColor(INK)
                c.setFont('Helvetica', 4)
                c.drawString(x + 1, y + size - 5, str(sq['Number']))
    button(c, 'Back to all clues', M, top - n * size - 40, W - 2 * M, 24, 'index')
    c.showPage()


def main():
    solved_path, feed_path, out_path = sys.argv[1:4]
    solved = json.load(open(solved_path))
    if 'meta' in solved[0]:
        solved = solved[1:]
    feed = json.load(open(feed_path))

    c = pdfcanvas.Canvas(out_path, pagesize=(W, H))
    c.setTitle('Times Cryptic No 29604 — clue by clue')
    c.setAuthor('Cryptic crossword helper')
    c.setSubject('Interactive hint deck, 25 July 2026')

    total = len(solved)
    cover(c, total)
    index_page(c, solved)
    for i, clue in enumerate(solved):
        clue_page(c, clue, i, total)
        for n in range(len(RUNGS)):
            hint_page(c, clue, i, total, n)
        answer_page(c, clue, i, total)
    grid_page(c, feed)
    c.save()
    print('wrote %s (%d clues, %d pages)' % (out_path, total, 3 + total * (len(RUNGS) + 2)))


if __name__ == '__main__':
    main()
