---
aliases: ["Приём · rsa_основа", "rsa_основа"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/rsa_основа]
technique: rsa_основа
---

# Приём · rsa_основа

> [!abstract] Описание
> Принцип RSA: открытый/закрытый ключ

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/rsa_основа AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/rsa_основа AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
