---
aliases: ["Приём · монте_карло_pi", "монте_карло_pi"]
cssclasses: [ege-moc, ege-technique]
tags: [ege/moc/technique, ege/technique/монте_карло_pi]
technique: монте_карло_pi
---

# Приём · монте_карло_pi

> [!abstract] Описание
> Оценка π методом Монте-Карло

## 🗂 Задачи с этим приёмом

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС, difficulty AS Сл, status AS Статус
FROM #ege/technique/монте_карло_pi AND -#ege/moc
SORT difficulty DESC, date DESC
```

## 📊 Успешность по приёму

```dataview
TABLE WITHOUT ID key AS Предмет, length(rows) AS Всего, length(filter(rows, (r) => r.status = "pass")) AS ✓, length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege/technique/монте_карло_pi AND -#ege/moc
WHERE subject_ru
GROUP BY subject_ru
SORT key ASC
```
