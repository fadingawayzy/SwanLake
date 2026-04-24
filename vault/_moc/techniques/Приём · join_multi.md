---
aliases: ["Приём · join_multi", "join_multi"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/join_multi]
technique: join_multi
---

# Приём · join_multi

> [!abstract] Описание
> JOIN по 3+ таблицам с условиями

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/join_multi AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/join_multi AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
