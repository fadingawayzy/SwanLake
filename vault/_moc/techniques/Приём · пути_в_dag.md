---
aliases: ["Приём · пути_в_dag", "пути_в_dag"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/пути_в_dag]
technique: пути_в_dag
---

# Приём · пути_в_dag

> [!abstract] Описание
> Подсчёт путей в ориентированном ацикличном графе

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/пути_в_dag AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/пути_в_dag AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
