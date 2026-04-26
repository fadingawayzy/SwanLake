#!/usr/bin/env python3
"""
Demo seeder — populates vault + DB with realistic data without API calls.

Uses real FIPI tasks wrapped in the rich Obsidian format, simulates:
  - generations (real source_ids)
  - attempts (random pass/fail with bias toward weak KES)
  - verifications (mostly matching, some mismatches)

Lets user see full MOC dashboards, stats, SRS queue without OpenRouter.

Usage: python seed_demo.py --reset
"""

import argparse
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from generator import to_obsidian, load_framework, get_subject_key
from db import connect, DB_PATH

SUBJECTS = ["math_profile", "physics", "russian", "informatics"]
STRATEGIES_PER_SUBJ = {
    "math_profile": ["замена", "ОДЗ", "параметр", "add_constraint", "chain_problems"],
    "physics": ["система_тел", "схема_резисторов", "трение", "change_question"],
    "russian": ["скрытая_позиция", "change_question", "add_constraint"],
    "informatics": ["рекурсия", "найти_функцию", "цикл", "increase_dimensions"],
}


def top_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k


def demo_solution(task_text: str, kes: str) -> dict:
    return {
        "task": task_text,
        "solution": (
            "*[Демо-решение — реальное решение будет сгенерировано после подключения OpenRouter API]*\n\n"
            "Шаг 1. Анализ условия и выявление ключевой структуры.\n\n"
            "Шаг 2. Применение метода согласно приёму усложнения.\n\n"
            f"Шаг 3. Решение подкласса КЭС {kes} с учётом выбранной стратегии.\n\n"
            "Шаг 4. Проверка и запись ответа."
        ),
        "answer": "*(демо — ответ не вычислен; запустите batch_generate.py)*",
        "difficulty": random.choice([2, 3, 3, 3, 4]),
        "technique": "",
    }


def seed_generations(framework: dict, per_subject: int = 12) -> list[Path]:
    vault = Path("vault")
    created_paths = []
    db = connect()

    for subj in SUBJECTS:
        tasks = json.loads(Path(f"data/{subj}.json").read_text(encoding="utf-8"))
        tasks_with_latex = [t for t in tasks if t.get("latex_text")]
        if not tasks_with_latex:
            tasks_with_latex = tasks
        sample = random.sample(tasks_with_latex, min(per_subject, len(tasks_with_latex)))

        strategies = STRATEGIES_PER_SUBJ.get(subj, ["add_parameter"])

        for i, source in enumerate(sample):
            strategy = random.choice(strategies)
            kes_prefix = top_prefix(source.get("kes", ""))
            if not kes_prefix:
                continue

            task_text = source.get("latex_text") or source.get("text", "")
            parsed = demo_solution(task_text, kes_prefix)

            out_dir = vault / subj / kes_prefix.replace(".", "-")
            out_dir.mkdir(parents=True, exist_ok=True)

            ts_offset = timedelta(hours=random.randint(0, 72))
            ts = (datetime.now() - ts_offset).strftime("%Y%m%d_%H%M%S")
            slug = f"demo_{subj}_{kes_prefix.replace('.', '-')}_{strategy}_{ts}_{i}"
            md_path = out_dir / f"{slug}.md"

            md_content = to_obsidian(source, source, subj, strategy, parsed, framework)
            md_path.write_text(md_content, encoding="utf-8")
            created_paths.append(md_path)

            db.execute("""INSERT OR REPLACE INTO generations
                          (md_path, ts, subject, kes, source_id, strategy, difficulty, model)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                       (str(md_path.resolve()),
                        (datetime.now() - ts_offset).isoformat(timespec="seconds"),
                        subj, kes_prefix, source["id"], strategy,
                        parsed["difficulty"], "demo/no-model"))

    db.commit()
    db.close()
    return created_paths


def seed_attempts(paths: list[Path], attempt_ratio: float = 0.6):
    """Simulate student attempts: bias fail rate by difficulty and KES."""
    db = connect()
    weak_kes_bias = {"7.3": 0.7, "2.5": 0.55, "6.2": 0.5, "3.1": 0.45, "2.13": 0.6}

    sampled = random.sample(paths, int(len(paths) * attempt_ratio))
    for md in sampled:
        text = md.read_text(encoding="utf-8")
        fm = {}
        fm_match = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
        if fm_match:
            for line in fm_match.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip().strip('"')

        subject = fm.get("subject", "")
        kes = fm.get("kes_code", "")
        diff = int(fm.get("difficulty", 3) or 3)

        fail_prob = 0.3 + (diff - 2) * 0.1 + weak_kes_bias.get(kes, 0)
        fail_prob = min(0.85, fail_prob)
        result = "fail" if random.random() < fail_prob else ("partial" if random.random() < 0.15 else "pass")

        notes = {
            "fail": random.choice(["не учёл ОДЗ", "арифметическая ошибка", "не увидел замену", "пропустил корень"]),
            "partial": "частично, не довёл до числа",
            "pass": "",
        }

        ts_offset = timedelta(hours=random.randint(1, 48))
        db.execute("""INSERT INTO attempts (ts, subject, kes, task_number, source_id,
                      technique, difficulty, md_path, result, note)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   ((datetime.now() - ts_offset).isoformat(timespec="seconds"),
                    subject, kes, fm.get("task_number"), fm.get("source_id"),
                    fm.get("technique"), diff, str(md.resolve()), result, notes[result]))
    db.commit()
    db.close()
    print(f"  Seeded {len(sampled)} attempts")


def seed_verifications(paths: list[Path], verify_ratio: float = 0.7,
                       mismatch_rate: float = 0.12):
    db = connect()
    sampled = random.sample(paths, int(len(paths) * verify_ratio))
    for md in sampled:
        match = 0 if random.random() < mismatch_rate else 1
        claimed = f"ДЕМО_{random.randint(100,999)}"
        verified = claimed if match else f"ДЕМО_{random.randint(100,999)}"
        ts_offset = timedelta(hours=random.randint(0, 24))
        db.execute("""INSERT OR REPLACE INTO verifications
                      (md_path, ts, model, claimed_answer, verified_answer, match, verifier_output)
                      VALUES (?, ?, ?, ?, ?, ?, ?)""",
                   (str(md.resolve()),
                    (datetime.now() - ts_offset).isoformat(timespec="seconds"),
                    "google/gemini-2.5-flash", claimed, verified, match,
                    f"(demo verification output — match={match})"))
    db.commit()
    db.close()
    print(f"  Seeded {len(sampled)} verifications ({int(mismatch_rate*100)}% mismatches)")


def reset_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    print(f"  Removed {DB_PATH}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="Wipe DB first")
    p.add_argument("--per-subject", type=int, default=12)
    p.add_argument("--no-attempts", action="store_true")
    p.add_argument("--no-verify", action="store_true")
    args = p.parse_args()

    random.seed(42)

    if args.reset:
        reset_db()

    framework = load_framework()
    print(f"Seeding {args.per_subject} demo tasks per subject...")
    paths = seed_generations(framework, args.per_subject)
    print(f"  Created {len(paths)} task files in vault/")

    if not args.no_attempts:
        seed_attempts(paths)
    if not args.no_verify:
        seed_verifications(paths)

    print(f"\nDone. Now run:")
    print(f"  python stats.py --subject math_profile")
    print(f"  python srs.py schedule")
    print(f"  python moc.py  # rebuild MOC stats")
    print(f"  Open vault/_moc/HOME.md in Obsidian")


if __name__ == "__main__":
    main()
