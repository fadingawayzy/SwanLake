#!/usr/bin/env python3
"""
Coverage analyzer — shows which КЭС codes in scraped data are missing
from modification_framework.json and from batch PLAN.

Usage: python coverage.py
"""

import json
from collections import Counter
from pathlib import Path

SUBJECTS = ["math_profile", "physics", "russian", "informatics"]


# === START_TOP_PREFIX_COVERAGE ===
def top_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k
# === END_TOP_PREFIX_COVERAGE ===


# === START_ANALYZE_COVERAGE ===
def main():
    framework = json.loads(Path("modification_framework.json").read_text(encoding="utf-8"))

    try:
        from batch_generate import PLAN
    except Exception:
        PLAN = []
    plan_kes = {(s, k) for s, k, *_ in PLAN}

    for subj in SUBJECTS:
        tasks = json.loads(Path(f"data/{subj}.json").read_text(encoding="utf-8"))
        data_codes = Counter(top_prefix(t.get("kes", "")) for t in tasks)
        data_codes.pop("", None)

        fw_codes = set(framework["subjects"].get(subj, {}).get("kes_modifications", {}).keys())

        covered_data = {c for c in data_codes if any(c.startswith(f) or f.startswith(c) for f in fw_codes)}
        missing_fw = set(data_codes) - covered_data
        missing_plan = {c for c in data_codes if (subj, c) not in plan_kes}

        print(f"\n=== {subj.upper()} ===")
        print(f"  Total tasks in data:     {sum(data_codes.values())}")
        print(f"  Unique КЭС codes:        {len(data_codes)}")
        print(f"  In framework:            {len(fw_codes)}")
        print(f"  In batch PLAN:           {sum(1 for s,_ in plan_kes if s==subj)}")
        print(f"  Missing from framework:  {len(missing_fw)}  → {sorted(missing_fw)}")
        print(f"  Missing from PLAN:       {len(missing_plan)}  → {sorted(missing_plan)}")
# === END_ANALYZE_COVERAGE ===


if __name__ == "__main__":
    main()
