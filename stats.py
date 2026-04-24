#!/usr/bin/env python3
"""
CLI stats — unified view: KES coverage × pass rate × verification match.
Shows what to drill next.

Usage:
    python stats.py                        # all subjects
    python stats.py --subject math_profile # drill one
    python stats.py --weak                 # only KES with issues
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from db import connect, DB_PATH

SUBJECTS = ["math_profile", "physics", "russian", "informatics"]


def top_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k


def bar(rate: float, width: int = 10) -> str:
    filled = int(rate * width)
    return "█" * filled + "░" * (width - filled)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--subject", choices=SUBJECTS)
    p.add_argument("--weak", action="store_true")
    args = p.parse_args()

    if not DB_PATH.exists():
        print("No DB. Run some tasks first.")
        return

    c = connect()

    attempts = {}
    for subj, kes, result in c.execute("SELECT subject, kes, result FROM attempts"):
        attempts.setdefault((subj, kes), Counter())[result] += 1

    verifications = {}
    for subj, kes, match in c.execute("""
        SELECT g.subject, g.kes, v.match
        FROM generations g LEFT JOIN verifications v ON g.md_path = v.md_path
    """):
        key = (subj, kes)
        verifications.setdefault(key, {"total": 0, "matched": 0, "unverified": 0})
        verifications[key]["total"] += 1
        if match is None:
            verifications[key]["unverified"] += 1
        elif match:
            verifications[key]["matched"] += 1

    generations_by_kes = Counter()
    for subj, kes in c.execute("SELECT subject, kes FROM generations"):
        generations_by_kes[(subj, kes)] += 1

    c.close()

    subjects = [args.subject] if args.subject else SUBJECTS

    for subj in subjects:
        tasks = json.loads(Path(f"data/{subj}.json").read_text(encoding="utf-8"))
        data_codes = Counter(top_prefix(t.get("kes", "")) for t in tasks)
        data_codes.pop("", None)

        print(f"\n{'='*76}")
        print(f"{subj.upper()}")
        print(f"{'='*76}")
        print(f"{'КЭС':<8} {'bank':>5} {'gen':>4} {'ver%':>5} {'pass%':>6} {'progress':<12} {'flags'}")
        print("-" * 76)

        for kes in sorted(data_codes.keys()):
            bank_n = data_codes[kes]
            gen_n = generations_by_kes.get((subj, kes), 0)
            ver = verifications.get((subj, kes), {"total": 0, "matched": 0, "unverified": 0})
            att = attempts.get((subj, kes), Counter())

            ver_rate = (ver["matched"] / (ver["total"] - ver["unverified"])) if (ver["total"] - ver["unverified"]) else 0
            ver_str = f"{int(ver_rate*100)}%" if (ver["total"] - ver["unverified"]) else "-"

            total_att = sum(att.values())
            pass_rate = (att["pass"] + 0.5 * att.get("partial", 0)) / total_att if total_att else 0
            pass_str = f"{int(pass_rate*100)}%" if total_att else "-"

            progress = bar(pass_rate) if total_att else "·" * 10

            flags = []
            if gen_n == 0:
                flags.append("NOGEN")
            if total_att == 0 and gen_n > 0:
                flags.append("UNSOLVED")
            if ver["total"] - ver["unverified"] > 0 and ver_rate < 0.7:
                flags.append("HALLUCINATE?")
            if total_att >= 2 and pass_rate < 0.5:
                flags.append("WEAK")

            if args.weak and not flags:
                continue

            print(f"{kes:<8} {bank_n:>5} {gen_n:>4} {ver_str:>5} {pass_str:>6} [{progress}] {' '.join(flags)}")

    print()


if __name__ == "__main__":
    main()
