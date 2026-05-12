#!/usr/bin/env python3
"""
Batch generator — run daily to populate Obsidian vault with modified ЕГЭ tasks.

Config: edit PLAN below. Run: python batch_generate.py

Each subject × КЭС × strategy combination produces N Obsidian Markdown files
in vault/<subject>/ ready to open in Obsidian.

Requires OPENROUTER_API_KEY in env or .env file.
Model: set OPENROUTER_MODEL (default: deepseek/deepseek-r1).
"""

import argparse
import importlib.util
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path


from dotenv import load_dotenv

from llm import complete, complete_tracked
from generator import (
    build_prompt, parse_response, to_obsidian,
    get_subject_key, get_client, get_model,
    already_generated, log_generation,
)

load_dotenv()


# === START_LOAD_PLAN_FROM_FILE ===
def load_plan_from_file(path: Path) -> list[tuple]:
    p = path.resolve()
    if not p.is_file() or p.suffix != ".py":
        raise SystemExit(f"ERROR: --plan must be an existing .py file, got {path}")
    spec = importlib.util.spec_from_file_location("plan_mod", p)
    if spec is None or spec.loader is None:
        raise SystemExit(f"ERROR: cannot load plan from {p}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "PLAN"):
        raise SystemExit(f"ERROR: {p} does not define PLAN")
    return mod.PLAN
# === END_LOAD_PLAN_FROM_FILE ===

# ── Daily practice plan ──────────────────────────────────────────────────────
# Each entry: (subject, kes_prefix, strategy, difficulty, count)
# Adjust based on your weak spots.
# === START_DEFINE_DEFAULT_PLAN ===
PLAN = [
    # Математика — текущие пробелы
    ("math_profile", "2.5", "замена",           3, 2),  # логарифмы с заменой
    ("math_profile", "2.5", "ОДЗ",              3, 2),  # ОДЗ вложенные
    ("math_profile", "4.1", "уравнение_касательной", 3, 1),
    ("math_profile", "7.3", "сечение",          3, 2),  # стереометрия
    ("math_profile", "6.2", "байес",            2, 1),  # вероятность

    # Физика
    ("physics",      "1",   "система_тел",      2, 2),
    ("physics",      "3",   "схема_резисторов", 3, 1),

    # Информатика
    ("informatics",  "2",   "рекурсия",         3, 2),
    ("informatics",  "3",   "найти_функцию",    2, 1),

    # Русский (текстовые задания — реже)
    ("russian",      "3.8.7", "скрытая_позиция", 2, 1),
]
# === END_DEFINE_DEFAULT_PLAN ===

VAULT_ROOT = Path("vault")


# === START_LOAD_BATCH_TASKS ===
def load_tasks(subject: str) -> list[dict]:
    f = Path("data") / f"{subject}.json"
    return json.loads(f.read_text(encoding="utf-8"))
# === END_LOAD_BATCH_TASKS ===


# === START_LOAD_BATCH_FRAMEWORK ===
def load_framework() -> dict:
    return json.loads(Path("modification_framework.json").read_text(encoding="utf-8"))
# === END_LOAD_BATCH_FRAMEWORK ===


# === START_LOOKUP_STRATEGY_DESC ===
def get_strategy_desc(framework: dict, subject: str, strategy: str) -> str:
    subj = framework["subjects"].get(subject, {})
    for kes_data in subj.get("kes_modifications", {}).values():
        for lvl in kes_data["levels"]:
            if lvl["name"] == strategy:
                return lvl["desc"]
    gmod = framework["global_modifications"].get(strategy, {})
    return gmod.get("desc", strategy)
# === END_LOOKUP_STRATEGY_DESC ===


# === START_RUN_BATCH_GENERATE ===
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=str, help="Path to external PLAN file (Python module with PLAN=...)")
    p.add_argument("--max", type=int, default=None, help="Cap total tasks generated")
    p.add_argument("--workers", type=int, default=5, help="Parallel LLM workers (default: 5)")
    args = p.parse_args()

    plan = load_plan_from_file(Path(args.plan)) if args.plan else PLAN
    if args.max:
        plan = plan[:args.max]

    framework = load_framework()
    client = get_client()
    model = get_model()
    today = datetime.now().strftime("%Y-%m-%d")

    jobs = []
    skipped = 0
    for subject, kes, strategy, difficulty, count in plan:
        tasks = load_tasks(subject)
        pool = [t for t in tasks
                if t.get("kes", "").startswith(kes) and t.get("latex_text")]
        if not pool:
            pool = [t for t in tasks if t.get("kes", "").startswith(kes)]
        if not pool:
            print(f"  SKIP {subject} КЭС={kes}: no tasks")
            skipped += count
            continue

        available = [t for t in pool if not already_generated(subject, t["id"])]
        if not available:
            print(f"  SKIP {subject} КЭС={kes}: all sources already generated")
            skipped += count
            continue

        out_dir = VAULT_ROOT / subject / kes.replace(".", "-")
        out_dir.mkdir(parents=True, exist_ok=True)
        strategy_desc = get_strategy_desc(framework, subject, strategy)
        subject_key = get_subject_key(subject)

        take = min(count, len(available))
        for i in range(take):
            jobs.append({
                "subject": subject, "kes": kes, "strategy": strategy,
                "difficulty": difficulty, "source": available[i],
                "out_dir": out_dir, "strategy_desc": strategy_desc,
                "subject_key": subject_key, "index": i,
            })
        skipped += count - take

    total = len(jobs)
    if not total:
        print("No tasks to generate. Skipped: {skipped}")
        return

    print(f"Batch generate: {total} tasks for {today} | model: {model} | workers: {args.workers}")
    t_start = time.time()

    def generate_one(job: dict) -> dict:
        prompt = build_prompt(job["source"], job["strategy"],
                              job["strategy_desc"], job["difficulty"], framework)
        result = complete_tracked(client, model, prompt, max_tokens=16384)
        parsed = parse_response(result["text"])
        return {**job, "result": result, "parsed": parsed}

    done = 0
    errors = 0
    total_cost = 0.0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(generate_one, j): j for j in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                data = future.result()
            except Exception as e:
                print(f"  [{done+errors+1}/{total}] ERR {job['subject']} КЭС={job['kes']}: {e}")
                errors += 1
                continue

            parsed = data["parsed"]
            result = data["result"]
            cost = result.get("cost_usd") or 0.0
            total_cost += cost

            ts = datetime.now().strftime("%H%M%S")
            slug = f"{today}_{job['kes'].replace('.', '-')}_{job['strategy']}_{ts}_{job['index']}"
            md_path = job["out_dir"] / f"{slug}.md"
            md_content = to_obsidian(job["source"], job["subject"], job["strategy"],
                                     parsed, framework)
            md_path.write_text(md_content, encoding="utf-8")
            log_generation(md_path, job["subject"], job["kes"], job["source"]["id"],
                           job["strategy"],
                           parsed.get("difficulty", job["difficulty"]), model,
                           cost, result.get("latency_ms"))

            done += 1
            print(f"  [{done+errors}/{total}] {job['subject']} КЭС={job['kes']} "
                  f"→ {md_path.name} | answer: {parsed['answer'][:40]} "
                  f"\\${cost:.6f}")

    elapsed = time.time() - t_start
    print(f"\nComplete: {done} generated, {errors} errors, {skipped} skipped "
          f"| {elapsed:.0f}s | cost \\${total_cost:.6f}")
# === END_RUN_BATCH_GENERATE ===


if __name__ == "__main__":
    main()
