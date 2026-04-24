#!/usr/bin/env python3
"""
Batch generator — run daily to populate Obsidian vault with modified ЕГЭ tasks.

Config: edit PLAN below. Run: python batch_generate.py

Each subject × КЭС × strategy combination produces N Obsidian Markdown files
in vault/<subject>/ ready to open in Obsidian.

Requires OPENROUTER_API_KEY in env or .env file.
Model: set OPENROUTER_MODEL (default: anthropic/claude-sonnet-4-6).
"""

import argparse
import importlib.util
import json
import random
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from llm import complete
from generator import (
    build_prompt, parse_response, to_obsidian,
    get_subject_key, get_client, get_model,
    already_generated, log_generation,
)

load_dotenv()


def load_plan_from_file(path: Path) -> list[tuple]:
    spec = importlib.util.spec_from_file_location("plan_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PLAN

# ── Daily practice plan ──────────────────────────────────────────────────────
# Each entry: (subject, kes_prefix, strategy, difficulty, count)
# Adjust based on your weak spots.
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

VAULT_ROOT = Path("vault")


def load_tasks(subject: str) -> list[dict]:
    f = Path("data") / f"{subject}.json"
    return json.loads(f.read_text(encoding="utf-8"))


def load_framework() -> dict:
    return json.loads(Path("modification_framework.json").read_text(encoding="utf-8"))


def get_strategy_desc(framework: dict, subject: str, strategy: str) -> str:
    subj = framework["subjects"].get(subject, {})
    for kes_data in subj.get("kes_modifications", {}).values():
        for lvl in kes_data["levels"]:
            if lvl["name"] == strategy:
                return lvl["desc"]
    gmod = framework["global_modifications"].get(strategy, {})
    return gmod.get("desc", strategy)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=str, help="Path to external PLAN file (Python module with PLAN=...)")
    p.add_argument("--max", type=int, default=None, help="Cap total tasks generated")
    args = p.parse_args()

    plan = load_plan_from_file(Path(args.plan)) if args.plan else PLAN
    if args.max:
        plan = plan[:args.max]

    client = get_client()
    framework = load_framework()
    today = datetime.now().strftime("%Y-%m-%d")

    total = sum(c for *_, c in plan)
    print(f"Batch generate: {total} tasks for {today} | model: {get_model()}")

    done = 0
    errors = 0

    for subject, kes, strategy, difficulty, count in plan:
        tasks = load_tasks(subject)
        pool = [t for t in tasks
                if t.get("kes", "").startswith(kes) and t.get("latex_text")]
        if not pool:
            pool = [t for t in tasks if t.get("kes", "").startswith(kes)]
        if not pool:
            print(f"  SKIP {subject} КЭС={kes}: no tasks")
            continue

        out_dir = VAULT_ROOT / subject / kes.replace(".", "-")
        out_dir.mkdir(parents=True, exist_ok=True)

        strategy_desc = get_strategy_desc(framework, subject, strategy)
        subject_key = get_subject_key(subject)

        for i in range(count):
            available = [t for t in pool if not already_generated(subject, t["id"])]
            if not available:
                print(f"    SKIP {subject}/{kes}: all sources already generated")
                break
            source = random.choice(available)
            print(f"  [{done+1}/{total}] {subject} КЭС={kes} [{strategy}] task={source['id']}")

            prompt = build_prompt(source, strategy, strategy_desc, difficulty, framework)
            try:
                text = complete(client, get_model(), prompt, max_tokens=16384)
                parsed = parse_response(text)
            except Exception as e:
                print(f"    API error: {e}")
                errors += 1
                continue

            ts = datetime.now().strftime("%H%M%S")
            slug = f"{today}_{kes.replace('.', '-')}_{strategy}_{ts}_{i}"
            md_path = out_dir / f"{slug}.md"
            md_content = to_obsidian(source, source, subject, strategy, parsed, framework)
            md_path.write_text(md_content, encoding="utf-8")
            log_generation(md_path, subject, kes, source["id"], strategy,
                           parsed.get("difficulty", difficulty), get_model())
            print(f"    → {md_path.name} | answer: {parsed['answer'][:50]}")
            done += 1

    print(f"\nComplete: {done} generated, {errors} errors.")


if __name__ == "__main__":
    main()
