---
aliases: ["Приём · add_proof_requirement", "add_proof_requirement"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/add_proof_requirement]
technique: add_proof_requirement
---

# Приём · add_proof_requirement

> [!abstract] Описание
> Добавить требование доказательства / обоснования

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/add_proof_requirement AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/add_proof_requirement AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
