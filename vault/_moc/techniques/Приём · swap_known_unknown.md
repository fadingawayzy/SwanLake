---
aliases: ["Приём · swap_known_unknown", "swap_known_unknown"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/swap_known_unknown]
technique: swap_known_unknown
---

# Приём · swap_known_unknown

> [!abstract] Описание
> Поменять известное и неизвестное местами

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/swap_known_unknown AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/swap_known_unknown AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
