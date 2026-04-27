# Changelog

Все значимые изменения проекта SwanLake.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

## [0.2.0] — 2026-04-27

### Added — GRACE methodology integration

- **Архитектурная документация** (`ARCHITECTURE.md`, 600+ строк):
  карта 17 модулей с Eiffel-style контрактами (pre/post/invariant),
  call graph, схема данных, 27 системных инвариантов, точки расширения.
- **Memory file для ИИ-агентов** (`CLAUDE.md` / `AGENTS.md`):
  7 cardinal rules для работы агентов с проектом
  (Plan Mode, GRACE anchors, apply_diff rules, cross-model verification).
- **GRACE-якоря** во всех 17 `.py` файлах:
  118 уникальных `# === START_<BLOCK_ID> === / # === END_<BLOCK_ID> ===`
  пар на функциональных блоках. Имена UPPER_SNAKE_CASE,
  уникальны во всём проекте.
- **MIT License** (`LICENSE`).
- **Hero-секция в README**:
  бейджи (Python, Release, License, Status), граф знаний,
  сравнительная таблица vs закрытые SaaS (Умскул, Яндекс Репетитор AI, Winny),
  Quickstart за 5 команд.

### Verified

- Кросс-модельная верификация якорей через Claude Sonnet 4.6
  (полнота × парность × уникальность): 17/17 файлов прошли,
  118 BLOCK_ID без флагов.
- Smoke test: импорт всех модулей, `seed_demo.py --reset`,
  `moc.py`, `coverage.py` — без regression относительно pre-grace состояния.

### Methodology references

- GRACE-разметка как якоря для sparse attention: arXiv:2502.11089 (DeepSeek NSA).
- Thinking tokens / MI peaks: arXiv:2506.02867.
- Кросс-модельная верификация против RLHF-сикофантии: канал «AI Projects».
- JSON в long context — antipattern: OpenAI GPT-4.1 Prompting Guide.

## [0.1.0] — initial commits

- Базовая система: scraper ФИПИ, LLM-генерация, кросс-верификация,
  Obsidian-vault с Dataview, SM-2 SRS, mock-экзамены.
