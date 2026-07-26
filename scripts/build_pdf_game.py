#!/usr/bin/env python3
"""Build a PDF that plays like an app on an iPhone, with no JavaScript.

Usage: build_pdf_game.py <solved_clues.json> <crossword.json> <out.pdf>

Apple's PDFKit — the engine behind Quick Look, Preview and Books — ignores PDF
JavaScript entirely, and ignores SetOCGState layer toggling too. What it does
honour is link annotations and form filling. So the interaction here is built
out of the one primitive that survives: the page IS the state.

Each clue gets an on-screen keyboard. Tapping a letter jumps to the page
representing "this clue, this prefix" — so a wrong letter lands on a page that
says so, and a right one advances, letter by letter, to a page that congratulates
you. That is real answer verification, driven purely by GoTo links.

Only prefixes along the correct path need to exist, so the page count is linear
in the number of letters (216 letters -> 432 typing pages), not exponential.
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

W, H = 360, 640
M = 22
INK = HexColor('#14161A')
PAPER = HexColor('#FAFAF6')
PAPER2 = HexColor('#F0F0EA')
KEY = HexColor('#FFFFFF')
GRAPHITE = HexColor('#62666E')
RULE = HexColor('#D9D9D1')
MARK = HexColor('#E9B824')
MARK_SOFT = HexColor('#F7E7AE')
OK = HexColor('#2E7D4F')
OK_SOFT = HexColor('#DCEDE2')
MISS = HexColor('#B4442E')
MISS_SOFT = HexColor('#F6DED8')
WHITE = Color(1, 1, 1)

ROWS = ['QWERTYUIOP', 'ASDFGHJKL', 'ZXCVBNM']

RUNGS = [
    ('definition_hint', 'Where the definition is'),
    ('indicators', 'What the setter is doing'),
    ('fodder', 'What the wordplay works on'),
    ('opening', 'The opening letters'),
    ('explanation', 'The full parsing'),
]


def redact_plain(text, answer, marker='[THE ANSWER]'):
    pattern = r'[\s,.\-’\']*'.join(re.escape(ch) for ch in bare(answer))
    return re.sub(pattern, marker, text, flags=re.I)


def draw_para(c, text, x, y, width, size, leading, colour=INK, font='Times-Roman'):
    p = Paragraph(text, ParagraphStyle('s', fontName=font, fontSize=size,
                                       leading=leading, textColor=colour))
    _, h = p.wrapOn(c, width, H)
    p.drawOn(c, x, y - h)
    return y - h


PAGE_OF = {}


def mark(c, name):
    """Bookmark a page and remember which page number it landed on.

    The map is written alongside the PDF so the link graph can be verified by
    simulating play, rather than trusted by eye.
    """
    PAGE_OF[name] = c.getPageNumber()
    c.bookmarkPage(name)


def link(c, dest, x, y, w, h):
    c.linkAbsolute('', dest, (x, y, x + w, y + h), Border='[0 0 0]')


def button(c, label, x, y, w, h, dest, *, fill=PAPER2, stroke=RULE,
           text_colour=INK, size=9.5, step=None, centred=False):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 2.5, stroke=1, fill=1)
    if centred:
        c.setFillColor(text_colour)
        c.setFont('Helvetica-Bold', size)
        c.drawCentredString(x + w / 2, y + h / 2 - 3.2, label)
    else:
        tx = x + 10
        if step is not None:
            c.setFillColor(MARK_SOFT if fill is PAPER2 else MARK)
            c.roundRect(x + 7, y + h / 2 - 6.5, 13, 13, 1.5, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont('Courier-Bold', 8)
            c.drawCentredString(x + 13.5, y + h / 2 - 3, str(step))
            tx = x + 26
        c.setFillColor(text_colour)
        c.setFont('Helvetica-Bold', size)
        c.drawString(tx, y + h / 2 - 3.2, label)
        c.setFillColor(GRAPHITE if text_colour is INK else text_colour)
        c.setFont('Helvetica', 9)
        c.drawRightString(x + w - 9, y + h / 2 - 3.2, '›')
    link(c, dest, x, y, w, h)


def slots(fmt):
    """Enumeration '5-2-5' -> the sequence of letter cells and separators."""
    out = []
    for part in re.split(r'([,-])', fmt):
        if part == ',':
            out.append('space')
        elif part == '-':
            out.append('dash')
        elif part.strip():
            out.extend(['letter'] * int(part))
    return out


def masthead(c, clue, i, total, label, tone=INK):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica-Bold', 7)
    c.drawString(M, H - 30, 'TIMES CRYPTIC No 29604')
    c.setFont('Courier', 7)
    c.drawRightString(W - M, H - 30, '%d / %d' % (i + 1, total))
    c.setStrokeColor(RULE)
    c.setLineWidth(0.8)
    c.line(M, H - 38, W - M, H - 38)

    y = H - 62
    chip = '%d %s' % (clue['number'], clue['direction'].upper())
    w = pdfmetrics.stringWidth(chip, 'Courier-Bold', 8) + 14
    c.setFillColor(INK)
    c.roundRect(M, y, w, 16, 2, stroke=0, fill=1)
    c.setFillColor(PAPER)
    c.setFont('Courier-Bold', 8)
    c.drawString(M + 7, y + 5, chip)
    c.setFillColor(tone)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(M + w + 8, y + 5, label.upper())
    return y


def footer(c, i, total, extra_dest=None):
    c.setStrokeColor(RULE)
    c.setLineWidth(0.8)
    c.line(M, 40, W - M, 40)
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(GRAPHITE)
    prev_dest = 'clue%d' % (i - 1) if i > 0 else 'index'
    next_dest = 'clue%d' % (i + 1) if i < total - 1 else 'index'
    c.drawString(M, 25, '‹ Prev clue' if i > 0 else '‹ All clues')
    link(c, prev_dest, M, 18, 66, 16)
    c.drawCentredString(W / 2, 25, extra_dest[0] if extra_dest else 'All clues')
    link(c, extra_dest[1] if extra_dest else 'index', W / 2 - 34, 18, 68, 16)
    c.drawRightString(W - M, 25, 'Next clue ›' if i < total - 1 else 'All clues ›')
    link(c, next_dest, W - M - 66, 18, 66, 16)


def cells_row(c, clue, typed, y, *, tone=INK):
    """Draw the answer pattern with the letters entered so far."""
    parts = slots(clue['format'])
    letters = len([p for p in parts if p == 'letter'])
    gap = 3
    seps = sum(7 if p == 'dash' else 4 for p in parts if p != 'letter')
    cw = min(24, (W - 2 * M - seps - (len(parts) - 1) * gap) / letters)
    ch = cw * 1.24
    total_w = letters * cw + seps + (len(parts) - 1) * gap
    x = (W - total_w) / 2
    n = 0
    for part in parts:
        if part == 'letter':
            filled = n < len(typed)
            c.setStrokeColor(tone if filled else RULE)
            c.setFillColor(OK_SOFT if filled and tone is OK else WHITE)
            c.setLineWidth(1.2)
            c.rect(x, y, cw, ch, stroke=1, fill=1)
            if filled:
                c.setFillColor(tone)
                c.setFont('Courier-Bold', cw * 0.62)
                c.drawCentredString(x + cw / 2, y + ch / 2 - cw * 0.22, typed[n])
            elif n == len(typed):
                c.setFillColor(MARK)
                c.rect(x + 2, y + 2, cw - 4, 2.5, stroke=0, fill=1)
            x += cw + gap
            n += 1
        else:
            if part == 'dash':
                c.setFillColor(GRAPHITE)
                c.setFont('Courier-Bold', 9)
                c.drawCentredString(x + 3.5, y + ch / 2 - 3, '-')
                x += 7 + gap
            else:
                x += 4 + gap
    return y - 6


def keyboard(c, clue, i, p, wrong_dest_for, y):
    """A tappable keyboard. Each key links to the page for that guess."""
    answer = bare(clue['answer'])
    nxt = answer[p]
    gap = 3.2
    kw = (W - 2 * M - 9 * gap) / 10
    kh = 32
    for r, row in enumerate(ROWS):
        rw = len(row) * kw + (len(row) - 1) * gap
        x = (W - rw) / 2
        ky = y - r * (kh + 6)
        for ch in row:
            hit = ch == nxt
            c.setFillColor(KEY)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.7)
            c.roundRect(x, ky, kw, kh, 3, stroke=1, fill=1)
            c.setFillColor(INK)
            c.setFont('Helvetica-Bold', 13)
            c.drawCentredString(x + kw / 2, ky + kh / 2 - 4.5, ch)
            dest = ('ok%d' % i if p + 1 == len(answer) else 'k%d_%d' % (i, p + 1)) \
                if hit else wrong_dest_for(ch)
            link(c, dest, x, ky, kw, kh)
            x += kw + gap
    return y - 3 * (kh + 6) + kh


def typing_page(c, clue, i, total, p, wrong=False):
    """The clue with p correct letters entered; `wrong` flags a bad last tap.

    One wrong-page per position, not per wrong key: naming the rejected letter
    would need 25 pages per position instead of one, for very little gain.
    """
    answer = bare(clue['answer'])
    mark(c, 'x%d_%d' % (i, p) if wrong else 'k%d_%d' % (i, p))
    tone = MISS if wrong else INK
    masthead(c, clue, i, total, 'not that letter' if wrong else 'typing', tone)

    y = draw_para(c, clue['clue'], M, H - 78, W - 2 * M, 11.5, 15, GRAPHITE)
    c.setFillColor(GRAPHITE)
    c.setFont('Courier-Bold', 9)
    c.drawString(M, y - 12, '(%s)' % clue['format'])

    cells_row(c, clue, answer[:p], 250)

    # status line
    if wrong:
        c.setFillColor(MISS_SOFT)
        c.roundRect(M, 222, W - 2 * M, 20, 2.5, stroke=0, fill=1)
        c.setFillColor(MISS)
        c.setFont('Helvetica-Bold', 9)
        c.drawCentredString(W / 2, 228,
                            'Not that letter — your first %d are still right' % p if p
                            else 'Not that letter — try another')
    else:
        c.setFillColor(GRAPHITE)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawCentredString(W / 2, 228,
                            'Tap the letters. %d of %d in.' % (p, len(answer)) if p
                            else 'Tap the letters of your answer.')

    keyboard(c, clue, i, p, lambda ch: 'x%d_%d' % (i, p), 194)

    # editing + escape hatches
    bw = (W - 2 * M - 3 * 5) / 4
    by = 74
    back = 'k%d_%d' % (i, p - 1) if p else 'clue%d' % i
    button(c, 'Delete', M, by, bw, 24, back, centred=True, size=8.5)
    button(c, 'Clear', M + bw + 5, by, bw, 24, 'k%d_0' % i, centred=True, size=8.5)
    button(c, 'Hints', M + 2 * (bw + 5), by, bw, 24, 'hint%d_0' % i, centred=True,
           size=8.5, fill=MARK_SOFT, stroke=MARK)
    button(c, 'Give up', M + 3 * (bw + 5), by, bw, 24, 'ans%d' % i, centred=True,
           size=8.5, fill=INK, stroke=INK, text_colour=PAPER)

    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 7)
    c.drawCentredString(W / 2, 58, 'Every letter is checked as you tap it.')

    footer(c, i, total, ('Back to clue', 'clue%d' % i))
    c.showPage()


def solved_page(c, clue, i, total):
    mark(c, 'ok%d' % i)
    masthead(c, clue, i, total, 'solved', OK)
    y = draw_para(c, clue['clue'], M, H - 78, W - 2 * M, 11.5, 15, GRAPHITE)

    c.setFillColor(OK_SOFT)
    c.setStrokeColor(OK)
    c.setLineWidth(1.2)
    c.roundRect(M, y - 62, W - 2 * M, 46, 3, stroke=1, fill=1)
    c.setFillColor(OK)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(W / 2, y - 30, 'CORRECT')
    c.setFillColor(INK)
    answer = clue['answer'].upper()
    size = 17
    while pdfmetrics.stringWidth(answer, 'Courier-Bold', size) > W - 2 * M - 24 and size > 8:
        size -= 0.5
    c.setFont('Courier-Bold', size)
    c.drawCentredString(W / 2, y - 52, answer)

    y = y - 82
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(M, y, 'HOW IT WORKS')
    y = draw_para(c, clue['explanation'], M, y - 8, W - 2 * M, 10.5, 15)

    by = max(80, y - 40)
    nxt = 'clue%d' % (i + 1) if i < total - 1 else 'index'
    button(c, 'Next clue' if i < total - 1 else 'Back to all clues', M, by,
           W - 2 * M, 26, nxt, fill=INK, stroke=INK, text_colour=PAPER)
    footer(c, i, total)
    c.showPage()


def clue_page(c, clue, i, total):
    mark(c, 'clue%d' % i)
    masthead(c, clue, i, total, 'the clue')

    y = draw_para(c, clue['clue'], M, H - 84, W - 2 * M, 15, 19.5)
    c.setFillColor(GRAPHITE)
    c.setFont('Courier-Bold', 10)
    c.drawString(M, y - 16, '(%s)' % clue['format'])

    y = cells_row(c, clue, '', y - 58)

    button(c, 'Tap in your answer', M, y - 40, W - 2 * M, 30, 'k%d_0' % i,
           fill=INK, stroke=INK, text_colour=PAPER, size=10.5, centred=True)
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 7)
    c.drawCentredString(W / 2, y - 52, 'An on-screen keyboard checks every letter as you tap it.')

    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(M, y - 76, 'STUCK? TAKE THE LOWEST RUNG THAT UNSTICKS YOU')

    by = y - 104
    for n, (_, title) in enumerate(RUNGS):
        button(c, title, M, by, W - 2 * M, 23, 'hint%d_%d' % (i, n), step=n + 1)
        by -= 26
    button(c, 'Give up — show the answer', M, by - 4, W - 2 * M, 24,
           'ans%d' % i, fill=PAPER2, stroke=RULE)
    footer(c, i, total)
    c.showPage()


def hint_page(c, clue, i, total, n):
    key, title = RUNGS[n]
    mark(c, 'hint%d_%d' % (i, n))
    masthead(c, clue, i, total, 'hint %d of %d' % (n + 1, len(RUNGS)))

    y = draw_para(c, clue['clue'], M, H - 78, W - 2 * M, 11.5, 15, GRAPHITE)
    c.setFillColor(GRAPHITE)
    c.setFont('Courier-Bold', 9)
    c.drawString(M, y - 12, '(%s)' % clue['format'])

    y -= 32
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

    by = max(96, bottom - 30)
    if n + 1 < len(RUNGS):
        button(c, 'Next hint: %s' % RUNGS[n + 1][1], M, by, W - 2 * M, 23,
               'hint%d_%d' % (i, n + 1), step=n + 2)
        by -= 27
    half = (W - 2 * M) / 2 - 4
    button(c, 'Back to typing', M, by, half, 22, 'k%d_0' % i,
           fill=INK, stroke=INK, text_colour=PAPER, centred=True, size=8.5)
    button(c, 'Show the answer', M + half + 8, by, half, 22, 'ans%d' % i,
           centred=True, size=8.5)
    footer(c, i, total, ('Back to clue', 'clue%d' % i))
    c.showPage()


def answer_page(c, clue, i, total):
    mark(c, 'ans%d' % i)
    masthead(c, clue, i, total, 'the answer')
    y = draw_para(c, clue['clue'], M, H - 78, W - 2 * M, 11.5, 15, GRAPHITE)

    c.setFillColor(PAPER2)
    c.setStrokeColor(INK)
    c.setLineWidth(1.2)
    c.roundRect(M, y - 54, W - 2 * M, 38, 3, stroke=1, fill=1)
    c.setFillColor(INK)
    answer = clue['answer'].upper()
    size = 17
    while pdfmetrics.stringWidth(answer, 'Courier-Bold', size) > W - 2 * M - 24 and size > 8:
        size -= 0.5
    c.setFont('Courier-Bold', size)
    c.drawCentredString(W / 2, y - 42, answer)

    y -= 76
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(M, y, 'HOW IT WORKS')
    y = draw_para(c, clue['explanation'], M, y - 8, W - 2 * M, 10.5, 15)
    y = draw_para(c, '<b>Definition:</b> ' + clue['definition_hint'], M, y - 10,
                  W - 2 * M, 9.5, 13.5, GRAPHITE)

    by = max(80, y - 36)
    nxt = 'clue%d' % (i + 1) if i < total - 1 else 'index'
    button(c, 'Next clue' if i < total - 1 else 'Back to all clues', M, by,
           W - 2 * M, 26, nxt, fill=INK, stroke=INK, text_colour=PAPER)
    footer(c, i, total)
    c.showPage()


def cover(c, total, letters):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont('Times-Bold', 19)
    c.drawString(M, H - 88, 'Times Cryptic')
    c.setFont('Times-Bold', 33)
    c.drawString(M, H - 122, 'No 29604')
    c.setFillColor(GRAPHITE)
    c.setFont('Courier', 8.5)
    c.drawString(M, H - 140, 'SATURDAY 25 JULY 2026  ·  %d CLUES' % total)
    c.setStrokeColor(RULE)
    c.line(M, H - 154, W - M, H - 154)

    y = draw_para(
        c,
        'Tap in your answer on the keyboard and every letter is checked as you enter '
        'it — a wrong tap says so and keeps the letters you already have right. No app, '
        'no internet, no scripting: the whole game is built out of pages and taps, so it '
        'works in Quick Look, Preview, Books and anything else that opens a PDF.',
        M, H - 172, W - 2 * M, 10.5, 15.5)

    y = draw_para(
        c,
        'Stuck? Five hints per clue, each on its own page, climbing from where the '
        'definition is to the full parsing. The answer is always one more tap away, '
        'and never on a page you can reach by accident.',
        M, y - 12, W - 2 * M, 9.5, 14, GRAPHITE)

    button(c, 'Start with 1 across', M, y - 40, W - 2 * M, 28, 'clue0',
           fill=INK, stroke=INK, text_colour=PAPER, size=10.5, centred=True)
    button(c, 'All 28 clues', M, y - 74, (W - 2 * M) / 2 - 4, 24, 'index', centred=True)
    button(c, 'Blank grid', M + (W - 2 * M) / 2 + 4, y - 74, (W - 2 * M) / 2 - 4, 24,
           'grid', centred=True)

    draw_para(c,
              'Clues © The Times / News UK, from the puzzle feed for 25 July 2026. '
              'Parsings written for practice; the full solution is verified against the '
              'feed’s own published grid hash.',
              M, 84, W - 2 * M, 7.5, 10.5, GRAPHITE, 'Helvetica')
    c.showPage()


def index_page(c, clues):
    mark(c, 'index')
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont('Times-Bold', 15)
    c.drawString(M, H - 52, 'All clues')
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 8)
    c.drawString(M, H - 66, 'Tap any clue to play it.')

    y = H - 88
    last = None
    for i, clue in enumerate(clues):
        if clue['direction'] != last:
            last = clue['direction']
            c.setFillColor(GRAPHITE)
            c.setFont('Helvetica-Bold', 7.5)
            c.drawString(M, y, last.upper())
            y -= 12
        c.setFillColor(INK)
        c.setFont('Courier-Bold', 7.5)
        c.drawString(M, y, '%-4s' % clue['id'])
        text = clue['clue']
        while pdfmetrics.stringWidth(text, 'Times-Roman', 8) > W - 2 * M - 62:
            text = text[:-2]
        if text != clue['clue']:
            text += '…'
        c.setFont('Times-Roman', 8)
        c.drawString(M + 26, y, text)
        c.setFillColor(GRAPHITE)
        c.setFont('Courier', 7)
        c.drawRightString(W - M, y, '(%s)' % clue['format'])
        link(c, 'clue%d' % i, M, y - 3, W - 2 * M, 12)
        y -= 14
    c.showPage()


def progress_page(c, clues):
    """A tick list. Quick Look can fill forms, so the ticks survive a save."""
    mark(c, 'progress')
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont('Times-Bold', 15)
    c.drawString(M, H - 52, 'Progress')
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 8)
    c.drawString(M, H - 66, 'Tick them off as you go — saves with the file if your viewer allows it.')

    x, y = M, H - 92
    for n, clue in enumerate(clues):
        if n == 14:
            x, y = W / 2 + 4, H - 92
        c.acroForm.checkbox(name='done_%s' % clue['id'], x=x, y=y - 3, size=11,
                            borderColor=INK, fillColor=WHITE, textColor=OK,
                            buttonStyle='check', borderWidth=0.8,
                            tooltip='Solved %s' % clue['id'])
        c.setFillColor(INK)
        c.setFont('Courier-Bold', 8)
        c.drawString(x + 18, y, clue['id'])
        c.setFillColor(GRAPHITE)
        c.setFont('Courier', 7)
        c.drawString(x + 44, y, '(%s)' % clue['format'])
        link(c, 'clue%d' % n, x + 18, y - 3, 120, 12)
        y -= 19
    button(c, 'Back to all clues', M, 56, W - 2 * M, 24, 'index', centred=True)
    c.showPage()


def grid_page(c, feed):
    mark(c, 'grid')
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont('Times-Bold', 15)
    c.drawString(M, H - 52, 'The grid')
    c.setFillColor(GRAPHITE)
    c.setFont('Helvetica', 8)
    c.drawString(M, H - 66, 'Blank, if you would rather solve it the usual way.')

    grid = feed['data']['grid']
    n = len(grid)
    size = (W - 2 * M) / n
    top = H - 92
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
    button(c, 'Back to all clues', M, top - n * size - 40, W - 2 * M, 24, 'index',
           centred=True)
    c.showPage()


def main():
    solved_path, feed_path, out_path = sys.argv[1:4]
    solved = json.load(open(solved_path))
    if 'meta' in solved[0]:
        solved = solved[1:]
    feed = json.load(open(feed_path))
    total = len(solved)
    letters = sum(len(bare(c['answer'])) for c in solved)

    c = pdfcanvas.Canvas(out_path, pagesize=(W, H), pageCompression=1)
    c.setTitle('Times Cryptic No 29604 — tap to solve')
    c.setSubject('Interactive hint deck, 25 July 2026')

    cover(c, total, letters)
    index_page(c, solved)
    progress_page(c, solved)

    # Sections are ordered so that a stray swipe lands on an unrelated page
    # rather than on the answer to the clue you are working on.
    for i, clue in enumerate(solved):
        clue_page(c, clue, i, total)
    for n in range(len(RUNGS)):
        for i, clue in enumerate(solved):
            hint_page(c, clue, i, total, n)

    # typing states, striped by depth so neighbours belong to different clues
    depth = max(len(bare(cl['answer'])) for cl in solved)
    for p in range(depth):
        for i, clue in enumerate(solved):
            if p < len(bare(clue['answer'])):
                typing_page(c, clue, i, total, p)
                typing_page(c, clue, i, total, p, wrong=True)

    for i, clue in enumerate(solved):
        solved_page(c, clue, i, total)
    for i, clue in enumerate(solved):
        answer_page(c, clue, i, total)
    grid_page(c, feed)
    c.save()
    json.dump(PAGE_OF, open(out_path + '.map.json', 'w'))
    print('wrote %s — %d clues, %d letters, %d pages'
          % (out_path, total, letters, c.getPageNumber() - 1))


if __name__ == '__main__':
    main()
