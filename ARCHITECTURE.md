# SwanLake — Architecture

> Этот документ — единственный источник правды о структуре проекта.
> При любом изменении кода, добавляющем/удаляющем функциональный блок,
> этот документ ОБЯЗАН быть обновлён в том же коммите.

## 1. Назначение проекта

SwanLake (ЕГЭ-202X) — конвейер подготовки к российскому ЕГЭ по четырём
предметам (math_profile, physics, russian, informatics). Скачивает открытый
банк ФИПИ, через OpenRouter LLM генерирует усложнённые варианты по приёмам
из `modification_framework.json`, прогоняет результат через кросс-верификацию
другой моделью, складывает в Obsidian-vault с YAML-фронтматтером и Dataview.
Учёт попыток ведётся в SQLite (`ege.db`), повторения — по SM-2. Без
фреймворков, без тестов; единственная точка интеграции — три таблицы
`attempts / verifications / generations`, связанные через `md_path`.

## 2. Основной поток данных

Один сквозной pipeline: `bank → modify → store → verify → review → schedule`.
ФИПИ-банк скачивается в `data/{subject}.json`, далее `batch_generate.py`
(или одиночный `generator.py`) собирает PLAN, для каждой записи вызывает
LLM, парсит ответ, рендерит Obsidian-заметку и пишет строку в `generations`.
`verifier.py` проходит по vault, перепроверяет ответ другой моделью и пишет
`verifications`. Пользователь повторяет задачи через `review.py`, попытки
оседают в `attempts`. `srs.py` читает `attempts` и считает SM-2 расписание.
Обзор и навигация — `stats.py`, `coverage.py`, `moc.py`, `dashboard.py`.

```
                ┌─────────────────────┐
                │   FIPI open bank    │
                │  (windows-1251 HTML)│
                └──────────┬──────────┘
                           │ scraper.py
                           ▼
                ┌─────────────────────┐
                │  data/{subject}.json│◄────────────┐
                └──────────┬──────────┘             │
                           │                        │
       modification_       │                        │
       framework.json      │                        │
              │            │                        │
              ▼            ▼                        │
      ┌────────────────────────────┐                │
      │ generate_plan.py → plan.py │                │
      └─────────────┬──────────────┘                │
                    │                               │
                    ▼                               │
      ┌──────────────────────────────────┐          │
      │ batch_generate.py / generator.py │          │
      │ build_prompt → llm.complete →    │          │
      │ parse_response → to_obsidian     │          │
      └─────────────┬──────────────┬─────┘          │
                    │              │                │
                    ▼              ▼                │
        ┌──────────────────┐  ┌──────────┐          │
        │ vault/**/*.md    │  │  ege.db  │          │
        │ (frontmatter +   │  │ (3 tbls) │          │
        │  callouts +      │  └────┬─────┘          │
        │  Dataview)       │       │                │
        └────┬─────────┬───┘       │                │
             │         │           │                │
             ▼         ▼           ▼                │
       ┌─────────┐ ┌────────┐ ┌─────────┐           │
       │verifier │ │review  │ │  srs    │           │
       │.py      │ │.py     │ │ .py     │           │
       └────┬────┘ └───┬────┘ └────┬────┘           │
            │          │           │                │
            ▼          ▼           ▼                │
       verifications attempts   due/queue           │
            │          │           │                │
            └──────────┴───────────┴────────────────┘
                                │
                                ▼
                  ┌─────────────────────────┐
                  │ stats.py / coverage.py  │
                  │ moc.py / dashboard.py   │
                  └─────────────────────────┘
```

## 3. Карта модулей

<modules>

  <module path="db.py" role="SQLITE_INTEGRATION_LAYER">
    <one_line>Единый SQLite-слой: схема attempts/verifications/generations + миграция legacy.</one_line>
    <contract>
      <pre>cwd содержит ege.db или место для её создания</pre>
      <pre>tracker.db и verifier.db — опциональны; если есть, схемы совпадают с SELECT-ами в migrate_legacy</pre>
      <post>Соединение sqlite3.Connection возвращено с применённой схемой (CREATE IF NOT EXISTS)</post>
      <post>migrate_legacy: ege.db не содержит дублей verifications (INSERT OR REPLACE), но может содержать дубли attempts при повторных запусках</post>
      <invariant>md_path — natural FK во всех трёх таблицах; целостность держится только конвенцией, без DB-уровня FK</invariant>
      <invariant>Схема идемпотентна (CREATE IF NOT EXISTS), но миграция колонок не покрыта — любое изменение SCHEMA требует ручного ALTER</invariant>
    </contract>
    <blocks>
      <block id="DEFINE_DB_SCHEMA">DB_PATH=Path("ege.db") + SQL-схема трёх таблиц с индексами</block>
      <block id="CONNECT_DB">sqlite3.Connection + executescript(SCHEMA). Точка входа всех модулей</block>
      <block id="MIGRATE_LEGACY_DBS">Одноразовая копия из tracker.db и verifier.db в ege.db</block>
      <block id="RUN_DB_MIGRATION_CLI">__main__ — вызов migrate_legacy с печатью счётчиков</block>
    </blocks>
    <calls_into>—</calls_into>
    <called_by>generator.py, batch_generate.py, verifier.py, tracker.py, srs.py, review.py, generate_plan.py, stats.py, seed_demo.py</called_by>
  </module>

  <module path="llm.py" role="OPENROUTER_LLM_CLIENT">
    <one_line>Тонкая обёртка над OpenAI SDK для OpenRouter с retry-логикой и выбором модели по env.</one_line>
    <contract>
      <pre>OPENROUTER_API_KEY установлен в env (или передан явно в make_client)</pre>
      <pre>prompt — non-empty user message</pre>
      <post>complete возвращает str (содержимое response.choices[0].message.content) или бросает RuntimeError после max_retries</post>
      <post>Retry на RateLimitError, APITimeoutError, APIConnectionError, APIError(status>=500); прочие APIError пробрасываются сразу</post>
      <invariant>get_verifier_model должна возвращать модель, отличную от get_primary_model — иначе кросс-проверка теряет независимость</invariant>
      <invariant>Backoff экспоненциальный с jitter: base_delay × (2**i) + uniform(0, base_delay)</invariant>
    </contract>
    <blocks>
      <block id="MAKE_OPENROUTER_CLIENT">openai.OpenAI с base_url=https://openrouter.ai/api/v1</block>
      <block id="CALL_LLM_WITH_RETRY">chat.completions.create + экспоненциальный backoff с jitter, max_retries=4</block>
      <block id="GET_PRIMARY_MODEL">env OPENROUTER_MODEL || "deepseek/deepseek-r1"</block>
      <block id="GET_VERIFIER_MODEL">env OPENROUTER_VERIFIER_MODEL || "google/gemini-2.5-flash"</block>
    </blocks>
    <calls_into>—</calls_into>
    <called_by>generator.py, verifier.py, batch_generate.py, mock_exam.py</called_by>
  </module>

  <module path="scraper.py" role="FIPI_BANK_SCRAPER">
    <one_line>Скачивание открытого банка ФИПИ для 4 предметов и сериализация в data/{subject}.json.</one_line>
    <contract>
      <pre>Сетевой доступ к ege.fipi.ru</pre>
      <pre>SUBJECTS-словарь содержит актуальные proj_id (хардкод; меняется при ротации ФИПИ)</pre>
      <pre>data/ существует или может быть создана</pre>
      <post>Для каждого subject из SUBJECTS создан data/{subject}.json с list[dict {id, task_number, answer_type, text, latex_text, kes, answer_format}]</post>
      <post>Идемпотентен: skip-if-exists по существующему файлу (никогда не перезаписывает)</post>
      <invariant>Кодировка страницы фиксирована windows-1251 (FIPI legacy)</invariant>
      <invariant>Регекс "Задание №(\d+)" зависит от языка/формата ФИПИ</invariant>
      <invariant>Не падает на одиночной ошибке страницы — печатает ERROR и идёт дальше</invariant>
    </contract>
    <blocks>
      <block id="DEFINE_FIPI_SUBJECTS_MAP">SUBJECTS = {math_profile, physics, russian, informatics} → proj_id</block>
      <block id="INIT_INSECURE_SSL_FLAG">EGE_SCRAPER_INSECURE=1 → verify=False (для старых сертификатов ФИПИ)</block>
      <block id="MAKE_FIPI_SESSION">requests.Session + UA-маскировка + cookie warm-up</block>
      <block id="CLEAN_FIPI_TEXT">Нормализация Unicode-пробелов (NBSP) в ASCII + collapse</block>
      <block id="PARSE_TASK_METADATA_FIPI">Извлечение КЭС и answer_format из info-блока id="i{hash}"</block>
      <block id="EXTRACT_TASK_NUMBER_FIPI">Регекс "Задание №(\d+)" из answer_type</block>
      <block id="PARSE_QUESTIONS_PAGE_FIPI">Парсинг страницы (.qblock div'ов) с MathML→LaTeX через mathml_to_latex</block>
      <block id="DETECT_TOTAL_PAGES_FIPI">Регекс setQCount(\d+) → ceil/10</block>
      <block id="SCRAPE_ONE_SUBJECT_FIPI">Цикл по pages с time.sleep(0.3); робастность к ошибкам страниц</block>
      <block id="RUN_SCRAPER_MAIN">Итерация SUBJECTS, skip-if-exists, write data/{subject}.json</block>
    </blocks>
    <calls_into>mathml_to_latex.py</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

  <module path="mathml_to_latex.py" role="MATHML_LATEX_CONVERTER">
    <one_line>Рекурсивная конвертация MathML-разметки ФИПИ в LaTeX-строки $...$.</one_line>
    <contract>
      <pre>form_tag — это td.cell_0 или контейнер с MathML-узлами с m: namespace prefix</pre>
      <post>extract_latex_from_block возвращает строку, где все &lt;math&gt; блоки заменены на $...$ с LaTeX</post>
      <post>convert — чистая функция; рекурсия по children; OPERATOR_MAP применяется к Unicode-операторам</post>
      <invariant>Покрывает msup/msub/msubsup/mfrac/msqrt/mroot/mover/munder/munderover/mfenced/mtable</invariant>
      <invariant>annotation теги выкидываются — собственный TeX строится с нуля</invariant>
      <invariant>Удаление "m:" namespace prefix через локальный re.sub + re-parse — дорого, но робастно</invariant>
    </contract>
    <blocks>
      <block id="DEFINE_MATHML_OPERATOR_MAP">OPERATOR_MAP — Unicode → LaTeX (− → -, · → \cdot, ≤ → \leq, греческие, NBSP → space)</block>
      <block id="GET_TAG_NAME_NS_STRIPPED">Helper: имя тега без namespace prefix, lower-case</block>
      <block id="GET_TAG_KIDS_FILTERED">Helper: только Tag-children, отбрасывая NavigableString-пробелы</block>
      <block id="CONVERT_MATHML_NODE">Рекурсивная конвертация MathML-узла в LaTeX-строку</block>
      <block id="EXTRACT_LATEX_FROM_BLOCK">Высокоуровневая обёртка: namespace strip + walk + замена &lt;math&gt; на $...$</block>
      <block id="RUN_MATHML_TEST_DEMO">__main__ — тестовые примеры (сложная дробь, вектор)</block>
    </blocks>
    <calls_into>—</calls_into>
    <called_by>scraper.py</called_by>
  </module>

  <module path="generator.py" role="LLM_TASK_GENERATOR">
    <one_line>Ядро генерации: построение промпта, парсинг ответа, рендер Obsidian-заметки и логирование в generations.</one_line>
    <contract>
      <pre>Существует data/{subject}.json и modification_framework.json в cwd</pre>
      <pre>Установлен OPENROUTER_API_KEY в env (.env подгружается при импорте модуля)</pre>
      <post>В vault/{subject}/{kes-dashed}/*.md создан файл с YAML-фронтматтером + блоки ## Задание/## Решение/## Ответ</post>
      <post>В таблице generations записана строка с md_path = str(Path.resolve()), subject, kes, source_id, strategy, difficulty, model</post>
      <post>--list-strategies печатает доступные приёмы и выходит</post>
      <invariant>Сгенерированный md содержит обязательные YAML-поля: kes_code (строка), task_number (строка), source_id (строка), subject, technique, difficulty, status</invariant>
      <invariant>kes_code и task_number — кавыченные строки в YAML (защита от float-парсинга Dataview)</invariant>
      <invariant>Тэги: ege/{subject}/{kes-dashed}, ege/technique/{strategy}, ege/difficulty/{N}, generated</invariant>
      <invariant>Идемпотентность: --random + already_generated отсекают повторы того же source_id (но --task-id путь не фильтрует)</invariant>
    </contract>
    <blocks>
      <block id="LOAD_DOTENV_GENERATOR">load_dotenv() при импорте модуля</block>
      <block id="GET_OPENROUTER_CLIENT_GUARDED">Фасад над llm.make_client + sys.exit при отсутствии ключа</block>
      <block id="GET_GENERATOR_MODEL">Фасад над llm.get_primary_model</block>
      <block id="CHECK_ALREADY_GENERATED">SELECT FROM generations WHERE subject=? AND source_id=?</block>
      <block id="LOG_GENERATION_TO_DB">INSERT OR REPLACE в generations с md_path как PK (resolved abs path)</block>
      <block id="LOAD_SUBJECT_TASKS">Чтение data/{subject}.json с graceful sys.exit</block>
      <block id="LOAD_FRAMEWORK">Чтение modification_framework.json (без кеша)</block>
      <block id="MAP_SUBJECT_KEY">Identity-mapping (точка расширения для алиасов)</block>
      <block id="FILTER_TASKS_BY_KES_PREFIX">Префиксный фильтр str.startswith по полю kes</block>
      <block id="TEST_KES_PREFIX_MATCH">Structured prefix-match по dot-сегментам ("2.10" matches "2", не "2.1")</block>
      <block id="SLUGIFY_FOR_WIKILINK">Замена / \ : на похожие Unicode (∕ ∖ ꞉)</block>
      <block id="LOOKUP_KES_STRATEGIES">Получение levels[] из framework: exact match → fallback самый длинный prefix</block>
      <block id="BUILD_GENERATION_PROMPT">Построение промпта со СТРОГОЙ структурой ответа (ЗАДАНИЕ/РЕШЕНИЕ/ОТВЕТ/СЛОЖНОСТЬ/ПРИЁМ); подмешивание prompt_suffix</block>
      <block id="PARSE_LLM_RESPONSE">Regex-парсинг LLM-ответа в dict {task, solution, answer, difficulty, technique, raw}</block>
      <block id="TOP_KES_PREFIX_GENERATOR">Каноническая форма "X.Y" (первые два сегмента dot-кода)</block>
      <block id="DEFINE_SUBJECT_RU_MAP_GEN">SUBJECT_RU = {math_profile: "Математика (профиль)", ...}</block>
      <block id="RENDER_OBSIDIAN_NOTE">Полный markdown с YAML, callouts (abstract/question/note/success/tip), Dataview-блок «похожие задачи»</block>
      <block id="GENERATE_TASK_E2E">Композиция build_prompt + complete + parse_response</block>
      <block id="RUN_GENERATOR_CLI">argparse + --kes/--task-id/--random/--list-strategies; цикл с защитой от повторов</block>
    </blocks>
    <calls_into>llm.py, db.py</calls_into>
    <called_by>batch_generate.py, mock_exam.py, seed_demo.py, dashboard.py (через subprocess)</called_by>
  </module>

  <module path="batch_generate.py" role="BATCH_RUNNER">
    <one_line>Батчевый раннер PLAN: разворачивает (subject, kes, strategy, difficulty, count) в LLM-генерации с записью в vault и DB.</one_line>
    <contract>
      <pre>data/{subject}.json и modification_framework.json существуют</pre>
      <pre>--plan указывает на .py-файл с переменной PLAN: list[tuple(5)] (или используется DEFAULT_PLAN)</pre>
      <pre>OPENROUTER_API_KEY установлен в env</pre>
      <post>Для каждой PLAN-записи создано count .md в vault/{subject}/{kes-dashed}/ + строка в generations</post>
      <post>already_generated отсекает повторы того же source_id (skip-counter печатается)</post>
      <invariant>--max ограничивает первые N записей PLAN, не общее число задач</invariant>
      <invariant>PLAN кортежи — строго 5 элементов; tuple unpacking упадёт молча при изменении формата</invariant>
      <invariant>importlib.util загружает произвольный Python — plan.py не доверенный по умолчанию</invariant>
    </contract>
    <blocks>
      <block id="LOAD_PLAN_FROM_FILE">importlib.util.spec_from_file_location + exec_module — выполняет произвольный .py</block>
      <block id="DEFINE_DEFAULT_PLAN">Хардкод PLAN — список (subject, kes, strategy, difficulty, count)</block>
      <block id="LOAD_BATCH_TASKS">Локальная копия load_tasks (дублирует generator.LOAD_SUBJECT_TASKS)</block>
      <block id="LOAD_BATCH_FRAMEWORK">Локальная копия load_framework (дублирует generator.LOAD_FRAMEWORK)</block>
      <block id="LOOKUP_STRATEGY_DESC">Поиск desc стратегии: kes_modifications → global_modifications → strategy_name</block>
      <block id="RUN_BATCH_GENERATE">Цикл по PLAN: build_prompt + complete + parse + to_obsidian + log_generation</block>
    </blocks>
    <calls_into>llm.py, generator.py</calls_into>
    <called_by>coverage.py (импорт DEFAULT_PLAN на module-level)</called_by>
  </module>

  <module path="verifier.py" role="CROSS_MODEL_VERIFIER">
    <one_line>Кросс-модельный верификатор: парсит .md, спрашивает другую LLM, нормализует и пишет verifications.</one_line>
    <contract>
      <pre>md-файл существует и содержит [!question]+ Условие или ## Задание + [!success] Ответ или **Ответ:**</pre>
      <pre>OPENROUTER_VERIFIER_MODEL отлична от OPENROUTER_MODEL (для независимости проверки)</pre>
      <post>В verifications записана строка (md_path, ts, model, claimed_answer, verified_answer, match 0/1, verifier_output)</post>
      <post>SKIP без записи если task или answer не извлеклись из .md</post>
      <invariant>verifier_model ≠ primary_model (см. INV-003)</invariant>
      <invariant>normalize: lower + strip $ \ + \frac{a}{b} → a/b + \left/\right strip + , → . + ; → ,</invariant>
      <invariant>temperature=0.1 для детерминизма верификатора</invariant>
      <invariant>SKIP-кейс возвращает True (не считается mismatch) — может скрыть невалидные .md</invariant>
    </contract>
    <blocks>
      <block id="STRIP_CALLOUT_PREFIX_VERIFY">Удаление "> " / ">" префиксов из callout-блоков</block>
      <block id="PARSE_GENERATED_MD_VERIFY">Парсинг task + answer + frontmatter; fallback цепочка callout → секция</block>
      <block id="NORMALIZE_VERIFY_ANSWER">Нормализация для сравнения (полная: \frac, \left, ; → ,)</block>
      <block id="ASK_VERIFIER_LLM">Промпт верификатора с фиксированным форматом "ОТВЕТ: X" + temperature=0.1</block>
      <block id="VERIFY_SINGLE_FILE">parse_md → verify → normalize → INSERT OR REPLACE в verifications</block>
      <block id="RUN_VERIFIER_CLI">argparse path | --dir | --skip-verified | --flag-only | --model</block>
    </blocks>
    <calls_into>llm.py, db.py</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

  <module path="tracker.py" role="ATTEMPTS_CLI">
    <one_line>CLI поверх attempts: add (с парсингом frontmatter), stats, weak, list.</one_line>
    <contract>
      <pre>md-файл (для add) содержит frontmatter с subject и kes</pre>
      <pre>ege.db существует или будет создана через cmd_init</pre>
      <post>cmd_add: INSERT в attempts с md_path = str(Path.resolve())</post>
      <post>cmd_stats: печать subject × KES progress bar (10 единиц █/░)</post>
      <post>cmd_weak: KES с pass_rate &lt; 0.5 и ≥2 attempts (HAVING)</post>
      <post>cmd_list: последние 20 attempts (LIMIT 20) с иконками ✓/✗/~</post>
      <invariant>parse_frontmatter — простой `key: value` (не yaml.safe_load); strip кавычек по краям</invariant>
      <invariant>top_prefix дублирует generator.top_kes_prefix</invariant>
    </contract>
    <blocks>
      <block id="PARSE_TRACKER_FRONTMATTER">Простой `key: value` парсер frontmatter без YAML</block>
      <block id="TOP_PREFIX_TRACKER">"X.Y.Z A B" → "X.Y" (дублирует TOP_KES_PREFIX_GENERATOR)</block>
      <block id="INIT_TRACKER_DB_CLI">cmd_init — connect + close для CREATE IF NOT EXISTS</block>
      <block id="ADD_ATTEMPT_CLI">cmd_add — парсит frontmatter md, INSERT в attempts</block>
      <block id="COMPUTE_TRACKER_STATS">cmd_stats — SELECT GROUP BY + progress bar</block>
      <block id="LIST_WEAK_KES">cmd_weak — HAVING rate &lt; 0.5 AND total ≥ 2</block>
      <block id="LIST_RECENT_ATTEMPTS">cmd_list — LIMIT 20 с опциональным фильтром subject</block>
      <block id="RUN_TRACKER_CLI">argparse subparsers + dispatch</block>
    </blocks>
    <calls_into>db.py</calls_into>
    <called_by>review.py</called_by>
  </module>

  <module path="srs.py" role="SM2_SCHEDULER">
    <one_line>SM-2 расписание поверх attempts: due/queue/schedule по группам md_path.</one_line>
    <contract>
      <pre>attempts таблица существует (или возвращается пустой список)</pre>
      <pre>history передаётся отсортированной ts ASC (что обеспечивает SELECT в load_cards)</pre>
      <post>load_cards возвращает list[dict] (md_path, subject, kes, last_seen, due, interval, ef, attempts, last_result)</post>
      <post>cmd_due печатает due ≤ now (sort by due ASC)</post>
      <post>cmd_queue печатает md_path по одному на строку (machine-readable, fail впереди)</post>
      <post>cmd_schedule печатает бакеты overdue/today/week/month/later (≤7д, ≤30д)</post>
      <invariant>q-шкала: pass=5, partial=3, fail=1; ef ∈ [1.3, ∞) (clamp снизу)</invariant>
      <invariant>q&lt;3 → reset streak, interval=1; иначе streak: 1→1д, 2→6д, 3+→round(prev × ef)</invariant>
      <invariant>Группировка строго по md_path (resolved abs); если vault перенесён, история разрывается</invariant>
    </contract>
    <blocks>
      <block id="COMPUTE_SM2_INTERVAL">SM-2: q-шкала + ef clamp + streak логика 1д/6д/round(prev × ef)</block>
      <block id="LOAD_SRS_CARDS">SELECT FROM attempts ORDER BY md_path, ts ASC → группировка → sm2_interval → due</block>
      <block id="LIST_DUE_CARDS">cmd_due — карты с due ≤ now с печатью</block>
      <block id="LIST_QUEUE_CARDS">cmd_queue — машинно-читаемый список md_path; fail вперёд</block>
      <block id="SUMMARIZE_SRS_SCHEDULE">cmd_schedule — бакеты overdue/today/week/month/later</block>
      <block id="RUN_SRS_CLI">argparse + dispatch</block>
    </blocks>
    <calls_into>db.py</calls_into>
    <called_by>review.py</called_by>
  </module>

  <module path="review.py" role="INTERACTIVE_REVIEW">
    <one_line>Интерактивный CLI ревью: читает SRS-due, спрашивает ответ, сравнивает, пишет в attempts.</one_line>
    <contract>
      <pre>vault содержит .md с frontmatter + блоками задания/ответа</pre>
      <pre>--file > --new dir > default (SRS-due очередь через srs.load_cards)</pre>
      <post>Для каждой решённой задачи INSERT в attempts (ts, subject, kes, task_number, source_id, technique, difficulty, md_path, result, note)</post>
      <post>result ∈ {pass, fail, partial}; пустой ввод = skip без записи</post>
      <post>'s' = показать решение, потом ручной выбор pass/fail/partial</post>
      <invariant>Дублирует parse_md и normalize из verifier.py — расхождение поведения возможно</invariant>
      <invariant>normalize упрощённая (без \frac, без ; обработки) — расходится с verifier.normalize</invariant>
      <invariant>KeyboardInterrupt → sys.exit(0) (грейсфул)</invariant>
    </contract>
    <blocks>
      <block id="STRIP_CALLOUT_PREFIX_REVIEW">Удаление "> " / ">" (дублирует STRIP_CALLOUT_PREFIX_VERIFY)</block>
      <block id="PARSE_GENERATED_MD_REVIEW">parse_md с дополнительным извлечением solution из [!note] / ## Решение</block>
      <block id="NORMALIZE_REVIEW_ANSWER">Упрощённая нормализация (БЕЗ \frac, БЕЗ ; — расходится с verifier)</block>
      <block id="LOG_REVIEW_ATTEMPT">INSERT в attempts через tracker.parse_frontmatter и tracker.top_prefix</block>
      <block id="REVIEW_ONE_TASK_INTERACTIVE">Показ условия → input() → сравнение → log_attempt; 's' = решение</block>
      <block id="RUN_REVIEW_CLI">argparse --file/--new/--subject + дефолт SRS-due</block>
    </blocks>
    <calls_into>srs.py, tracker.py, db.py</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

  <module path="generate_plan.py" role="PLAN_AUTOBUILDER">
    <one_line>Авто-сборка PLAN-списка для batch_generate с multiplier по weakness_weights из attempts.</one_line>
    <contract>
      <pre>data/*.json существуют для перебираемых предметов</pre>
      <pre>modification_framework.json существует</pre>
      <pre>(опционально) ege.db существует для --weights</pre>
      <post>Stdout — Python модуль с переменной PLAN: list[tuple(5)] для редиректа в plan.py</post>
      <post>multiplier по fail_rate: ≥0.5 → +2, ≥0.25 → +1; иначе базовый count</post>
      <invariant>Двусторонний startswith при выборе стратегии может смешивать соседние коды</invariant>
      <invariant>Hash-fallback в GLOBAL_FALLBACK детерминирован при одном PYTHONHASHSEED, но не между запусками с разным seed</invariant>
    </contract>
    <blocks>
      <block id="TOP_PREFIX_PLAN">Дублирует TOP_KES_PREFIX_GENERATOR</block>
      <block id="PICK_PLAN_STRATEGY">Первый level matching КЭС или hash-fallback в GLOBAL_FALLBACK</block>
      <block id="COMPUTE_WEAKNESS_WEIGHTS">SELECT FROM attempts → dict {(subject, kes): fail_rate}</block>
      <block id="RUN_PLAN_GENERATOR_CLI">argparse --weights/--per-kes/--difficulty + print PLAN = [...]</block>
    </blocks>
    <calls_into>db.py</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

  <module path="coverage.py" role="COVERAGE_REPORTER">
    <one_line>Сравнивает 3 множества КЭС (data/, framework, PLAN) — печатает missing.</one_line>
    <contract>
      <pre>data/*.json существуют для всех SUBJECTS</pre>
      <pre>modification_framework.json + batch_generate.PLAN импортируемы</pre>
      <post>Stdout — отчёт missing_from_framework + missing_from_plan по каждому предмету</post>
      <invariant>Импорт batch_generate выполняет load_dotenv() как побочный эффект (через generator.py)</invariant>
      <invariant>covered_data использует двусторонний startswith — "10.5" ложно покрыт префиксом "1"</invariant>
    </contract>
    <blocks>
      <block id="TOP_PREFIX_COVERAGE">Дублирует TOP_KES_PREFIX_GENERATOR</block>
      <block id="ANALYZE_COVERAGE">3 множества КЭС → diff → missing_from_framework + missing_from_plan</block>
    </blocks>
    <calls_into>batch_generate.py (module-level import)</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

  <module path="stats.py" role="GLOBAL_STATS">
    <one_line>Сводный CLI-отчёт по КЭС: bank/gen/ver%/pass%/прогресс + флаги NOGEN/UNSOLVED/HALLUCINATE?/WEAK.</one_line>
    <contract>
      <pre>data/{subject}.json существуют</pre>
      <pre>ege.db существует (или таблицы пустые)</pre>
      <post>Stdout — таблица КЭС с колонками bank/gen/ver%/pass%/progress + флаги</post>
      <post>--weak показывает только КЭС с флагом WEAK</post>
      <invariant>ver_rate считает только верифицированные (исключает unverified из знаменателя)</invariant>
      <invariant>pass_rate использует partial = 0.5 веса</invariant>
      <invariant>Флаги: NOGEN (gen_n==0), UNSOLVED (gen_n>0 + 0 attempts), HALLUCINATE? (ver_rate &lt; 0.7), WEAK (≥2 attempts + pass_rate &lt; 0.5)</invariant>
    </contract>
    <blocks>
      <block id="TOP_PREFIX_STATS">Дублирует TOP_KES_PREFIX_GENERATOR</block>
      <block id="RENDER_PROGRESS_BAR">bar(rate, width) → █/░ строка</block>
      <block id="COMPUTE_GLOBAL_STATS">3 SELECT (attempts, generations LEFT JOIN verifications, generations) → таблица КЭС с флагами</block>
    </blocks>
    <calls_into>db.py</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

  <module path="dashboard.py" role="STREAMLIT_PANEL">
    <one_line>Streamlit-веб-панель: форма для запуска generator.py через subprocess + метрики vault/data.</one_line>
    <contract>
      <pre>streamlit установлен; запускать `streamlit run dashboard.py`</pre>
      <pre>generator.py доступен в cwd для subprocess.run</pre>
      <post>Левый столбец: selectbox subject/strategy + text_input kes/out_dir + slider n + кнопка генерации</post>
      <post>Правый столбец: метрики vault (total/solved/errors) + data (count per subject)</post>
      <invariant>Без авторизации — только для локального запуска</invariant>
      <invariant>get_vault_analytics использует substring проверку 'status: "pass"' — ложные срабатывания на упоминаниях в теле</invariant>
      <invariant>load_framework кешируется через @st.cache_data на сессию</invariant>
    </contract>
    <blocks>
      <block id="INIT_STREAMLIT_PAGE_DASH">st.set_page_config + title</block>
      <block id="LOAD_FRAMEWORK_CACHED_DASH">@st.cache_data load_framework — fallback {} при FileNotFoundError</block>
      <block id="ENUMERATE_STRATEGIES_DASH">Уникальные имена стратегий из levels + global_modifications (insertion-order)</block>
      <block id="COMPUTE_DATA_LAKE_STATS_DASH">os.listdir + open для каждого .json в data/</block>
      <block id="COMPUTE_VAULT_ANALYTICS_DASH">os.walk vault/ + substring проверка status (нестрогая)</block>
      <block id="RENDER_GENERATION_PANEL_DASH">UI: subject/strategy/kes/out_dir/n + subprocess.run python generator.py</block>
      <block id="RENDER_STATUS_PANEL_DASH">UI: метрики vault + data + progress bar</block>
    </blocks>
    <calls_into>generator.py (через subprocess, не import)</calls_into>
    <called_by>— (Streamlit entrypoint)</called_by>
  </module>

  <module path="moc.py" role="MOC_BUILDER">
    <one_line>Генерация Map-of-Content для Obsidian: HOME, subject, kes, technique хабы с Dataview-запросами.</one_line>
    <contract>
      <pre>modification_framework.json существует (читается на module-level — побочный I/O при импорте)</pre>
      <pre>data/{subject}.json существуют для подсчёта задач в банке</pre>
      <post>Записаны: vault/_moc/HOME.md, vault/_moc/{ru-name}.md, vault/_moc/kes/КЭС {code} {slug}.md, vault/_moc/techniques/Приём · {name}.md</post>
      <post>Все MOC-файлы перезаписываются (write_text без проверки существования)</post>
      <invariant>SUBJECT_RU дублируется в generator.py — расхождение ломает wikilinks</invariant>
      <invariant>Имя файла technique-MOC включает разделитель · (U+00B7) — должен совпадать с wikilink в task notes</invariant>
      <invariant>Имя файла KES-MOC: "КЭС {code} {safe_link(topic)}.md" — должно совпадать с шаблоном в to_obsidian</invariant>
      <invariant>Если две стратегии в разных subject имеют одинаковое name — desc последней перезапишет</invariant>
    </contract>
    <blocks>
      <block id="DEFINE_MOC_CONSTS">VAULT/MOC_ROOT/SUBJECTS/SUBJECT_RU + module-level FRAMEWORK = json.load</block>
      <block id="TOP_PREFIX_MOC">Дублирует TOP_KES_PREFIX_GENERATOR</block>
      <block id="SAFE_LINK_MOC">Дублирует SLUGIFY_FOR_WIKILINK</block>
      <block id="KES_MATCH_MOC">Дублирует TEST_KES_PREFIX_MATCH</block>
      <block id="LOOKUP_KES_FRAMEWORK_MOC">Аналог LOOKUP_KES_STRATEGIES + topic</block>
      <block id="WRITE_MOC_FILE">mkdir parents=True + write_text utf-8</block>
      <block id="BUILD_HOME_MOC">vault/_moc/HOME.md с 5 Dataview-блоками (today, new+unverified, subjects, techniques, kes_code)</block>
      <block id="BUILD_SUBJECT_MOC">vault/_moc/{ru-name}.md — список КЭС + Dataview всех задач + слабые темы</block>
      <block id="BUILD_KES_MOC">vault/_moc/kes/КЭС {code} {slug}.md — приёмы + задачи + ошибки</block>
      <block id="BUILD_TECHNIQUE_MOC">vault/_moc/techniques/Приём · {name}.md — описание + задачи по тегу + успешность</block>
      <block id="RUN_MOC_BUILDER_CLI">argparse --home-only + полная пересборка</block>
    </blocks>
    <calls_into>—</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

  <module path="mock_exam.py" role="MOCK_EXAM_BUILDER">
    <one_line>Сборка пробного варианта ЕГЭ; --hard прогоняет каждое задание через harden() (LLM-усложнение).</one_line>
    <contract>
      <pre>data/{subject}.json существует и содержит задачи с заполненным kes</pre>
      <pre>(--hard) modification_framework.json + OPENROUTER_API_KEY</pre>
      <post>Записан vault/mocks/{subject}/mock_{subject}_{ts}{_hard}.md (или --out)</post>
      <post>Без --hard: ответы — placeholder (формат:fmt); с --hard: реальные ответы + решения</post>
      <invariant>EXPECTED_TASK_COUNT хардкодит количество заданий (math:19, phys:30, rus:27, inf:27)</invariant>
      <invariant>random.choice(kes_sorted) может дать дубль КЭС → дубль задания под разным task_number</invariant>
      <invariant>harden fallback strategy_name="add_parameter" — имя из global_modifications, не KES-level (некорректно для целевой стратегии)</invariant>
      <invariant>--seed → random.seed для воспроизводимости</invariant>
    </contract>
    <blocks>
      <block id="DEFINE_EXAM_TASK_COUNTS">EXPECTED_TASK_COUNT — реальные числа заданий ЕГЭ</block>
      <block id="DEFINE_EXAM_TIME_LIMITS">TIME_LIMIT_MIN — минуты экзамена</block>
      <block id="TOP_PREFIX_EXAM">Дублирует TOP_KES_PREFIX_GENERATOR</block>
      <block id="BUCKET_TASKS_BY_KES">by_kes — группировка tasks по top_prefix</block>
      <block id="PICK_VARIANT_PREFER_LATEX">random.choice с приоритетом latex_text != ""</block>
      <block id="HARDEN_TASK">Первый level matching КЭС → build_prompt + complete + parse_response</block>
      <block id="RENDER_EXAM_MD">Markdown с фронтматтером (type: mock_exam, mode), ответами в кодблоке</block>
      <block id="RUN_MOCK_EXAM_CLI">argparse --subject/--hard/--out/--seed + сборка chosen_kes из buckets</block>
    </blocks>
    <calls_into>generator.py, llm.py</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

  <module path="seed_demo.py" role="DEMO_SEEDER">
    <one_line>Заполняет vault/ + ege.db фейковыми данными на основе реальных условий ФИПИ для демонстрации.</one_line>
    <contract>
      <pre>data/*.json существуют (реальные условия для placeholder-решений)</pre>
      <pre>modification_framework.json существует</pre>
      <post>Создано ~per_subject .md в vault/ + INSERT OR REPLACE в generations с model="demo/no-model"</post>
      <post>Симулированы attempts с bias по weak_kes_bias (clamp до 0.85)</post>
      <post>Симулированы verifications с mismatch_rate=0.12 по умолчанию</post>
      <post>--reset удаляет ege.db перед заполнением</post>
      <invariant>random.seed(42) в main() — детерминированный набор демо-задач</invariant>
      <invariant>weak_kes_bias = {7.3:0.7, 2.5:0.55, 6.2:0.5, 3.1:0.45, 2.13:0.6}</invariant>
      <invariant>answer всегда строка-плейсхолдер "*(демо — ответ не вычислен; запустите batch_generate.py)*"</invariant>
    </contract>
    <blocks>
      <block id="DEFINE_SEED_STRATEGIES">STRATEGIES_PER_SUBJ — пул стратегий для демо-генерации</block>
      <block id="TOP_PREFIX_SEED">Дублирует TOP_KES_PREFIX_GENERATOR</block>
      <block id="BUILD_DEMO_SOLUTION">Фейковое решение/ответ-плейсхолдер с random difficulty</block>
      <block id="SEED_GENERATIONS">random.sample реальных задач → to_obsidian + INSERT в generations</block>
      <block id="SEED_ATTEMPTS">Симуляция attempts с fail_prob = 0.3 + (diff-2)*0.1 + weak_kes_bias[kes]</block>
      <block id="SEED_VERIFICATIONS">Симуляция verifications с фиктивными ответами и mismatch_rate</block>
      <block id="RESET_DEMO_DB">Удаление ege.db (Path.unlink)</block>
      <block id="RUN_DEMO_SEEDER_CLI">random.seed(42) + argparse --reset/--per-subject/--no-attempts/--no-verify</block>
    </blocks>
    <calls_into>generator.py, db.py</calls_into>
    <called_by>— (CLI entrypoint)</called_by>
  </module>

</modules>

## 4. Граф вызовов (cross-module)

<call_graph>
  <edge from="generator.py:GET_OPENROUTER_CLIENT_GUARDED" to="llm.py:MAKE_OPENROUTER_CLIENT"/>
  <edge from="generator.py:GENERATE_TASK_E2E" to="llm.py:CALL_LLM_WITH_RETRY"/>
  <edge from="generator.py:GET_GENERATOR_MODEL" to="llm.py:GET_PRIMARY_MODEL"/>
  <edge from="generator.py:CHECK_ALREADY_GENERATED" to="db.py:CONNECT_DB"/>
  <edge from="generator.py:LOG_GENERATION_TO_DB" to="db.py:CONNECT_DB"/>

  <edge from="verifier.py:RUN_VERIFIER_CLI" to="llm.py:MAKE_OPENROUTER_CLIENT"/>
  <edge from="verifier.py:RUN_VERIFIER_CLI" to="llm.py:GET_VERIFIER_MODEL"/>
  <edge from="verifier.py:ASK_VERIFIER_LLM" to="llm.py:CALL_LLM_WITH_RETRY"/>
  <edge from="verifier.py:RUN_VERIFIER_CLI" to="db.py:CONNECT_DB"/>
  <edge from="verifier.py:VERIFY_SINGLE_FILE" to="db.py:CONNECT_DB"/>

  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="llm.py:CALL_LLM_WITH_RETRY"/>
  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="generator.py:BUILD_GENERATION_PROMPT"/>
  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="generator.py:PARSE_LLM_RESPONSE"/>
  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="generator.py:RENDER_OBSIDIAN_NOTE"/>
  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="generator.py:MAP_SUBJECT_KEY"/>
  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="generator.py:GET_OPENROUTER_CLIENT_GUARDED"/>
  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="generator.py:GET_GENERATOR_MODEL"/>
  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="generator.py:CHECK_ALREADY_GENERATED"/>
  <edge from="batch_generate.py:RUN_BATCH_GENERATE" to="generator.py:LOG_GENERATION_TO_DB"/>

  <edge from="mock_exam.py:HARDEN_TASK" to="generator.py:BUILD_GENERATION_PROMPT"/>
  <edge from="mock_exam.py:HARDEN_TASK" to="generator.py:MAP_SUBJECT_KEY"/>
  <edge from="mock_exam.py:HARDEN_TASK" to="llm.py:CALL_LLM_WITH_RETRY"/>
  <edge from="mock_exam.py:RUN_MOCK_EXAM_CLI" to="generator.py:GET_OPENROUTER_CLIENT_GUARDED"/>
  <edge from="mock_exam.py:RUN_MOCK_EXAM_CLI" to="generator.py:GET_GENERATOR_MODEL"/>
  <edge from="mock_exam.py:RUN_MOCK_EXAM_CLI" to="generator.py:PARSE_LLM_RESPONSE"/>
  <edge from="mock_exam.py:RUN_MOCK_EXAM_CLI" to="generator.py:LOAD_FRAMEWORK"/>

  <edge from="seed_demo.py:SEED_GENERATIONS" to="generator.py:RENDER_OBSIDIAN_NOTE"/>
  <edge from="seed_demo.py:SEED_GENERATIONS" to="db.py:CONNECT_DB"/>
  <edge from="seed_demo.py:SEED_ATTEMPTS" to="db.py:CONNECT_DB"/>
  <edge from="seed_demo.py:SEED_VERIFICATIONS" to="db.py:CONNECT_DB"/>
  <edge from="seed_demo.py:RUN_DEMO_SEEDER_CLI" to="generator.py:LOAD_FRAMEWORK"/>
  <edge from="seed_demo.py:RESET_DEMO_DB" to="db.py:DEFINE_DB_SCHEMA"/>

  <edge from="review.py:RUN_REVIEW_CLI" to="srs.py:LOAD_SRS_CARDS"/>
  <edge from="review.py:LOG_REVIEW_ATTEMPT" to="tracker.py:PARSE_TRACKER_FRONTMATTER"/>
  <edge from="review.py:LOG_REVIEW_ATTEMPT" to="tracker.py:TOP_PREFIX_TRACKER"/>
  <edge from="review.py:LOG_REVIEW_ATTEMPT" to="db.py:CONNECT_DB"/>

  <edge from="srs.py:LOAD_SRS_CARDS" to="db.py:CONNECT_DB"/>

  <edge from="tracker.py:INIT_TRACKER_DB_CLI" to="db.py:CONNECT_DB"/>
  <edge from="tracker.py:ADD_ATTEMPT_CLI" to="db.py:CONNECT_DB"/>
  <edge from="tracker.py:COMPUTE_TRACKER_STATS" to="db.py:CONNECT_DB"/>
  <edge from="tracker.py:LIST_WEAK_KES" to="db.py:CONNECT_DB"/>
  <edge from="tracker.py:LIST_RECENT_ATTEMPTS" to="db.py:CONNECT_DB"/>

  <edge from="stats.py:COMPUTE_GLOBAL_STATS" to="db.py:CONNECT_DB"/>

  <edge from="generate_plan.py:COMPUTE_WEAKNESS_WEIGHTS" to="db.py:CONNECT_DB"/>

  <edge from="coverage.py:ANALYZE_COVERAGE" to="batch_generate.py:DEFINE_DEFAULT_PLAN"/>

  <edge from="scraper.py:PARSE_QUESTIONS_PAGE_FIPI" to="mathml_to_latex.py:EXTRACT_LATEX_FROM_BLOCK"/>

  <edge from="dashboard.py:RENDER_GENERATION_PANEL_DASH" to="generator.py:RUN_GENERATOR_CLI"/>
</call_graph>

## 5. Схема данных

<data>
  <store path="data/*.json" format="JSON (utf-8)" written_by="scraper.py" read_by="generator.py, batch_generate.py, mock_exam.py, seed_demo.py, generate_plan.py, coverage.py, stats.py, moc.py, dashboard.py">
    list[dict {id, task_number, answer_type, text, latex_text, kes, answer_format}]
  </store>

  <store path="modification_framework.json" format="JSON (utf-8)" written_by="(ручная авторская сборка)" read_by="generator.py, batch_generate.py, mock_exam.py, seed_demo.py, generate_plan.py, coverage.py, moc.py, dashboard.py">
    subjects.{key}.kes_modifications.{code}.{topic, levels: [{name, desc, tier}]} +
    global_modifications.{name}.{desc, prompt_suffix} +
    olympiad_modifications + over_education_topics + difficulty_levels.{1..4}
  </store>

  <store path="ege.db" format="SQLite" tables="attempts, verifications, generations">
    attempts(id PK, ts, subject, kes, kes_prefix, task_number, source_id, technique, difficulty, md_path, result, note);
    verifications(md_path PK, ts, model, claimed_answer, verified_answer, match, verifier_output);
    generations(md_path PK, ts, subject, kes, source_id, strategy, difficulty, model)
  </store>

  <store path="vault/**/*.md" format="Markdown + YAML frontmatter" written_by="generator.py (через batch_generate.py / mock_exam.py / seed_demo.py)" read_by="verifier.py, review.py, srs.py (через attempts), dashboard.py, moc.py (генерирует MOC, не читает task notes)">
    Frontmatter: {subject, kes, kes_code (str), task_number (str), source_id (str), technique, difficulty, status, created, date, tags: [...], cssclasses: [ege-task, ege-{subject}], aliases: [...]} +
    Body: ## Задание (callout [!question]+) → ## Решение (callout [!note]) → ## Ответ (callout [!success]) + Dataview-блок похожих задач
  </store>

  <store path="vault/_moc/**/*.md" format="Markdown + YAML frontmatter" written_by="moc.py" read_by="(только пользователь через Obsidian)">
    HOME.md, {ru-name}.md per subject, kes/КЭС {code} {slug}.md, techniques/Приём · {name}.md.
    Каждый MOC содержит Dataview-запросы по тегам #ege/{subject}/{kes-dashed} / #ege/technique/{name}
  </store>

  <store path="vault/mocks/{subject}/mock_*.md" format="Markdown + YAML frontmatter" written_by="mock_exam.py" read_by="(только пользователь)">
    type: mock_exam; mode ∈ {СТАНДАРТНЫЙ, УСЛОЖНЁННЫЙ}; задания + ответы в кодблоке
  </store>

  <store path="demo_variants/*.md" format="Markdown" written_by="(legacy / ручной)" read_by="—">
    Демонстрационные варианты ФИПИ (входят в zip-кодификатор)
  </store>

  <store path=".env" format="dotenv" written_by="(пользователь)" read_by="generator.py (load_dotenv при импорте), batch_generate.py, verifier.py, mock_exam.py, dashboard.py">
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_VERIFIER_MODEL, EGE_SCRAPER_INSECURE
  </store>

  <store path="tracker.db / verifier.db" format="SQLite (legacy)" written_by="(старые версии)" read_by="db.py:MIGRATE_LEGACY_DBS">
    Опциональны; одноразовая миграция в ege.db через `python db.py`
  </store>
</data>

**Точка интеграции трёх таблиц** — `md_path` как `str(Path(...).resolve())`.
Все скрипты, пишущие в `vault/` ИЛИ DB, обязаны использовать resolved
absolute path. Перенос `vault/` сломает все ссылки `attempts`, `verifications`,
`generations` (целостность держится конвенцией, без DB-FK).

## 6. Инварианты системы

- INV-001: `md_path` в любой таблице БД соответствует реальному файлу в `vault/` (natural FK без DB-уровня).
- INV-002: `kes_code` в frontmatter — всегда строка в кавычках (`"7.3"`), никогда float.
- INV-003: `generator.py` и `verifier.py` ОБЯЗАНЫ использовать разные модели LLM (primary ≠ verifier для независимости кросс-проверки).
- INV-004: `task_number` в frontmatter — всегда кавыченная строка; по умолчанию `"?"` если scraper не извлёк.
- INV-005: `top_prefix` — каноническая форма КЭС "X.Y" (первые два dot-сегмента); все скрипты режут до этого.
- INV-006: Тег задачи — `ege/{subject}/{kes-dashed}`, где `kes-dashed = top_prefix(kes).replace('.', '-')`.
- INV-007: Имя файла KES-MOC — `КЭС {code} {safe_link(topic)}.md` в `vault/_moc/kes/`; должно совпадать с шаблоном wikilink в `to_obsidian`.
- INV-008: Имя файла technique-MOC — `Приём · {name}.md` с разделителем · (U+00B7).
- INV-009: Имя файла subject-MOC — `SUBJECT_RU[subj].md` (русское); словарь дублируется в `generator.py` и `moc.py` — должны совпадать.
- INV-010: `strategy_name` из `kes_modifications.levels[*].name` совпадает с тегом `ege/technique/{name}` и именем technique-MOC файла. Без / и пробелов в name (Obsidian-tag валидность). Не валидируется кодом.
- INV-011: `build_prompt` подмешивает `prompt_suffix` из `global_modifications` если strategy_name пересекается substring-wise с глобальным ключом.
- INV-012: Формат дат: `created` в frontmatter `%Y-%m-%dT%H:%M`, `date` — `%Y-%m-%d`, `ts` в DB — `datetime.now().isoformat(timespec="seconds")`. Несовпадение между фронтматтером и DB.
- INV-013: `verifier.normalize` ≠ `review.normalize`. Verifier раскрывает `\frac{a}{b}` → `a/b`, меняет `;` → `,` после `,` → `.`. Review — простой lower+strip+,→. Возможны расхождения вердикта.
- INV-014: Обе нормализации ожидают «красивые» ответы (целые / простые дроби) — условие держится через промпт-инструкцию, не валидируется.
- INV-015: Структура `modification_framework.json` фиксирована: `subjects.{key}.kes_modifications.{code}.{topic, levels: [{name, desc, tier}]}` + `global_modifications.{name}.{desc, prompt_suffix}` + `olympiad_modifications` + `over_education_topics` + `difficulty_levels.{1..4}`. Не валидируется при загрузке.
- INV-016: `verifier.parse_md` фронтматтер парсер — строчный split по `:`, не yaml. Списки (`aliases: [a, b]`) распадутся на одну строку value.
- INV-017: `sm2_interval` корректен только при history отсортированной ts ASC (что обеспечивает SELECT в `load_cards`).
- INV-018: Схема DB через `CREATE IF NOT EXISTS` — миграции колонок не покрыты. Изменение SCHEMA требует ручного `ALTER TABLE` на существующих базах.
- INV-019: Структура `vault/{subject}/{kes-dashed}/` — конвенция `to_obsidian` + `batch_generate.RUN_BATCH_GENERATE` (mkdir parents=True).
- INV-020: Порядок задач в `data/{subject}.json` — порядок встречи на FIPI пагинации (без сортировки). `random.seed(42)` + этот порядок дают воспроизводимый набор демо-задач.
- INV-021: Subject-ключи фиксированы в `SUBJECTS = ["math_profile", "physics", "russian", "informatics"]`. Дублируются в 6+ файлах (scraper, moc, generate_plan, coverage, stats, seed_demo) — добавление нового предмета требует правки всех.
- INV-022: `parse_response` регекс с DOTALL + lookahead. Если LLM выдаст "ОТВЕТ:" внутри решения — будет извлечена первая попавшаяся секция.
- INV-023: `tracker.parse_frontmatter` strip кавычек только по краям (`.strip('"')`).
- INV-024: `cssclasses` в YAML: `[ege-task, ege-{subject}]` для task notes, `[ege-moc, ege-{subject}]` для MOC. Должны быть определены в Obsidian CSS snippet (`ege-tasks.css`, не в Python-репозитории).
- INV-025: `batch_generate.PLAN` записи — кортежи строго на 5 элементов (subject, kes, strategy, difficulty, count). Изменение формата → молчаливый tuple-unpacking error.
- INV-026: Идемпотентность генерации: `--random` / batch flow проверяет `already_generated(subject, source_id)` и пропускает повторы. Путь `--task-id` НЕ фильтрует.
- INV-027: SKIP-кейс в `verify_file` (task или answer не извлеклись) возвращает `True` — не считается mismatch и может скрыть невалидные .md.

## 7. Соглашения проекта

- 7.1. **Семантическая разметка GRACE**: каждый функциональный блок в `.py`-файле обрамляется парными комментариями `# === START_<BLOCK_ID> ===` и `# === END_<BLOCK_ID> ===`, где `BLOCK_ID` — UPPER_SNAKE_CASE из таблицы блоков выше (см. § 3). Имена уникальны во всём проекте.
- 7.2. **Правки кода**: только через `apply_diff` с уникальными START/END якорями в SEARCH-блоке (см. CLAUDE.md → § Diff Rules).
- 7.3. **Кросс-модельная верификация**: `generator.py` и `verifier.py` всегда работают на разных моделях LLM (см. INV-003). Реализовано через `OPENROUTER_MODEL` и `OPENROUTER_VERIFIER_MODEL` env-переменные.
- 7.4. **Frontmatter-поля**: `kes_code`, `task_number`, `source_id` — всегда строки в двойных кавычках (защита от Dataview float-парсинга).
- 7.5. **БД**: ключ для связи всех таблиц — `md_path` (абсолютный resolved путь). Все INSERT-ы используют `str(Path(...).resolve())`.
- 7.6. **Идемпотентность**: scraper skip-if-exists по data/, generator skip-if-already-generated по (subject, source_id), DB-схема CREATE IF NOT EXISTS.
- 7.7. **Кодировка**: ФИПИ — windows-1251, всё остальное — utf-8.
- 7.8. **Тэги Obsidian**: `ege/{subject}/{kes-dashed}` + `ege/technique/{name}` + `ege/difficulty/{N}` + `generated`. Точки в КЭС заменяются на дефисы (Obsidian парсит `.` как сегменты тегов).
- 7.9. **Имена файлов wikilink-safe**: `safe_link()` заменяет `/` `\` `:` на похожие Unicode-символы (∕ ∖ ꞉).

## 8. Точки расширения

Что можно добавлять без рефакторинга существующего:
- **Новые предметы** (например, `chemistry`, `biology`) — через расширение `modification_framework.json.subjects` + добавление в `SUBJECTS`-списки в `scraper.py`, `moc.py`, `generate_plan.py`, `coverage.py`, `stats.py`, `seed_demo.py` (см. INV-021 — 6+ файлов).
- **Новые приёмы усложнения** — добавлением в `kes_modifications.{code}.levels` или `global_modifications` в `modification_framework.json`. Имя стратегии должно быть Obsidian-tag-safe (без / и пробелов).
- **Новые модели LLM** — через `.env` (`OPENROUTER_MODEL` / `OPENROUTER_VERIFIER_MODEL`). Поддерживаются любые OpenRouter-совместимые модели.
- **Новые форматы заметок** — расширение `RENDER_OBSIDIAN_NOTE` в `generator.py`.
- **Новые SRS-стратегии** — замена `COMPUTE_SM2_INTERVAL` в `srs.py` (например, FSRS).
- **Новые источники банка** — параллельный `scraper2.py` с тем же выходом `data/{subject}.json`.
- **Новые SQL-запросы для отчётов** — в `stats.py` или новых модулях; схема `ege.db` описана в § 5.

## 9. Известные ограничения

- **API-стоимость**: ~$0.02–0.05 за задачу на R1, ~$0.005 на Qwen. При 1000 задач — $5–50. Проверяйте лимиты OpenRouter перед батчем.
- **Эссе по русскому (задание 27)**: автоматическая проверка слабая — нужна человеческая оценка. Сгенерированные эссе помечены `verified: false` навсегда.
- **Программирование (информатика, задания 24–27)**: код LLM иногда содержит off-by-one. Всегда запускать сгенерированный код на демо-входах из `Доп.файлы_ИНФ-11/` (входят в zip-кодификатор ФИПИ).
- **Кодификатор 2027** ещё не опубликован (на 2026-04 актуален 2026). При выходе — скачать новый zip с https://doc.fipi.ru/ege/.../2027/ и пересобрать каркас по `coverage.py`.
- **Хардкоды FIPI**: `proj_id` в `scraper.SUBJECTS`, кодировка windows-1251, регекс "Задание №(\d+)" — три точки отказа при изменении ФИПИ. Нет fallback на utf-8, нет автоматической детекции.
- **Дубли служебных функций** (см. R1 в audit): `top_prefix` × 8, `safe_link` × 2, `kes_match` × 2, `parse_md` × 2, `_strip_callout` × 2, `SUBJECT_RU` × 2, `load_framework` × 2, `load_tasks` × 2. Любой багфикс должен трогать N мест.
- **Расхождение нормализации** между `verifier.normalize` и `review.normalize` (см. R2/INV-013) → ложные `HALLUCINATE?` флаги в `stats.py` + ложные fail в `attempts`.
- **`coverage.py` — ложные позитивы покрытия**: двусторонний startswith → "10.5" покрыт префиксом "1" (см. R3).
- **`parse_response` без валидации**: пропуск секции LLM → молчаливая запись `difficulty: 0` или пустого ответа (см. R5).
- **Module-level побочные эффекты** при import: `generator.py` → `load_dotenv()`, `coverage.py` → `batch_generate` → `load_dotenv()`, `moc.py` → `FRAMEWORK = json.load(...)` (см. R6). Без файла → ImportError на любом import-зависимом скрипте.
- **SQLite без WAL**: `PRAGMA journal_mode=WAL` не выставлен. Параллельный verifier + review → возможен `database is locked` (см. R7).
- **Frontmatter-парсер хрупок** к многострочным значениям и спискам (см. R8/INV-016).
- **`dashboard.py`**: Streamlit-панель, запуск `streamlit run dashboard.py`. Без полноценной авторизации — поднимать только локально.
