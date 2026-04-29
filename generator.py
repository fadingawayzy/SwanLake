#!/usr/bin/env python3
"""
ЕГЭ task modifier — generates harder variants of ФИПИ bank tasks.

Usage:
    python generator.py --subject math_profile --kes 2.5 --strategy замена --n 3
    python generator.py --subject math_profile --task-id D13540 --strategy параметр
    python generator.py --subject physics --random --n 5 --out vault/

Requires OPENROUTER_API_KEY in env or .env file.
Model: set OPENROUTER_MODEL (default: deepseek/deepseek-r1).
"""

import argparse
import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIError

from llm import make_client, complete, get_primary_model
from db import connect as db_connect

# === START_LOAD_DOTENV_GENERATOR ===
load_dotenv()
# === END_LOAD_DOTENV_GENERATOR ===

DATA_DIR = Path("data")
FRAMEWORK_FILE = Path("modification_framework.json")
VAULT_DIR = Path("vault")


# === START_GET_OPENROUTER_CLIENT_GUARDED ===
def get_client() -> OpenAI:
    try:
        return make_client()
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")
# === END_GET_OPENROUTER_CLIENT_GUARDED ===


# === START_GET_GENERATOR_MODEL ===
def get_model() -> str:
    return get_primary_model()
# === END_GET_GENERATOR_MODEL ===


# === START_CHECK_ALREADY_GENERATED ===
def already_generated(subject: str, source_id: str) -> bool:
    c = db_connect()
    row = c.execute(
        "SELECT 1 FROM generations WHERE subject=? AND source_id=? LIMIT 1",
        (subject, source_id)
    ).fetchone()
    c.close()
    return row is not None
# === END_CHECK_ALREADY_GENERATED ===


# === START_LOG_GENERATION_TO_DB ===
def log_generation(md_path: Path, subject: str, kes: str, source_id: str,
                   strategy: str, difficulty: int, model: str):
    from datetime import datetime as _dt
    c = db_connect()
    c.execute("""INSERT OR REPLACE INTO generations
                 (md_path, ts, subject, kes, source_id, strategy, difficulty, model)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (str(md_path.resolve()), _dt.now().isoformat(timespec="seconds"),
               subject, kes, source_id, strategy, difficulty, model))
    c.commit()
    c.close()
# === END_LOG_GENERATION_TO_DB ===


# === START_LOAD_SUBJECT_TASKS ===
def load_tasks(subject: str) -> list[dict]:
    f = DATA_DIR / f"{subject}.json"
    if not f.exists():
        sys.exit(f"ERROR: {f} not found. Run scraper.py first.")
    return json.loads(f.read_text(encoding="utf-8"))
# === END_LOAD_SUBJECT_TASKS ===


# === START_LOAD_FRAMEWORK ===
def load_framework() -> dict:
    return json.loads(FRAMEWORK_FILE.read_text(encoding="utf-8"))
# === END_LOAD_FRAMEWORK ===


# === START_MAP_SUBJECT_KEY ===
def get_subject_key(subject: str) -> str:
    mapping = {
        "math_profile": "math_profile",
        "physics": "physics",
        "russian": "russian",
        "informatics": "informatics",
    }

    return mapping.get(subject, subject)
# === END_MAP_SUBJECT_KEY ===


# === START_FILTER_TASKS_BY_KES_PREFIX ===
def find_tasks_by_kes(tasks: list[dict], kes_prefix: str) -> list[dict]:
    return [t for t in tasks if t.get("kes", "").startswith(kes_prefix)]
# === END_FILTER_TASKS_BY_KES_PREFIX ===


# === START_TEST_KES_PREFIX_MATCH ===
def kes_match(code: str, fw_code: str) -> bool:
    a = code.split(".")
    b = fw_code.split(".")
    return len(b) <= len(a) and a[:len(b)] == b
# === END_TEST_KES_PREFIX_MATCH ===


# === START_SLUGIFY_FOR_WIKILINK ===
def safe_link(s: str) -> str:
    return s.replace("/", "∕").replace("\\", "∖").replace(":", "꞉")
# === END_SLUGIFY_FOR_WIKILINK ===


# === START_LOOKUP_KES_STRATEGIES ===
def get_kes_strategies(framework: dict, subject_key: str, kes_code: str) -> list[dict]:
    subject = framework["subjects"].get(subject_key, {})
    mods = subject.get("kes_modifications", {})
    if kes_code in mods:
        return mods[kes_code]["levels"]
    best_key = ""
    for key in mods:
        if kes_match(kes_code, key) and len(key.split(".")) > len(best_key.split(".")):
            best_key = key
    return mods[best_key]["levels"] if best_key else []
# === END_LOOKUP_KES_STRATEGIES ===


# === START_BUILD_GENERATION_PROMPT ===
def build_prompt(task: dict, strategy_name: str, strategy_desc: str,
                  difficulty_target: int, framework: dict) -> str:
    text = task.get("latex_text") or task.get("text", "")
    kes = task.get("kes", "N/A")
    task_num = task.get("task_number", "?")
    answer_fmt = task.get("answer_format", "")

    diff_desc = framework["difficulty_levels"].get(str(difficulty_target), "")

    global_mods = framework["global_modifications"]
    global_suffix = ""
    for gkey, gval in global_mods.items():
        if strategy_name.lower() in gkey.lower() or gkey.lower() in strategy_name.lower():
            global_suffix = gval["prompt_suffix"]
            break

    prompt = f"""Ты эксперт по ЕГЭ (профессиональный составитель заданий). Тебе нужно создать УСЛОЖНЁННЫЙ вариант задания из открытого банка ФИПИ.

## Исходное задание
Номер задания: №{task_num}
КЭС: {kes}
Формат ответа: {answer_fmt}

Текст задания (LaTeX):
{text}

## Стратегия усложнения
Приём: **{strategy_name}**
Описание: {strategy_desc}
{('Дополнительная инструкция: ' + global_suffix) if global_suffix else ''}

## Целевой уровень сложности: {difficulty_target}/4
{diff_desc}

## Требования к результату
1. Сохрани тип задания (геометрия/алгебра/etc.) и формат ответа.
2. Применяй РОВНО указанный приём усложнения — не несколько сразу.
3. Все числа и условия должны давать «красивые» ответы (целые или простые дроби).
4. После задания дай **полное решение** и укажи **ответ**.
5. Оцени сложность по шкале 1-4.

## Формат ответа (строго)
```
ЗАДАНИЕ:
<текст задания в LaTeX>

РЕШЕНИЕ:
<пошаговое решение>

ОТВЕТ: <ответ>
СЛОЖНОСТЬ: <1-4>
ПРИЁМ: {strategy_name}
```

Создай модифицированное задание:"""

    return prompt
# === END_BUILD_GENERATION_PROMPT ===


# === START_PARSE_LLM_RESPONSE ===
def parse_response(text: str) -> dict:
    result = {
        "task": "",
        "solution": "",
        "answer": "",
        "difficulty": 0,
        "technique": "",
        "raw": text,
    }
    m = re.search(r"ЗАДАНИЕ:\s*(.*?)(?=РЕШЕНИЕ:|$)", text, re.DOTALL)
    if m:
        result["task"] = m.group(1).strip()
    m = re.search(r"РЕШЕНИЕ:\s*(.*?)(?=ОТВЕТ:|$)", text, re.DOTALL)
    if m:
        result["solution"] = m.group(1).strip()
    m = re.search(r"ОТВЕТ:\s*(.+?)(?=\n|$)", text)
    if m:
        result["answer"] = m.group(1).strip()
    m = re.search(r"СЛОЖНОСТЬ:\s*(\d+)", text)
    if m:
        result["difficulty"] = int(m.group(1))
    m = re.search(r"ПРИЁМ:\s*(.+?)(?=\n|$)", text)
    if m:
        result["technique"] = m.group(1).strip()
    return result
# === END_PARSE_LLM_RESPONSE ===


# === START_TOP_KES_PREFIX_GENERATOR ===
def top_kes_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k
# === END_TOP_KES_PREFIX_GENERATOR ===


# === START_DEFINE_SUBJECT_RU_MAP_GEN ===
SUBJECT_RU = {
    "math_profile": "Математика (профиль)",
    "physics": "Физика",
    "russian": "Русский язык",
    "informatics": "Информатика",
}
# === END_DEFINE_SUBJECT_RU_MAP_GEN ===


# === START_RENDER_OBSIDIAN_NOTE ===
def to_obsidian(source: dict, subject: str, strategy: str,
                parsed: dict, framework: dict) -> str:
    now = datetime.now()
    now_iso_date = now.strftime("%Y-%m-%d")
    now_iso_dt = now.strftime("%Y-%m-%dT%H:%M")
    kes_full = source.get("kes", "")
    task_num = source.get("task_number", "") or "?"
    source_id = source.get("id", "")

    subject_key = get_subject_key(subject)
    subj_mods = framework["subjects"].get(subject_key, {}).get("kes_modifications", {})
    kes_short = top_kes_prefix(kes_full)
    topic = ""
    if kes_short in subj_mods:
        topic = subj_mods[kes_short].get("topic", "")
    else:
        best_key = ""
        for k in subj_mods:
            if kes_match(kes_short, k) and len(k.split(".")) > len(best_key.split(".")):
                best_key = k
        if best_key:
            topic = subj_mods[best_key].get("topic", "")
    if not topic:
        topic = kes_full.split(" ", 1)[1] if " " in kes_full else "без темы"

    subj_ru = SUBJECT_RU.get(subject, subject)
    title = f"{subj_ru} №{task_num} — {topic} [{strategy}]"
    alias_short = f"{subject} КЭС {kes_short} {source_id}"

    lines = [
        "---",
        f"id: {source_id}-{now.strftime('%H%M%S')}",
        f'aliases: ["{alias_short}", "{topic} {strategy}"]',
        f"created: {now_iso_dt}",
        f"date: {now_iso_date}",
        f"subject: {subject}",
        f'subject_ru: "{subj_ru}"',
        f'task_number: "{task_num}"',
        f'kes: "{kes_full}"',
        f'kes_code: "{kes_short}"',
        f"topic: \"{topic}\"",
        f'technique: "{strategy}"',
        f"difficulty: {parsed.get('difficulty', 0)}",
        f'source_id: "{source_id}"',
        f'status: "new"',
        "verified: false",
        f'cssclasses: [ege-task, ege-{subject}]',
        f"tags:",
        f"  - ege",
        f"  - ege/{subject}",
        f"  - ege/{subject}/{kes_short.replace('.', '-')}",
        f"  - ege/technique/{strategy}",
        f"  - ege/difficulty/{parsed.get('difficulty', 0)}",
        f"  - generated",
        "---",
        "",
        f"# {title}",
        "",
        f"> [!abstract]- Метаданные",
        f"> - **Предмет:** [[{subj_ru}]]",
        f"> - **КЭС:** [[КЭС {kes_short} {safe_link(topic)}|{kes_short} · {topic}]]",
        f"> - **Приём усложнения:** [[Приём · {strategy}]]",
        f"> - **Сложность:** {parsed.get('difficulty', 0)}/4",
        f"> - **Оригинал:** `{source_id}` · [ФИПИ банк](https://ege.fipi.ru/bank/questions.php?proj=)",
        f"> - **Создано:** {now_iso_dt}",
        "",
        f"`status:: new` · `difficulty:: {parsed.get('difficulty', 0)}` · `kes:: {kes_short}` · `technique:: {strategy}`",
        "",
        "## Задание",
        "",
        f"> [!question]+ Условие",
        "> ",
        "\n".join(f"> {ln}" if ln.strip() else ">" for ln in (parsed["task"] or source.get("text", "")).splitlines()),
        "",
        "## Решение",
        "",
        f"> [!note]- Разворот решения (клик)",
        "> ",
        "\n".join(f"> {ln}" if ln.strip() else ">" for ln in parsed["solution"].splitlines()),
        "",
        f"> [!success] Ответ",
        f"> {parsed['answer']}",
        "",
        "## Разбор",
        "",
        "> [!tip]- Заметки после решения",
        "> - Что сделал правильно:",
        "> - Где споткнулся:",
        "> - Ключевая идея приёма:",
        "> - Повторить: ",
        "",
        "## Связи",
        "",
        f"- Тема: [[КЭС {kes_short} {safe_link(topic)}|КЭС {kes_short} {topic}]]",
        f"- Приём: [[Приём · {strategy}]]",
        f"- Предмет: [[{subj_ru}]]",
        f"- Все задачи КЭС {kes_short}: тег #ege/{subject}/{kes_short.replace('.', '-')}",
        "",
        "---",
        "",
        f"```dataview",
        f"TABLE WITHOUT ID file.link AS Задача, difficulty AS Сложн, status AS Статус, technique AS Приём",
        f"FROM #ege/{subject}/{kes_short.replace('.', '-')} AND -#ege/moc",
        f'WHERE file.name != this.file.name',
        f"SORT difficulty DESC, file.ctime DESC",
        f"LIMIT 10",
        f"```",
        "",
    ]
    return "\n".join(lines)
# === END_RENDER_OBSIDIAN_NOTE ===

# === START_GENERATE_TASK_E2E ===
def generate_task(client: OpenAI, task: dict, strategy_name: str,
                  strategy_desc: str, difficulty_target: int,
                  framework: dict) -> dict:
    prompt = build_prompt(task, strategy_name, strategy_desc, difficulty_target, framework)
    text = complete(client, get_model(), prompt, max_tokens=16384)
    return parse_response(text)
# === END_GENERATE_TASK_E2E ===

# === START_RUN_GENERATOR_CLI ===
def main():
    parser = argparse.ArgumentParser(description="ЕГЭ task difficulty enhancer")
    parser.add_argument("--subject", default="math_profile",
                        choices=["math_profile", "physics", "russian", "informatics"])
    parser.add_argument("--kes", help="КЭС code prefix, e.g. '2.5'")
    parser.add_argument("--task-id", help="Specific task hash ID from bank")
    parser.add_argument("--strategy", help="Strategy name (from framework), e.g. 'замена'")
    parser.add_argument("--global-strategy", help="Global strategy: add_parameter|increase_dimensions|add_constraint|chain_problems|change_question")
    parser.add_argument("--difficulty", type=int, default=3, choices=[1, 2, 3, 4])
    parser.add_argument("--n", type=int, default=1, help="Number of tasks to generate")
    parser.add_argument("--random", action="store_true", dest="use_random",
                        help="Pick random task from filtered set")
    parser.add_argument("--out", type=str, default=None,
                        help="Output dir for Obsidian Markdown files")
    parser.add_argument("--list-strategies", action="store_true",
                        help="List all available strategies for subject+KES")
    args = parser.parse_args()

    framework = load_framework()
    subject_key = get_subject_key(args.subject)

    if args.list_strategies:
        subj = framework["subjects"].get(subject_key, {})
        mods = subj.get("kes_modifications", {})
        print(f"\nStrategies for {args.subject}:")
        for kes_code, data in mods.items():
            print(f"\n  КЭС {kes_code} — {data['topic']}")
            for lvl in data["levels"]:
                print(f"    • {lvl['name']}: {lvl['desc']}")
        print("\nGlobal strategies:")
        for k, v in framework["global_modifications"].items():
            print(f"  • {k}: {v['desc']}")
        return

    tasks = load_tasks(args.subject)

    if args.task_id:
        pool = [t for t in tasks if t["id"] == args.task_id]
        if not pool:
            sys.exit(f"Task {args.task_id} not found in {args.subject}")
    elif args.kes:
        pool = find_tasks_by_kes(tasks, args.kes)
        if not pool:
            sys.exit(f"No tasks found for КЭС prefix '{args.kes}' in {args.subject}")
        print(f"Found {len(pool)} tasks for КЭС {args.kes}")
    else:
        pool = [t for t in tasks if t.get("latex_text")]
        if not pool:
            pool = tasks

    strategy_name = ""
    strategy_desc = ""

    if args.global_strategy:
        gmod = framework["global_modifications"].get(args.global_strategy)
        if not gmod:
            sys.exit(f"Unknown global strategy: {args.global_strategy}")
        strategy_name = args.global_strategy
        strategy_desc = gmod["desc"]
    elif args.strategy:
        kes_for_lookup = args.kes or (pool[0].get("kes", "").split(" ")[0] if pool else "")
        levels = get_kes_strategies(framework, subject_key, kes_for_lookup)
        for lvl in levels:
            if lvl["name"] == args.strategy:
                strategy_name = lvl["name"]
                strategy_desc = lvl["desc"]
                break
        if not strategy_name:
            strategy_name = args.strategy
            strategy_desc = f"Применить приём: {args.strategy}"
    else:
        kes_for_lookup = args.kes or (pool[0].get("kes", "").split(" ")[0] if pool else "")
        levels = get_kes_strategies(framework, subject_key, kes_for_lookup)
        if levels:
            chosen = random.choice(levels)
            strategy_name = chosen["name"]
            strategy_desc = chosen["desc"]
            print(f"Auto-selected strategy: {strategy_name} — {strategy_desc}")
        else:
            strategy_name = "параметр"
            strategy_desc = "Ввести параметр a вместо ключевого числа"

    out_dir = None
    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

    client = get_client()

    generated_count = 0
    tried = set()

    while generated_count < args.n:
        if args.use_random or not args.task_id:
            available = [t for t in pool
                         if t["id"] not in tried
                         and not already_generated(args.subject, t["id"])]
            if not available:
                print(f"Exhausted pool (pool={len(pool)} tried={len(tried)} + already generated).")
                break
            source_task = random.choice(available)
        else:
            if pool[0]["id"] in tried:
                break
            source_task = pool[0]

        tried.add(source_task["id"])

        print(f"\n[{generated_count+1}/{args.n}] Task {source_task['id']} | КЭС: {source_task.get('kes', '')[:40]}")
        print(f"  Strategy: {strategy_name}")

        try:
            parsed = generate_task(
                client, source_task, strategy_name, strategy_desc,
                args.difficulty, framework
            )
        except APIError as e:
            print(f"  API error: {e}")
            continue

        print(f"  Difficulty: {parsed['difficulty']}/4")
        print(f"  Answer: {parsed['answer'][:80]}")

        if out_dir:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = f"{args.subject}_kes{(args.kes or '').replace('.', '-')}_{strategy_name}_{ts}_{generated_count}"
            md_path = out_dir / f"{slug}.md"
            md_content = to_obsidian(
                source_task, args.subject,
                strategy_name, parsed, framework
            )
            md_path.write_text(md_content, encoding="utf-8")
            log_generation(md_path, args.subject,
                           source_task.get("kes", "").split(" ")[0],
                           source_task["id"], strategy_name,
                           parsed.get("difficulty", args.difficulty), get_model())
            print(f"  Saved: {md_path}")
        else:
            print("\n" + "="*60)
            print(parsed["task"] or "(no task text parsed)")
            print("\n--- РЕШЕНИЕ ---")
            print(parsed["solution"])
            print(f"\nОТВЕТ: {parsed['answer']}")
            print("="*60)

        generated_count += 1

    print(f"\nDone. Generated {generated_count} task(s).")
# === END_RUN_GENERATOR_CLI ===


if __name__ == "__main__":
    main()
