---
aliases: ["Приём · сжатие_lossless", "сжатие_lossless"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/сжатие_lossless]
technique: сжатие_lossless
---

# Приём · сжатие_lossless

> [!abstract] Описание
> Без потерь vs с потерями

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/сжатие_lossless AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/сжатие_lossless AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
