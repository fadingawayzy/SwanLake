#!/usr/bin/env python3
"""
Spaced repetition scheduler — SM-2 variant for ЕГЭ task cards.

Reads tracker.db attempts, computes next review date per card. Cards with
result='fail' come back soon; 'pass' spaces out exponentially.

Usage:
    python srs.py due                    # list cards due today
    python srs.py queue --limit 20       # top N due cards
    python srs.py schedule               # full schedule overview
"""

import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from db import connect, DB_PATH as DB


# === START_COMPUTE_SM2_INTERVAL ===
def sm2_interval(history: list[str]) -> tuple[int, float]:
    """Return (days_until_next, ease_factor). history = oldest→newest results."""
    if not history:
        return 0, 2.5
    ef = 2.5
    interval = 0
    streak = 0
    for r in history:
        q = {"pass": 5, "partial": 3, "fail": 1}.get(r, 3)
        ef = max(1.3, ef + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        if q < 3:
            streak = 0
            interval = 1
        else:
            streak += 1
            if streak == 1:
                interval = 1
            elif streak == 2:
                interval = 6
            else:
                interval = int(round(interval * ef))
    return interval, ef
# === END_COMPUTE_SM2_INTERVAL ===


# === START_LOAD_SRS_CARDS ===
def load_cards() -> list[dict]:
    if not DB.exists():
        return []
    c = connect()
    rows = c.execute("""
        SELECT md_path, subject, kes, ts, result
        FROM attempts
        WHERE md_path IS NOT NULL
        ORDER BY md_path, ts ASC
    """).fetchall()
    c.close()

    by_path: dict[str, list] = {}
    for path, subj, kes, ts, res in rows:
        by_path.setdefault(path, []).append((subj, kes, ts, res))

    cards = []
    for path, history in by_path.items():
        subj = history[-1][0]
        kes = history[-1][1]
        last_ts = history[-1][2]
        results = [h[3] for h in history]
        interval, ef = sm2_interval(results)
        last = datetime.fromisoformat(last_ts)
        due = last + timedelta(days=interval)
        cards.append({
            "md_path": path,
            "subject": subj,
            "kes": kes,
            "last_seen": last,
            "due": due,
            "interval": interval,
            "ef": ef,
            "attempts": len(history),
            "last_result": results[-1],
        })
    return cards
# === END_LOAD_SRS_CARDS ===


# === START_LIST_DUE_CARDS ===
def cmd_due(args):
    now = datetime.now()
    _cards = load_cards()
    cards = [c for c in _cards if c["due"] <= now]
    cards.sort(key=lambda c: c["due"])
    if not cards:
        print("Nothing due.")
        return
    print(f"{len(cards)} cards due:")
    for c in cards:
        overdue = (now - c["due"]).days
        tag = f"{overdue}d overdue" if overdue > 0 else "today"
        flag = {"pass": "✓", "fail": "✗", "partial": "~"}.get(c["last_result"], "?")
        print(f"  [{tag:>11}] {flag} {c['subject']}/{c['kes']:<6} iv={c['interval']:>3}d  {Path(c['md_path']).name}")
# === END_LIST_DUE_CARDS ===


# === START_LIST_QUEUE_CARDS ===
def cmd_queue(args):
    now = datetime.now()
    cards = [c for c in load_cards() if c["due"] <= now]
    cards.sort(key=lambda c: (c["last_result"] != "fail", c["due"]))
    for c in cards[:args.limit]:
        print(c["md_path"])
# === END_LIST_QUEUE_CARDS ===


# === START_SUMMARIZE_SRS_SCHEDULE ===
def cmd_schedule(args):
    cards = load_cards()
    buckets = {"overdue": 0, "today": 0, "week": 0, "month": 0, "later": 0}
    now = datetime.now()
    for c in cards:
        d = (c["due"] - now).days
        if d < 0: buckets["overdue"] += 1
        elif d == 0: buckets["today"] += 1
        elif d <= 7: buckets["week"] += 1
        elif d <= 30: buckets["month"] += 1
        else: buckets["later"] += 1
    print(f"Total cards: {len(cards)}")
    for k, v in buckets.items():
        print(f"  {k:<10} {v}")
# === END_SUMMARIZE_SRS_SCHEDULE ===


# === START_RUN_SRS_CLI ===
def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("due")
    q = sub.add_parser("queue")
    q.add_argument("--limit", type=int, default=20)
    sub.add_parser("schedule")
    args = p.parse_args()
    {"due": cmd_due, "queue": cmd_queue, "schedule": cmd_schedule}[args.cmd](args)
# === END_RUN_SRS_CLI ===


if __name__ == "__main__":
    main()
