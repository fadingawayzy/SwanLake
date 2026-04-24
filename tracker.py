#!/usr/bin/env python3
"""
Performance tracker — SQLite log of attempted tasks with pass/fail + notes.
Drives adaptive PLAN weighting in generate_plan.py --weights tracker.

Usage:
    python tracker.py init                           # create DB
    python tracker.py add <md_path> pass|fail [note] # log attempt
    python tracker.py stats                          # subject × КЭС success rates
    python tracker.py weak                           # KES with <50% success
    python tracker.py list [subject]                 # recent attempts
"""

import argparse
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from db import connect as conn, DB_PATH as DB


def parse_frontmatter(md: Path) -> dict:
    text = md.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
    return fm


def top_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k


def cmd_init(args):
    conn().close()
    print(f"Initialized {DB}")


def cmd_add(args):
    md = Path(args.path)
    if not md.exists():
        sys.exit(f"Not found: {md}")
    fm = parse_frontmatter(md)
    subject = fm.get("subject", "")
    kes = top_prefix(fm.get("kes", ""))
    if not subject or not kes:
        sys.exit(f"Missing subject/kes in frontmatter of {md}")

    c = conn()
    c.execute("""
        INSERT INTO attempts (ts, subject, kes, task_number, source_id, technique, difficulty, md_path, result, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(timespec="seconds"),
        subject, kes, fm.get("task_number"), fm.get("source_id"),
        fm.get("technique"), int(fm.get("difficulty") or 0),
        str(md.resolve()), args.result, args.note or "",
    ))
    c.commit()
    print(f"Logged: {subject}/{kes} → {args.result}")
    c.close()


def cmd_stats(args):
    c = conn()
    rows = c.execute("""
        SELECT subject, kes,
            SUM(CASE WHEN result='pass' THEN 1 ELSE 0 END) as passes,
            SUM(CASE WHEN result='fail' THEN 1 ELSE 0 END) as fails,
            SUM(CASE WHEN result='partial' THEN 1 ELSE 0 END) as partials,
            COUNT(*) as total
        FROM attempts GROUP BY subject, kes ORDER BY subject, kes
    """).fetchall()
    c.close()
    if not rows:
        print("No attempts logged yet.")
        return
    current = None
    for subj, kes, p, f, pa, t in rows:
        if subj != current:
            print(f"\n=== {subj} ===")
            current = subj
        rate = p / t if t else 0
        bar = "█" * int(rate * 10) + "░" * (10 - int(rate * 10))
        print(f"  {kes:<8} [{bar}] {int(rate*100):>3}%  ({p}p/{f}f/{pa}~ of {t})")


def cmd_weak(args):
    c = conn()
    rows = c.execute("""
        SELECT subject, kes,
            SUM(CASE WHEN result='pass' THEN 1.0 ELSE 0 END) / COUNT(*) as rate,
            COUNT(*) as total
        FROM attempts GROUP BY subject, kes
        HAVING rate < 0.5 AND total >= 2
        ORDER BY rate ASC
    """).fetchall()
    c.close()
    if not rows:
        print("No weak areas yet (need ≥2 attempts with <50% pass).")
        return
    print("Weak КЭС (pass rate < 50%, min 2 attempts):")
    for subj, kes, rate, total in rows:
        print(f"  {subj}/{kes}: {int(rate*100)}% over {total} attempts")


def cmd_list(args):
    c = conn()
    q = "SELECT ts, subject, kes, result, task_number, note FROM attempts"
    params = ()
    if args.subject:
        q += " WHERE subject=?"
        params = (args.subject,)
    q += " ORDER BY ts DESC LIMIT 20"
    rows = c.execute(q, params).fetchall()
    c.close()
    for ts, subj, kes, res, tn, note in rows:
        flag = {"pass": "✓", "fail": "✗", "partial": "~"}.get(res, "?")
        print(f"  {flag} {ts[:16]}  {subj}/{kes:<6}  №{tn or '?':<4}  {note[:40]}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    a = sub.add_parser("add")
    a.add_argument("path")
    a.add_argument("result", choices=["pass", "fail", "partial"])
    a.add_argument("note", nargs="?", default="")
    sub.add_parser("stats")
    sub.add_parser("weak")
    l = sub.add_parser("list")
    l.add_argument("subject", nargs="?")
    args = p.parse_args()

    {"init": cmd_init, "add": cmd_add, "stats": cmd_stats,
     "weak": cmd_weak, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    main()
