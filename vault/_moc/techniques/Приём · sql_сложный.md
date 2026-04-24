---
aliases: ["Приём · sql_сложный", "sql_сложный"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/sql_сложный]
technique: sql_сложный
---

# Приём · sql_сложный

> [!abstract] Описание
> Добавить JOIN, GROUP BY, HAVING в запрос

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/sql_сложный AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID subject_ru AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓
FROM #ege/technique/sql_сложный AND -#ege/moc
GROUP BY subject_ru
```
