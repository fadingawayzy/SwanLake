---
aliases: ["Приём · объём_utf8", "объём_utf8"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/объём_utf8]
technique: объём_utf8
---

# Приём · объём_utf8

> [!abstract] Описание
> Расчёт объёма UTF-8 текста (1-4 байта на символ)

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/объём_utf8 AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/объём_utf8 AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
