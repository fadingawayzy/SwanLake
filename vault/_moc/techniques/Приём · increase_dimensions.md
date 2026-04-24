---
aliases: ["Приём · increase_dimensions", "increase_dimensions"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/increase_dimensions]
technique: increase_dimensions
---

# Приём · increase_dimensions

> [!abstract] Описание
> Перевести плоскую задачу в пространственную (2D→3D)

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/increase_dimensions AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/increase_dimensions AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
