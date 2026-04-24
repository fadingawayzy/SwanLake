---
aliases: ["Приём · add_parameter", "add_parameter"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/add_parameter]
technique: add_parameter
---

# Приём · add_parameter

> [!abstract] Описание
> Заменить конкретное число на параметр a, найти все допустимые значения a

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/add_parameter AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/add_parameter AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
