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
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import APIError

from generator import (
    build_prompt, parse_response, get_client, get_model,
    get_subject_key, load_framework
)
from llm import complete_tracked

load_dotenv()

# === START_DEFINE_EXAM_TASK_COUNTS ===
EXPECTED_TASK_COUNT = {
    "math_profile": 19,
    "physics": 30,
    "russian": 27,
    "informatics": 27,
}
# === END_DEFINE_EXAM_TASK_COUNTS ===

# === START_DEFINE_EXAM_TIME_LIMITS ===
TIME_LIMIT_MIN = {
    "math_profile": 235,
    "physics": 235,
    "russian": 210,
    "informatics": 235,
}
# === END_DEFINE_EXAM_TIME_LIMITS ===

# === START_TOP_PREFIX_EXAM ===
def top_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k
# === END_TOP_PREFIX_EXAM ===


# === START_BUCKET_TASKS_BY_KES ===
def by_kes(tasks: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list] = {}
    for t in tasks:
        k = top_prefix(t.get("kes", ""))
        if k:
            buckets.setdefault(k, []).append(t)
    return buckets
# === END_BUCKET_TASKS_BY_KES ===


# === START_PICK_VARIANT_PREFER_LATEX ===
def pick_variant(pool: list[dict]) -> dict | None:
    latex = [t for t in pool if t.get("latex_text")]
    return random.choice(latex) if latex else (random.choice(pool) if pool else None)
# === END_PICK_VARIANT_PREFER_LATEX ===


# === START_HARDEN_TASK ===
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
    result = complete_tracked(client, model, prompt, max_tokens=16384)
    parsed = parse_response(result["text"])
    parsed["cost_usd"] = result["cost_usd"]
    parsed["latency_ms"] = result["latency_ms"]
    return parsed
# === END_HARDEN_TASK ===


# === START_RENDER_EXAM_MD ===
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
# === END_RENDER_EXAM_MD ===


# === START_RUN_MOCK_EXAM_CLI ===
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

    t_start = time.time()
    if args.hard:
        print(f"Building HARD mock exam: {args.subject} ({expected} tasks)", flush=True)
        print(f"  Model: {model}", flush=True)
    else:
        print(f"Building STANDARD mock exam: {args.subject} ({expected} tasks)", flush=True)

    kes_sorted = sorted(buckets.keys())
    chosen_kes = kes_sorted[:expected] if len(kes_sorted) >= expected else kes_sorted
    while len(chosen_kes) < expected and kes_sorted:
        chosen_kes.append(random.choice(kes_sorted))

    ok = 0
    errors = 0
    total_cost = 0.0

    for idx, kes in enumerate(chosen_kes, 1):
        src = pick_variant(buckets[kes])
        if not src:
            print(f"  [{idx}/{expected}] WARN: no task for КЭС {kes}", flush=True)
            errors += 1
            continue
        src = {**src, "task_number": str(idx)}

        if args.hard and client:
            print(f"  [{idx}/{expected}] hardening КЭС={kes} ...", end=" ", flush=True)
            try:
                parsed = harden(src, framework, args.subject, client, model)
                items.append({
                    **src,
                    "display_text": parsed["task"] or src.get("latex_text", ""),
                    "_answer": parsed["answer"],
                    "_solution": parsed["solution"],
                })
                cost = parsed.get("cost_usd") or 0.0
                lat = parsed.get("latency_ms") or 0
                total_cost += cost
                print(f"answer={parsed['answer'][:20]} \\${cost:.6f} {lat}ms", flush=True)
                ok += 1
            except APIError as e:
                print(f"API error: {e[:60]}", flush=True)
                items.append(src)
                errors += 1
        else:
            fmt = src.get("answer_format", "").strip()
            placeholder = f"(решить самостоятельно — формат: {fmt})" if fmt else "(решить самостоятельно)"
            items.append({**src, "_answer": placeholder})
            ok += 1

    elapsed = time.time() - t_start
    out_dir = Path(args.out) / args.subject
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "_hard" if args.hard else ""
    md_path = out_dir / f"mock_{args.subject}_{ts}{suffix}.md"
    md_path.write_text(render_exam(args.subject, items, args.hard), encoding="utf-8")

    print(f"\nSaved: {md_path}")
    print(f"Time limit: {TIME_LIMIT_MIN[args.subject]} min | {len(items)} tasks")
    if args.hard:
        print(f"Results: {ok} ok, {errors} errors | elapsed {elapsed:.0f}s | total cost \\${total_cost:.6f}")
        print(f"  Note: hardest tasks (КЭС 2.10/2.11/3.6/7.3/7.4) expect LLM reasoning — verifier check advised")
# === END_RUN_MOCK_EXAM_CLI ===


if __name__ == "__main__":
    main()
