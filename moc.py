#!/usr/bin/env python3
"""
MOC (Map of Content) generator for Obsidian vault.

Creates hub notes with Dataview queries:
  vault/_moc/HOME.md                         — dashboard root
  vault/_moc/{subject}.md                    — subject index
  vault/_moc/kes/КЭС {code} {topic}.md       — per-KES hub
  vault/_moc/techniques/Приём · {name}.md    — per-technique hub
  vault/_moc/Предмет.md aliases              — for wikilink targets

All notes are overwrite-safe; re-run after bulk generation.

Usage:
    python moc.py                            # rebuild all MOCs
    python moc.py --home-only                # just HOME.md
"""

import argparse
import json
from collections import Counter
from pathlib import Path

VAULT = Path("vault")
MOC_ROOT = VAULT / "_moc"
FRAMEWORK = json.loads(Path("modification_framework.json").read_text(encoding="utf-8"))

SUBJECTS = ["math_profile", "physics", "russian", "informatics"]
SUBJECT_RU = {
    "math_profile": "Математика (профиль)",
    "physics": "Физика",
    "russian": "Русский язык",
    "informatics": "Информатика",
}


def top_prefix(kes: str) -> str:
    k = kes.split(" ")[0]
    parts = k.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else k


def safe_link(s: str) -> str:
    """Replace path-illegal chars in topic to keep it usable as filename + wikilink target.
    U+2215 (∕) renders like ASCII '/' but is not a path separator."""
    return s.replace("/", "∕").replace("\\", "∖").replace(":", "꞉")


def kes_match(code: str, fw_code: str) -> bool:
    a = code.split(".")
    b = fw_code.split(".")
    return len(b) <= len(a) and a[:len(b)] == b


def lookup_fw(mods: dict, code: str) -> tuple[str, list]:
    if code in mods:
        return mods[code].get("topic", ""), mods[code].get("levels", [])
    best_key = ""
    for fw_code in mods:
        if kes_match(code, fw_code) and len(fw_code.split(".")) > len(best_key.split(".")):
            best_key = fw_code
    if best_key:
        return mods[best_key].get("topic", ""), mods[best_key].get("levels", [])
    return "", []


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_home():
    lines = [
        "---",
        "aliases: [Dashboard, Главная, HOME]",
        "cssclasses: [ege-dashboard]",
        "tags: [ege/moc/home]",
        "---",
        "",
        "# 🎯 ЕГЭ — Командный центр",
        "",
        "> [!info] 400-point target",
        "> Цель: 100 из 100 по 4 предметам. Ежедневный grind через generate → verify → review → SRS.",
        "",
        "## 📊 Сегодня",
        "",
        "### Просрочено + сегодня",
        "```dataview",
        "TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус",
        "FROM #ege AND -#ege/moc",
        'WHERE status != "pass"',
        "SORT difficulty DESC, date ASC",
        "LIMIT 20",
        "```",
        "",
        "### Новые, неверифицированные",
        "```dataview",
        "TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС",
        "FROM #ege AND -#ege/moc",
        "WHERE status = \"new\" AND verified = false",
        "SORT date DESC",
        "LIMIT 15",
        "```",
        "",
        "## 📚 Предметы",
        "",
    ]
    for subj in SUBJECTS:
        ru = SUBJECT_RU[subj]
        lines.append(f"- [[{ru}]]")
    lines += [
        "",
        "## 🔁 Приёмы усложнения",
        "",
        "```dataview",
        "LIST",
        "FROM #ege/moc/technique",
        "SORT file.name ASC",
        "```",
        "",
        "## 📈 Статистика по КЭС (pass rate)",
        "",
        "```dataview",
        'TABLE WITHOUT ID key AS КЭС, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗',
        "FROM #ege AND -#ege/moc",
        "WHERE kes_code",
        "GROUP BY kes_code",
        "SORT key ASC",
        "```",
        "",
        "## 🛠 CLI флоу",
        "",
        "```bash",
        "python generate_plan.py --weights tracker > plan.py",
        "python batch_generate.py --plan plan.py --max 15",
        "python verifier.py --dir vault/ --skip-verified --flag-only",
        "python review.py --limit 20",
        "python stats.py --weak",
        "python srs.py due",
        "```",
        "",
    ]
    write(MOC_ROOT / "HOME.md", "\n".join(lines))


def build_subject(subj: str):
    ru = SUBJECT_RU[subj]
    mods = FRAMEWORK["subjects"].get(subj, {}).get("kes_modifications", {})

    try:
        tasks = json.loads(Path(f"data/{subj}.json").read_text(encoding="utf-8"))
        codes = Counter(top_prefix(t.get("kes", "")) for t in tasks)
        codes.pop("", None)
    except Exception:
        codes = Counter()

    lines = [
        "---",
        f'aliases: ["{subj}", "{ru}"]',
        f"cssclasses: [ege-moc, ege-{subj}]",
        f"tags: [ege/moc/subject, ege/{subj}]",
        "---",
        "",
        f"# {ru} — индекс",
        "",
        "> [!info] Всего задач в банке: "
        + str(sum(codes.values())) + " · уникальных КЭС: " + str(len(codes)),
        "",
        "## 📖 КЭС (темы)",
        "",
    ]
    for code in sorted(codes.keys()):
        topic, _ = lookup_fw(mods, code)
        topic = topic or "без темы"
        slug = safe_link(topic)
        lines.append(f"- [[КЭС {code} {slug}|{code} · {topic}]] ({codes[code]} задач в банке)")

    lines += [
        "",
        "## 🗂 Все сгенерированные задачи",
        "",
        "```dataview",
        "TABLE WITHOUT ID file.link AS Задача, kes_code AS КЭС, technique AS Приём, difficulty AS Сл, status AS Статус",
        f"FROM #ege/{subj} AND -#ege/moc",
        "SORT kes_code ASC, difficulty DESC",
        "```",
        "",
        "## 🎯 Слабые темы (fail rate > 50%)",
        "",
        "```dataview",
        'TABLE WITHOUT ID key AS КЭС, length(filter(rows, (r) => r.status = "fail")) AS Провалов, length(rows) AS Всего, round(length(filter(rows, (r) => r.status = "fail")) / length(rows) * 100) AS "Fail %"',
        f"FROM #ege/{subj} AND -#ege/moc",
        'WHERE (status = "pass" OR status = "fail") AND kes_code',
        "GROUP BY kes_code",
        'WHERE length(filter(rows, (r) => r.status = "fail")) / length(rows) > 0.5',
        'SORT length(filter(rows, (r) => r.status = "fail")) / length(rows) DESC',
        "```",
        "",
    ]
    write(MOC_ROOT / f"{ru}.md", "\n".join(lines))


def build_kes_moc(subj: str, code: str, topic: str, levels: list):
    slug = safe_link(topic)
    lines = [
        "---",
        f'aliases: ["КЭС {code}", "{topic}", "{code} {topic}"]',
        f"cssclasses: [ege-moc, ege-kes]",
        f"tags: [ege/moc/kes, ege/{subj}/{code.replace('.', '-')}]",
        f"kes_code: {code}",
        f"subject: {subj}",
        "---",
        "",
        f"# КЭС {code} · {topic}",
        "",
        f"Часть темы: [[{SUBJECT_RU[subj]}]]",
        "",
        "## 📋 Приёмы усложнения для этой темы",
        "",
    ]
    if levels:
        for lvl in levels:
            lines.append(f"- [[Приём · {lvl['name']}]] — {lvl.get('desc', '')}")
    else:
        lines.append("- *Приёмы не определены — используются глобальные стратегии.*")

    lines += [
        "",
        "## 🗂 Задачи по теме",
        "",
        "```dataview",
        "TABLE WITHOUT ID file.link AS Задача, technique AS Приём, difficulty AS Сл, status AS Статус, date AS Дата",
        f"FROM #ege/{subj}/{code.replace('.', '-')} AND -#ege/moc",
        "SORT difficulty DESC, date DESC",
        "```",
        "",
        "## 📝 Заметки по теме",
        "",
        "> [!tip]- Ключевые формулы / подходы",
        "> - ",
        "",
        "> [!warning]- Типичные ошибки",
        "> - ",
        "",
    ]
    write(MOC_ROOT / "kes" / f"КЭС {code} {slug}.md", "\n".join(lines))


def build_technique(name: str, desc: str):
    lines = [
        "---",
        f'aliases: ["Приём · {name}", "{name}"]',
        f"cssclasses: [ege-moc, ege-technique]",
        f"tags: [ege/moc/technique, ege/technique/{name}]",
        f"technique: {name}",
        "---",
        "",
        f"# Приём · {name}",
        "",
        f"> [!abstract] Описание",
        f"> {desc}",
        "",
        "## 🗂 Задачи с этим приёмом",
        "",
        "```dataview",
        "TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус",
        f"FROM #ege/technique/{name} AND -#ege/moc",
        "SORT difficulty DESC, date DESC",
        "```",
        "",
        "## 📊 Успешность по приёму",
        "",
        "```dataview",
        'TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗',
        f"FROM #ege/technique/{name} AND -#ege/moc",
        "WHERE subject_ru",
        "GROUP BY subject_ru",
        "SORT key ASC",
        "```",
        "",
    ]
    write(MOC_ROOT / "techniques" / f"Приём · {name}.md", "\n".join(lines))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--home-only", action="store_true")
    args = p.parse_args()

    MOC_ROOT.mkdir(parents=True, exist_ok=True)
    build_home()

    if args.home_only:
        print(f"Built: {MOC_ROOT / 'HOME.md'}")
        return

    for subj in SUBJECTS:
        build_subject(subj)
        mods = FRAMEWORK["subjects"].get(subj, {}).get("kes_modifications", {})
        try:
            tasks = json.loads(Path(f"data/{subj}.json").read_text(encoding="utf-8"))
            codes_in_data = {top_prefix(t.get("kes", "")) for t in tasks}
            codes_in_data.discard("")
        except Exception:
            codes_in_data = set()

        for code in codes_in_data:
            topic, levels = lookup_fw(mods, code)
            topic = topic or "без темы"
            build_kes_moc(subj, code, topic, levels)

    techniques = {}
    for subj_data in FRAMEWORK["subjects"].values():
        for kes_data in subj_data.get("kes_modifications", {}).values():
            for lvl in kes_data.get("levels", []):
                techniques[lvl["name"]] = lvl.get("desc", "")
    for name, desc in FRAMEWORK.get("global_modifications", {}).items():
        techniques[name] = desc.get("desc", "")
    for name, desc in techniques.items():
        build_technique(name, desc)

    print(f"Built MOCs in {MOC_ROOT}/")
    print(f"  HOME.md")
    print(f"  {len(SUBJECTS)} subjects")
    print(f"  KES hubs per subject")
    print(f"  {len(techniques)} technique hubs")


if __name__ == "__main__":
    main()
