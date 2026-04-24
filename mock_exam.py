#!/usr/bin/env python3
"""
Mock exam generator — builds full ЕГЭ variant by sampling one task per
задание number (1..N) from scraped data, optionally generates harder versions.

Usage:
    python mock_exam.py --subject math_profile           # raw bank mock
    python mock_exam.py --subject physics --hard         # LLM-harden each task
    python mock_exam.py --subject informatics --out vault/mocks/
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import APIError

from generator import (
    build_prompt, parse_response, get_client, get_model,
    get_subject_key, load_framework
)

load_dotenv()

EXPECTED_TASK_COUNT = {
    "math_profile": 19,
    "physics": 30,
    "russian": 27,
    "informatics": 27,
}

TIME_LIMIT_MIN = {
    "math_profile": 235,
    "physics": 235,
    "russian": 210,
    "informatics": 235,
}


def top_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k


def by_kes(tasks: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list] = {}
    for t in tasks:
        k = top_prefix(t.get("kes", ""))
        if k:
            buckets.setdefault(k, []).append(t)
    return buckets


def pick_variant(pool: list[dict]) -> dict | None:
    latex = [t for t in pool if t.get("latex_text")]
    return random.choice(latex) if latex else (random.choice(pool) if pool else None)


def harden(task: dict, framework: dict, subject: str, client, model: str) -> dict:
    subj_key = get_subject_key(subject)
    kes = task.get("kes", "").split(" ")[0]
    mods = framework["subjects"].get(subj_key, {}).get("kes_modifications", {})
    strategy_name = "add_parameter"
    strategy_desc = "Ввести параметр вместо числа"
    for code, data in mods.items():
        if kes.startswith(code):
            levels = data.get("levels", [])
            if levels:
                strategy_name = levels[0]["name"]
                strategy_desc = levels[0]["desc"]
            break

    prompt = build_prompt(task, strategy_name, strategy_desc, 3, framework)
    response = client.chat.completions.create(
        model=model,
        max_tokens=16384,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_response(response.choices[0].message.content or "")


def render_exam(subject: str, items: list[dict], hard: bool) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    n = EXPECTED_TASK_COUNT.get(subject, 0)
    tmin = TIME_LIMIT_MIN.get(subject, 0)
    mode = "УСЛОЖНЁННЫЙ" if hard else "СТАНДАРТНЫЙ"

    lines = [
        "---",
        f"created: {now}",
        f"subject: {subject}",
        f"type: mock_exam",
        f"mode: {mode.lower()}",
        f"tasks: {len(items)}",
        f"tags: [ege, {subject}, mock_exam]",
        "---",
        "",
        f"# ЕГЭ {subject} — Пробник ({mode})",
        f"",
        f"**Время:** {tmin} мин | **Задач:** {len(items)}/{n}",
        f"**Сгенерировано:** {now}",
        "",
        "---",
        "",
    ]

    answers = []
    for i, it in enumerate(items, 1):
        task_num = it.get("task_number", i)
        kes = it.get("kes", "")
        text = it.get("display_text") or it.get("latex_text") or it.get("text", "")
        lines += [
            f"## Задание {task_num}",
            f"*КЭС: {kes}*",
            "",
            text,
            "",
            "---",
            "",
        ]
        answers.append((task_num, it.get("_answer", "")))

    lines += ["## Ответы (не подглядывать)", "", "```"]
    for tn, a in answers:
        lines.append(f"№{tn}: {a}")
    lines += ["```", ""]

    if hard:
        lines += ["## Решения", ""]
        for i, it in enumerate(items, 1):
            sol = it.get("_solution", "")
            if sol:
                lines += [f"### Решение №{it.get('task_number', i)}", "", sol, ""]

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--subject", required=True,
                   choices=["math_profile", "physics", "russian", "informatics"])
    p.add_argument("--hard", action="store_true", help="Generate harder variants via LLM")
    p.add_argument("--out", type=str, default="vault/mocks")
    p.add_argument("--seed", type=int)
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    framework = load_framework()
    tasks = json.loads(Path(f"data/{args.subject}.json").read_text(encoding="utf-8"))
    buckets = by_kes(tasks)

    expected = EXPECTED_TASK_COUNT[args.subject]
    items = []

    client = get_client() if args.hard else None
    model = get_model() if args.hard else None

    kes_sorted = sorted(buckets.keys())
    chosen_kes = kes_sorted[:expected] if len(kes_sorted) >= expected else kes_sorted
    while len(chosen_kes) < expected and kes_sorted:
        chosen_kes.append(random.choice(kes_sorted))

    for idx, kes in enumerate(chosen_kes, 1):
        src = pick_variant(buckets[kes])
        if not src:
            print(f"  WARN: no task for КЭС {kes}")
            continue
        src = {**src, "task_number": str(idx)}

        if args.hard and client:
            print(f"  [{idx}/{expected}] hardening КЭС={kes}")
            try:
                parsed = harden(src, framework, args.subject, client, model)
                items.append({
                    **src,
                    "display_text": parsed["task"] or src.get("latex_text", ""),
                    "_answer": parsed["answer"],
                    "_solution": parsed["solution"],
                })
            except APIError as e:
                print(f"    API error: {e} — falling back to bank task")
                items.append(src)
        else:
            items.append({**src, "_answer": src.get("answer", "")})

    out_dir = Path(args.out) / args.subject
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "_hard" if args.hard else ""
    md_path = out_dir / f"mock_{args.subject}_{ts}{suffix}.md"
    md_path.write_text(render_exam(args.subject, items, args.hard), encoding="utf-8")
    print(f"\nSaved: {md_path}")
    print(f"Time limit: {TIME_LIMIT_MIN[args.subject]} min | {len(items)} tasks")


if __name__ == "__main__":
    main()
