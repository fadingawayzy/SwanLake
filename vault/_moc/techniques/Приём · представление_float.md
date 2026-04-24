---
aliases: ["Приём · представление_float", "представление_float"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/представление_float]
technique: представление_float
---

# Приём · представление_float

> [!abstract] Описание
> IEEE 754 — представление дробных

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/представление_float AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/представление_float AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
