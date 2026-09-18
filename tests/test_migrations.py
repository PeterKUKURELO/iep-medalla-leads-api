import os
import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _alembic(database: Path, revision: str, command: str = "upgrade") -> None:
    environment = {**os.environ, "APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database}"}
    result = subprocess.run(
        [str(ROOT / ".venv/bin/alembic"), command, revision],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_migrations_from_empty_database(tmp_path):
    database = tmp_path / "fresh.sqlite3"
    _alembic(database, "head")
    with sqlite3.connect(database) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"leads", "lead_notifications", "consumer_complaints"}.issubset(tables)


def test_migration_backfills_legacy_data_and_indexes(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    _alembic(database, "20260811_01")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO leads (form_type, full_name, phone, email, privacy_accepted) VALUES (?, ?, ?, ?, ?)",
            ("contact", "Legacy", "999999999", "legacy@example.com", 1),
        )
        connection.commit()
    _alembic(database, "head")
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT brand_key, form_data FROM leads WHERE email = ?", ("legacy@example.com",)).fetchone()
        assert row == ("iep-medalla", "{}")
        jobs = connection.execute("SELECT kind, status FROM lead_notifications ORDER BY kind").fetchall()
        assert jobs == [("admin", "pending"), ("user", "pending")]
        indexes = {row[1] for row in connection.execute("PRAGMA index_list('leads')")}
        assert {"ix_leads_brand_created_at", "ix_leads_brand_form_created_at"}.issubset(indexes)


def test_migrations_can_downgrade_on_disposable_empty_database(tmp_path):
    database = tmp_path / "rollback.sqlite3"
    _alembic(database, "head")
    _alembic(database, "base", command="downgrade")
    with sqlite3.connect(database) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "leads" not in tables
        assert "lead_notifications" not in tables
        assert "consumer_complaints" not in tables
