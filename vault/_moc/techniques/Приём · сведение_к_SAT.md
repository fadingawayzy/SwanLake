---
aliases: ["Приём · сведение_к_SAT", "сведение_к_SAT"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/сведение_к_SAT]
technique: сведение_к_SAT
---

# Приём · сведение_к_SAT

> [!abstract] Описание
> Свести к SAT

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/сведение_к_SAT AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/сведение_к_SAT AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
