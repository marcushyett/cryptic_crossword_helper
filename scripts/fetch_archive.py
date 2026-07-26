#!/usr/bin/env python3
"""Walk The Times cryptic feed backwards and cache every puzzle it still serves.

Usage: fetch_archive.py <out_dir> [--weeks N] [--anchor YYYYMMDD:ID]

The feed URL is /puzzles/sp/crosswordcryptic/<date>/<id>/data.json, where the id
is an internal CMS id, not the puzzle number. Ids are handed out in weekly
blocks that step back by roughly 545 an issue week, with the six days of a week
landing within a few ids of each other — so each week is found by scanning a
window around an estimate, then pinning the other five days next to it.

Puzzles past their solution date carry settings.solution: the finished grid read
row-major with a space per black square. That gives clue/answer pairs for the
whole archive without solving anything.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import sys
import urllib.request

BASE = 'https://feeds.thetimes.com/puzzles/sp/crosswordcryptic/%s/%d/data.json'
ANCHOR = ('20260725', 94104)
WEEK_STEP = 545          # observed id drop from one issue week to the next
POOL = 32


def url(date, cid):
    return BASE % (date, cid)


def head(date, cid, timeout=15):
    req = urllib.request.Request(url(date, cid), method='HEAD')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def get(date, cid, timeout=30):
    try:
        with urllib.request.urlopen(url(date, cid), timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def find_id(date, lo, hi):
    """Scan an id window for the one that serves this date."""
    hits = []
    with cf.ThreadPoolExecutor(POOL) as ex:
        futures = {ex.submit(head, date, cid): cid for cid in range(lo, hi + 1)}
        for fut in cf.as_completed(futures):
            if fut.result():
                hits.append(futures[fut])
    return min(hits) if hits else None


def week_dates(monday):
    """Mon-Sat: the Times cryptic does not publish on Sunday."""
    return [(monday + dt.timedelta(days=n)).strftime('%Y%m%d') for n in range(6)]


def discover(weeks, anchor):
    """Yield one week of (date, id) pairs at a time, walking backwards.

    A generator rather than a list so callers can cache each week as it is
    found: a long walk that gets interrupted still leaves usable puzzles on
    disk.
    """
    anchor_date = dt.datetime.strptime(anchor[0], '%Y%m%d').date()
    monday = anchor_date - dt.timedelta(days=anchor_date.weekday())
    estimate = anchor[1]
    found = []
    step = WEEK_STEP
    last_id = None
    for w in range(weeks):
        dates = week_dates(monday)
        # Pin the week by finding any one of its days. The gap between weekly
        # blocks drifts, so widen the window before giving up on the archive.
        anchor_id = None
        for radius in (150, 450, 1200):
            for probe in dates:
                anchor_id = find_id(probe, estimate - radius, estimate + radius)
                if anchor_id:
                    break
            if anchor_id:
                break
        if not anchor_id:
            print('week of %s: not found — archive ends here' % dates[0], file=sys.stderr)
            break
        # the rest of the week sits within a handful of ids
        week = {}
        with cf.ThreadPoolExecutor(POOL) as ex:
            jobs = {}
            for d in dates:
                for cid in range(anchor_id - 10, anchor_id + 11):
                    jobs[ex.submit(head, d, cid)] = (d, cid)
            for fut in cf.as_completed(jobs):
                d, cid = jobs[fut]
                if fut.result() and d not in week:
                    week[d] = cid
        yield [(d, week[d]) for d in sorted(week)]
        print('week of %s: %d puzzles (ids %d-%d)'
              % (dates[0], len(week), min(week.values()), max(week.values())),
              file=sys.stderr)
        # learn the drift from the last hop instead of trusting the constant
        if last_id is not None:
            step = int(0.5 * step + 0.5 * (last_id - anchor_id))
        last_id = anchor_id
        estimate = anchor_id - step
        monday -= dt.timedelta(days=7)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_dir')
    ap.add_argument('--weeks', type=int, default=12)
    ap.add_argument('--anchor', default='%s:%d' % ANCHOR)
    args = ap.parse_args()

    date, cid = args.anchor.split(':')
    os.makedirs(os.path.join(args.out_dir, 'raw'), exist_ok=True)
    index = []
    for pairs in discover(args.weeks, (date, int(cid))):
        with cf.ThreadPoolExecutor(12) as ex:
            jobs = {ex.submit(get, d, c): (d, c) for d, c in pairs}
            for fut in cf.as_completed(jobs):
                d, c = jobs[fut]
                data = fut.result()
                if not data:
                    continue
                copy = data['data']['copy']
                path = os.path.join(args.out_dir, 'raw', '%s_%d.json' % (d, c))
                with open(path, 'w') as f:
                    json.dump(data, f)
                index.append({
                    'date': d, 'id': c, 'title': copy['title'],
                    'has_solution': 'solution' in copy.get('settings', {}),
                    'file': os.path.basename(path),
                })
        index.sort(key=lambda r: r['date'])
        with open(os.path.join(args.out_dir, 'index.json'), 'w') as f:
            json.dump(index, f, indent=1)
    solved = sum(1 for r in index if r['has_solution'])
    print('cached %d puzzles (%d with published solutions) -> %s'
          % (len(index), solved, args.out_dir))


if __name__ == '__main__':
    main()
