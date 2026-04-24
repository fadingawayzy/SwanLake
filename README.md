# ЕГЭ-202X

Система подготовки к ЕГЭ по 4 предметам:
**математика (профиль), физика, информатика, русский язык**.

Берёт реальные задания из открытого банка ФИПИ, переписывает их в более
сложные варианты через LLM (OpenRouter), верифицирует ответы кросс-моделью,
складывает в Obsidian-хранилище с Dataview-дашбордами и SRS (интервальное
повторение по SM-2).

---

## Зачем

ЕГЭ-задачи 2-й части переоцениваются на ≈3–5 баллов каждая. Выдвинем гипотезу и будем работать в следующем ключе: чтобы
гарантированно набрать достойное число или иметь глубинное понимание предметов, недостаточно решать задачи уровня банка ФИПИ —
нужно тренироваться на их **усложнённых версиях** и **олимпиадных приёмах**.
Эта система автоматически:

1. Скачивает банк ФИПИ (`scraper.py`).
2. Для каждой темы (КЭС) применяет приёмы усложнения из
   `modification_framework.json` (стратегии standard / hard / olympiad).
3. Просит LLM сгенерировать задачу + полное решение.
4. Просит **другую** LLM проверить ответ (independent-model agreement).
5. Складывает в Obsidian-vault с метаданными для Dataview.
6. Учитывает попытки + расписание повторений (SM-2).

---

## Архитектура

```
data/                        ← скачанные задачи ФИПИ (JSON)
  math_profile.json
  physics.json
  russian.json
  informatics.json

modification_framework.json  ← каркас приёмов усложнения по КЭС
                               (полностью соответствует кодификатору ЕГЭ-2026
                               + надстройка над школьной программой)

ege.db                       ← SQLite: attempts / verifications / generations

vault/                       ← Obsidian vault
  _moc/                        MOC-индексы (HOME, предметы, КЭС, приёмы)
  _templates/ege-task.md       шаблон Templater для ручного создания
  .obsidian/                   плагины: Dataview, Templater, Git, …
  {subject}/{kes}/*.md         сгенерированные задачи

demo_variants/               ← вывод mock_exam.py
```

---

## Установка

### 1. Зависимости

```bash
python -m venv venv
source venv/bin/activate   # или fish: source venv/bin/activate.fish
pip install openai python-dotenv requests beautifulsoup4
```

### 2. API-ключ OpenRouter

Зарегистрируйтесь на <https://openrouter.ai>, получите ключ:

```bash
cp .env.example .env
$EDITOR .env
```

Минимально (допустимы любые модели, в т.ч. и бесплатные, но предпочтительно их не использовать - галлюцинации и freetier ограничения)

```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=deepseek/deepseek-r1
OPENROUTER_VERIFIER_MODEL=google/gemini-2.5-flash
```

**Почему две модели:** генератор и верификатор должны быть **разными**, иначе
кросс-проверка не отлавливает галлюцинации.

### 3. Obsidian

1. Откройте Obsidian → *Open folder as vault* → выберите `vault/`.
2. Включите community plugins (если запросит).
3. Включите *Restricted Mode* → off.
4. Все необходимые плагины уже установлены и настроены:
   - **Dataview** — таблицы и статистика по задачам
   - **Templater** — шаблон новой задачи (создаётся автоматически в `vault/`)
   - **Obsidian Git** — автоматический бэкап
   - **Tag Wrangler**, **Advanced Tables**, **Admonition**, **QuickAdd**, **Calendar**
5. Откройте `_moc/HOME.md` — главный дашборд.

CSS-сниппет `ege-tasks.css` подсвечивает callout'ы и сложности — включён
автоматически.

---

## Рабочий поток

### Базовый цикл (ежедневно)

```bash
# 1. Сгенерировать план задач на основе слабых тем
python generate_plan.py --weights tracker > plan.py

# 2. Запустить генерацию (15 задач за раз)
python batch_generate.py --plan plan.py --max 15

# 3. Кросс-верификация ответов (другой моделью)
python verifier.py --dir vault/ --skip-verified --flag-only

# 4. Решить задачи в Obsidian, отметить статус (pass / fail / partial)
python review.py --limit 20

# 5. Посмотреть, что повторить сегодня (SM-2)
python srs.py due

# 6. Глобальная статистика — слабые места
python stats.py --weak
```

### Демо без API (посмотреть, как всё выглядит)

```bash
python seed_demo.py --reset
# создаёт ~48 задач с реальными условиями ФИПИ + симулирует попытки/верификации
python moc.py    # пересобрать индексы Obsidian
```

---

## Скрипты

| Скрипт | Назначение |
|--------|-----------|
| `scraper.py` | Скачивает задачи из открытого банка ФИПИ → `data/{subject}.json` |
| `generator.py` | Генерация одной/нескольких усложнённых задач |
| `batch_generate.py` | Батч-генерация по плану |
| `generate_plan.py` | Авто-генерация плана: покрытие всех КЭС / адаптивный по слабым темам |
| `verifier.py` | Кросс-верификация ответов другой моделью |
| `tracker.py` | Учёт попыток (`add` / `stats` / `weak` / `list`) |
| `srs.py` | SM-2 расписание (`due` / `queue` / `schedule`) |
| `review.py` | Интерактивное ревью задач из CLI |
| `stats.py` | Сводная статистика: покрытие × генерация × верификация × pass rate |
| `coverage.py` | Сравнение каркаса vs. реальные данные (поиск пропусков КЭС) |
| `mock_exam.py` | Сборка пробного варианта ЕГЭ (`--hard` для LLM-усложнения) |
| `moc.py` | Пересборка Obsidian-MOC (после изменений каркаса/данных) |
| `seed_demo.py` | Заполнение демо-данными для просмотра функционала |
| `dashboard.py` | Терминальный дашборд (по желанию) |
| `db.py` / `llm.py` | Внутренние модули (не запускаются напрямую) |

---

## База данных (`ege.db`)

SQLite, три таблицы:

```sql
attempts        -- ts, subject, kes, task_number, source_id,
                -- technique, difficulty, md_path, result, note
verifications   -- md_path, ts, model, claimed_answer, verified_answer,
                -- match (0/1), verifier_output
generations     -- md_path, ts, subject, kes, source_id, strategy,
                -- difficulty, model
```

Ключ — `md_path` (абсолютный путь к .md в vault). Связь между всеми тремя
таблицами по `md_path`. SRS строится из истории `attempts` (SM-2 без
дополнительного хранения).

---

## Каркас приёмов (`modification_framework.json`)

```jsonc
{
  "subjects": {
    "math_profile": {
      "kes_modifications": {
        "2.10": {
          "topic": "Уравнения и неравенства с параметрами",
          "levels": [
            {"name": "все_значения", "desc": "...", "tier": "hard"},
            {"name": "графический",   "desc": "...", "tier": "olympiad"}
          ]
        }
      }
    }
  },
  "global_modifications": { /* приёмы, применимые к любому предмету */ },
  "olympiad_modifications": { /* инвариант, экстремальный, AM-GM, ... */ },
  "over_education_topics": { /* темы вне ЕГЭ для гарантии 100 баллов */ }
}
```

**Tier-система:** каждый приём помечен `standard` / `hard` / `olympiad`.
Генератор может фильтровать по уровню — например, для финального этапа
подготовки запускать только `olympiad`-приёмы.

**Покрытие (полное соответствие кодификатору ФИПИ-2026):**

| Предмет | КЭС в каркасе | КЭС в банке ФИПИ |
|---------|---------------|------------------|
| math_profile | 42 | 26 (надмножество) |
| physics | 16 | 20 (полные разделы 1–4) |
| russian | 25 | 11 (надмножество) |
| informatics | 45 | 23 (надмножество) |

Если ФИПИ в 2027 расширит кодификатор — обновите `modification_framework.json`
(коды просто добавляются, обратная совместимость есть).

---

## Структура задачи в Obsidian

Каждая сгенерированная задача — отдельный `.md` файл с YAML-фронтматтером:

```yaml
---
id: D13540-153022
aliases: ["math_profile КЭС 2.10 D13540", "..."]
created: 2026-04-24T15:30
date: 2026-04-24
subject: math_profile
subject_ru: "Математика (профиль)"
task_number: "18"
kes: "2.10 Уравнения с параметром"
kes_code: "2.10"
topic: "..."
technique: "все_значения"
difficulty: 4
source_id: "D13540"
status: "new"
verified: false
cssclasses: [ege-task, ege-math_profile]
tags:
  - ege
  - ege/math_profile
  - ege/math_profile/2-10
  - ege/technique/все_значения
  - ege/difficulty/4
  - generated
---
```

Содержимое:

- **Метаданные** (свернутый callout)
- **Inline Dataview-поля** (`status:: ...` для быстрого фильтра)
- **Условие** в callout `[!question]+` (раскрыто по умолчанию)
- **Решение** в свёрнутом `[!note]-` (чтобы не подсматривать)
- **Ответ** в `[!success]`
- **Разбор** в `[!tip]-` для заметок после решения
- **Связи** — wikilinks на КЭС-MOC, приём, предмет
- **Похожие задачи** — встроенный Dataview-запрос

---

## Obsidian: дашборды (MOC)

Структура `vault/_moc/`:

```
HOME.md                            ← главный дашборд: что делать сегодня
Математика (профиль).md            ← индекс предмета: все КЭС + слабые темы
Физика.md
Русский язык.md
Информатика.md

kes/КЭС {код} {тема}.md            ← хаб темы: задачи + приёмы + заметки
techniques/Приём · {имя}.md        ← хаб приёма: задачи разных предметов
```

Все хабы автогенерируются через `python moc.py`. После любых изменений
`modification_framework.json` или `data/` — пересоберите MOCs.

---

## Dataview: типичные запросы

В `HOME.md`:

```dataview
TABLE WITHOUT ID file.link AS Задача, subject_ru AS Предмет, kes_code AS КЭС,
                difficulty AS Сл, status AS Статус
FROM #ege AND -#ege/moc
WHERE status != "pass"
SORT difficulty DESC, date ASC
LIMIT 20
```

Статистика по КЭС (после `GROUP BY` колонка-ключ называется `key`):

```dataview
TABLE WITHOUT ID
  key AS КЭС,
  length(rows) AS Всего,
  length(filter(rows, (r) => r.status = "pass")) AS ✓,
  length(filter(rows, (r) => r.status = "fail")) AS ✗
FROM #ege AND -#ege/moc
WHERE kes_code
GROUP BY kes_code
SORT key ASC
```

Слабые темы (fail rate > 50%):

```dataview
TABLE WITHOUT ID
  key AS КЭС,
  length(filter(rows, (r) => r.status = "fail")) AS Провалов,
  length(rows) AS Всего,
  round(length(filter(rows, (r) => r.status = "fail")) / length(rows) * 100) AS "Fail %"
FROM #ege/math_profile AND -#ege/moc
WHERE (status = "pass" OR status = "fail") AND kes_code
GROUP BY kes_code
WHERE length(filter(rows, (r) => r.status = "fail")) / length(rows) > 0.5
SORT length(filter(rows, (r) => r.status = "fail")) / length(rows) DESC
```

### Что было сломано в Dataview-запросах (исправлено)

| Проблема | Было | Стало |
|----------|------|-------|
| После `GROUP BY` поле остаётся `kes_code` | `kes_code AS КЭС` → пусто | `key AS КЭС` |
| `SORT 2 DESC` (по индексу колонки) | не работает | `SORT <выражение> DESC` |
| `kes_code: 7.3` парсится как float | `WHERE kes_code = "7.3"` → false | `kes_code: "7.3"` (строка) |
| `task_number: ?` ломает YAML | `task_number: ?` | `task_number: "?"` |
| Тег `ege/` с висящим слешем | `- ege/` | `- ege/{subject}` |
| Похожие задачи через путь `FROM "vault/..."` ломаются на нестандартных КЭС | `FROM "vault/{subj}/{kes}"` | `FROM #ege/{subj}/{kes-dashed}` |

---

## SRS (SM-2)

Без отдельной таблицы. История попыток в `attempts`, расписание считается на лету:

- Первый `pass` → +1 день
- Второй `pass` → +6 дней
- Дальше: `interval × ease_factor` (EF растёт от 2.5 при `pass`, падает при `fail`)
- `fail` → reset до 1 дня

```bash
python srs.py due              # сегодня + просрочено
python srs.py queue --limit 20 # топ-20 ближайших
python srs.py schedule         # календарь повторений
```

---

## Mock-экзамен

Соберёт пробный вариант, эквивалентный реальному:

```bash
python mock_exam.py --subject math_profile --seed 42
python mock_exam.py --subject physics --hard --seed 42
```

Без `--hard` — задачи из банка ФИПИ. С `--hard` — пропущены через LLM
с олимпиадным приёмом.

Вывод в `demo_variants/{subject}_{ts}.md`.

---

## Чеклист для 400/400

- [ ] OpenRouter оплачен (минимум $5 на эксперименты, ~$30 на полную подготовку)
- [ ] `modification_framework.json` соответствует свежему кодификатору ФИПИ
      (на 2026 год соответствует; на 2027 — сравнить через `python coverage.py`)
- [ ] `python coverage.py` показывает `Missing from framework: 0` для всех предметов
- [ ] Сгенерировано ≥ 5 hard-задач на каждую КЭС
- [ ] Сгенерировано ≥ 2 olympiad-задачи на каждую КЭС
- [ ] Все задачи прошли кросс-верификацию (`match=1`)
- [ ] Слабые темы (`stats.py --weak`) повторяются не реже раза в 3 дня
- [ ] Mock-экзамен сдан минимум 3 раза с pass rate ≥ 95% за месяц до ЕГЭ

---

## Известные ограничения

- **API-стоимость:** примерно $0.02–0.05 за задачу (R1) или $0.005 (Qwen).
  При 1000 задач — $5–50. Проверяйте лимиты OpenRouter.
- **Эссе по русскому (задание 27):** автоматическая проверка слабая (нужна
  человеческая оценка). Сгенерированные эссе помечены `verified: false` навсегда.
- **Программирование (информатика, задания 24–27):** код LLM иногда содержит
  off-by-one. Всегда запускайте сгенерированный код на демо-входах из
  `Доп.файлы_ИНФ-11/` (входят в zip-кодификатор ФИПИ).
- **2027 кодификатор** ещё не опубликован (на момент апреля 2026 актуален 2026).
  При выходе — скачать новый zip с `https://doc.fipi.ru/ege/.../2027/` и
  пересобрать каркас по `coverage.py`.

---

## Полезные команды

```bash
# Покрытие (что есть в банке, чего нет в каркасе)
python coverage.py

# Топ-15 задач для повторения сегодня
python srs.py queue --limit 15

# Сгенерировать одну конкретную задачу
python generator.py --subject math_profile --kes 2.10 --strategy все_значения --n 1

# Скачать свежие задачи ФИПИ
python scraper.py --subject physics --pages 50

# Очистить vault от старых задач (оставить только MOC + шаблоны)
find vault -name '*.md' -not -path '*/_moc/*' -not -path '*/_templates/*' -delete
python moc.py
```

---

## Лицензия / атрибуция

Задачи ФИПИ — публичны (открытый банк ЕГЭ).
Код — для личного использования.
