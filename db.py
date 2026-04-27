#!/usr/bin/env python3
"""
Unified SQLite DB — tracker attempts + verifier results + generation log.
Single source of truth; all scripts import from here.
"""

import sqlite3
from pathlib import Path

# === START_DEFINE_DB_SCHEMA ===
DB_PATH = Path("ege.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    subject TEXT NOT NULL,
    kes TEXT NOT NULL,
    task_number TEXT,
    source_id TEXT,
    technique TEXT,
    difficulty INTEGER,
    md_path TEXT,
    result TEXT CHECK(result IN ('pass','fail','partial')),
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_att_subj_kes ON attempts(subject, kes);
CREATE INDEX IF NOT EXISTS idx_att_ts ON attempts(ts);
CREATE INDEX IF NOT EXISTS idx_att_md ON attempts(md_path);

CREATE TABLE IF NOT EXISTS verifications (
    md_path TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    model TEXT NOT NULL,
    claimed_answer TEXT,
    verified_answer TEXT,
    match INTEGER NOT NULL,
    verifier_output TEXT
);
CREATE INDEX IF NOT EXISTS idx_ver_match ON verifications(match);

CREATE TABLE IF NOT EXISTS generations (
    md_path TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    subject TEXT NOT NULL,
    kes TEXT NOT NULL,
    source_id TEXT NOT NULL,
    strategy TEXT,
    difficulty INTEGER,
    model TEXT
);
CREATE INDEX IF NOT EXISTS idx_gen_source ON generations(subject, source_id);
CREATE INDEX IF NOT EXISTS idx_gen_kes ON generations(subject, kes);
"""
# === END_DEFINE_DB_SCHEMA ===

# === START_CONNECT_DB ===
def connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.executescript(SCHEMA)
    return c
# === END_CONNECT_DB ===

# === START_MIGRATE_LEGACY_DBS ===

def migrate_legacy():
    """Import old tracker.db + verifier.db into unified ege.db."""
    old_tracker = Path("tracker.db")
    old_verifier = Path("verifier.db")
    new = connect()

    migrated_att = 0
    migrated_ver = 0

    if old_tracker.exists() and old_tracker.resolve() != DB_PATH.resolve():
        src = sqlite3.connect(old_tracker)
        try:
            rows = src.execute("""SELECT ts, subject, kes, task_number, source_id,
                                  technique, difficulty, md_path, result, note
                                  FROM attempts""").fetchall()
            for r in rows:
                new.execute("""INSERT INTO attempts
                    (ts, subject, kes, task_number, source_id, technique,
                     difficulty, md_path, result, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", r)
                migrated_att += 1
        except sqlite3.Error:
            pass
        src.close()

    if old_verifier.exists():
        src = sqlite3.connect(old_verifier)
        try:
            rows = src.execute("""SELECT md_path, ts, claimed_answer, verified_answer,
                                  match, verifier_output FROM verifications""").fetchall()
            for r in rows:
                new.execute("""INSERT OR REPLACE INTO verifications
                    (md_path, ts, model, claimed_answer, verified_answer, match, verifier_output)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (r[0], r[1], "legacy", r[2], r[3], r[4], r[5]))
                migrated_ver += 1
        except sqlite3.Error:
            pass
        src.close()

    new.commit()
    new.close()
    return migrated_att, migrated_ver
# === END_MIGRATE_LEGACY_DBS ===

# === START_RUN_DB_MIGRATION_CLI ===

if __name__ == "__main__":
    att, ver = migrate_legacy()
    print(f"DB ready: {DB_PATH}")
    print(f"Migrated: {att} attempts, {ver} verifications")
# === END_RUN_DB_MIGRATION_CLI ===
