---
aliases: ["Приём · признаки_делимости_P", "признаки_делимости_P"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/признаки_делимости_P]
technique: признаки_делимости_P
---

# Приём · признаки_делимости_P

> [!abstract] Описание
> Признаки делимости в произвольной СС

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/признаки_делимости_P AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/признаки_делимости_P AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
