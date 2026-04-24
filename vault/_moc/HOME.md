---
aliases: [Dashboard, Главная, HOME]
cssclasses: [ege-dashboard]
tags: [ege/moc/home]
---

# 🎯 ЕГЭ — Командный центр

> [!info] 400-point target
> Цель: 100 из 100 по 4 предметам. Ежедневный grind через generate → verify → review → SRS.

## 📊 Сегодня

### Просрочено + сегодня
```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege AND -#ege/moc
WHERE status != "pass"
SORT difficulty DESC, date ASC
LIMIT 20
```

### Новые, неверифицированные
```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС
FROM #ege AND -#ege/moc
WHERE status = "new" AND verified = false
SORT date DESC
LIMIT 15
```

## 📚 Предметы

- [[Математика (профиль)]]
- [[Физика]]
- [[Русский язык]]
- [[Информатика]]

## 🔁 Приёмы усложнения

```dataview
LIST
FROM #ege/moc/technique
SORT file.name ASC
```

## 📈 Статистика по КЭС (pass rate)

```dataview
TABLE WITHOUT ID key AS КЭС, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege AND -#ege/moc
WHERE kes_code
GROUP BY kes_code
SORT key ASC
```

## 🛠 CLI флоу

```bash
python generate_plan.py --weights tracker > plan.py
python batch_generate.py --plan plan.py --max 15
python verifier.py --dir vault/ --skip-verified --flag-only
python review.py --limit 20
python stats.py --weak
python srs.py due
```
