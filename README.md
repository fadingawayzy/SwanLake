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
pip install -r requirements.txt
```

В `requirements.txt`: `openai`, `python-dotenv`, `requests`, `beautifulsoup4`,
`lxml` (парсер HTML для scraper.py), `streamlit` (для `dashboard.py`).

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

В демо-файлах поле «Ответ» отображается как
`*(демо — ответ не вычислен; запустите batch_generate.py)*`. Это нормально:
без LLM-вызова реального ответа взять негде. После `batch_generate.py`
сгенерируются настоящие задачи с ответами и решениями.

---

## Взаимодействие с ИИ

Связка из 4 шагов: **генерация → верификация → ревью → SRS**.

### 1. Генерация (`generator.py` / `batch_generate.py`)

LLM (`OPENROUTER_MODEL`, по умолчанию `deepseek/deepseek-r1`) переписывает
задачу из банка ФИПИ под выбранный приём усложнения. Возвращает
`ЗАДАНИЕ / РЕШЕНИЕ / ОТВЕТ / СЛОЖНОСТЬ / ПРИЁМ`. Файл сохраняется в
`vault/<subject>/<kes>/*.md` со фронтматтером, callout-блоками
(условие/решение/ответ) и Dataview-полями.

### 2. Кросс-верификация (`verifier.py`)

```bash
python verifier.py --dir vault/ --skip-verified --flag-only
```

Решает ту же задачу **другой** моделью (`OPENROUTER_VERIFIER_MODEL`,
по умолчанию `google/gemini-2.5-flash`), нормализует ответ
(LaTeX → строка, дробь → `a/b`, запятая → точка) и сравнивает.
Совпадение пишется в таблицу `verifications` (`match=1`),
расхождение — `match=0`, тогда требуется ручная проверка.
`--flag-only` печатает только расхождения.

В Obsidian статус виден в полях фронтматтера (`verified: false/true`).
После всех итераций тег `#ege` + фильтр `verified = false` показывает
неподтверждённые задачи.

### 3. Самопроверка (`review.py`)

```bash
python review.py --limit 20            # SRS-очередь на сегодня
python review.py --new vault/math_profile  # только нетронутые
python review.py --file vault/.../foo.md   # конкретная задача
```

CLI показывает условие, ждёт ввод ответа, сравнивает с эталоном,
просит заметку «что пошло не так» при ошибке. Запись в `attempts`
с полями `result ∈ {pass, fail, partial}` и текстом ошибки.

### 4. Расписание повторений (`srs.py`)

SM-2 строится на лету из истории `attempts`:

```bash
python srs.py due       # сегодня + просрочено
python srs.py queue --limit 20
python srs.py schedule  # календарь
```

### Заполнение «что пошло не так»

После `review.py` поле `note` в `attempts` хранит причину провала
(«не учёл ОДЗ», «арифметическая», и т. п.). Отчёт через
`stats.py --weak` или Dataview-запрос по тегу `#ege/<subject>`
с фильтром `status = "fail"`. Заметки также можно править руками
прямо в Obsidian — секция `## Разбор` с callout `[!tip]-` для
заметок после решения.

### Стоимость и модели

Цены OpenRouter актуальны на момент чека через `/api/v1/models`:

| Модель | Вход $ / 1M | Выход $ / 1M | Назначение |
|--------|-------------|--------------|------------|
| qwen/qwen3-next-80b-a3b-instruct | 0.09 | 1.10 | дешёвый primary |
| qwen/qwen3-235b-a22b | 0.45 | 1.82 | основной reasoning |
| google/gemini-2.5-flash | 0.30 | 2.50 | верификатор |
| deepseek/deepseek-r1 | 0.70 | 2.50 | топовый reasoning |

Одна задача — 1.5–10k токенов вывода, итого ≈ $0.005–$0.025 в
зависимости от модели. Free-варианты (`:free`) ограничены 8 rpm
и временно троттлятся — годятся для смоук-теста.

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
| `dashboard.py` | Веб-дашборд на Streamlit: `streamlit run dashboard.py` (по желанию) |
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
- **`dashboard.py`:** Streamlit-панель, запуск `streamlit run dashboard.py`.
  Без полноценной авторизации — поднимать только локально.

---

## Полезные команды

```bash
# Покрытие (что есть в банке, чего нет в каркасе)
python coverage.py

# Топ-15 задач для повторения сегодня
python srs.py queue --limit 15

# Сгенерировать одну конкретную задачу
python generator.py --subject math_profile --kes 2.10 --strategy все_значения --n 1

# Скачать свежие задачи ФИПИ (все 4 предмета сразу; пропускает уже скачанные)
python scraper.py
# При проблемах с SSL у ФИПИ можно временно отключить проверку сертификата:
# EGE_SCRAPER_INSECURE=1 python scraper.py

# Очистить vault от старых задач (оставить только MOC + шаблоны)
find vault -name '*.md' -not -path '*/_moc/*' -not -path '*/_templates/*' -delete
python moc.py
```

---

## Как выглядит Obsidian в общем

<img width="1062" height="539" alt="Вставленное изображение (7)" src="https://github.com/user-attachments/assets/2f7ce498-3157-4d19-a0dc-8302ba2f499b" />
<img width="1244" height="955" alt="Вставленное изображение (6)" src="https://github.com/user-attachments/assets/447cb2a5-14d8-43b1-809a-68ea8ed6c777" />
<img width="1246" height="688" alt="Вставленное изображение (5)" src="https://github.com/user-attachments/assets/6e2446dd-7853-44ec-ac21-9998725f54e4" />
<img width="1259" height="989" alt="Вставленное изображение (4)" src="https://github.com/user-attachments/assets/3208223d-bab3-4b2f-9e36-ca314cd7a77b" />
<img width="1056" height="950" alt="Вставленное изображение (3)" src="https://github.com/user-attachments/assets/1ff86522-8076-4197-96c1-94e581c6848b" />
<img width="1053" height="909" alt="Вставленное изображение (2)" src="https://github.com/user-attachments/assets/43e9ef75-eda6-4125-a015-0bda04c53ce9" />
<img width="1280" height="668" alt="Вставленное изображение" src="https://github.com/user-attachments/assets/8d2686d4-4d6e-4467-942a-bcc428abd665" />


## Лицензия / атрибуция

Задачи ФИПИ — публичны (открытый банк ЕГЭ).
Код — для личного использования.
# GRACESwanLake
# GRACESwanLake
