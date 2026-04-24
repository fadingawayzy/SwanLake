#!/usr/bin/env python3
"""
Auto-generate comprehensive batch PLAN covering every КЭС code present
in scraped data, weighted by task count.

Prints PLAN as Python list — paste into batch_generate.py or pipe to a file.

Usage:
    python generate_plan.py                    # print full plan
    python generate_plan.py --weights tracker  # weight by tracker.db weakness
    python generate_plan.py --per-kes 2        # tasks per КЭС (default 1)
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from db import connect as db_connect, DB_PATH

SUBJECTS = ["math_profile", "physics", "russian", "informatics"]
GLOBAL_FALLBACK = ["add_parameter", "increase_dimensions", "add_constraint", "chain_problems", "change_question"]


def top_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k


def pick_strategy(framework: dict, subject: str, kes: str) -> str:
    subj = framework["subjects"].get(subject, {})
    mods = subj.get("kes_modifications", {})
    for fw_code, data in mods.items():
        if kes.startswith(fw_code) or fw_code.startswith(kes):
            levels = data.get("levels", [])
            if levels:
                return levels[0]["name"]
    idx = abs(hash(f"{subject}:{kes}")) % len(GLOBAL_FALLBACK)
    return GLOBAL_FALLBACK[idx]


def weakness_weights() -> dict:
    if not DB_PATH.exists():
        return {}
    conn = db_connect()
    rows = conn.execute("""
        SELECT subject, kes,
            SUM(CASE WHEN result='fail' THEN 1 ELSE 0 END) as fails,
            COUNT(*) as total
        FROM attempts GROUP BY subject, kes
    """).fetchall()
    conn.close()
    w = {}
    for subj, kes, fails, total in rows:
        if total > 0:
            w[(subj, kes)] = fails / total
    return w


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--weights", choices=["none", "tracker"], default="none")
    p.add_argument("--per-kes", type=int, default=1)
    p.add_argument("--difficulty", type=int, default=3)
    args = p.parse_args()

    framework = json.loads(Path("modification_framework.json").read_text(encoding="utf-8"))
    weak = weakness_weights() if args.weights == "tracker" else {}

    plan = []
    for subj in SUBJECTS:
        tasks = json.loads(Path(f"data/{subj}.json").read_text(encoding="utf-8"))
        codes = Counter(top_prefix(t.get("kes", "")) for t in tasks)
        codes.pop("", None)

        for kes, count in sorted(codes.items()):
            n = args.per_kes
            fail_rate = weak.get((subj, kes), 0.0)
            if fail_rate > 0.5:
                n += 2
            elif fail_rate > 0.25:
                n += 1
            strategy = pick_strategy(framework, subj, kes)
            plan.append((subj, kes, strategy, args.difficulty, n))

    print("PLAN = [")
    current_subj = None
    for subj, kes, strat, diff, n in plan:
        if subj != current_subj:
            print(f"    # {subj}")
            current_subj = subj
        print(f'    ("{subj}", "{kes}", "{strat}", {diff}, {n}),')
    print("]")
    print(f"\n# Total: {sum(e[4] for e in plan)} tasks across {len(plan)} КЭС codes", )


if __name__ == "__main__":
    main()
