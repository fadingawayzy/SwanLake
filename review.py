#!/usr/bin/env python3
"""
Interactive review CLI — pulls due cards from SRS, shows task, prompts for
answer, compares, logs to tracker.

Usage:
    python review.py                     # SRS-due queue
    python review.py --subject physics   # filter
    python review.py --file path.md      # single file
    python review.py --new vault/dir     # only unattempted files
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from srs import load_cards
from tracker import parse_frontmatter, top_prefix
from db import connect
from datetime import datetime


def parse_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    out = {"task": "", "solution": "", "answer": ""}

    m = re.search(r"## Задание\s*\n(.*?)## Решение", text, re.DOTALL)
    if m: out["task"] = m.group(1).strip()
    m = re.search(r"## Решение\s*\n(.*?)\*\*Ответ:\*\*", text, re.DOTALL)
    if m: out["solution"] = m.group(1).strip()
    m = re.search(r"\*\*Ответ:\*\*\s*(.+?)\n", text)
    if m: out["answer"] = m.group(1).strip()
    return out


def normalize(a: str) -> str:
    a = a.lower().strip()
    a = re.sub(r"[\s$\\]", "", a)
    a = a.replace(",", ".")
    return a


def log_attempt(md: Path, result: str, note: str):
    fm = parse_frontmatter(md)
    c = connect()
    c.execute("""INSERT INTO attempts (ts, subject, kes, task_number, source_id,
                 technique, difficulty, md_path, result, note)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (datetime.now().isoformat(timespec="seconds"),
               fm.get("subject", ""), top_prefix(fm.get("kes", "")),
               fm.get("task_number"), fm.get("source_id"),
               fm.get("technique"), int(fm.get("difficulty") or 0),
               str(md.resolve()), result, note))
    c.commit()
    c.close()


def review_one(md: Path):
    parsed = parse_md(md)
    if not parsed["task"]:
        print(f"SKIP {md}: no task section")
        return

    fm = parse_frontmatter(md)
    print("\n" + "=" * 70)
    print(f"{fm.get('subject', '?')} | КЭС: {fm.get('kes', '?')} | №{fm.get('task_number', '?')}")
    print(f"Приём: {fm.get('technique', '?')} | Сложность: {fm.get('difficulty', '?')}/4")
    print("=" * 70)
    print(parsed["task"])
    print("=" * 70)

    try:
        user_ans = input("\nТвой ответ (пусто = пропуск, 's' = показать решение): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

    if user_ans == "":
        return
    if user_ans.lower() == "s":
        print("\n--- РЕШЕНИЕ ---")
        print(parsed["solution"])
        print(f"\nОТВЕТ: {parsed['answer']}")
        user_ans = input("\nТвой ответ (pass/fail/partial): ").strip().lower()
        if user_ans in ("pass", "fail", "partial"):
            note = input("Заметка: ").strip()
            log_attempt(md, user_ans, note)
            print(f"→ logged {user_ans}")
        return

    match = normalize(user_ans) == normalize(parsed["answer"])
    print(f"\nПравильный: {parsed['answer']}")
    if match:
        print("✓ ВЕРНО")
        result = "pass"
        note = ""
    else:
        print("✗ НЕВЕРНО")
        show = input("Показать решение? [Y/n]: ").strip().lower()
        if show != "n":
            print("\n--- РЕШЕНИЕ ---")
            print(parsed["solution"])
        note = input("Заметка (что пошло не так): ").strip()
        result = "fail"

    log_attempt(md, result, note)
    print(f"→ logged {result}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="Single MD file")
    p.add_argument("--subject", help="Filter by subject")
    p.add_argument("--new", help="Review unattempted files in dir")
    p.add_argument("--limit", type=int, default=10)
    args = p.parse_args()

    if args.file:
        review_one(Path(args.file))
        return

    if args.new:
        from srs import load_cards as lc
        seen = {c["md_path"] for c in lc()}
        files = [f for f in Path(args.new).rglob("*.md") if str(f.resolve()) not in seen]
        files = sorted(files)[:args.limit]
        print(f"{len(files)} unattempted files")
        for f in files:
            review_one(f)
        return

    now = datetime.now()
    cards = [c for c in load_cards() if c["due"] <= now]
    if args.subject:
        cards = [c for c in cards if c["subject"] == args.subject]
    cards.sort(key=lambda c: (c["last_result"] != "fail", c["due"]))
    cards = cards[:args.limit]

    if not cards:
        print("Ничего не просрочено. Run `python srs.py schedule`.")
        return

    for c in cards:
        review_one(Path(c["md_path"]))


if __name__ == "__main__":
    main()
